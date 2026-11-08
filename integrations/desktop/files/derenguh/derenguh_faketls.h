// Fake-TLS 1.3 client handshake for DerenguhProto (tdesktop).
// Uses OpenSSL (bundled with tdesktop) for HMAC-SHA256 and RAND_bytes.
// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <QByteArray>

namespace derenguh {

// Build a TLS ClientHello record with the chosen SNI and the HMAC digest embedded
// in the 32-byte random field. `secret` is the 16-byte shared key.
[[nodiscard]] QByteArray buildClientHello(const QByteArray &secret,
                                          const QByteArray &sni);

// The 32-byte digest (random field) of a ClientHello record, needed to verify the
// server's response.
[[nodiscard]] QByteArray clientDigest(const QByteArray &clientHelloRecord);

// Verify the concatenated ServerHello + CCS + fake-cert bytes against the secret.
[[nodiscard]] bool verifyServerHello(const QByteArray &helloPacket,
                                     const QByteArray &secret,
                                     const QByteArray &clientDigest);

// TLS application_data record framing.
[[nodiscard]] QByteArray wrapRecord(const QByteArray &payload);

// Parse one application_data record from `buffer` starting at `offset`.
// Returns the payload and advances `offset`; returns empty + false on need-more-data.
struct RecordParseResult {
    QByteArray payload;
    bool complete = false;
    bool valid = true;
    int consumed = 0;
};
[[nodiscard]] RecordParseResult parseRecord(const QByteArray &buffer, int offset);

} // namespace derenguh
