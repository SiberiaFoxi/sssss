"""Reference DerenguhProto client (asyncio).

This is a compact, readable implementation of the client side of the protocol. It
serves three purposes:
  * smoke-testing a running server without the full Telegram client,
  * the executable specification the C++/Kotlin client ports must match,
  * the driver used by the integration tests.

It carries an opaque byte stream (in production: the client's obfuscated-2 MTProto
bytes for a given DC) through the Fake-TLS + compression tunnel.

CLI:  python -m derenguh_proxy.reference_client --link 'derenguh://proxy?...'
"""
from __future__ import annotations

import argparse
import asyncio

from .constants import STATUS_OK, CODEC_ZLIB, TLS_VERS
from .faketls import (
    build_client_hello, verify_server_hello, client_digest,
    FakeTLSReader, FakeTLSWriter,
)
from .protocol import ClientHello, ServerAck
from .compression import make_compressor, make_decompressor
from .link import parse_link


class DerenguhClient:
    def __init__(self, host: str, port: int, secret: bytes, sni: str,
                 dc_index: int = 2, codec: int = CODEC_ZLIB):
        self.host, self.port, self.secret, self.sni = host, port, secret, sni
        self.dc_index, self.requested_codec = dc_index, codec
        self.codec = codec
        self._reader = None
        self._writer = None
        self.tls_reader = None
        self.tls_writer = None
        self._compressor = None
        self._decompressor = None

    async def _read_server_hello(self, reader: asyncio.StreamReader) -> bytes:
        # Record 1: Handshake (ServerHello), version 0x0303.
        hdr = await reader.readexactly(5)
        if hdr[0] != 0x16:
            raise ValueError("expected ServerHello handshake record")
        n = int.from_bytes(hdr[3:5], "big")
        rec1 = hdr + await reader.readexactly(n)
        # Record 2: ChangeCipherSpec (6 bytes: 14 03 03 00 01 01).
        rec2 = await reader.readexactly(6)
        # Record 3: application_data (fake certificate).
        hdr3 = await reader.readexactly(5)
        n3 = int.from_bytes(hdr3[3:5], "big")
        rec3 = hdr3 + await reader.readexactly(n3)
        return rec1 + rec2 + rec3

    async def connect(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
        ch = build_client_hello(self.secret, self.sni)
        self._writer.write(ch)
        await self._writer.drain()

        hello_pkt = await self._read_server_hello(self._reader)
        if not verify_server_hello(hello_pkt, self.secret, client_digest(ch)):
            raise ValueError("server Fake-TLS authentication failed")

        self.tls_reader = FakeTLSReader(self._reader)
        self.tls_writer = FakeTLSWriter(self._writer)

        self.tls_writer.write_record(
            ClientHello(codec=self.requested_codec, dc_index=self.dc_index).encode())
        await self.tls_writer.drain()

        ack_bytes = await self.tls_reader.read_record()
        if ack_bytes is None:
            raise ConnectionError("server closed before ack")
        ack = ServerAck.decode(ack_bytes)
        if ack.status != STATUS_OK:
            raise ConnectionError(f"server rejected connection, status={ack.status}")
        self.codec = ack.codec
        self._compressor = make_compressor(self.codec)
        self._decompressor = make_decompressor(self.codec)

    async def send(self, data: bytes) -> None:
        block = self._compressor.compress(data)
        if block:
            self.tls_writer.write_record(block)
            await self.tls_writer.drain()

    async def recv(self) -> bytes | None:
        payload = await self.tls_reader.read_record()
        if payload is None:
            return None
        return self._decompressor.decompress(payload)

    async def recv_exactly(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = await self.recv()
            if not chunk:
                break
            buf += chunk
        return bytes(buf[:n])

    def close(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception:
                pass


async def _smoke(link: str, payload: bytes) -> None:
    fields = parse_link(link)
    client = DerenguhClient(fields["server"], fields["port"], fields["secret"],
                            fields["sni"])
    await client.connect()
    print(f"connected; negotiated codec={client.codec}")
    await client.send(payload)
    echo = await client.recv_exactly(len(payload))
    print(f"sent {len(payload)} bytes, received {len(echo)} bytes, "
          f"match={echo == payload}")
    client.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="DerenguhProto reference client / smoke test")
    ap.add_argument("--link", required=True, help="derenguh://proxy?... link")
    ap.add_argument("--bytes", type=int, default=4096, help="payload size to echo")
    args = ap.parse_args()
    asyncio.run(_smoke(args.link, bytes(range(256)) * (args.bytes // 256 + 1)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
