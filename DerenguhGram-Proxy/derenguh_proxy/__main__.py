"""Entry point: python -m derenguh_proxy  (or the `derenguh-proxy` console script).

Prints the required startup banner: port, chosen SNI, and a ready derenguh:// link.
Runs without root, inside a 128 MB container, port from $SERVER_PORT (default 3183).
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys

from .config import Config
from .server import Server
from .link import build_link, secret_to_key
from .constants import CODEC_NAMES
from . import compression


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def _print_banner(cfg: Config) -> None:
    link = build_link(cfg.public_host, cfg.port, cfg.default_sni, cfg.secret)
    codecs = ", ".join(CODEC_NAMES[c] for c in compression.available_codecs())
    line = "=" * 64
    print(line)
    print("  DerenguhGram-Proxy v1.0.0 — started successfully")
    print(line)
    print(f"  Listen        : {cfg.host}:{cfg.port}")
    print(f"  Default SNI   : {cfg.default_sni}")
    print(f"  Allowed SNI   : {', '.join(cfg.allowed_sni)}")
    print(f"  Codecs        : {codecs} (preferred: {CODEC_NAMES[cfg.preferred_codec]})")
    print(f"  TCP splice    : {'on' if cfg.mask_enabled else 'off'} -> real streaming host:{cfg.mask_port}")
    print(f"  Max conns     : {cfg.max_connections}   RAM target: 128 MB (streaming)")
    print(f"  Secret (hex)  : {cfg.secret.hex()}")
    print(f"  Secret (key)  : {secret_to_key(cfg.secret)}")
    if cfg.secret_generated:
        print("  NOTE: no DERENGUH_SECRET set — a random secret was generated.")
        print("        Set DERENGUH_SECRET to keep the same link across restarts.")
    print(line)
    print("  Connection link (paste into DerenguhGram-Client):")
    print(f"  {link}")
    print(line)
    sys.stdout.flush()


async def _run(cfg: Config) -> None:
    server = Server(cfg)
    srv = await server.start()
    _print_banner(cfg)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass  # Windows / restricted container

    async with srv:
        await stop.wait()
        log = logging.getLogger("derenguh")
        log.info("shutting down; stats=%s", server.stats)


def main() -> int:
    cfg = Config.from_env()
    _setup_logging(cfg.log_level)
    try:
        asyncio.run(_run(cfg))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
