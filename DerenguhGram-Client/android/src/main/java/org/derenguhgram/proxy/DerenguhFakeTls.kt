// Fake-TLS 1.3 client handshake (Android). javax.crypto.Mac + SecureRandom.
// SPDX: GPL-3.0-only
package org.derenguhgram.proxy

import java.security.SecureRandom
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

object DerenguhFakeTls {
    private const val DIGEST_POS = 11
    private const val DIGEST_LEN = 32
    private const val MAX_RECORD_PAYLOAD = 16384 + 24
    private val rng = SecureRandom()

    private fun hmac(secret: ByteArray, msg: ByteArray): ByteArray {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(secret, "HmacSHA256"))
        return mac.doFinal(msg)
    }

    private fun random(n: Int) = ByteArray(n).also { rng.nextBytes(it) }

    private fun u16(v: Int) = byteArrayOf((v ushr 8).toByte(), v.toByte())

    private fun ext(type: Int, payload: ByteArray): ByteArray =
        u16(type) + u16(payload.size) + payload

    private fun serverNameExt(sni: String): ByteArray {
        val host = sni.toByteArray(Charsets.US_ASCII)
        val name = byteArrayOf(0) + u16(host.size) + host
        return ext(0x0000, u16(name.size) + name)
    }

    /** Build a ClientHello record with SNI + HMAC digest in the random field. */
    fun buildClientHello(secret: ByteArray, sni: String): ByteArray {
        val sessionId = random(32)
        val cipherSuites = hex("130113021303c02bc02fc02cc03000ff")
        val compression = hex("00")

        var exts = serverNameExt(sni)
        exts += ext(0x002b, hex("020304"))
        exts += ext(0x000a, hex("0006001d00170018"))
        exts += ext(0x0033, hex("0024001d0020") + random(32))
        exts += ext(0x000d, hex("00080403050306030804"))
        exts += ext(0x000b, hex("0100"))
        exts += ext(0x0010, hex("000c02683208") + "http/1.1".toByteArray(Charsets.US_ASCII))
        exts += ext(0x002d, hex("0101"))
        exts += ext(0x0023, ByteArray(0))

        fun assemble(extra: ByteArray): ByteArray {
            val allExts = exts + extra
            var body = hex("0303") + ByteArray(DIGEST_LEN)
            body += byteArrayOf(sessionId.size.toByte()) + sessionId
            body += u16(cipherSuites.size) + cipherSuites
            body += byteArrayOf(compression.size.toByte()) + compression
            body += u16(allExts.size) + allExts
            val hs = byteArrayOf(0x01, (body.size ushr 16).toByte(),
                (body.size ushr 8).toByte(), body.size.toByte()) + body
            return hex("160301") + u16(hs.size) + hs
        }

        var record = assemble(ByteArray(0))
        if (record.size - 5 < 512) {
            val pad = 512 - (record.size - 5) - 4
            if (pad > 0) record = assemble(ext(0x0015, ByteArray(pad)))
        }

        val msg = record.copyOf().also { it.fill(0, DIGEST_POS, DIGEST_POS + DIGEST_LEN) }
        val h = hmac(secret, msg)
        val ts = (System.currentTimeMillis() / 1000).toInt()
        val digest = h.copyOfRange(0, DIGEST_LEN - 4)
        val tail = ByteArray(4) { i ->
            (h[DIGEST_LEN - 4 + i].toInt() xor ((ts ushr (8 * i)) and 0xff)).toByte()
        }
        val full = digest + tail
        System.arraycopy(full, 0, record, DIGEST_POS, DIGEST_LEN)
        return record
    }

    fun clientDigest(record: ByteArray): ByteArray =
        record.copyOfRange(DIGEST_POS, DIGEST_POS + DIGEST_LEN)

    fun verifyServerHello(helloPacket: ByteArray, secret: ByteArray, cliDigest: ByteArray): Boolean {
        if (helloPacket.size < DIGEST_POS + DIGEST_LEN) return false
        val digest = helloPacket.copyOfRange(DIGEST_POS, DIGEST_POS + DIGEST_LEN)
        val zeroed = helloPacket.copyOf().also { it.fill(0, DIGEST_POS, DIGEST_POS + DIGEST_LEN) }
        val computed = hmac(secret, cliDigest + zeroed)
        return computed.contentEquals(digest)
    }

    fun wrapRecord(payload: ByteArray): ByteArray {
        val out = java.io.ByteArrayOutputStream(payload.size + 16)
        var start = 0
        while (start < payload.size) {
            val end = minOf(start + MAX_RECORD_PAYLOAD, payload.size)
            out.write(hex("170303"))
            out.write(u16(end - start))
            out.write(payload, start, end - start)
            start = end
        }
        return out.toByteArray()
    }

    private fun hex(s: String): ByteArray =
        ByteArray(s.length / 2) { s.substring(it * 2, it * 2 + 2).toInt(16).toByte() }
}
