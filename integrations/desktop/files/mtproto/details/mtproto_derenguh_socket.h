// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "mtproto/details/mtproto_abstract_socket.h"
#include "mtproto/mtproto_proxy_data.h"
#include "derenguh/derenguh_compression.h"
#include <QtNetwork/QTcpSocket>
#include <memory>
namespace MTP::details {
class DerenguhSocket final : public AbstractSocket {
public:
    DerenguhSocket(not_null<QThread*> thread, const ProxyData &proxy, int16 protocolDcId);
    void connectToHost(const QString &address, int port) override;
    bool isGoodStartNonce(bytes::const_span nonce) override;
    void timedOut() override;
    bool isConnected() override;
    bool hasBytesAvailable() override;
    int64 read(bytes::span buffer) override;
    void write(bytes::const_span prefix, bytes::const_span buffer) override;
    int32 debugState() override;
    QString debugPostfix() const override;
private:
    enum class State { Tcp, ServerHello, Ack, Ready, Failed };
    void onTcpConnected();
    void onReadyRead();
    void onError(QAbstractSocket::SocketError e);
    void fail();
    void processBuffer();
    void sendRaw(const QByteArray &data);
    ProxyData _proxy;
    QByteArray _secret;
    int _dcIndex = 0;
    QTcpSocket _socket;
    State _state = State::Tcp;
    QByteArray _rx;
    QByteArray _plain;
    QByteArray _clientHello;
    QByteArray _pending;
    std::unique_ptr<derenguh::ZlibEncoder> _enc;
    std::unique_ptr<derenguh::ZlibDecoder> _dec;
    int _plainOffset = 0;
};
} // namespace
