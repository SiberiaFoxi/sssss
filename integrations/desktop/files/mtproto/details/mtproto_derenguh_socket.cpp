// SPDX-License-Identifier: GPL-3.0-only
#include "mtproto/details/mtproto_derenguh_socket.h"
#include "derenguh/derenguh_faketls.h"
#include "derenguh/derenguh_protocol.h"
#include "base/invoke_queued.h"
#include <QtCore/QtEndian>
#include <QtCore/QUrl>
#include <cstring>
namespace MTP::details {
namespace {
constexpr int kMaxBuffer = 4 * 1024 * 1024;
int DcFromProtocolId(int16 id) {
    int dc = id < 0 ? -int(id) : int(id);
    if (dc >= 10000) return 0; // test backend not supported by DerenguhProto v1
    return (dc >= 1 && dc <= 5) ? dc : 0;
}
}
DerenguhSocket::DerenguhSocket(not_null<QThread*> thread, const ProxyData &proxy, int16 protocolDcId)
: AbstractSocket(thread), _proxy(proxy), _dcIndex(DcFromProtocolId(protocolDcId)) {
    _secret = QByteArray::fromBase64(proxy.password.toLatin1(), QByteArray::Base64UrlEncoding);
    _socket.moveToThread(thread);
    _socket.setProxy(QNetworkProxy::NoProxy);
    const auto wrap = [&](auto handler) { return [=](auto &&...args) { InvokeQueued(this, [=] { handler(args...); }); }; };
    connect(&_socket, &QTcpSocket::connected, wrap([=] { onTcpConnected(); }));
    connect(&_socket, &QTcpSocket::disconnected, wrap([=] { _disconnected.fire({}); }));
    connect(&_socket, &QTcpSocket::readyRead, wrap([=] { onReadyRead(); }));
    connect(&_socket, &QAbstractSocket::errorOccurred, wrap([=](QAbstractSocket::SocketError e) { onError(e); }));
}
void DerenguhSocket::connectToHost(const QString&, int) {
    if (_dcIndex == 0 || _secret.size() != 16 || _proxy.user.isEmpty()) { fail(); return; }
    _socket.connectToHost(_proxy.host, _proxy.port);
}
void DerenguhSocket::sendRaw(const QByteArray &data) { _socket.write(data); }
void DerenguhSocket::onTcpConnected() {
    _clientHello = derenguh::buildClientHello(_secret, _proxy.user.toUtf8());
    sendRaw(_clientHello);
    _state = State::ServerHello;
}
void DerenguhSocket::onReadyRead() {
    _rx.append(_socket.readAll());
    if (_rx.size() > kMaxBuffer) { fail(); return; }
    processBuffer();
}
void DerenguhSocket::processBuffer() {
    if (_state == State::ServerHello) {
        if (_rx.size() < 5) return;
        if (uint8_t(_rx[0]) != 0x16) { fail(); return; }
        const int n1 = (uint8_t(_rx[3]) << 8) | uint8_t(_rx[4]);
        if (n1 <= 0 || n1 > 16384) { fail(); return; }
        const int need1 = 5 + n1;
        if (_rx.size() < need1 + 6) return;
        const int certOff = need1 + 6;
        if (_rx.size() < certOff + 5) return;
        if (uint8_t(_rx[certOff]) != 0x17) { fail(); return; }
        const int n3 = (uint8_t(_rx[certOff + 3]) << 8) | uint8_t(_rx[certOff + 4]);
        const int total = certOff + 5 + n3;
        if (n3 > 16384 + 2048 || _rx.size() < total) return;
        const QByteArray packet = _rx.left(total);
        _rx.remove(0, total);
        if (!derenguh::verifyServerHello(packet, _secret, derenguh::clientDigest(_clientHello))) { fail(); return; }
        derenguh::ClientControl ctrl; ctrl.codec = derenguh::Codec::Zlib; ctrl.dcIndex = uint8_t(_dcIndex);
        sendRaw(derenguh::wrapRecord(ctrl.encode()));
        _state = State::Ack;
    }
    while (_state == State::Ack || _state == State::Ready) {
        const auto rec = derenguh::parseRecord(_rx, 0);
        if (!rec.valid) { fail(); return; }
        if (!rec.complete) return;
        _rx.remove(0, rec.consumed);
        if (rec.payload.isEmpty()) continue;
        if (_state == State::Ack) {
            const auto ack = derenguh::ServerAck::decode(rec.payload);
            if (!ack || ack->status != derenguh::Status::Ok || ack->codec != derenguh::Codec::Zlib) { fail(); return; }
            _enc = std::make_unique<derenguh::ZlibEncoder>();
            _dec = std::make_unique<derenguh::ZlibDecoder>();
            _state = State::Ready;
            if (!_pending.isEmpty()) { write({}, bytes::make_span(_pending.constData(), _pending.size())); _pending.clear(); }
            _connected.fire({});
        } else {
            const auto plain = _dec->decompress(rec.payload);
            if (!plain.isEmpty()) { _plain.append(plain); _readyRead.fire({}); }
        }
    }
}
void DerenguhSocket::onError(QAbstractSocket::SocketError e) { logError(int(e), _socket.errorString()); fail(); }
void DerenguhSocket::fail() { if (_state != State::Failed) { _state = State::Failed; _socket.abort(); _error.fire({}); } }
bool DerenguhSocket::isGoodStartNonce(bytes::const_span nonce) {
    Expects(nonce.size() >= 8);
    const auto bytes = nonce.data();
    const auto first = qFromUnaligned<uint32>(bytes);
    const auto second = qFromUnaligned<uint32>(bytes + 4);
    const auto zero = gsl::to_integer<uchar>(nonce.front());
    return zero != 0xEF && first != 0x44414548U && first != 0x54534F50U && first != 0x20544547U
        && first != 0xEEEEEEEEU && first != 0xDDDDDDDDU && first != 0x02010316U && second != 0;
}
void DerenguhSocket::timedOut() { fail(); }
bool DerenguhSocket::isConnected() { return _state == State::Ready; }
bool DerenguhSocket::hasBytesAvailable() { return _plainOffset < _plain.size(); }
int64 DerenguhSocket::read(bytes::span buffer) {
    const int avail = _plain.size() - _plainOffset;
    const int n = std::min<int>(int(buffer.size()), avail);
    if (n <= 0) return 0;
    memcpy(buffer.data(), _plain.constData() + _plainOffset, n);
    _plainOffset += n;
    if (_plainOffset == _plain.size()) { _plain.clear(); _plainOffset = 0; }
    return n;
}
void DerenguhSocket::write(bytes::const_span prefix, bytes::const_span buffer) {
    QByteArray data;
    data.reserve(int(prefix.size() + buffer.size()));
    if (!prefix.empty()) data.append(reinterpret_cast<const char*>(prefix.data()), int(prefix.size()));
    if (!buffer.empty()) data.append(reinterpret_cast<const char*>(buffer.data()), int(buffer.size()));
    if (_state != State::Ready) { if (_pending.size() + data.size() > kMaxBuffer) { fail(); return; } _pending.append(data); return; }
    const auto block = _enc->compress(data);
    if (!block.isEmpty()) sendRaw(derenguh::wrapRecord(block));
}
int32 DerenguhSocket::debugState() { return int(_state); }
QString DerenguhSocket::debugPostfix() const { return u"derenguh dc%1"_q.arg(_dcIndex); }
} // namespace
