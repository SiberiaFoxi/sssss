"""Unit tests for the pure modules (no network). Run: python -m unittest discover -s tests"""
import unittest

from derenguh_proxy import compression
from derenguh_proxy.constants import (
    CODEC_NONE, CODEC_ZLIB, CODEC_BROTLI, STATUS_OK,
)
from derenguh_proxy.protocol import ClientHello, ServerAck, ProtocolError
from derenguh_proxy.link import (
    generate_secret, secret_to_key, key_to_secret, build_link, parse_link,
)
from derenguh_proxy.faketls import (
    build_client_hello, verify_client_hello, build_server_hello,
    verify_server_hello, client_digest,
)
from derenguh_proxy.sni import extract_sni


class CompressionTests(unittest.TestCase):
    def _roundtrip(self, codec):
        comp = compression.make_compressor(codec)
        dec = compression.make_decompressor(codec)
        out = bytearray()
        # Feed many small chunks to exercise the persistent streaming state.
        for i in range(50):
            chunk = (b"the quick brown fox %d " % i) * 20
            block = comp.compress(chunk)
            out += dec.decompress(block)
        expected = b"".join((b"the quick brown fox %d " % i) * 20 for i in range(50))
        self.assertEqual(bytes(out), expected)

    def test_none_roundtrip(self):
        self._roundtrip(CODEC_NONE)

    def test_zlib_roundtrip(self):
        self._roundtrip(CODEC_ZLIB)

    def test_brotli_roundtrip(self):
        if compression.HAVE_BROTLI:
            self._roundtrip(CODEC_BROTLI)
        else:
            self.skipTest("brotli not installed")

    def test_negotiate_downgrade(self):
        self.assertEqual(compression.negotiate(CODEC_ZLIB), CODEC_ZLIB)
        self.assertEqual(compression.negotiate(CODEC_NONE), CODEC_NONE)
        if not compression.HAVE_BROTLI:
            self.assertEqual(compression.negotiate(CODEC_BROTLI), CODEC_ZLIB)
        self.assertEqual(compression.negotiate(99), CODEC_ZLIB)

    def test_zlib_actually_compresses(self):
        comp = compression.make_compressor(CODEC_ZLIB)
        data = b"A" * 8192
        block = comp.compress(data)
        self.assertLess(len(block), len(data) // 4)


class ProtocolTests(unittest.TestCase):
    def test_client_hello_roundtrip(self):
        h = ClientHello(codec=CODEC_ZLIB, dc_index=3, flags=1)
        self.assertEqual(ClientHello.decode(h.encode()), h)

    def test_forbidden_dc(self):
        h = ClientHello(codec=CODEC_ZLIB, dc_index=9)
        with self.assertRaises(ProtocolError):
            ClientHello.decode(h.encode())

    def test_bad_magic(self):
        with self.assertRaises(ProtocolError):
            ClientHello.decode(b"XX" + b"\x00" * 6)

    def test_ack_roundtrip(self):
        a = ServerAck(codec=CODEC_ZLIB, status=STATUS_OK)
        self.assertEqual(ServerAck.decode(a.encode()), a)


class LinkTests(unittest.TestCase):
    def test_secret_key_roundtrip(self):
        s = generate_secret()
        self.assertEqual(key_to_secret(secret_to_key(s)), s)
        self.assertEqual(key_to_secret(s.hex()), s)

    def test_link_roundtrip(self):
        s = generate_secret()
        link = build_link("example.org", 3183, "music.yandex.ru", s)
        self.assertTrue(link.startswith("derenguh://proxy?"))
        parsed = parse_link(link)
        self.assertEqual(parsed["server"], "example.org")
        self.assertEqual(parsed["port"], 3183)
        self.assertEqual(parsed["sni"], "music.yandex.ru")
        self.assertEqual(parsed["secret"], s)

    def test_bad_key(self):
        with self.assertRaises(ValueError):
            key_to_secret("not-a-valid-key!!")


class FakeTLSTests(unittest.TestCase):
    def setUp(self):
        self.secret = generate_secret()

    def test_client_hello_authenticates(self):
        for sni in ("music.yandex.ru", "vk.com", "rutube.ru", "yandex.ru",
                    "dzen.ru", "vkvideo.ru"):
            ch = build_client_hello(self.secret, sni)
            self.assertTrue(verify_client_hello(ch, self.secret), sni)
            self.assertEqual(extract_sni(ch), sni)
            self.assertGreaterEqual(len(ch) - 5, 512)  # realistic handshake size

    def test_wrong_secret_fails(self):
        ch = build_client_hello(self.secret, "vk.com")
        self.assertFalse(verify_client_hello(ch, generate_secret()))

    def test_server_hello_authenticates(self):
        ch = build_client_hello(self.secret, "dzen.ru")
        sess_id = ch[44:44 + ch[43]]
        hello = build_server_hello(self.secret, client_digest(ch), sess_id)
        self.assertTrue(verify_server_hello(hello, self.secret, client_digest(ch)))
        self.assertFalse(verify_server_hello(hello, generate_secret(), client_digest(ch)))

    def test_sni_parser_defensive(self):
        self.assertIsNone(extract_sni(b""))
        self.assertIsNone(extract_sni(b"\x16\x03\x01\x00\x00"))
        self.assertIsNone(extract_sni(b"GET / HTTP/1.1\r\n"))


if __name__ == "__main__":
    unittest.main()
