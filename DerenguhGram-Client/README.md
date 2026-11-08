# DerenguhGram-Client

Исходные модули для неофициального мода Telegram (ПК + Android): новый тип прокси
**DerenguhGram Proxy**, окно **ClanSecrets** и переключатели приватности. Предполагаемая
пара — [DerenguhGram-Proxy](../DerenguhGram-Proxy/).

> **Статус поставки: незавершённая интеграция, не установочные клиенты.** Здесь нет
> полного форка `tdesktop` или `DrKLO/Telegram`, законченного Android Gradle-проекта,
> подписанного APK или собранного Windows EXE. Интеграционные примеры требуют адаптации
> к выбранной версии upstream; сборка и работа клиентских модулей не проверялись.
> Инструкции `docs/BUILD_*.md` описывают дальнейшие шаги, но не являются подтверждением
> успешной сборки. Сервер проверен локальными тестами с mock-DC; подключение к реальному
> Telegram и сквозная работа модифицированных клиентов не проверялись.

## Модули, требующие интеграции и проверки

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

## Дальнейшие шаги (не готовый запуск клиента)

1. Запустите исходный прототип сервера: [DerenguhGram-Proxy/README](../DerenguhGram-Proxy/README.md).
2. Адаптируйте интеграцию и сборку: [Windows](docs/BUILD_WINDOWS.md) · [Android](docs/BUILD_ANDROID.md).
   Эти инструкции ещё не подтверждены успешной сборкой данного мода.
3. Только после завершения интеграции проверьте импорт `derenguh://`-ссылки, выбор SNI,
   подключение и отображение статуса в ClanSecrets на реальном устройстве.

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
