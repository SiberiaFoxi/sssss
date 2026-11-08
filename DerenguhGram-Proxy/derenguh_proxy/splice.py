"""TCP splice: hand unrecognised connections to the real streaming service.

If the first record is not an authenticated DerenguhGram ClientHello (a DPI scanner,
a browser, a port probe), we open a TCP connection to the genuine host the SNI points
at and pipe bytes both ways. The probe then receives a legitimate TLS ServerHello and
certificate from the real RU streaming endpoint, so the proxy is indistinguishable
from that service to an active prober. This is a userspace splice (no root / no
kernel splice(2)), which is exactly what a Pterodactyl container allows.
"""
from __future__ import annotations

import asyncio
import logging

from .config import Config
from .relay import raw_pipe, run_pair, tune_socket
from .sni import extract_sni
from .constants import STREAMING_SNI

log = logging.getLogger("derenguh.splice")

# Cache resolved hosts so a flood of probes does not hammer the resolver.
_dns_cache: dict[str, str] = {}


async def _resolve(host: str) -> str | None:
    if host in _dns_cache:
        return _dns_cache[host]
    try:
        loop = asyncio.get_running_loop()
        infos = await loop.getaddrinfo(host, None, type=asyncio.socket.SOCK_STREAM)
        if not infos:
            return None
        ip = infos[0][4][0]
        _dns_cache[host] = ip
        return ip
    except OSError:
        return None


def _pick_mask_host(cfg: Config, first_record: bytes) -> str:
    if cfg.mask_use_sni_host:
        sni = extract_sni(first_record)
        # Only splice to hosts in our allowlist; never become an open relay to
        # arbitrary attacker-chosen domains.
        if sni and sni in cfg.allowed_sni:
            return sni
    return cfg.mask_host


async def splice_to_mask(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                         first_record: bytes, cfg: Config) -> None:
    """Forward an unrecognised connection to a real streaming host."""
    if not cfg.mask_enabled:
        # Drop the connection promptly (the caller closes the writer in finally).
        # We do not send a ServerHello, so an unauthenticated peer learns nothing.
        return

    host = _pick_mask_host(cfg, first_record)
    target = host
    if cfg.mask_use_sni_host:
        resolved = await _resolve(host)
        if resolved:
            target = resolved

    upstream_writer = None
    try:
        upstream_reader, upstream_writer = await asyncio.wait_for(
            asyncio.open_connection(target, cfg.mask_port, limit=16384),
            timeout=cfg.connect_timeout,
        )
        tune_socket(upstream_writer)
        # Replay the bytes we already read so the real server sees a full ClientHello.
        upstream_writer.write(first_record)
        await upstream_writer.drain()

        await run_pair(
            raw_pipe(reader, upstream_writer, cfg.idle_timeout),
            raw_pipe(upstream_reader, writer, cfg.idle_timeout),
        )
    except (OSError, asyncio.TimeoutError, asyncio.IncompleteReadError) as exc:
        log.debug("splice to %s failed: %s", target, exc)
    finally:
        if upstream_writer is not None:
            try:
                upstream_writer.close()
            except Exception:
                pass
