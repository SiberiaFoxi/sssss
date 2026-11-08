// Proxy config + derenguh:// link parser (Android). SPDX: GPL-3.0-only
package org.derenguhgram.proxy

import android.util.Base64
import java.net.URLDecoder

data class DerenguhProxyConfig(
    val host: String,
    val port: Int,
    val secret: ByteArray,
    val sni: String,
    val codec: Int = DerenguhProto.CODEC_ZLIB,
) {
    companion object {
        /** Parse derenguh://proxy?server=..&port=..&sni=..&key=.. (base64url key). */
        fun fromLink(link: String): DerenguhProxyConfig {
            require(link.startsWith("derenguh://proxy?")) { "not a derenguh://proxy link" }
            val query = link.substringAfter("?")
            val params = query.split("&").associate {
                val k = it.substringBefore("=")
                val v = URLDecoder.decode(it.substringAfter("=", ""), "UTF-8")
                k to v
            }
            val host = params["server"] ?: error("missing server")
            val port = params["port"]?.toInt() ?: error("missing port")
            val sni = params["sni"] ?: error("missing sni")
            val key = params["key"] ?: error("missing key")
            val secret = Base64.decode(key, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)
            require(secret.size == 16) { "key must decode to 16 bytes" }
            return DerenguhProxyConfig(host, port, secret, sni)
        }
    }
}

/** Telegram DC endpoints (regular/media/test) -> DC index. Unknown/CDN fails closed. */
object TelegramDcMap {
    private val map = mapOf(
        "149.154.175.50" to 1, "2001:b28:f23d:f001::a" to 1,
        "149.154.175.10" to 1, "2001:b28:f23d:f001::e" to 1,
        "149.154.167.51" to 2, "95.161.76.100" to 2, "2001:67c:4e8:f002::a" to 2, "2001:67c:04e8:f002::a" to 2,
        "149.154.167.40" to 2, "2001:67c:4e8:f002::e" to 2, "149.154.167.151" to 2,
        "149.154.175.100" to 3, "2001:b28:f23d:f003::a" to 3,
        "149.154.175.117" to 3, "2001:b28:f23d:f003::e" to 3,
        "149.154.167.91" to 4, "2001:67c:4e8:f004::a" to 4, "2001:67c:04e8:f004::a" to 4, "149.154.167.250" to 4,
        "149.154.171.5" to 5, "2001:b28:f23f:f005::a" to 5, "149.154.171.251" to 5,
    )
    fun dcForHost(host: String): Int? = map[host.lowercase().trim('.')]
}
