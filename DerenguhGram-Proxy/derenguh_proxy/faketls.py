"""Fake-TLS 1.3 look-alike tunnel (server side + reference client builder).

The handshake is byte-compatible with alexbers/mtprotoproxy's Fake-TLS so a DPI box
sees the same fingerprint as a widely-deployed MTProto proxy. Authentication is an
HMAC-SHA256 over the ClientHello keyed by the 16-byte shared secret; the last 4 bytes
of the digest carry a little-endian timestamp for anti-replay. No real certificate is
ever produced ("emulation of certificates is not required" per the spec).

Layering after the handshake:
    TCP -> TLS application_data records -> flushed compression blocks -> obfuscated-2
The obfuscated-2 bytes are opaque to us and pass straight through to the Telegram DC.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import time

from .constants import (
    TLS_VERS, TLS_CIPHERSUITE, TLS_CHANGE_CIPHER, TLS_APP_HDR,
    DIGEST_LEN, DIGEST_POS, SESSION_ID_LEN_POS, SESSION_ID_POS,
    MAX_TLS_RECORD_PAYLOAD, MAX_TLS_RECORD_ACCEPT,
)

_ZERO_DIGEST = b"\x00" * DIGEST_LEN


def _hmac(secret: bytes, msg: bytes) -> bytes:
    return hmac.new(secret, msg, hashlib.sha256).digest()


def verify_client_hello(record: bytes, secret: bytes,
                        time_skew_min: int = -20 * 60,
                        time_skew_max: int = 10 * 60,
                        ignore_time_skew: bool = False) -> bool:
    """Authenticate a ClientHello record against the shared secret."""
    if len(record) < DIGEST_POS + DIGEST_LEN:
        return False
    digest = record[DIGEST_POS:DIGEST_POS + DIGEST_LEN]
    msg = record[:DIGEST_POS] + _ZERO_DIGEST + record[DIGEST_POS + DIGEST_LEN:]
    computed = _hmac(secret, msg)
    xored = bytes(a ^ b for a, b in zip(digest, computed))
    if xored[:DIGEST_LEN - 4] != b"\x00" * (DIGEST_LEN - 4):
        return False
    timestamp = int.from_bytes(xored[-4:], "little")
    if ignore_time_skew:
        return True
    skew = time.time() - timestamp
    client_time_is_small = timestamp < 60 * 60 * 24 * 1000  # uptime instead of epoch
    return (time_skew_min < skew < time_skew_max) or client_time_is_small


def client_digest(record: bytes) -> bytes:
    return record[DIGEST_POS:DIGEST_POS + DIGEST_LEN]


def build_server_hello(secret: bytes, cli_digest: bytes, session_id: bytes,
                       cert_len: int | None = None) -> bytes:
    """Construct the Fake-TLS ServerHello + CCS + fake certificate record."""
    if cert_len is None:
        cert_len = int.from_bytes(os.urandom(2), "big") % (4096 - 1024) + 1024
    fake_cert = os.urandom(cert_len)

    # key_share(x25519) + supported_versions(TLS1.3) — 46-byte extension blob.
    tls_extensions = b"\x00\x2e" + b"\x00\x33\x00\x24" + b"\x00\x1d\x00\x20"
    tls_extensions += os.urandom(32) + b"\x00\x2b\x00\x02\x03\x04"

    sess_id_len = bytes([len(session_id)])
    srv_hello = TLS_VERS + _ZERO_DIGEST + sess_id_len + session_id
    srv_hello += TLS_CIPHERSUITE + b"\x00" + tls_extensions

    hello_pkt = b"\x16" + TLS_VERS + int.to_bytes(len(srv_hello) + 4, 2, "big")
    hello_pkt += b"\x02" + int.to_bytes(len(srv_hello), 3, "big") + srv_hello
    hello_pkt += TLS_CHANGE_CIPHER + TLS_APP_HDR
    hello_pkt += int.to_bytes(len(fake_cert), 2, "big") + fake_cert

    msg = cli_digest + hello_pkt[:DIGEST_POS] + _ZERO_DIGEST + hello_pkt[DIGEST_POS + DIGEST_LEN:]
    computed = _hmac(secret, msg)
    return hello_pkt[:DIGEST_POS] + computed + hello_pkt[DIGEST_POS + DIGEST_LEN:]


def verify_server_hello(hello_pkt: bytes, secret: bytes, cli_digest: bytes) -> bool:
    """Client-side check of the server's Fake-TLS response."""
    if len(hello_pkt) < DIGEST_POS + DIGEST_LEN:
        return False
    digest = hello_pkt[DIGEST_POS:DIGEST_POS + DIGEST_LEN]
    msg = cli_digest + hello_pkt[:DIGEST_POS] + _ZERO_DIGEST + hello_pkt[DIGEST_POS + DIGEST_LEN:]
    return hmac.compare_digest(digest, _hmac(secret, msg))


def _ext(ext_type: int, payload: bytes) -> bytes:
    return ext_type.to_bytes(2, "big") + len(payload).to_bytes(2, "big") + payload


