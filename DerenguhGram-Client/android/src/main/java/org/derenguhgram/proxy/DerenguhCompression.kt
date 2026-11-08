// Streaming zlib codec (Android). java.util.zip.Deflater/Inflater with SYNC_FLUSH.
// SPDX: GPL-3.0-only
package org.derenguhgram.proxy

import java.util.zip.Deflater
import java.util.zip.Inflater

/**
 * One persistent deflate stream. Deflater defaults to a 15-bit window; the server's
 * inflater (MAX_WBITS) accepts it, and our inflater accepts the server's 12-bit
 * window stream from the zlib header. SYNC_FLUSH makes each block decodable.
 */
class ZlibEncoder(level: Int = 6) {
    private val deflater = Deflater(level) // nowrap=false -> zlib header
    private val buf = ByteArray(16384)

    fun compress(data: ByteArray): ByteArray {
        deflater.setInput(data)
        val out = java.io.ByteArrayOutputStream(data.size / 2 + 64)
        // SYNC_FLUSH emits a decodable boundary; drain until a partial buffer means
        // the flush is complete (a full buffer implies more output may be pending).
        var n: Int
        do {
            n = deflater.deflate(buf, 0, buf.size, Deflater.SYNC_FLUSH)
            if (n > 0) out.write(buf, 0, n)
        } while (n == buf.size)
        return out.toByteArray()
    }

    fun close() = deflater.end()
}

class ZlibDecoder {
    private val inflater = Inflater() // nowrap=false, MAX_WBITS
    private val buf = ByteArray(16384)

    fun decompress(block: ByteArray): ByteArray {
        inflater.setInput(block)
        val out = java.io.ByteArrayOutputStream(block.size * 2 + 64)
        while (true) {
            val n = try {
                inflater.inflate(buf)
            } catch (e: java.util.zip.DataFormatException) {
                throw IllegalStateException("bad zlib block", e)
            }
            if (n > 0) out.write(buf, 0, n)
            if (n == 0) break
        }
        return out.toByteArray()
    }

    fun close() = inflater.end()
}
