"""Protocol constants, Telegram data-center map and the RU streaming SNI allowlist.

Nothing in here touches the network; it is safe to import from tests and from the
client-side reference implementation. Keep this file byte-for-byte in sync with the
client's `DerenguhProto` constants (see DerenguhGram-Client/docs/PROTOCOL.md).
"""
from __future__ import annotations

# --- DerenguhProto wire constants -------------------------------------------------
PROTO_MAGIC = b"DG"          # first two bytes of every control frame
PROTO_VERSION = 0x01         # DerenguhProto v1
CONTROL_FRAME_LEN = 8        # magic(2) ver(1) codec(1) dc/status(1) flags(1) rsv(2)

# Compression codecs (negotiated in the control frame).
CODEC_NONE = 0x00
CODEC_ZLIB = 0x01
CODEC_BROTLI = 0x02
CODEC_NAMES = {CODEC_NONE: "none", CODEC_ZLIB: "zlib", CODEC_BROTLI: "brotli"}

# Server ack status codes (the `dc_index` byte position is reused for status).
STATUS_OK = 0x00
STATUS_DC_UNREACHABLE = 0x01
STATUS_UNSUPPORTED_CODEC = 0x02
STATUS_PROTO_ERROR = 0x03
STATUS_FORBIDDEN_DC = 0x04

# --- Fake-TLS layout (identical to alexbers/mtprotoproxy so the DPI fingerprint
#     matches a known-good MTProto proxy) ------------------------------------------
TLS_VERS = b"\x03\x03"                 # legacy_record_version = TLS 1.2
TLS_CIPHERSUITE = b"\x13\x01"          # TLS_AES_128_GCM_SHA256
TLS_CHANGE_CIPHER = b"\x14" + TLS_VERS + b"\x00\x01\x01"
TLS_APP_HDR = b"\x17" + TLS_VERS       # application_data record prefix
TLS_HANDSHAKE_HDR = b"\x16\x03\x01"    # ClientHello record prefix clients send

DIGEST_LEN = 32
DIGEST_POS = 11                        # offset of the 32-byte "random" field
SESSION_ID_LEN_POS = DIGEST_POS + DIGEST_LEN          # 43
SESSION_ID_POS = SESSION_ID_LEN_POS + 1               # 44

# Maximum application_data payload we emit per TLS record. Real TLS 1.3 caps at
# 16384 + 256; mtprotoproxy uses 16384 + 24. We stay well inside the fingerprint.
MAX_TLS_RECORD_PAYLOAD = 16384 + 24
# Hard ceiling we accept from a peer before treating the record as hostile.
MAX_TLS_RECORD_ACCEPT = 16384 + 512

# --- Telegram data centers (the ONLY upstreams the relay may dial) ----------------
# A DerenguhGram proxy is intentionally NOT an open relay: the client may only ask
# for DC 1..5, which map to these fixed addresses. Port 443 speaks obfuscated-2.
TG_DATACENTER_PORT = 443
TG_DATACENTERS_V4 = {
    1: "149.154.175.50",
    2: "149.154.167.51",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "149.154.171.5",
}
TG_DATACENTERS_V6 = {
    1: "2001:b28:f23d:f001::a",
    2: "2001:67c:04e8:f002::a",
    3: "2001:b28:f23d:f003::a",
    4: "2001:67c:04e8:f004::a",
    5: "2001:b28:f23f:f005::a",
}
VALID_DC_INDICES = frozenset(TG_DATACENTERS_V4)

# --- RU streaming SNI allowlist ---------------------------------------------------
# The client picks one of these as the TLS SNI. The server accepts exactly this set.
# NOTE: SNI is a *hostname*, never a URL path. "yandex.ru/video" is not a valid SNI;
# the correct host is yandex.ru. We normalise the user's list to hostnames.
STREAMING_SNI = (
    "music.yandex.ru",   # Яндекс.Музыка
    "vk.com",            # VK Music / VK Видео
    "rutube.ru",         # RuTube
    "yandex.ru",         # Яндекс.Видео (host; path /video is not part of SNI)
    "dzen.ru",           # Яндекс.Дзен
    "vkvideo.ru",        # VK Видео
)
DEFAULT_SNI = "music.yandex.ru"

# --- Memory / streaming budget (128 MB container target) --------------------------
RELAY_CHUNK = 8192          # bytes read per relay iteration (never buffer a message)
STREAM_LIMIT = 16384        # asyncio StreamReader high-water mark
SOCKET_BUF = 16384          # SO_RCVBUF / SO_SNDBUF hint
DEFAULT_MAX_CONNECTIONS = 64
DEFAULT_HANDSHAKE_TIMEOUT = 12.0
DEFAULT_CONNECT_TIMEOUT = 8.0
DEFAULT_IDLE_TIMEOUT = 300.0
