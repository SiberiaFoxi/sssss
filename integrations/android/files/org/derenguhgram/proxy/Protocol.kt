// DerenguhProto v1 constants + control frames (Android / Kotlin).
// Must match DerenguhGram-Proxy/docs/PROTOCOL.md. SPDX: GPL-3.0-only
package org.derenguhgram.proxy

object DerenguhProto {
    const val MAGIC0: Byte = 0x44 // 'D'
    const val MAGIC1: Byte = 0x47 // 'G'
    const val VERSION: Byte = 0x01
    const val CONTROL_FRAME_LEN = 8

    const val CODEC_NONE = 0
    const val CODEC_ZLIB = 1
    const val CODEC_BROTLI = 2

    const val STATUS_OK = 0
    const val STATUS_DC_UNREACHABLE = 1
    const val STATUS_UNSUPPORTED_CODEC = 2
    const val STATUS_PROTO_ERROR = 3
    const val STATUS_FORBIDDEN_DC = 4

    val VALID_DC = 1..5

    val SNI_CHOICES = listOf(
        "music.yandex.ru" to "Яндекс.Музыка / VK Music",
        "vk.com" to "VK Видео",
        "rutube.ru" to "RuTube",
        "yandex.ru" to "Яндекс.Видео",
        "dzen.ru" to "Яндекс.Дзен",
        "vkvideo.ru" to "VK Видео (vkvideo)",
    )
}

data class ClientControl(val codec: Int, val dcIndex: Int, val flags: Int = 0) {
    fun encode(): ByteArray {
        require(dcIndex in DerenguhProto.VALID_DC) { "forbidden DC $dcIndex" }
        return byteArrayOf(
            DerenguhProto.MAGIC0, DerenguhProto.MAGIC1, DerenguhProto.VERSION,
            codec.toByte(), dcIndex.toByte(), flags.toByte(), 0, 0,
        )
    }
}

data class ServerAck(val codec: Int, val status: Int, val flags: Int) {
    companion object {
        fun decode(data: ByteArray): ServerAck? {
            if (data.size != DerenguhProto.CONTROL_FRAME_LEN) return null
            if (data[0] != DerenguhProto.MAGIC0 || data[1] != DerenguhProto.MAGIC1) return null
            if (data[2] != DerenguhProto.VERSION) return null
            return ServerAck(
                codec = data[3].toInt() and 0xff,
                status = data[4].toInt() and 0xff,
                flags = data[5].toInt() and 0xff,
            )
        }
    }
}
