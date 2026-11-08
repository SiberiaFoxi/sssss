// Core DerenguhProto client tunnel over a blocking java.net.Socket (Android).
// Runs on a background thread. SPDX: GPL-3.0-only
package org.derenguhgram.proxy

import java.io.DataInputStream
import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.Socket

/**
 * Establishes the Fake-TLS + compression tunnel to a DerenguhGram-Proxy server and
 * carries an opaque obfuscated-2 MTProto stream for [dcIndex].
 *
 * Blocking I/O: call from a worker thread, never the main thread.
 */
class DerenguhTunnel(
    private val host: String,
    private val port: Int,
    private val secret: ByteArray,
    private val sni: String,
    private val dcIndex: Int,
    private val requestedCodec: Int = DerenguhProto.CODEC_ZLIB,
) {
    private lateinit var socket: Socket
    private lateinit var input: DataInputStream
    private lateinit var output: OutputStream
    private var encoder: ZlibEncoder? = null
    private var decoder: ZlibDecoder? = null
    var negotiatedCodec: Int = requestedCodec
        private set

    fun connect(timeoutMs: Int = 10000) {
        socket = Socket()
        socket.connect(InetSocketAddress(host, port), timeoutMs)
        socket.tcpNoDelay = true
        input = DataInputStream(socket.getInputStream().buffered())
        output = socket.getOutputStream().buffered()

        val hello = DerenguhFakeTls.buildClientHello(secret, sni)
        output.write(hello)
        output.flush()

        val helloPacket = readServerHello()
        if (!DerenguhFakeTls.verifyServerHello(helloPacket, secret, DerenguhFakeTls.clientDigest(hello))) {
            close()
            throw IllegalStateException("server Fake-TLS authentication failed")
        }

        val ctrl = ClientControl(requestedCodec, dcIndex).encode()
        output.write(DerenguhFakeTls.wrapRecord(ctrl))
        output.flush()

        val ackBytes = readAppRecord() ?: throw IllegalStateException("closed before ack")
        val ack = ServerAck.decode(ackBytes) ?: throw IllegalStateException("malformed ack")
        if (ack.status != DerenguhProto.STATUS_OK) {
            close()
            throw IllegalStateException("proxy rejected, status=${ack.status}")
        }
        negotiatedCodec = ack.codec
        when (negotiatedCodec) {
            DerenguhProto.CODEC_ZLIB -> { encoder = ZlibEncoder(); decoder = ZlibDecoder() }
            DerenguhProto.CODEC_NONE -> { /* passthrough */ }
            else -> { close(); throw IllegalStateException("unsupported negotiated codec") }
        }
    }

    /** Read ServerHello handshake record + CCS + fake-cert record. */
    private fun readServerHello(): ByteArray {
        val hdr = ByteArray(5).also { input.readFully(it) }
        require(hdr[0] == 0x16.toByte()) { "expected ServerHello" }
        val n1 = ((hdr[3].toInt() and 0xff) shl 8) or (hdr[4].toInt() and 0xff)
        val rec1 = hdr + ByteArray(n1).also { input.readFully(it) }
        val rec2 = ByteArray(6).also { input.readFully(it) } // ChangeCipherSpec
        val hdr3 = ByteArray(5).also { input.readFully(it) }
        val n3 = ((hdr3[3].toInt() and 0xff) shl 8) or (hdr3[4].toInt() and 0xff)
        val rec3 = hdr3 + ByteArray(n3).also { input.readFully(it) }
        return rec1 + rec2 + rec3
    }

    /** Read one application_data record payload, skipping ChangeCipherSpec. */
    private fun readAppRecord(): ByteArray? {
        while (true) {
            val hdr = ByteArray(5)
            try {
                input.readFully(hdr)
            } catch (e: java.io.EOFException) {
                return null
            }
            val type = hdr[0].toInt() and 0xff
            val len = ((hdr[3].toInt() and 0xff) shl 8) or (hdr[4].toInt() and 0xff)
            require(type == 0x14 || type == 0x17) { "bad TLS record type $type" }
            require(len <= 16384 + 512) { "TLS record too large" }
            val payload = ByteArray(len).also { if (len > 0) input.readFully(it) }
            if (type == 0x14) continue
            return payload
        }
    }

    fun send(data: ByteArray) {
        val block = encoder?.compress(data) ?: data
        if (block.isNotEmpty()) {
            output.write(DerenguhFakeTls.wrapRecord(block))
            output.flush()
        }
    }

    /** Returns decoded bytes, or null on clean EOF. */
    fun recv(): ByteArray? {
        val payload = readAppRecord() ?: return null
        return decoder?.decompress(payload) ?: payload
    }

    fun close() {
        encoder?.close(); decoder?.close()
        runCatching { socket.close() }
    }
}