def _server_name_ext(sni: str) -> bytes:
    host = sni.encode("ascii")
    name = b"\x00" + len(host).to_bytes(2, "big") + host  # type=host_name
    return len(name).to_bytes(2, "big") + name


def build_client_hello(secret: bytes, sni: str, session_id: bytes | None = None,
                       timestamp: int | None = None) -> bytes:
    """Reference ClientHello builder (used by the test client and as the client spec).

    Produces a realistic TLS 1.3 ClientHello (>= 512-byte handshake) with the chosen
    SNI and the HMAC digest embedded in the 32-byte random field.
    """
    if session_id is None:
        session_id = os.urandom(32)
    if timestamp is None:
        timestamp = int(time.time())

    cipher_suites = b"\x13\x01\x13\x02\x13\x03\xc0\x2b\xc0\x2f\xc0\x2c\xc0\x30\x00\xff"
    compression = b"\x00"

    exts = b""
    exts += _ext(0x0000, _server_name_ext(sni))
    exts += _ext(0x002b, b"\x02\x03\x04")                 # supported_versions: TLS1.3
    exts += _ext(0x000a, b"\x00\x06\x00\x1d\x00\x17\x00\x18")  # supported_groups
    exts += _ext(0x0033, b"\x00\x24\x00\x1d\x00\x20" + os.urandom(32))  # key_share x25519
    exts += _ext(0x000d, b"\x00\x08\x04\x03\x05\x03\x06\x03\x08\x04")  # sig algs
    exts += _ext(0x000b, b"\x01\x00")                     # ec_point_formats
    exts += _ext(0x0010, b"\x00\x0c\x02h2\x08http/1.1")   # ALPN
    exts += _ext(0x002d, b"\x01\x01")                     # psk_key_exchange_modes
    exts += _ext(0x0023, b"")                             # session_ticket

    def assemble(extra_exts: bytes) -> bytes:
        all_exts = exts + extra_exts
        body = TLS_VERS + _ZERO_DIGEST + bytes([len(session_id)]) + session_id
        body += len(cipher_suites).to_bytes(2, "big") + cipher_suites
        body += bytes([len(compression)]) + compression
        body += len(all_exts).to_bytes(2, "big") + all_exts
        hs = b"\x01" + len(body).to_bytes(3, "big") + body
        return b"\x16\x03\x01" + len(hs).to_bytes(2, "big") + hs

    record = assemble(b"")
    handshake_len = len(record) - 5
    if handshake_len < 512:
        # padding extension (0x0015) of zero bytes to reach a realistic size.
        pad = 512 - handshake_len - 4
        if pad > 0:
            record = assemble(_ext(0x0015, b"\x00" * pad))

    # Embed the digest: random = HMAC[:28] || (HMAC[28:32] XOR timestamp_le).
    msg = record[:DIGEST_POS] + _ZERO_DIGEST + record[DIGEST_POS + DIGEST_LEN:]
    computed = _hmac(secret, msg)
    ts = int(timestamp).to_bytes(4, "little")
    digest = computed[:DIGEST_LEN - 4] + bytes(
        computed[DIGEST_LEN - 4 + i] ^ ts[i] for i in range(4))
    return record[:DIGEST_POS] + digest + record[DIGEST_POS + DIGEST_LEN:]


class FakeTLSReader:
    """Reads TLS records, skips ChangeCipherSpec, yields application_data payloads."""
    __slots__ = ("_reader",)

    def __init__(self, reader: asyncio.StreamReader):
        self._reader = reader

    async def read_record(self) -> bytes | None:
        """Return one application_data payload, or None on clean EOF."""
        while True:
            header = await self._reader.read(5)
            if not header:
                return None
            if len(header) < 5:
                header += await self._reader.readexactly(5 - len(header))
            rec_type = header[0]
            version = header[1:3]
            length = int.from_bytes(header[3:5], "big")
            if version != TLS_VERS or rec_type not in (0x14, 0x17):
                raise ValueError("bad TLS record header")
            if length > MAX_TLS_RECORD_ACCEPT:
                raise ValueError("TLS record too large")
            payload = await self._reader.readexactly(length) if length else b""
            if rec_type == 0x14:  # ChangeCipherSpec — ignore
                continue
            return payload


class FakeTLSWriter:
    """Wraps payloads into TLS application_data records, chunked to the fingerprint."""
    __slots__ = ("_writer",)

    def __init__(self, writer: asyncio.StreamWriter):
        self._writer = writer

    def write_record(self, payload: bytes) -> None:
        for start in range(0, len(payload), MAX_TLS_RECORD_PAYLOAD):
            chunk = payload[start:start + MAX_TLS_RECORD_PAYLOAD]
            self._writer.write(TLS_APP_HDR + len(chunk).to_bytes(2, "big") + chunk)

    async def drain(self) -> None:
        await self._writer.drain()

    def close(self) -> None:
        try:
            self._writer.close()
        except Exception:
            pass
