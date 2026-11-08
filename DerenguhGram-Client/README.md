# DerenguhGram-Client

Неофициальный модифицированный клиент Telegram (ПК + Android) с новым типом прокси
**DerenguhGram Proxy**, окном **ClanSecrets** и режимами приватности. Работает в паре с
[DerenguhGram-Proxy](../DerenguhGram-Proxy/).

> **Статус поставки.** Этот репозиторий содержит готовые к интеграции модули и
> инструкции. Полные компилируемые форки `tdesktop` и `DrKLO/Telegram` собираются в их
> собственных тулчейнах (Qt/VS и Android Studio/NDK) — следуйте `docs/BUILD_*.md`.
> Серверная часть ([DerenguhGram-Proxy](../DerenguhGram-Proxy/)) полностью реализована и
> протестирована отдельно.

## Возможности

* **DerenguhGram Proxy** — новый тип прокси: Fake-TLS с SNI стриминговых сервисов РФ +
  сжатие zlib/brotli + прозрачный туннель obfuscated-2 MTProto. Единый формат
  `derenguh://`-ссылки с сервером.
* **ClanSecrets** — окно диагностики: логи, путь к кэшу, просмотр собственного кэша,
  папка экспорта разрешённого контента.
* **Приватность** — Невидимка / Нечиталка / Неписалка (подавляют ваши собственные
  сигналы активности).

### Границы приватности

Мод **не** перехватывает чужие самоуничтожающиеся/одноразовые медиа: это обход защиты,
включённой отправителем. Вместо скрытого сохранения — кнопка «запросить постоянную
копию» (решение за отправителем). Подробнее: [docs/CLANSECRETS.md](docs/CLANSECRETS.md).

## Структура

```
DerenguhGram-Client/
├── desktop/                     # модуль tdesktop (C++ / Qt)
│   ├── CMakeLists.txt
│   ├── src/
│   │   ├── derenguh_protocol.h        # константы + control-кадры
│   │   ├── derenguh_compression.*     # потоковый zlib
│   │   ├── derenguh_faketls.*         # ClientHello/ServerHello, рекорды
│   │   ├── derenguh_proxy.*           # транспорт ProxyTransport + парсер ссылки
│   │   ├── clan_secrets_window.*      # окно ClanSecrets
│   │   └── privacy_settings.*         # переключатели приватности
│   └── patches/                       # иллюстративные точки интеграции
├── android/                     # модуль Android (Kotlin)
│   └── src/main/java/org/derenguhgram/
│       ├── proxy/                     # Protocol, Compression, FakeTls, Tunnel,
│       │                              # LocalBridge (SOCKS5), Config
│       ├── clansecrets/               # ClanSecretsActivity
│       └── privacy/                   # PrivacyController
├── shared/test_vectors.json     # общие векторы совместимости (из Python-эталона)
└── docs/
    ├── PROTOCOL.md                # спецификация DerenguhProto v1
    ├── BUILD_WINDOWS.md           # сборка .exe
    ├── BUILD_ANDROID.md           # сборка .apk + подпись
    ├── FORK_GUIDE.md              # карта интеграции в форки
    ├── PRIVACY_MODES.md           # точки внедрения гейтов
    └── CLANSECRETS.md             # дизайн окна + границы приватности
```

## Быстрый старт

1. Поднимите сервер: см. [DerenguhGram-Proxy/README](../DerenguhGram-Proxy/README.md).
2. Соберите клиент: [Windows](docs/BUILD_WINDOWS.md) · [Android](docs/BUILD_ANDROID.md).
3. Вставьте `derenguh://`-ссылку в настройки прокси (тип «DerenguhGram Proxy»),
   выберите SNI, подключитесь. Статус — в ClanSecrets → Логи.

## Совместимость

Формат секрета/ключей и протокол едины для клиента и сервера. Проверка портов —
`shared/test_vectors.json` (сгенерирован из протестированной Python-реализации):
ClientHello-дайджест, control-кадры, zlib-блок для декодирования, формат ссылки.

## Базовые репозитории и лицензии

| Платформа | База | Лицензия |
|---|---|---|
| ПК | [telegramdesktop/tdesktop](https://github.com/telegramdesktop/tdesktop) | GPLv3 |
| Android | [DrKLO/Telegram](https://github.com/DrKLO/Telegram) / [Hook-droid/Tg](https://github.com/Hook-droid/Tg) | GPLv2+ |

Изученные референсы (логика адаптирована, не скопирована): HushTelegram (ghost),
Telegami (статусы), telegram_gx (DPI). Логика сохранения эфемерного контента из
GhostGram **не** портировалась по причинам выше.

Не используйте бренд и логотип Telegram; публикуйте исходники форка согласно лицензии.
