"""Server configuration: defaults + environment overrides (Pterodactyl-friendly).

Every value can be set via an environment variable so the server runs unconfigured
inside a game-panel container. No config file is required. The shared secret may be
provided as 32-char hex or base64url; if absent, one is generated and printed once.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from .constants import (
    STREAMING_SNI, DEFAULT_SNI, DEFAULT_MAX_CONNECTIONS,
    DEFAULT_HANDSHAKE_TIMEOUT, DEFAULT_CONNECT_TIMEOUT, DEFAULT_IDLE_TIMEOUT,
    CODEC_ZLIB,
)
from .link import generate_secret, key_to_secret


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    try:
        return int(val) if val is not None else default
    except ValueError:
        return default


@dataclass
class Config:
    host: str = "0.0.0.0"
    port: int = 3183
    secret: bytes = field(default_factory=generate_secret)
    secret_generated: bool = False
    allowed_sni: tuple[str, ...] = STREAMING_SNI
    default_sni: str = DEFAULT_SNI
    # Public host advertised in the connection link (falls back to a placeholder).
    public_host: str = "your.server.host"
    max_connections: int = DEFAULT_MAX_CONNECTIONS
    handshake_timeout: float = DEFAULT_HANDSHAKE_TIMEOUT
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT
    idle_timeout: float = DEFAULT_IDLE_TIMEOUT
    preferred_codec: int = CODEC_ZLIB
    # TCP splice: where to forward unrecognised / unauthenticated connections.
    mask_enabled: bool = True
    mask_port: int = 443
    # If True, splice to the real IP of the SNI the scanner sent; otherwise use
    # mask_host. Reaching the real streaming host makes the scanner's probe legit.
    mask_use_sni_host: bool = True
    mask_host: str = DEFAULT_SNI
    prefer_ipv6: bool = False
    ignore_time_skew: bool = False
    log_level: str = "info"

    @classmethod
    def from_env(cls) -> "Config":
        cfg = cls()
        cfg.host = os.environ.get("SERVER_IP", os.environ.get("LISTEN_ADDR", cfg.host))
        # Pterodactyl exposes SERVER_PORT; also accept PORT / DERENGUH_PORT.
        cfg.port = _env_int("SERVER_PORT", _env_int("PORT", _env_int("DERENGUH_PORT", cfg.port)))
        cfg.public_host = os.environ.get("DERENGUH_PUBLIC_HOST", cfg.public_host)

        raw_secret = os.environ.get("DERENGUH_SECRET", "").strip()
        if raw_secret:
            cfg.secret = key_to_secret(raw_secret)
            cfg.secret_generated = False
        else:
            cfg.secret = generate_secret()
            cfg.secret_generated = True

        sni_env = os.environ.get("DERENGUH_ALLOWED_SNI", "").strip()
        if sni_env:
            hosts = tuple(h.strip().lower().rstrip(".") for h in sni_env.split(",") if h.strip())
            cfg.allowed_sni = hosts or STREAMING_SNI
        cfg.default_sni = os.environ.get("DERENGUH_SNI", cfg.default_sni).strip().lower()
        if cfg.default_sni not in cfg.allowed_sni:
            cfg.default_sni = cfg.allowed_sni[0]

        cfg.max_connections = _env_int("DERENGUH_MAX_CONN", cfg.max_connections)
        cfg.handshake_timeout = float(_env_int("DERENGUH_HANDSHAKE_TIMEOUT", int(cfg.handshake_timeout)))
        cfg.connect_timeout = float(_env_int("DERENGUH_CONNECT_TIMEOUT", int(cfg.connect_timeout)))
        cfg.idle_timeout = float(_env_int("DERENGUH_IDLE_TIMEOUT", int(cfg.idle_timeout)))
        cfg.mask_enabled = _env_bool("DERENGUH_MASK", cfg.mask_enabled)
        cfg.mask_port = _env_int("DERENGUH_MASK_PORT", cfg.mask_port)
        cfg.mask_use_sni_host = _env_bool("DERENGUH_MASK_USE_SNI", cfg.mask_use_sni_host)
        cfg.mask_host = os.environ.get("DERENGUH_MASK_HOST", cfg.mask_host)
        cfg.prefer_ipv6 = _env_bool("DERENGUH_PREFER_IPV6", cfg.prefer_ipv6)
        cfg.ignore_time_skew = _env_bool("DERENGUH_IGNORE_TIME_SKEW", cfg.ignore_time_skew)
        cfg.log_level = os.environ.get("DERENGUH_LOG_LEVEL", cfg.log_level)

        codec_env = os.environ.get("DERENGUH_CODEC", "").strip().lower()
        cfg.preferred_codec = {"none": 0, "zlib": 1, "brotli": 2}.get(codec_env, cfg.preferred_codec)
        return cfg
