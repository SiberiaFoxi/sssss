// DerenguhProxy: a Qt transport that tunnels an MTProto (obfuscated-2) byte stream
// through a DerenguhGram-Proxy server (Fake-TLS + compression). SPDX: GPL-3.0-only
//
// Integration: tdesktop's MTProto connection writes/reads raw transport bytes. When
// the active proxy type is Derenguh, route those bytes through this object instead
// of a direct TCP socket. See desktop/patches/ and docs/FORK_GUIDE.md.
#pragma once

#include <QObject>
#include <QTcpSocket>
#include <QByteArray>
#include <memory>
#include "derenguh_protocol.h"
#include "derenguh_compression.h"

namespace derenguh {

struct ProxyConfig {
    QString host;
    quint16 port = 3183;
    QByteArray secret;          // 16 bytes
    QByteArray sni = "music.yandex.ru";
    uint8_t dcIndex = 2;        // the DC the MTProto session is targeting
    Codec codec = Codec::Zlib;
};

class ProxyTransport : public QObject {
    Q_OBJECT
public:
    explicit ProxyTransport(const ProxyConfig &config, QObject *parent = nullptr);
    ~ProxyTransport() override;

    void connectToProxy();
    void abort();
    [[nodiscard]] bool isReady() const { return _state == State::Ready; }

    // Feed raw MTProto bytes (obfuscated-2) toward the DC via the tunnel.
    void sendMtproto(const QByteArray &data);

signals:
    void ready();                       // tunnel established, start MTProto handshake
    void mtprotoBytes(const QByteArray &data); // decoded bytes from the DC
    void failed(const QString &reason);

private slots:
    void onConnected();
    void onReadyRead();
    void onSocketError(QAbstractSocket::SocketError);

private:
    enum class State {
        TcpConnect,
        WaitServerHello,
        WaitAck,
        Ready,
        Failed,
    };

    void processServerHello();
    void processAck();
    void processData();
    void fail(const QString &reason);
    void sendControlFrame();

    ProxyConfig _config;
    QTcpSocket _socket;
    State _state = State::TcpConnect;
    QByteArray _rx;                     // raw socket receive buffer
    QByteArray _clientHelloDigest;
    std::unique_ptr<ZlibEncoder> _encoder;
    std::unique_ptr<ZlibDecoder> _decoder;
    Codec _negotiated = Codec::Zlib;
};

// Parse a derenguh://proxy?server=..&port=..&sni=..&key=.. link into a config.
// Returns false on malformed input. `key` is base64url (16 bytes).
[[nodiscard]] bool parseProxyLink(const QString &link, ProxyConfig &out, QString &error);

} // namespace derenguh
