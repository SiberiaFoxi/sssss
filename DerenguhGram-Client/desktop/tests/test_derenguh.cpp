// Interop tests for the DerenguhGram desktop module against shared/test_vectors.json.
// Build inside the tdesktop environment (Qt6 + OpenSSL + zlib). SPDX: GPL-3.0-only
//
// Run (after linking derenguh_desktop): the binary exits 0 on success, 1 on failure.
#include "derenguh_protocol.h"
#include "derenguh_compression.h"
#include "derenguh_faketls.h"

#include <QCoreApplication>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QByteArray>
#include <openssl/hmac.h>
#include <openssl/evp.h>
#include <cstdio>

static int failures = 0;
#define CHECK(cond, msg) do { if (!(cond)) { std::printf("FAIL: %s\n", msg); ++failures; } \
    else { std::printf("ok: %s\n", msg); } } while (0)

static QByteArray b64(const QJsonValue &v) {
    return QByteArray::fromBase64(v.toString().toUtf8());
}

// Mirror of the server's verify_client_hello, to validate the C++ ClientHello builder.
static bool verifyClientHello(const QByteArray &record, const QByteArray &secret) {
    if (record.size() < 43) return false;
    QByteArray msg = record;
    std::memset(msg.data() + 11, 0, 32);
    unsigned char out[EVP_MAX_MD_SIZE]; unsigned int len = 0;
    HMAC(EVP_sha256(), secret.constData(), secret.size(),
         reinterpret_cast<const unsigned char*>(msg.constData()), size_t(msg.size()), out, &len);
    QByteArray digest = record.mid(11, 32);
    for (int i = 0; i < 28; ++i)
        if (uint8_t(digest[i] ^ out[i]) != 0) return false;
    return true; // (timestamp skew ignored for the interop check)
}

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    QFile f(QCoreApplication::applicationDirPath() + "/../../shared/test_vectors.json");
    if (!f.open(QIODevice::ReadOnly)) { std::printf("cannot open test_vectors.json\n"); return 1; }
    const auto doc = QJsonDocument::fromJson(f.readAll()).object();
    const QByteArray secret = QByteArray::fromHex(doc["secret_hex"].toString().toUtf8());

    // 1) Control frames match the wire bytes.
    for (const auto &v : doc["control_frames"].toArray()) {
        const auto o = v.toObject();
        derenguh::ClientControl c;
        c.codec = derenguh::Codec(o["codec"].toInt());
        c.dcIndex = uint8_t(o["dc_index"].toInt());
        CHECK(c.encode() == b64(o["b64"]), "control frame encode");
    }

    // 2) Server ack decodes.
    const auto ack = derenguh::ServerAck::decode(b64(doc["server_ack_ok_zlib"]));
    CHECK(ack && ack->status == derenguh::Status::Ok
          && ack->codec == derenguh::Codec::Zlib, "server ack decode");

    // 3) zlib interop: decode the Python-produced block.
    const auto zv = doc["zlib_decompress_vector"].toObject();
    derenguh::ZlibDecoder dec;
    CHECK(dec.decompress(b64(zv["block_b64"])) == b64(zv["plain_b64"]), "zlib decode interop");

    // 4) ClientHello builder authenticates against the shared secret.
    const QByteArray hello = derenguh::buildClientHello(secret, "music.yandex.ru");
    CHECK(hello.size() - 5 >= 512, "client hello size >= 512");
    CHECK(verifyClientHello(hello, secret), "client hello HMAC authenticates");

    // 5) Record framing round-trips.
    const QByteArray payload = QByteArray(40000, 'x');
    const QByteArray framed = derenguh::wrapRecord(payload);
    int off = 0, got = 0; QByteArray reassembled;
    while (off < framed.size()) {
        const auto r = derenguh::parseRecord(framed, off);
        if (!r.valid || !r.complete) break;
        reassembled.append(r.payload); off += r.consumed; ++got;
    }
    CHECK(reassembled == payload && got == 3, "record framing round-trip (3 records)");

    std::printf(failures ? "\n%d FAILURES\n" : "\nALL PASSED\n", failures);
    return failures ? 1 : 0;
}
