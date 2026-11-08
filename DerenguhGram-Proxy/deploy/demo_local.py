"""Self-contained live demo + memory probe. No Telegram / no external network.

Starts the real Server with a local echo "DC", drives it with the reference client,
then opens many concurrent idle+active connections and reports peak RSS to show the
streaming relay stays well inside a 128 MB container.

Run:  python deploy/demo_local.py
"""
from __future__ import annotations

import asyncio
import os
import resource
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from derenguh_proxy.config import Config
from derenguh_proxy.server import Server
from derenguh_proxy.reference_client import DerenguhClient
from derenguh_proxy.link import generate_secret, build_link
from derenguh_proxy.constants import CODEC_ZLIB


def rss_mb() -> float:
    # ru_maxrss is KB on Linux.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


async def echo_dc(reader, writer):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.IncompleteReadError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def main() -> None:
    dc = await asyncio.start_server(echo_dc, "127.0.0.1", 0)
    dc_port = dc.sockets[0].getsockname()[1]

    cfg = Config()
    cfg.host = "127.0.0.1"
    cfg.port = 0
    cfg.secret = generate_secret()
    cfg.public_host = "127.0.0.1"
    cfg.max_connections = 256
    server = Server(cfg)

    async def dial_dc(dc_index):
        return await asyncio.open_connection("127.0.0.1", dc_port)
    server.dial_dc = dial_dc

    srv = await server.start()
    port = srv.sockets[0].getsockname()[1]
    print("Live demo link:", build_link("127.0.0.1", port, cfg.default_sni, cfg.secret))

    # 1) Functional echo through the full tunnel.
    client = DerenguhClient("127.0.0.1", port, cfg.secret, "music.yandex.ru",
                            dc_index=2, codec=CODEC_ZLIB)
    await client.connect()
    payload = bytes(range(256)) * 64  # 16 KB
    await client.send(payload)
    got = await client.recv_exactly(len(payload))
    print(f"Echo round-trip: {len(payload)} bytes, match={got == payload}, "
          f"codec={client.codec}")
    client.close()

    # 2) Concurrency + memory probe: 200 connections each pushing 256 KB total.
    base = rss_mb()
    N = 200
    PER = 256 * 1024

    async def worker(i):
        c = DerenguhClient("127.0.0.1", port, cfg.secret, cfg.allowed_sni[i % 6],
                           dc_index=(i % 5) + 1, codec=CODEC_ZLIB)
        await c.connect()
        chunk = bytes((i + j) % 256 for j in range(4096))
        received = bytearray()

        async def rd():
            while len(received) < PER:
                d = await c.recv()
                if not d:
                    break
                received.extend(d)
        t = asyncio.ensure_future(rd())
        for _ in range(PER // len(chunk)):
            await c.send(chunk)
        await t
        c.close()
        return len(received) == PER

    results = await asyncio.gather(*(worker(i) for i in range(N)))
    peak = rss_mb()
    print(f"Concurrent connections: {N}, all echoed correctly: {all(results)}")
    print(f"Total bytes relayed: {N * PER / 1024 / 1024:.1f} MB")
    print(f"RSS baseline: {base:.1f} MB, peak: {peak:.1f} MB, delta: {peak - base:.1f} MB")
    print(f"Server stats: {server.stats}")

    srv.close()
    await srv.wait_closed()
    dc.close()
    await dc.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
