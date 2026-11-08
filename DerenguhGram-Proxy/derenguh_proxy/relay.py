"""Bounded-memory bidirectional relay and raw TCP splice.

Memory discipline (128 MB target): we never accumulate a whole MTProto message. The
client->DC path reads one TLS record at a time and feeds it straight to a streaming
decompressor; the DC->client path reads at most RELAY_CHUNK bytes, compresses, and
writes one record. Backpressure is enforced with drain() after every write.
"""
from __future__ import annotations

import asyncio
import socket

from .constants import RELAY_CHUNK, SOCKET_BUF
from .compression import Compressor, Decompressor
from .faketls import FakeTLSReader, FakeTLSWriter


def tune_socket(writer: asyncio.StreamWriter) -> None:
    sock = writer.get_extra_info("socket")
    if sock is None:
        return
    for opt, val in ((socket.SO_RCVBUF, SOCKET_BUF), (socket.SO_SNDBUF, SOCKET_BUF)):
        try:
            sock.setsockopt(socket.SOL_SOCKET, opt, val)
        except OSError:
            pass
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    except OSError:
        pass


async def client_to_dc(tls_reader: FakeTLSReader, decompressor: Decompressor,
                       dc_writer: asyncio.StreamWriter, idle_timeout: float) -> None:
    """Client (compressed, Fake-TLS) -> Telegram DC (raw obfuscated-2)."""
    while True:
        payload = await asyncio.wait_for(tls_reader.read_record(), timeout=idle_timeout)
        if payload is None:
            break
        if not payload:
            continue
        plain = decompressor.decompress(payload)
        if plain:
            dc_writer.write(plain)
            await dc_writer.drain()
    if not dc_writer.is_closing():
        try:
            dc_writer.write_eof()
        except (OSError, NotImplementedError):
            pass


async def dc_to_client(dc_reader: asyncio.StreamReader, compressor: Compressor,
                       tls_writer: FakeTLSWriter, idle_timeout: float) -> None:
    """Telegram DC (raw obfuscated-2) -> client (compressed, Fake-TLS)."""
    while True:
        data = await asyncio.wait_for(dc_reader.read(RELAY_CHUNK), timeout=idle_timeout)
        if not data:
            break
        block = compressor.compress(data)
        if block:
            tls_writer.write_record(block)
            await tls_writer.drain()


async def raw_pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                   idle_timeout: float) -> None:
    """Unframed byte pipe used by the TCP splice fallback."""
    while True:
        data = await asyncio.wait_for(reader.read(RELAY_CHUNK), timeout=idle_timeout)
        if not data:
            break
        writer.write(data)
        await writer.drain()
    if not writer.is_closing():
        try:
            writer.write_eof()
        except (OSError, NotImplementedError):
            pass


async def run_pair(task_a, task_b) -> None:
    """Run two relay coroutines; when either finishes/fails, cancel the other."""
    a = asyncio.ensure_future(task_a)
    b = asyncio.ensure_future(task_b)
    try:
        await asyncio.wait({a, b}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in (a, b):
            if not t.done():
                t.cancel()
        # Drain cancellations/exceptions so they never leak as "never retrieved".
        await asyncio.gather(a, b, return_exceptions=True)
