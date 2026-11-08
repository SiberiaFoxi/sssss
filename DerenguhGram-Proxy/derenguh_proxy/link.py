"""Shared-secret generation and the derenguh:// connection link.

The secret is 16 random bytes. It is used ONLY as the HMAC key for the Fake-TLS
handshake (client authentication to the proxy). It is deliberately independent of
the MTProto auth key and of the obfuscated-2 transport keys, which stay end-to-end
between the client and Telegram. Both sides must use the identical 16 bytes.

Link format (matches the client's URL parser):
    derenguh://proxy?server=<host>&port=<port>&sni=<sni>&key=<base64url_key>
"""
from __future__ import annotations

import base64
import binascii
import os
import urllib.parse

SECRET_LEN = 16


def generate_secret() -> bytes:
    return os.urandom(SECRET_LEN)


def secret_to_key(secret: bytes) -> str:
    """base64url without padding, as carried in the link's `key` parameter."""
    if len(secret) != SECRET_LEN:
        raise ValueError(f"secret must be {SECRET_LEN} bytes")
    return base64.urlsafe_b64encode(secret).decode("ascii").rstrip("=")


def key_to_secret(key: str) -> bytes:
    """Accept base64url (link form) or 32-char hex (config form)."""
    key = key.strip()
    if len(key) == 2 * SECRET_LEN:
        try:
            return bytes.fromhex(key)
        except ValueError:
            pass
    pad = "=" * (-len(key) % 4)
    try:
        secret = base64.urlsafe_b64decode(key + pad)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("key is neither 32-char hex nor base64url") from exc
    if len(secret) != SECRET_LEN:
        raise ValueError(f"decoded secret must be {SECRET_LEN} bytes, got {len(secret)}")
    return secret


def build_link(host: str, port: int, sni: str, secret: bytes) -> str:
    params = {
        "server": host,
        "port": str(port),
        "sni": sni,
        "key": secret_to_key(secret),
    }
    return "derenguh://proxy?" + urllib.parse.urlencode(params)


def parse_link(link: str) -> dict:
    """Parse a derenguh:// link back into its fields (used by tests and tooling)."""
    parsed = urllib.parse.urlsplit(link)
    if parsed.scheme != "derenguh" or parsed.netloc != "proxy":
        raise ValueError("not a derenguh://proxy link")
    qs = urllib.parse.parse_qs(parsed.query)
    try:
        return {
            "server": qs["server"][0],
            "port": int(qs["port"][0]),
            "sni": qs["sni"][0],
            "secret": key_to_secret(qs["key"][0]),
        }
    except (KeyError, IndexError) as exc:
        raise ValueError("link is missing required parameters") from exc
