// Local SOCKS5 -> DerenguhProto bridge (Android). SPDX: GPL-3.0-only
//
// Lets Telegram use the DerenguhGram-Proxy WITHOUT patching the native tgnet layer:
// the app starts this bridge on 127.0.0.1:<port> and configures Telegram's built-in
// SOCKS5 proxy to point at it. Telegram CONNECTs to a Telegram DC IP; the bridge maps
// that IP to a DC index, opens a DerenguhTunnel, and relays the obfuscated-2 stream.
//
// A true "DerenguhGram Proxy" entry in the proxy-type list is a UI wrapper around this
// bridge (see docs/BUILD_ANDROID.md). A native proxy-type patch is also documented.
package org.derenguhgram.proxy

import java.io.DataInputStream
import java.io.OutputStream
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.Executors
import kotlin.concurrent.thread

class DerenguhLocalBridge(private val config: DerenguhProxyConfig) {
    private var server: ServerSocket? = null
    private val pool = Executors.newCachedThreadPool()
    @Volatile private var running = false
    var localPort: Int = 0
        private set

    /** Bind to an ephemeral loopback port; returns the port to feed Telegram's SOCKS5. */
    fun start(): Int {
        val s = ServerSocket()
        s.bind(InetSocketAddress(InetAddress.getByName("127.0.0.1"), 0))
        server = s
        localPort = s.localPort
        running = true
        thread(name = "derenguh-bridge-accept") { acceptLoop(s) }
        return localPort
    }

    fun stop() {
        running = false
        runCatching { server?.close() }
        pool.shutdownNow()
    }

    private fun acceptLoop(s: ServerSocket) {
        while (running) {
            val client = try { s.accept() } catch (e: Exception) { break }
            pool.execute { runCatching { handle(client) } }
        }
    }

    private fun handle(client: Socket) {
        client.tcpNoDelay = true
        val input = DataInputStream(client.getInputStream().buffered())
        val output = client.getOutputStream().buffered()

        // --- SOCKS5 greeting ---
        val ver = input.readUnsignedByte()
        require(ver == 5) { "only SOCKS5 supported" }
        val nMethods = input.readUnsignedByte()
        input.readFully(ByteArray(nMethods))
        output.write(byteArrayOf(5, 0)) // no auth
        output.flush()

        // --- SOCKS5 request ---
        val hdr = ByteArray(4).also { input.readFully(it) }
        require(hdr[1] == 1.toByte()) { "only CONNECT supported" }
        val host = when (hdr[3].toInt() and 0xff) {
            1 -> ByteArray(4).also { input.readFully(it) }.joinToString(".") { (it.toInt() and 0xff).toString() }
            3 -> { val n = input.readUnsignedByte(); String(ByteArray(n).also { input.readFully(it) }) }
            4 -> ByteArray(16).also { input.readFully(it) }.let { InetAddress.getByAddress(it).hostAddress ?: "" }
            else -> error("bad address type")
        }
        val portBytes = ByteArray(2).also { input.readFully(it) }
        val dcIndex = TelegramDcMap.dcForHost(host)

        val tunnel = DerenguhTunnel(config.host, config.port, config.secret, config.sni,
            dcIndex, config.codec)
        try {
            tunnel.connect()
        } catch (e: Exception) {
            // SOCKS5 failure reply.
            output.write(byteArrayOf(5, 1, 0, 1, 0, 0, 0, 0, 0, 0))
            output.flush()
            client.close()
            return
        }

        // SOCKS5 success reply (BND.ADDR=0.0.0.0, BND.PORT=0).
        output.write(byteArrayOf(5, 0, 0, 1, 0, 0, 0, 0, 0, 0))
        output.flush()

        // Relay: Telegram -> tunnel, tunnel -> Telegram.
        val up = thread(name = "derenguh-up") {
            val buf = ByteArray(8192)
            try {
                while (true) {
                    val n = input.read(buf)
                    if (n < 0) break
                    tunnel.send(buf.copyOf(n))
                }
            } catch (_: Exception) {}
            runCatching { tunnel.close() }
            runCatching { client.close() }
        }
        try {
            while (true) {
                val data = tunnel.recv() ?: break
                if (data.isNotEmpty()) { output.write(data); output.flush() }
            }
        } catch (_: Exception) {}
        runCatching { tunnel.close() }
        runCatching { client.close() }
        runCatching { up.join(500) }
    }
}
