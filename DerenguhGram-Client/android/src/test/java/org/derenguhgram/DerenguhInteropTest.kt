// Interop tests against shared/test_vectors.json (Android unit test, JUnit).
// SPDX: GPL-3.0-only
//
// Copy shared/test_vectors.json into app test resources, or load via a relative path
// in a plain JVM test. Here we use android.util.Base64-free java.util.Base64 so it can
// run as a local unit test.
package org.derenguhgram

import org.derenguhgram.proxy.ClientControl
import org.derenguhgram.proxy.ServerAck
import org.derenguhgram.proxy.DerenguhProto
import org.derenguhgram.proxy.DerenguhFakeTls
import org.derenguhgram.proxy.ZlibDecoder
import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.util.Base64
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

class DerenguhInteropTest {
    private val vectors by lazy {
        // Adjust the path to where test_vectors.json lives in your fork's test setup.
        val text = File("../shared/test_vectors.json").readText()
        // Minimal JSON access without extra deps: use org.json (available on Android/JVM test).
        org.json.JSONObject(text)
    }

    private fun b64(s: String) = Base64.getDecoder().decode(s)

    @Test fun controlFramesMatch() {
        val arr = vectors.getJSONArray("control_frames")
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            val enc = ClientControl(o.getInt("codec"), o.getInt("dc_index")).encode()
            assertArrayEquals(b64(o.getString("b64")), enc)
        }
    }

    @Test fun serverAckDecodes() {
        val ack = ServerAck.decode(b64(vectors.getString("server_ack_ok_zlib")))
        assertNotNull(ack)
        assertEquals(DerenguhProto.STATUS_OK, ack!!.status)
        assertEquals(DerenguhProto.CODEC_ZLIB, ack.codec)
    }

    @Test fun zlibDecodeInterop() {
        val zv = vectors.getJSONObject("zlib_decompress_vector")
        val dec = ZlibDecoder()
        val out = dec.decompress(b64(zv.getString("block_b64")))
        dec.close()
        assertArrayEquals(b64(zv.getString("plain_b64")), out)
    }

    @Test fun clientHelloAuthenticates() {
        val secret = hexToBytes(vectors.getString("secret_hex"))
        val record = DerenguhFakeTls.buildClientHello(secret, "music.yandex.ru")
        assertTrue(record.size - 5 >= 512)
        // Mirror server verify: zero random, HMAC, first 28 bytes of XOR must be zero.
        val msg = record.copyOf().also { it.fill(0, 11, 43) }
        val mac = Mac.getInstance("HmacSHA256").apply { init(SecretKeySpec(secret, "HmacSHA256")) }
        val h = mac.doFinal(msg)
        for (i in 0 until 28) assertEquals(0, (record[11 + i].toInt() xor h[i].toInt()) and 0xff)
    }

    private fun hexToBytes(s: String) =
        ByteArray(s.length / 2) { s.substring(it * 2, it * 2 + 2).toInt(16).toByte() }
}
