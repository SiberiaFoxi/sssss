// SPDX-License-Identifier: GPL-3.0-only
#include "derenguh_faketls.h"

#include <openssl/hmac.h>
#include <openssl/rand.h>
#include <openssl/sha.h>
#include <QDateTime>
#include <cstring>

namespace derenguh {

namespace {
constexpr int kDigestPos = 11;
constexpr int kDigestLen = 32;
constexpr int kMaxRecordPayload = 16384 + 24;

QByteArray hmacSha256(const QByteArray &key, const QByteArray &msg) {
    unsigned char out[EVP_MAX_MD_SIZE];
    unsigned int len = 0;
    HMAC(EVP_sha256(),
         key.constData(), key.size(),
         reinterpret_cast<const unsigned char *>(msg.constData()), size_t(msg.size()),
         out, &len);
    return QByteArray(reinterpret_cast<const char *>(out), int(len));
}

QByteArray randomBytes(int n) {
    QByteArray out(n, '\0');
    RAND_bytes(reinterpret_cast<unsigned char *>(out.data()), n);
    return out;
}

void appendU16(QByteArray &b, uint16_t v) {
    b.append(char(v >> 8));
    b.append(char(v & 0xff));
}

QByteArray extension(uint16_t type, const QByteArray &payload) {
    QByteArray e;
    appendU16(e, type);
    appendU16(e, uint16_t(payload.size()));
    e.append(payload);
    return e;
}

QByteArray serverNameExt(const QByteArray &sni) {
    QByteArray name;
    name.append(char(0)); // host_name
    appendU16(name, uint16_t(sni.size()));
    name.append(sni);
    QByteArray list;
    appendU16(list, uint16_t(name.size()));
    list.append(name);
    return extension(0x0000, list);
}
} // namespace

QByteArray buildClientHello(const QByteArray &secret, const QByteArray &sni) {
    const QByteArray sessionId = randomBytes(32);
    const QByteArray cipherSuites = QByteArray::fromHex("130113021303c02bc02fc02cc03000ff");
    const QByteArray compression = QByteArray::fromHex("00");

    QByteArray exts;
    exts.append(serverNameExt(sni));
    exts.append(extension(0x002b, QByteArray::fromHex("020304")));            // supported_versions
    exts.append(extension(0x000a, QByteArray::fromHex("0006001d00170018")));   // supported_groups
    exts.append(extension(0x0033, QByteArray::fromHex("0024001d0020") + randomBytes(32))); // key_share
    exts.append(extension(0x000d, QByteArray::fromHex("00080403050306030804"))); // sig algs
    exts.append(extension(0x000b, QByteArray::fromHex("0100")));
    exts.append(extension(0x0010, QByteArray::fromHex("000c02683208") + QByteArray("http/1.1"))); // ALPN
    exts.append(extension(0x002d, QByteArray::fromHex("0101")));
    exts.append(extension(0x0023, QByteArray()));

    auto assemble = [&](const QByteArray &extra) {
        const QByteArray allExts = exts + extra;
        QByteArray body;
        body.append(QByteArray::fromHex("0303"));        // legacy_version
        body.append(QByteArray(kDigestLen, '\0'));        // random (zeroed for now)
        body.append(char(sessionId.size()));
        body.append(sessionId);
        appendU16(body, uint16_t(cipherSuites.size()));
        body.append(cipherSuites);
        body.append(char(compression.size()));
        body.append(compression);
        appendU16(body, uint16_t(allExts.size()));
        body.append(allExts);

        QByteArray hs;
        hs.append(char(0x01));                            // client_hello
        hs.append(char((body.size() >> 16) & 0xff));
        hs.append(char((body.size() >> 8) & 0xff));
        hs.append(char(body.size() & 0xff));
        hs.append(body);

        QByteArray record;
        record.append(QByteArray::fromHex("160301"));
        appendU16(record, uint16_t(hs.size()));
        record.append(hs);
        return record;
    };

    QByteArray record = assemble(QByteArray());
    if (record.size() - 5 < 512) {
        const int pad = 512 - (record.size() - 5) - 4;
        if (pad > 0) record = assemble(extension(0x0015, QByteArray(pad, '\0')));
    }

    // Embed digest: random[0:28]=H[0:28], random[28:32]=H[28:32] XOR le32(time).
    QByteArray msg = record;
    std::memset(msg.data() + kDigestPos, 0, kDigestLen);
    const QByteArray h = hmacSha256(secret, msg);
    const uint32_t ts = uint32_t(QDateTime::currentSecsSinceEpoch());
    QByteArray digest = h.left(kDigestLen - 4);
    for (int i = 0; i < 4; ++i) {
        digest.append(char(uint8_t(h[kDigestLen - 4 + i]) ^ uint8_t((ts >> (8 * i)) & 0xff)));
    }
    record.replace(kDigestPos, kDigestLen, digest);
    return record;
}

QByteArray clientDigest(const QByteArray &clientHelloRecord) {
    if (clientHelloRecord.size() < kDigestPos + kDigestLen) return {};
    return clientHelloRecord.mid(kDigestPos, kDigestLen);
}

bool verifyServerHello(const QByteArray &helloPacket, const QByteArray &secret,
                       const QByteArray &cliDigest) {
    if (helloPacket.size() < kDigestPos + kDigestLen) return false;
    const QByteArray digest = helloPacket.mid(kDigestPos, kDigestLen);
    QByteArray msg = helloPacket;
    std::memset(msg.data() + kDigestPos, 0, kDigestLen);
    msg.prepend(cliDigest);
    const QByteArray computed = hmacSha256(secret, msg);
    return computed == digest;
}

QByteArray wrapRecord(const QByteArray &payload) {
    QByteArray out;
    for (int start = 0; start < payload.size(); start += kMaxRecordPayload) {
        const QByteArray chunk = payload.mid(start, kMaxRecordPayload);
        out.append(QByteArray::fromHex("170303"));
        appendU16(out, uint16_t(chunk.size()));
        out.append(chunk);
    }
    return out;
}

RecordParseResult parseRecord(const QByteArray &buffer, int offset) {
    RecordParseResult r;
    const int avail = buffer.size() - offset;
    if (avail < 5) return r; // need more
    const uint8_t type = uint8_t(buffer[offset]);
    const uint8_t v1 = uint8_t(buffer[offset + 1]);
    const uint8_t v2 = uint8_t(buffer[offset + 2]);
    const int len = (uint8_t(buffer[offset + 3]) << 8) | uint8_t(buffer[offset + 4]);
    if (v1 != 0x03 || v2 != 0x03 || (type != 0x14 && type != 0x17)) {
        r.valid = false;
        return r;
    }
    if (len > 16384 + 512) {
        r.valid = false;
        return r;
    }
    if (avail < 5 + len) return r; // need more
    r.consumed = 5 + len;
    r.complete = true;
    if (type == 0x17) {
        r.payload = buffer.mid(offset + 5, len);
    } // type 0x14 (CCS) -> complete but empty payload, caller skips
    return r;
}

} // namespace derenguh
