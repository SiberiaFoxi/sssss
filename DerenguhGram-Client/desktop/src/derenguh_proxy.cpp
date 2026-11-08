// SPDX-License-Identifier: GPL-3.0-only
#include "derenguh_proxy.h"
#include "derenguh_faketls.h"

#include <QUrl>
#include <QUrlQuery>
#include <QtEndian>

namespace derenguh {

ProxyTransport::ProxyTransport(const ProxyConfig &config, QObject *parent)
    : QObject(parent), _config(config) {
    connect(&_socket, &QTcpSocket::connected, this, &ProxyTransport::onConnected);
    connect(&_socket, &QTcpSocket::readyRead, this, &ProxyTransport::onReadyRead);
    connect(&_socket, &QTcpSocket::errorOccurred, this, &ProxyTransport::onSocketError);
}

ProxyTransport::~ProxyTransport() = default;

void ProxyTransport::connectToProxy() {
    _state = State::TcpConnect;
    _rx.clear();
    _socket.connectToHost(_config.host, _config.port);
}

void ProxyTransport::abort() {
    _state = State::Failed;
    _socket.abort();
}

void ProxyTransport::onConnected() {
    const QByteArray hello = buildClientHello(_config.secret, _config.sni);
    _clientHelloDigest = clientDigest(hello);
    _socket.write(hello);
    _state = State::WaitServerHello;
}

void ProxyTransport::onSocketError(QAbstractSocket::SocketError) {
    fail(_socket.errorString());
}

void ProxyTransport::fail(const QString &reason) {
    if (_state == State::Failed) return;
    _state = State::Failed;
    _socket.abort();
    emit failed(reason);
}

void ProxyTransport::onReadyRead() {
    _rx.append(_socket.readAll());
    switch (_state) {
    case State::WaitServerHello: processServerHello(); break;
    case State::WaitAck: processAck(); break;
    case State::Ready: processData(); break;
    default: break;
    }
}

void ProxyTransport::processServerHello() {
    // ServerHello = handshake record (0x16) + CCS (6 bytes) + app-data record (0x17).
    if (_rx.size() < 5) return;
    if (uint8_t(_rx[0]) != 0x16) { fail("expected ServerHello"); return; }
    const int len1 = (uint8_t(_rx[3]) << 8) | uint8_t(_rx[4]);
    const int afterRec1 = 5 + len1;
    if (_rx.size() < afterRec1 + 6 + 5) return;
    // CCS must be 14 03 03 00 01 01.
    if (uint8_t(_rx[afterRec1]) != 0x14) { fail("expected ChangeCipherSpec"); return; }
    const int rec3Start = afterRec1 + 6;
    if (uint8_t(_rx[rec3Start]) != 0x17) { fail("expected fake certificate"); return; }
    const int len3 = (uint8_t(_rx[rec3Start + 3]) << 8) | uint8_t(_rx[rec3Start + 4]);
    const int total = rec3Start + 5 + len3;
    if (_rx.size() < total) return;

    const QByteArray helloPacket = _rx.left(total);
    _rx.remove(0, total);
    if (!verifyServerHello(helloPacket, _config.secret, _clientHelloDigest)) {
        fail("server authentication failed");
        return;
    }
    sendControlFrame();
    _state = State::WaitAck;
    if (!_rx.isEmpty()) processAck();
}

void ProxyTransport::sendControlFrame() {
    ClientControl ctrl;
    ctrl.codec = _config.codec;
    ctrl.dcIndex = _config.dcIndex;
    _socket.write(wrapRecord(ctrl.encode()));
}

void ProxyTransport::processAck() {
    while (true) {
        const auto r = parseRecord(_rx, 0);
        if (!r.valid) { fail("bad TLS record in ack"); return; }
        if (!r.complete) return;
        _rx.remove(0, r.consumed);
        if (r.payload.isEmpty()) continue; // skip CCS
        const auto ack = ServerAck::decode(r.payload);
        if (!ack) { fail("malformed ack"); return; }
        if (ack->status != Status::Ok) {
            fail(QString("proxy rejected (status %1)").arg(int(ack->status)));
            return;
        }
        _negotiated = ack->codec;
        if (_negotiated == Codec::Zlib) {
            _encoder = std::make_unique<ZlibEncoder>();
            _decoder = std::make_unique<ZlibDecoder>();
        } else if (_negotiated == Codec::Brotli) {
            // Brotli encoder/decoder would be wired here if built with brotli.
            fail("brotli not built into this client");
            return;
        } // Codec::None -> no encoder/decoder
        _state = State::Ready;
        emit ready();
        if (!_rx.isEmpty()) processData();
        return;
    }
}

void ProxyTransport::processData() {
    while (true) {
        const auto r = parseRecord(_rx, 0);
        if (!r.valid) { fail("bad TLS data record"); return; }
        if (!r.complete) return;
        _rx.remove(0, r.consumed);
        if (r.payload.isEmpty()) continue;
        QByteArray plain = _decoder ? _decoder->decompress(r.payload) : r.payload;
        if (!plain.isEmpty()) emit mtprotoBytes(plain);
    }
}

void ProxyTransport::sendMtproto(const QByteArray &data) {
    if (_state != State::Ready) return;
    const QByteArray block = _encoder ? _encoder->compress(data) : data;
    if (!block.isEmpty()) _socket.write(wrapRecord(block));
}

bool parseProxyLink(const QString &link, ProxyConfig &out, QString &error) {
    QUrl url(link);
    if (url.scheme() != "derenguh" || url.host() != "proxy") {
        error = "not a derenguh://proxy link";
        return false;
    }
    QUrlQuery q(url.query());
    if (!q.hasQueryItem("server") || !q.hasQueryItem("port")
        || !q.hasQueryItem("sni") || !q.hasQueryItem("key")) {
        error = "link missing required parameters";
        return false;
    }
    out.host = q.queryItemValue("server");
    out.port = quint16(q.queryItemValue("port").toUInt());
    out.sni = q.queryItemValue("sni").toUtf8();
    const QString key = q.queryItemValue("key");
    QByteArray secret = QByteArray::fromBase64(key.toUtf8(),
        QByteArray::Base64UrlEncoding | QByteArray::OmitTrailingEquals);
    if (secret.size() != 16) {
        error = "key must decode to 16 bytes";
        return false;
    }
    out.secret = secret;
    return true;
}

} // namespace derenguh
