# Иллюстративные точки интеграции (DrKLO / Hook-droid)

Не готовые `git apply`-патчи, а места вставки (версии форков различаются).

## 1. Прокси — вариант A (локальный мост, без нативного патча)

См. `android/INTEGRATION_SNIPPETS.md` → `DerenguhProxyManager.enable(link, account)`.
Экран «DerenguhGram Proxy» в настройках вызывает его; штатный SOCKS5 Telegram
указывается на `127.0.0.1:<port>` моста.

## 1b. Прокси — вариант B (нативный тип)

`TMessagesProj/jni/tgnet/ConnectionsManager.h`:
```cpp
enum ProxyType { PROXY_SOCKS5 = 1, PROXY_HTTP = 2, PROXY_MTPROTO = 3, PROXY_DERENGUH = 4 };
```
`Connection.cpp` (этап установки соединения): при `PROXY_DERENGUH` выполняйте
DerenguhProto-рукопожатие (логика `DerenguhTunnel`, вызов через JNI или порт на C++).
Это даёт отдельный тип в списке прокси.

## 2. ClanSecrets Activity

`AndroidManifest.xml`:
```xml
<activity android:name="org.derenguhgram.clansecrets.ClanSecretsActivity"
          android:exported="false" android:label="ClanSecrets"/>
```
Пункт меню:
```java
startActivity(new Intent(context, ClanSecretsActivity.class));
```

## 3. Приватность

`Application.onCreate`:
```java
PrivacyController.INSTANCE.init(getApplicationContext());
```
Гейты (`grep`-цели в `docs/PRIVACY_MODES.md`):
```java
// перед TL_account_updateStatus(offline=false)
if (!PrivacyController.INSTANCE.shouldSendOnlineUpdate()) return;
// MessagesController.markDialogAsRead / markMessageAsRead
if (!PrivacyController.INSTANCE.shouldSendReadReceipt()) return;
// перед TL_messages_setTyping
if (!PrivacyController.INSTANCE.shouldSendTyping()) return;
```
