// SPDX-License-Identifier: GPL-3.0-only
#include "derenguh_compression.h"

#include <zlib.h>
#include <vector>

namespace derenguh {

namespace {
// Match the server: 4 KB window (wbits=12), memLevel=5, level=6. The decoder uses
// MAX_WBITS so it also accepts the server's small-window stream and any standard
// zlib stream. Z_SYNC_FLUSH makes every block independently decodable.
constexpr int kWindowBits = 12;
constexpr int kMemLevel = 5;
constexpr int kFlushMode = Z_SYNC_FLUSH;
} // namespace

struct ZlibEncoder::Impl {
    z_stream stream{};
    bool ok = false;
};

ZlibEncoder::ZlibEncoder(int level) : _impl(std::make_unique<Impl>()) {
    _impl->ok = deflateInit2(&_impl->stream, level, Z_DEFLATED,
                             kWindowBits, kMemLevel, Z_DEFAULT_STRATEGY) == Z_OK;
}

ZlibEncoder::~ZlibEncoder() {
    if (_impl->ok) deflateEnd(&_impl->stream);
}

QByteArray ZlibEncoder::compress(const QByteArray &data) {
    QByteArray out;
    if (!_impl->ok) return out;
    auto &s = _impl->stream;
    s.next_in = reinterpret_cast<Bytef *>(const_cast<char *>(data.data()));
    s.avail_in = uInt(data.size());
    std::vector<char> buf(16384);
    do {
        s.next_out = reinterpret_cast<Bytef *>(buf.data());
        s.avail_out = uInt(buf.size());
        const int ret = deflate(&s, kFlushMode);
        if (ret != Z_OK && ret != Z_STREAM_END && ret != Z_BUF_ERROR) break;
        const int produced = int(buf.size()) - int(s.avail_out);
        out.append(buf.data(), produced);
    } while (s.avail_out == 0 || s.avail_in > 0);
    return out;
}

struct ZlibDecoder::Impl {
    z_stream stream{};
    bool ok = false;
};

ZlibDecoder::ZlibDecoder() : _impl(std::make_unique<Impl>()) {
    _impl->ok = inflateInit2(&_impl->stream, MAX_WBITS) == Z_OK;
}

ZlibDecoder::~ZlibDecoder() {
    if (_impl->ok) inflateEnd(&_impl->stream);
}

QByteArray ZlibDecoder::decompress(const QByteArray &block) {
    QByteArray out;
    if (!_impl->ok) return out;
    auto &s = _impl->stream;
    s.next_in = reinterpret_cast<Bytef *>(const_cast<char *>(block.data()));
    s.avail_in = uInt(block.size());
    std::vector<char> buf(16384);
    do {
        s.next_out = reinterpret_cast<Bytef *>(buf.data());
        s.avail_out = uInt(buf.size());
        const int ret = inflate(&s, Z_NO_FLUSH);
        if (ret != Z_OK && ret != Z_STREAM_END && ret != Z_BUF_ERROR) break;
        const int produced = int(buf.size()) - int(s.avail_out);
        out.append(buf.data(), produced);
        if (ret == Z_STREAM_END) break;
    } while (s.avail_out == 0);
    return out;
}

} // namespace derenguh
