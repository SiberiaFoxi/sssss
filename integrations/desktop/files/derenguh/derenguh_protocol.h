// DerenguhProto v1 constants and control-frame codec (tdesktop / Qt).
// Must match DerenguhGram-Proxy/docs/PROTOCOL.md byte-for-byte.
// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <QByteArray>
#include <cstdint>
#include <optional>

namespace derenguh {

inline constexpr uint8_t kProtoMagic0 = 0x44; // 'D'
inline constexpr uint8_t kProtoMagic1 = 0x47; // 'G'
inline constexpr uint8_t kProtoVersion = 0x01;
inline constexpr int kControlFrameLen = 8;

enum class Codec : uint8_t { None = 0, Zlib = 1, Brotli = 2 };

enum class Status : uint8_t {
    Ok = 0,
    DcUnreachable = 1,
    UnsupportedCodec = 2,
    ProtoError = 3,
    ForbiddenDc = 4,
};

// Telegram DC indices the proxy is allowed to dial.
inline constexpr int kMinDc = 1;
inline constexpr int kMaxDc = 5;

struct ClientControl {
    Codec codec = Codec::Zlib;
    uint8_t dcIndex = 2;
    uint8_t flags = 0;

    [[nodiscard]] QByteArray encode() const {
        QByteArray out(kControlFrameLen, '\0');
        out[0] = char(kProtoMagic0);
        out[1] = char(kProtoMagic1);
        out[2] = char(kProtoVersion);
        out[3] = char(codec);
        out[4] = char(dcIndex);
        out[5] = char(flags);
        // bytes 6..7 reserved = 0
        return out;
    }
};

struct ServerAck {
    Codec codec = Codec::Zlib;
    Status status = Status::Ok;
    uint8_t flags = 0;

    [[nodiscard]] static std::optional<ServerAck> decode(const QByteArray &data) {
        if (data.size() != kControlFrameLen) return std::nullopt;
        if (uint8_t(data[0]) != kProtoMagic0 || uint8_t(data[1]) != kProtoMagic1)
            return std::nullopt;
        if (uint8_t(data[2]) != kProtoVersion) return std::nullopt;
        ServerAck ack;
        ack.codec = Codec(uint8_t(data[3]));
        ack.status = Status(uint8_t(data[4]));
        ack.flags = uint8_t(data[5]);
        return ack;
    }
};

// Streaming SNI choices offered in the proxy settings UI.
struct SniChoice {
    const char *host;
    const char *label;
};
inline constexpr SniChoice kSniChoices[] = {
    {"music.yandex.ru", "VK Music / Яндекс.Музыка"},
    {"vk.com", "VK Видео"},
    {"rutube.ru", "RuTube"},
    {"yandex.ru", "Яндекс.Видео"},
    {"dzen.ru", "Яндекс.Дзен"},
    {"vkvideo.ru", "VK Видео (vkvideo)"},
};

} // namespace derenguh
