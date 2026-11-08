"""End-to-end tests against a real running Server with a mock DC and mock mask host.

These exercise the full path: Fake-TLS handshake -> control frame -> DC dial ->
bidirectional compressed relay, plus the TCP-splice fallback for unrecognised peers.
No external network is used; the Telegram DC and the streaming host are local mocks.
"""
import asyncio
import unittest

from derenguh_proxy.config import Config
from derenguh_proxy.server import Server
from derenguh_proxy.reference_client import DerenguhClient
from derenguh_proxy.faketls import build_client_hello
from derenguh_proxy.link import generate_secret
from derenguh_proxy.constants import CODEC_ZLIB, CODEC_NONE


async def _echo_handler(reader, writer):
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


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.secret = generate_secret()
        # Mock Telegram DC: echoes whatever obfuscated-2 bytes it receives.
        self.dc = await asyncio.start_server(_echo_handler, "127.0.0.1", 0)
        self.dc_port = self.dc.sockets[0].getsockname()[1]

        self.cfg = Config()
        self.cfg.host = "127.0.0.1"
        self.cfg.port = 0
        self.cfg.secret = self.secret
        self.cfg.idle_timeout = 10.0
        self.cfg.handshake_timeout = 5.0
        self.cfg.connect_timeout = 5.0

        self.server = Server(self.cfg)

        async def dial_dc(dc_index):
            return await asyncio.open_connection("127.0.0.1", self.dc_port)
        self.server.dial_dc = dial_dc

        self.srv = await self.server.start()
        self.port = self.srv.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.srv.close()
        await self.srv.wait_closed()
        self.dc.close()
        await self.dc.wait_closed()

    async def test_echo_small(self):
        client = DerenguhClient("127.0.0.1", self.port, self.secret,
                                "music.yandex.ru", dc_index=2, codec=CODEC_ZLIB)
        await client.connect()
        self.assertEqual(client.codec, CODEC_ZLIB)
        payload = b"\x16\x03\x01\x02\x00" + bytes(range(256)) * 4  # obfuscated-2-ish
        await client.send(payload)
        echo = await asyncio.wait_for(client.recv_exactly(len(payload)), timeout=5)
        self.assertEqual(echo, payload)
        self.assertEqual(self.server.stats["authenticated"], 1)
        client.close()

    async def test_echo_streaming_many_chunks(self):
        client = DerenguhClient("127.0.0.1", self.port, self.secret,
                                "vkvideo.ru", dc_index=4, codec=CODEC_ZLIB)
        await client.connect()
        chunks = [bytes((i * 7 + j) % 256 for j in range(1024)) for i in range(40)]
        expected = b"".join(chunks)
        received = bytearray()

        async def reader():
            while len(received) < len(expected):
                data = await client.recv()
                if not data:
                    break
                received.extend(data)

        rtask = asyncio.ensure_future(reader())
        for c in chunks:
            await client.send(c)
        await asyncio.wait_for(rtask, timeout=8)
        self.assertEqual(bytes(received), expected)
        client.close()

    async def test_codec_none(self):
        client = DerenguhClient("127.0.0.1", self.port, self.secret,
                                "rutube.ru", dc_index=1, codec=CODEC_NONE)
        await client.connect()
        self.assertEqual(client.codec, CODEC_NONE)
        payload = b"no-compression-path" * 100
        await client.send(payload)
        echo = await asyncio.wait_for(client.recv_exactly(len(payload)), timeout=5)
        self.assertEqual(echo, payload)
        client.close()

    async def test_all_sni(self):
        for sni in self.cfg.allowed_sni:
            client = DerenguhClient("127.0.0.1", self.port, self.secret, sni, dc_index=2)
            await client.connect()
            await client.send(b"ping-" + sni.encode())
            echo = await asyncio.wait_for(client.recv_exactly(5 + len(sni)), timeout=5)
            self.assertEqual(echo, b"ping-" + sni.encode())
            client.close()

    async def test_wrong_secret_is_spliced_not_relayed(self):
        # A client with the wrong secret must NOT reach the DC; with mask disabled it
        # is simply dropped (connection closed without an ack).
        self.cfg.mask_enabled = False
        client = DerenguhClient("127.0.0.1", self.port, generate_secret(),
                                "vk.com", dc_index=2)
        with self.assertRaises((ValueError, ConnectionError, asyncio.IncompleteReadError)):
            await asyncio.wait_for(client.connect(), timeout=5)
        self.assertEqual(self.server.stats["authenticated"], 0)
        client.close()


class SpliceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.secret = generate_secret()
        self.marker = b"REAL-STREAMING-TLS-RESPONSE\x16\x03\x03\x00\x05hello"

        async def mask_handler(reader, writer):
            try:
                await reader.read(4096)  # consume the replayed ClientHello
                writer.write(self.marker)
                await writer.drain()
            except Exception:
                pass
            finally:
                try:
                    writer.close()
                except Exception:
                    pass

        self.mask = await asyncio.start_server(mask_handler, "127.0.0.1", 0)
        self.mask_port = self.mask.sockets[0].getsockname()[1]

        self.cfg = Config()
        self.cfg.host = "127.0.0.1"
        self.cfg.port = 0
        self.cfg.secret = self.secret
        self.cfg.mask_enabled = True
        self.cfg.mask_use_sni_host = False
        self.cfg.mask_host = "127.0.0.1"
        self.cfg.mask_port = self.mask_port
        self.cfg.idle_timeout = 5.0
        self.cfg.connect_timeout = 5.0

        self.server = Server(self.cfg)
        self.srv = await self.server.start()
        self.port = self.srv.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.srv.close()
        await self.srv.wait_closed()
        self.mask.close()
        await self.mask.wait_closed()

    async def test_non_tls_probe_is_spliced(self):
        # A plain HTTP probe must not block the server; it is spliced to the mask host.
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(b"GET / HTTP/1.1\r\nHost: music.yandex.ru\r\n\r\n")
        await writer.drain()
        got = await asyncio.wait_for(reader.readexactly(len(self.marker)), timeout=5)
        self.assertEqual(got, self.marker)
        self.assertEqual(self.server.stats["spliced"], 1)
        writer.close()

    async def test_scanner_gets_real_host_response(self):
        # A DPI scanner sends a ClientHello with the wrong secret. The proxy must
        # splice it to the real streaming host, which returns its genuine response.
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        scanner_hello = build_client_hello(generate_secret(), "music.yandex.ru")
        writer.write(scanner_hello)
        await writer.drain()
        got = await asyncio.wait_for(reader.readexactly(len(self.marker)), timeout=5)
        self.assertEqual(got, self.marker)
        self.assertEqual(self.server.stats["spliced"], 1)
        self.assertEqual(self.server.stats["authenticated"], 0)
        writer.close()


if __name__ == "__main__":
    unittest.main()
