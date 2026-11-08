// Local SOCKS5 -> DerenguhProto bridge (Android). SPDX: GPL-3.0-only
package org.derenguhgram.proxy

import java.io.DataInputStream
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import java.util.concurrent.Semaphore
import kotlin.concurrent.thread

class DerenguhLocalBridge(private val config: DerenguhProxyConfig) {
    private var server: ServerSocket? = null
    private val pool = Executors.newFixedThreadPool(16) { r -> Thread(r, "derenguh-conn").apply { isDaemon = true } }
    private val slots = Semaphore(32)
    private val clients = ConcurrentHashMap.newKeySet<Socket>()
    @Volatile private var running = false
    var localPort: Int = 0; private set
    val isRunning: Boolean get() = running
    val port: Int get() = localPort

    fun start(): Int {
        val s = ServerSocket()
        s.bind(InetSocketAddress(InetAddress.getByName("127.0.0.1"), 0))
        server = s; localPort = s.localPort; running = true
        thread(name = "derenguh-bridge-accept", isDaemon = true) { acceptLoop(s) }
        return localPort
    }

    fun stop() {
        running = false
        runCatching { server?.close() }
        clients.forEach { runCatching { it.close() } }
        clients.clear(); pool.shutdownNow()
    }

    private fun acceptLoop(s: ServerSocket) {
        while (running) {
            val client = try { s.accept() } catch (e: Exception) { break }
            if (!slots.tryAcquire()) { runCatching { client.close() }; continue }
            clients.add(client)
            try {
                pool.execute {
                    try { handle(client) } catch (_: Exception) {}
                    finally { clients.remove(client); runCatching { client.close() }; slots.release() }
                }
            } catch (_: Exception) { clients.remove(client); runCatching { client.close() }; slots.release() }
        }
        running = false
    }

    private fun handle(client: Socket) {
        client.tcpNoDelay = true; client.soTimeout = 15000
        val input = DataInputStream(client.getInputStream().buffered())
        val output = client.getOutputStream().buffered()
        val ver = input.readUnsignedByte(); require(ver == 5)
        val nMethods = input.readUnsignedByte(); require(nMethods in 1..255)
        input.readFully(ByteArray(nMethods))
        output.write(byteArrayOf(5, 0)); output.flush()
        val hdr = ByteArray(4).also { input.readFully(it) }
        require(hdr[1] == 1.toByte())
        val host = when (hdr[3].toInt() and 0xff) {
            1 -> ByteArray(4).also { input.readFully(it) }.joinToString(".") { (it.toInt() and 0xff).toString() }
            3 -> { val n = input.readUnsignedByte(); String(ByteArray(n).also { input.readFully(it) }, Charsets.US_ASCII) }
            4 -> ByteArray(16).also { input.readFully(it) }.let { InetAddress.getByAddress(it).hostAddress ?: "" }
            else -> error("bad address type")
        }
        input.readFully(ByteArray(2))
        val dcIndex = TelegramDcMap.dcForHost(host)
        if (dcIndex == null) { output.write(byteArrayOf(5, 1, 0, 1, 0, 0, 0, 0, 0, 0)); output.flush(); return }
        val tunnel = DerenguhTunnel(config.host, config.port, config.secret, config.sni, dcIndex, config.codec)
        try { tunnel.connect() } catch (e: Exception) {
            runCatching { output.write(byteArrayOf(5, 1, 0, 1, 0, 0, 0, 0, 0, 0)); output.flush() }
            runCatching { tunnel.close() }; return
        }
        client.soTimeout = 0
        output.write(byteArrayOf(5, 0, 0, 1, 0, 0, 0, 0, 0, 0)); output.flush()
        val up = thread(name = "derenguh-up", isDaemon = true) {
            val buf = ByteArray(8192)
            try { while (true) { val n = input.read(buf); if (n < 0) break; if (n > 0) tunnel.send(buf.copyOf(n)) } } catch (_: Exception) {}
            runCatching { tunnel.close() }; runCatching { client.close() }
        }
        try { while (true) { val data = tunnel.recv() ?: break; if (data.isNotEmpty()) { output.write(data); output.flush() } } } catch (_: Exception) {}
        runCatching { tunnel.close() }; runCatching { client.close() }; runCatching { up.join(500) }
    }
}
