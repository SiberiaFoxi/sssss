"""Minimal TLS ClientHello SNI extraction (no full TLS stack needed).

We only need the server_name extension to (a) check the allowlist and (b) pick the
real host to splice unrecognised connections to. Parsing is defensive: any malformed
buffer returns None instead of raising, so a hostile scanner cannot crash the server.
"""
from __future__ import annotations

import struct


def extract_sni(record: bytes) -> str | None:
    """Return the first host_name SNI from a TLS ClientHello record, or None.

    ``record`` is the full TLS record starting at 0x16 (handshake). Returns None for
    anything that is not a well-formed ClientHello with a host_name SNI.
    """
    try:
        if len(record) < 5 or record[0] != 0x16:
            return None
        rec_len = int.from_bytes(record[3:5], "big")
        body = record[5:5 + rec_len]
        if len(body) < 4 or body[0] != 0x01:  # handshake type client_hello
            return None
        hs_len = int.from_bytes(body[1:4], "big")
        hs = body[4:4 + hs_len]
        pos = 0
        # client_version(2) + random(32)
        pos += 2 + 32
        if pos + 1 > len(hs):
            return None
        sid_len = hs[pos]
        pos += 1 + sid_len
        if pos + 2 > len(hs):
            return None
        cs_len = int.from_bytes(hs[pos:pos + 2], "big")
        pos += 2 + cs_len
        if pos + 1 > len(hs):
            return None
        comp_len = hs[pos]
        pos += 1 + comp_len
        if pos + 2 > len(hs):
            return None
        ext_total = int.from_bytes(hs[pos:pos + 2], "big")
        pos += 2
        ext_end = min(pos + ext_total, len(hs))
        while pos + 4 <= ext_end:
            ext_type = int.from_bytes(hs[pos:pos + 2], "big")
            ext_len = int.from_bytes(hs[pos + 2:pos + 4], "big")
            pos += 4
            ext_data = hs[pos:pos + ext_len]
            pos += ext_len
            if ext_type == 0x0000:  # server_name
                return _parse_server_name(ext_data)
        return None
    except (IndexError, struct.error, ValueError):
        return None


def _parse_server_name(data: bytes) -> str | None:
    try:
        if len(data) < 2:
            return None
        list_len = int.from_bytes(data[0:2], "big")
        pos = 2
        end = min(2 + list_len, len(data))
        while pos + 3 <= end:
            name_type = data[pos]
            name_len = int.from_bytes(data[pos + 1:pos + 3], "big")
            pos += 3
            name = data[pos:pos + name_len]
            pos += name_len
            if name_type == 0x00:  # host_name
                return name.decode("ascii", "strict").lower().rstrip(".")
        return None
    except (IndexError, UnicodeDecodeError, ValueError):
        return None


def is_valid_tls_client_hello_prefix(data: bytes) -> bool:
    """Cheap check used before reading the whole record."""
    return len(data) >= 3 and data[0] == 0x16 and data[1] == 0x03
