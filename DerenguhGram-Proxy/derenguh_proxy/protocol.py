"""DerenguhProto control-frame encoding/decoding.

After the Fake-TLS handshake the client sends exactly one 8-byte control frame as
the first application_data record; the server replies with one 8-byte ack. Every
record afterwards carries a flushed compression block (see compression.py).

Client control frame:  "DG" | ver | codec | dc_index | flags | 00 00
Server ack frame:      "DG" | ver | codec | status   | flags | 00 00
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

from .constants import (
    PROTO_MAGIC, PROTO_VERSION, CONTROL_FRAME_LEN, VALID_DC_INDICES,
)

_HDR = struct.Struct(">2sBBBBH")  # magic, ver, codec, dc/status, flags, reserved


class ProtocolError(ValueError):
    """Raised when a control frame is malformed."""


@dataclass(frozen=True)
class ClientHello:
    codec: int
    dc_index: int
    flags: int = 0

    def encode(self) -> bytes:
        return _HDR.pack(PROTO_MAGIC, PROTO_VERSION, self.codec, self.dc_index,
                         self.flags, 0)

    @classmethod
    def decode(cls, data: bytes) -> "ClientHello":
        if len(data) != CONTROL_FRAME_LEN:
            raise ProtocolError(f"control frame must be {CONTROL_FRAME_LEN} bytes")
        magic, ver, codec, dc_index, flags, reserved = _HDR.unpack(data)
        if magic != PROTO_MAGIC:
            raise ProtocolError("bad magic")
        if ver != PROTO_VERSION:
            raise ProtocolError(f"unsupported version {ver}")
        if dc_index not in VALID_DC_INDICES:
            raise ProtocolError(f"forbidden DC index {dc_index}")
        if reserved != 0:
            raise ProtocolError("reserved bits must be zero")
        return cls(codec=codec, dc_index=dc_index, flags=flags)


@dataclass(frozen=True)
class ServerAck:
    codec: int
    status: int
    flags: int = 0

    def encode(self) -> bytes:
        return _HDR.pack(PROTO_MAGIC, PROTO_VERSION, self.codec, self.status,
                         self.flags, 0)

    @classmethod
    def decode(cls, data: bytes) -> "ServerAck":
        if len(data) != CONTROL_FRAME_LEN:
            raise ProtocolError(f"ack frame must be {CONTROL_FRAME_LEN} bytes")
        magic, ver, codec, status, flags, reserved = _HDR.unpack(data)
        if magic != PROTO_MAGIC:
            raise ProtocolError("bad magic")
        if ver != PROTO_VERSION:
            raise ProtocolError(f"unsupported version {ver}")
        return cls(codec=codec, status=status, flags=flags)
