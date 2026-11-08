// Streaming zlib codec for DerenguhProto (tdesktop). Uses zlib bundled with tdesktop.
// A single persistent deflate/inflate stream per direction; Z_SYNC_FLUSH per block.
// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <QByteArray>
#include <memory>
#include "derenguh_protocol.h"

namespace derenguh {

// Opaque wrappers so the header does not pull in <zlib.h>.
class ZlibEncoder {
public:
    explicit ZlibEncoder(int level = 6);
    ~ZlibEncoder();
    ZlibEncoder(const ZlibEncoder &) = delete;
    ZlibEncoder &operator=(const ZlibEncoder &) = delete;

    // Returns a sync-flushed block ready to be wrapped in a TLS record.
    [[nodiscard]] QByteArray compress(const QByteArray &data);

private:
    struct Impl;
    std::unique_ptr<Impl> _impl;
};

class ZlibDecoder {
public:
    ZlibDecoder();
    ~ZlibDecoder();
    ZlibDecoder(const ZlibDecoder &) = delete;
    ZlibDecoder &operator=(const ZlibDecoder &) = delete;

    // Feed one received block; returns decoded bytes (may be empty).
    [[nodiscard]] QByteArray decompress(const QByteArray &block);

private:
    struct Impl;
    std::unique_ptr<Impl> _impl;
};

} // namespace derenguh
