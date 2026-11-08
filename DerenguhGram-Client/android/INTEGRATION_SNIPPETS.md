# Android — фрагменты интеграции

## AndroidManifest.xml (внутри `<application>`)

```xml
<activity
    android:name="org.derenguhgram.clansecrets.ClanSecretsActivity"
    android:exported="false"
    android:label="ClanSecrets" />
```

Локальный мост слушает только `127.0.0.1`, поэтому разрешение `INTERNET` (уже есть у
Telegram) достаточно; отдельный network-security-config не требуется.

## Включение прокси (вариант A — локальный мост + штатный SOCKS5)

```kotlin
import org.derenguhgram.proxy.DerenguhLocalBridge
import org.derenguhgram.proxy.DerenguhProxyConfig
import org.telegram.messenger.MessagesController
import org.telegram.messenger.SharedConfig

object DerenguhProxyManager {
    private var bridge: DerenguhLocalBridge? = null

    fun enable(link: String, account: Int) {
        disable()
        val cfg = DerenguhProxyConfig.fromLink(link)
        val b = DerenguhLocalBridge(cfg)
        val port = b.start()
        bridge = b
        // Штатный SOCKS5 Telegram указывает на локальный мост (без авторизации).
        val info = SharedConfig.ProxyInfo("127.0.0.1", port, "", "", "")
        MessagesController.getInstance(account).enableProxy(info)
    }

    fun disable() {
        bridge?.stop()
        bridge = null
    }
}
```

## Пункт меню ClanSecrets

```java
// например, в обработчике пункта бокового меню / настроек:
context.startActivity(new android.content.Intent(context,
        org.derenguhgram.clansecrets.ClanSecretsActivity.class));
```

## Инициализация приватности (Application.onCreate)

```java
org.derenguhgram.privacy.PrivacyController.INSTANCE.init(getApplicationContext());
```

Гейты приватности — см. `docs/PRIVACY_MODES.md`.

## Зависимости

Транспорт использует только стандартные API (`java.util.zip`, `javax.crypto`,
`java.net`, `android.util.Base64`). Менять `build.gradle` для транспорта не нужно.
Опциональный brotli на Android не включён по умолчанию (сервер сам понизит до zlib).
