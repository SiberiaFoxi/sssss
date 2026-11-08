# Руководство по интеграции в форки (Fork Guide)

Модули DerenguhGram спроектированы как **аддитивные**: они добавляют новый код и
вставляют небольшие «гейты» в существующие места upstream. Ниже — карта точек
интеграции для обеих платформ. Имена функций могут отличаться между версиями —
используйте приведённые `grep`-цели, чтобы найти их в своём форке.

---

## A. Desktop (tdesktop)

### A1. Новый тип прокси «DerenguhGram Proxy»

1. В enum типов прокси (найдите `grep -rn "ProxyType\|MTP::ProxyType\|enum class Type" Telegram/SourceFiles`)
   добавьте значение `Derenguh`.
2. В UI настроек прокси (`storage/localimageworker...` → `Settings`, окно
   «Advanced → Connection type / Proxy») добавьте радио-пункт «DerenguhGram Proxy»
   с полями: ссылка `derenguh://…`, выпадающий список SNI (`derenguh::kSniChoices`).
3. В фабрике соединений MTProto (`grep -rn "AbstractSocket\|TcpConnection\|ConnectToHost" Telegram/SourceFiles/mtproto`)
   при типе `Derenguh` создавайте `derenguh::ProxyTransport` вместо прямого TCP:
   ```cpp
   auto transport = new derenguh::ProxyTransport(cfg);
   connect(transport, &derenguh::ProxyTransport::ready, [=]{ /* начать MTProto handshake */ });
   connect(transport, &derenguh::ProxyTransport::mtprotoBytes, [=](const QByteArray &b){ /* feeding read */ });
   // запись MTProto-байтов -> transport->sendMtproto(b);
   transport->connectToProxy();
   ```
   `cfg.dcIndex` берётся из номера DC, к которому подключается сессия.

### A2. Пункт меню ClanSecrets

В главном меню (`grep -rn "Settings\|AddButton\|MainMenu" Telegram/SourceFiles/window`
или `main_menu`), добавьте пункт:
```cpp
menu->addAction("ClanSecrets", [=]{
    auto *w = new derenguh::ClanSecretsWindow();
    w->setVersionInfo(/* AppVersion */);
    w->setCachePath(/* cWorkingDir() + "tdata" */);
    w->show();
});
```
Логи прокси направляйте в `w->appendLog(...)` из `ProxyTransport` (сигнал/колбэк).

### A3. Хуки приватности

См. `docs/PRIVACY_MODES.md` — три гейта `derenguh::PrivacySettings`.

---

## B. Android (DrKLO / Hook-droid)

### B1. Прокси

* **Быстрый путь (вариант A):** `DerenguhLocalBridge` + штатный SOCKS5. Экран
  «DerenguhGram Proxy» — новый пункт в `ProfileActivity`/настройках, который парсит
  ссылку, запускает мост и вызывает `enableProxy(ProxyInfo("127.0.0.1", port, ...))`.
* **Нативный путь (вариант B):** добавьте `PROXY_DERENGUH` в
  `TMessagesProj/jni/tgnet/ConnectionsManager.h`/`Connection.cpp` и выполняйте
  DerenguhProto-рукопожатие на этапе соединения. Логику можно вызвать через JNI из
  `DerenguhTunnel`.

### B2. ClanSecrets Activity

`AndroidManifest.xml`:
```xml
<activity android:name="org.derenguhgram.clansecrets.ClanSecretsActivity"
          android:exported="false" android:label="ClanSecrets"/>
```
Пункт меню (например в `ProfileActivity` или боковом меню):
```java
startActivity(new Intent(context, ClanSecretsActivity.class));
```

### B3. Приватность

`PrivacyController.init(context)` при старте; гейты — в `docs/PRIVACY_MODES.md`.

---

## C. Общий секрет / ссылка

Обе платформы парсят `derenguh://proxy?server=&port=&sni=&key=` одинаково
(`parseProxyLink` / `DerenguhProxyConfig.fromLink`). Ключ — base64url(16 байт).
Совместимость проверяется общими векторами `shared/test_vectors.json`.

## D. Лицензии

* tdesktop — **GPLv3**: производный клиент обязан распространяться под GPLv3 с
  исходниками. Модули `desktop/` помечены GPL-3.0-only.
* DrKLO/Telegram — **GPLv2+**: аналогично, публикуйте исходники форка.
* Не используйте бренд/логотип Telegram; указывайте, что клиент неофициальный.
