"""Generate shared test vectors from the verified Python implementation.

Both client ports (C++/Kotlin) load these to check byte-level compatibility.
Run: python3 deploy/gen_test_vectors.py > ../DerenguhGram-Client/shared/test_vectors.json
"""
import base64
import json
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from derenguh_proxy.faketls import build_client_hello, client_digest
from derenguh_proxy.protocol import ClientHello, ServerAck
from derenguh_proxy.link import build_link, secret_to_key
from derenguh_proxy.constants import CODEC_ZLIB, STATUS_OK

SECRET = bytes.fromhex("00112233445566778899aabbccddeeff")
SESSION_ID = bytes(range(32))
TIMESTAMP = 1700000000
SNI = "music.yandex.ru"


def b64(b):
    return base64.b64encode(b).decode()


def main():
    ch = build_client_hello(SECRET, SNI, session_id=SESSION_ID, timestamp=TIMESTAMP)
    # A zlib block (server params: wbits=12, memLevel=5, level=6) the client must decode.
    plain = b"DerenguhProto interop vector " * 40
    co = zlib.compressobj(6, zlib.DEFLATED, 12, 5)
    block = co.compress(plain) + co.flush(zlib.Z_SYNC_FLUSH)

    vectors = {
        "secret_hex": SECRET.hex(),
        "secret_key": secret_to_key(SECRET),
        "link": build_link("proxy.example.org", 3183, SNI, SECRET),
        "client_hello": {
            "sni": SNI,
            "session_id_b64": b64(SESSION_ID),
            "timestamp": TIMESTAMP,
            "record_b64": b64(ch),
            "digest_b64": b64(client_digest(ch)),
            "record_len": len(ch),
        },
        "control_frames": [
            {"codec": c, "dc_index": d, "b64": b64(ClientHello(codec=c, dc_index=d).encode())}
            for c in (0, 1, 2) for d in (1, 2, 5)
        ],
        "server_ack_ok_zlib": b64(ServerAck(codec=CODEC_ZLIB, status=STATUS_OK).encode()),
        "zlib_decompress_vector": {
            "comment": "Decode block_b64 with a standard inflater; must equal plain_b64.",
            "block_b64": b64(block),
            "plain_b64": b64(plain),
        },
    }
    print(json.dumps(vectors, indent=2))


if __name__ == "__main__":
    main()
