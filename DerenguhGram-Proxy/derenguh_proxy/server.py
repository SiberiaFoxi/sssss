"""DerenguhGram-Proxy asyncio server.

Connection lifecycle:
  1. Read the first TLS record (the ClientHello).
  2. Authenticate it via Fake-TLS HMAC. If it fails -> TCP splice to the real host.
  3. Send the Fake-TLS ServerHello; wrap the socket in Fake-TLS record framing.
  4. Read the 8-byte DerenguhProto control frame; negotiate codec; pick the DC.
  5. Dial the fixed Telegram DC address (never an arbitrary host).
  6. Send the ack, then run the two bounded-memory relay directions.
"""
from __future__ import annotations

import asyncio
import logging

from .config import Config
from .constants import (
    TG_DATACENTER_PORT, TG_DATACENTERS_V4, TG_DATACENTERS_V6,
    STATUS_OK, STATUS_DC_UNREACHABLE, STATUS_UNSUPPORTED_CODEC,
    STATUS_FORBIDDEN_DC, STREAM_LIMIT, VALID_DC_INDICES, CODEC_NAMES,
)
from . import compression
from .faketls import (
    verify_client_hello, client_digest, build_server_hello,
    FakeTLSReader, FakeTLSWriter,
)
from .sni import extract_sni
from .protocol import ClientHello, ServerAck, ProtocolError
from .relay import client_to_dc, dc_to_client, run_pair, tune_socket
from .splice import splice_to_mask

log = logging.getLogger("derenguh.server")


class Server:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._active = 0
        self._sem = asyncio.Semaphore(cfg.max_connections)
        self.stats = {"accepted": 0, "authenticated": 0, "spliced": 0,
                      "rejected": 0, "errors": 0}
        # Optional test hook: override how a DC connection is opened.
        self.dial_dc = self._default_dial_dc

    async def _default_dial_dc(self, dc_index: int):
        if self.cfg.prefer_ipv6:
            host = TG_DATACENTERS_V6.get(dc_index) or TG_DATACENTERS_V4[dc_index]
        else:
            host = TG_DATACENTERS_V4[dc_index]
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, TG_DATACENTER_PORT, limit=STREAM_LIMIT),
            timeout=self.cfg.connect_timeout,
        )
        tune_socket(writer)
        return reader, writer

    async def _read_first_record(self, reader: asyncio.StreamReader) -> bytes | None:
        header = await asyncio.wait_for(reader.readexactly(5),
                                        timeout=self.cfg.handshake_timeout)
        # Only read a full record body for TLS-looking probes. For anything else
        # (e.g. a plain HTTP probe) return the header and let the splice pipe the rest,
        # so we never block waiting for a misinterpreted "length".
        if header[0] != 0x16 or header[1] != 0x03:
            return header
        length = int.from_bytes(header[3:5], "big")
        if length == 0 or length > 16384 + 2048:
            return header
        body = await asyncio.wait_for(reader.readexactly(length),
                                      timeout=self.cfg.handshake_timeout)
        return header + body

    async def handle(self, reader: asyncio.StreamReader,
                     writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        async with self._sem:
            self._active += 1
            self.stats["accepted"] += 1
            tune_socket(writer)
            dc_writer = None
            try:
                first = await self._read_first_record(reader)
                if first is None:
                    return

                is_tls = len(first) >= 3 and first[0] == 0x16 and first[1] == 0x03
                authed = is_tls and verify_client_hello(
                    first, self.cfg.secret, ignore_time_skew=self.cfg.ignore_time_skew)

                if not authed:
                    self.stats["spliced"] += 1
                    log.debug("unrecognised connection from %s -> splice", peer)
                    await splice_to_mask(reader, writer, first, self.cfg)
                    return

                sni = extract_sni(first)
                if sni is not None and sni not in self.cfg.allowed_sni:
                    # Authenticated but wrong SNI: still splice rather than leak.
                    self.stats["spliced"] += 1
                    await splice_to_mask(reader, writer, first, self.cfg)
                    return

                self.stats["authenticated"] += 1
                sess_id_len = first[43]
                sess_id = first[44:44 + sess_id_len]
                hello = build_server_hello(self.cfg.secret, client_digest(first), sess_id)
                writer.write(hello)
                await writer.drain()

                tls_reader = FakeTLSReader(reader)
                tls_writer = FakeTLSWriter(writer)

                control_bytes = await asyncio.wait_for(tls_reader.read_record(),
                                                       timeout=self.cfg.handshake_timeout)
                if control_bytes is None:
                    return
                try:
                    hello_ctrl = ClientHello.decode(control_bytes)
                except ProtocolError as exc:
                    log.debug("bad control frame from %s: %s", peer, exc)
                    self.stats["rejected"] += 1
                    ack = ServerAck(codec=self.cfg.preferred_codec,
                                    status=STATUS_FORBIDDEN_DC
                                    if "DC" in str(exc) else STATUS_UNSUPPORTED_CODEC)
                    tls_writer.write_record(ack.encode())
                    await tls_writer.drain()
                    return

                codec = compression.negotiate(hello_ctrl.codec)
                if hello_ctrl.dc_index not in VALID_DC_INDICES:
                    ack = ServerAck(codec=codec, status=STATUS_FORBIDDEN_DC)
                    tls_writer.write_record(ack.encode())
                    await tls_writer.drain()
                    return

                try:
                    dc_reader, dc_writer = await self.dial_dc(hello_ctrl.dc_index)
                except (OSError, asyncio.TimeoutError) as exc:
                    log.warning("DC %d unreachable: %s", hello_ctrl.dc_index, exc)
                    ack = ServerAck(codec=codec, status=STATUS_DC_UNREACHABLE)
                    tls_writer.write_record(ack.encode())
                    await tls_writer.drain()
                    return

                ack = ServerAck(codec=codec, status=STATUS_OK)
                tls_writer.write_record(ack.encode())
                await tls_writer.drain()

                log.info("client %s authenticated (sni=%s dc=%d codec=%s)",
                         peer, sni, hello_ctrl.dc_index, CODEC_NAMES.get(codec, codec))

                decompressor = compression.make_decompressor(codec)
                compressor = compression.make_compressor(codec)
                await run_pair(
                    client_to_dc(tls_reader, decompressor, dc_writer, self.cfg.idle_timeout),
                    dc_to_client(dc_reader, compressor, tls_writer, self.cfg.idle_timeout),
                )
            except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError):
                pass
            except Exception:
                self.stats["errors"] += 1
                log.exception("connection handler error")
            finally:
                self._active -= 1
                for w in (dc_writer, writer):
                    if w is not None:
                        try:
                            w.close()
                        except Exception:
                            pass

    async def start(self) -> asyncio.AbstractServer:
        return await asyncio.start_server(self.handle, self.cfg.host, self.cfg.port,
                                          limit=STREAM_LIMIT, reuse_address=True)
