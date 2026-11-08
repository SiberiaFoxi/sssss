# Иллюстративные точки интеграции (tdesktop)

Это **не** готовые `git apply`-патчи (имена/строки зависят от версии форка), а точные
места вставки. Найдите их через `grep` в своём форке и добавьте гейты/вызовы.

## 1. Тип прокси Derenguh

`grep -rn "enum.*Type\|ProxyType\|Settings::Proxy" Telegram/SourceFiles/platform Telegram/SourceFiles/core`

```cpp
// в enum типов прокси:
enum class ProxyType { None, Socks5, Mtproto, Http, Derenguh /* + */ };
```

Фабрика соединения (`grep -rn "AbstractSocket\|TcpConnection::Connect" Telegram/SourceFiles/mtproto`):

```cpp
if (proxy.type == ProxyType::Derenguh) {
    derenguh::ProxyConfig cfg;
    cfg.host = proxy.host; cfg.port = proxy.port;
    cfg.secret = proxy.derenguhSecret;     // 16 байт из настроек
    cfg.sni = proxy.derenguhSni;           // выбранный SNI
    cfg.dcIndex = dcId;                    // DC текущей сессии
    auto *t = new derenguh::ProxyTransport(cfg, this);
    QObject::connect(t, &derenguh::ProxyTransport::ready, this, [=]{ startMtprotoHandshake(); });
    QObject::connect(t, &derenguh::ProxyTransport::mtprotoBytes, this, [=](const QByteArray &b){ onTransportBytes(b); });
    QObject::connect(t, &derenguh::ProxyTransport::failed, this, [=](const QString &e){ onTransportError(e); });
    t->connectToProxy();
    return;
}
```

## 2. Меню ClanSecrets

`grep -rn "AddMenuButton\|MainMenu\|Settings.*addAction" Telegram/SourceFiles/window`

```cpp
addAction("ClanSecrets", [=]{
    auto *w = new derenguh::ClanSecretsWindow(Core::App().mainWindow());
    w->setVersionInfo(QString::fromLatin1(AppVersionStr));
    w->setCachePath(cWorkingDir() + qsl("tdata"));
    w->setProxyStatus(currentProxyStatusString());
    w->show();
});
```

## 3. Гейты приватности

См. `docs/PRIVACY_MODES.md`. Кратко:

```cpp
// Session::updateOnline / sendUpdateStatus
if (!derenguh::PrivacySettings::instance().shouldSendOnlineUpdate()) return;
// Api read-history path
if (!derenguh::PrivacySettings::instance().shouldSendReadReceipt()) return;
// Api typing helper
if (!derenguh::PrivacySettings::instance().shouldSendTyping()) return;
```

## 4. CMake

```cmake
add_subdirectory(SourceFiles/derenguh derenguh)   # путь к desktop/
target_link_libraries(Telegram PRIVATE derenguh_desktop)
```
