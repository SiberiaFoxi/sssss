# Сборка DerenguhGram-Client для Android (.apk)

База — [DrKLO/Telegram](https://github.com/DrKLO/Telegram) (Java/Kotlin, GPLv2+) или
более мод-дружелюбный форк [Hook-droid/Tg](https://github.com/Hook-droid/Tg) (12.7.0+).
Модули DerenguhGram лежат в `android/src/main/java/org/derenguhgram`.

> Актуальные требования upstream (master, v12.10.1): **Android Studio 2025.1.4**,
> **NDK 27.2.12479018**, **SDK 36**. В репозитории есть dummy `release.keystore`,
> `google-services.json` и заполненный `BuildVars.java` — для публикации замените их
> своими. См. [README](https://github.com/DrKLO/Telegram/blob/master/README.md).

## 1. Форк и credentials

1. Форкните `DrKLO/Telegram` (или `Hook-droid/Tg`) → `DerenguhGram-Android`.
2. Получите `api_id` / `api_hash` на <https://my.telegram.org>.
3. Не используйте имя «Telegram» и стандартный логотип; публикуйте свой код (лицензия).

## 2. Клонирование

```bash
git clone --recursive --shallow-submodules https://github.com/<you>/DerenguhGram-Android.git Telegram
cd Telegram
# если забыли --recursive:
git submodule update --init --recursive --depth=1
```

## 3. Подпись APK (keystore)

```bash
keytool -genkeypair -v -keystore release.keystore -alias derenguh \
  -keyalg RSA -keysize 2048 -validity 10000
cp release.keystore TMessagesProj/config/
```

В `gradle.properties` задайте:

```properties
RELEASE_KEY_PASSWORD=ваш_пароль
RELEASE_KEY_ALIAS=derenguh
RELEASE_STORE_PASSWORD=ваш_пароль
```

> Храните keystore и пароли вне репозитория. Без своей подписи APK нельзя обновлять
> поверх установленного приложения, и он не пройдет проверку целостности.

## 4. Конфигурация приложения

1. `TMessagesProj/src/main/java/org/telegram/messenger/BuildVars.java` — впишите
   `APP_ID` (api_id) и `APP_HASH` (api_hash).
2. Firebase: создайте приложения `org.telegram.messenger` и `.beta`, скачайте
   `google-services.json` в `TMessagesProj/` (для push-уведомлений).
3. Откройте проект в Android Studio (**Open**, не Import).

## 5. Подключение модулей DerenguhGram

Скопируйте `android/src/main/java/org/derenguhgram/` в
`TMessagesProj/src/main/java/org/derenguhgram/`. Зависимостей сверх стандартных
(`java.util.zip`, `javax.crypto`, `java.net`) не требуется — `build.gradle` менять не
нужно для транспорта. Точки интеграции:

### Вариант A — без патча нативного слоя (рекомендуется для старта)

`DerenguhLocalBridge` поднимает локальный SOCKS5 на `127.0.0.1:<port>` и туннелирует
через DerenguhProto. Используйте штатную поддержку SOCKS5 в Telegram:

```kotlin
// при включении прокси DerenguhGram:
val bridge = DerenguhLocalBridge(DerenguhProxyConfig.fromLink(link))
val port = bridge.start()
// настроить штатный SOCKS5-прокси Telegram на 127.0.0.1:port (без авторизации)
MessagesController.getInstance(currentAccount).enableProxy(
    SharedConfig.ProxyInfo("127.0.0.1", port, "", "", ""))
```

Экран «DerenguhGram Proxy» в настройках — это UI-обёртка вокруг моста (поле ссылки,
выбор SNI, кнопка включить). Ограничение: мост маршрутизирует 5 основных DC по их IP;
CDN-медиа вне этих DC идёт мимо прокси.

### Вариант B — настоящий новый тип прокси (патч tgnet)

Добавьте тип `PROXY_DERENGUH` в нативный `tgnet` (`ConnectionsManager`/`Connection`)
и вызывайте логику `DerenguhTunnel` на этапе установки соединения. Это даёт отдельный
тип «DerenguhGram Proxy» рядом с MTProto/HTTP/SOCKS5. Иллюстративные места — в
`android/patches/` и `docs/FORK_GUIDE.md`.

### ClanSecrets и приватность

* Зарегистрируйте `ClanSecretsActivity` в `AndroidManifest.xml` и добавьте пункт в
  главное меню (см. `docs/CLANSECRETS.md`).
* Хуки приватности — `docs/PRIVACY_MODES.md` (`PrivacyController`).

## 6. Сборка APK

```bash
./gradlew :TMessagesProj:assembleRelease
# APK: TMessagesProj/build/outputs/apk/release/
```

Из Android Studio: **Build → Generate Signed Bundle / APK → APK**, выберите свой
keystore. Для отладки: `./gradlew assembleDebug`.

## Зависимости

| Компонент | Версия |
|---|---|
| Android Studio | 2025.1.4 |
| Android NDK | 27.2.12479018 |
| Android SDK | 36 |
| JDK | 17 (поставляется со Studio) |
| keystore | свой, RSA 2048 |

Системные библиотеки не нужны: транспорт использует только стандартные API Java/Kotlin.
