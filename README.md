# DerenguhGram

Два связанных проекта для доступа к Telegram через маскирующий сжимающий прокси:

| Проект | Что это | Статус |
|---|---|---|
| [DerenguhGram-Proxy](DerenguhGram-Proxy/) | сервер-прокси (Python, asyncio): Fake-TLS под РФ-стриминг, сжатие, TCP Splice | **реализован и протестирован** (23 теста) |
| [DerenguhGram-Client](DerenguhGram-Client/) | мод клиента Telegram (C++/Qt + Kotlin): тип прокси DerenguhGram, ClanSecrets, приватность | **готовые к интеграции модули + инструкции по сборке** |

## Архитектура

```
DerenguhGram-Client                         DerenguhGram-Proxy                Telegram
 (tdesktop / Android)                       (Python asyncio)                  DC 1..5
        │                                          │                              │
        │  Fake-TLS ClientHello (SNI=music.yandex.ru, HMAC)                        │
        ├─────────────────────────────────────────►│                              │
        │  ServerHello + control/ack (codec, DC)    │── TCP connect DC N:443 ─────►│
        │  zlib-сжатый obfuscated-2 поток          ⇄│⇄  сырой obfuscated-2 поток  ⇄│
        │                                          │                              │
   DPI-сканер (без валидного HMAC) ────────────────►│── TCP Splice ──► реальный РФ-сервис
```

Прокси — **транспортный туннель**: шифрование obfuscated-2 остаётся end-to-end между
клиентом и Telegram, прокси не видит ключи MTProto. Сжатие — потоковый zlib (brotli
опционально). Единый формат секрета и `derenguh://`-ссылки для обеих сторон.

## Быстрый старт

```bash
# 1. Сервер
cd DerenguhGram-Proxy
export SERVER_PORT=3183 DERENGUH_PUBLIC_HOST=ваш.домен
export DERENGUH_SECRET=$(python3 -c "from derenguh_proxy import generate_secret; print(generate_secret().hex())")
python3 -m derenguh_proxy        # печатает готовую derenguh://-ссылку

# 2. Проверка без Telegram (mock-DC + замер памяти)
python3 deploy/demo_local.py

# 3. Клиент — сборка форка: DerenguhGram-Client/docs/BUILD_WINDOWS.md / BUILD_ANDROID.md
```

## Совместимость

Протокол **DerenguhProto v1** описан в
[DerenguhGram-Proxy/docs/PROTOCOL.md](DerenguhGram-Proxy/docs/PROTOCOL.md) (копия в
клиенте). Общие векторы — [DerenguhGram-Client/shared/test_vectors.json](DerenguhGram-Client/shared/test_vectors.json),
сгенерированы из протестированной Python-реализации и проверяют ClientHello-дайджест,
control-кадры, zlib-декодирование и формат ссылки для портов на C++/Kotlin.

## Приватность и границы

* Режимы **Невидимка / Нечиталка / Неписалка** подавляют собственные сигналы
  активности пользователя.
* Окно **ClanSecrets** показывает логи, кэш и экспортирует только разрешённый контент.
* Мод **не** перехватывает чужие самоуничтожающиеся/одноразовые медиа — это обход
  защиты, включённой отправителем. Вместо этого — запрос постоянной копии с согласия
  отправителя. Обоснование: [DerenguhGram-Client/docs/CLANSECRETS.md](DerenguhGram-Client/docs/CLANSECRETS.md).

## Лицензии

* Proxy — MIT (наследует архитектуру [alexbers/mtprotoproxy](https://github.com/alexbers/mtprotoproxy), MIT).
* Client desktop — GPLv3 (база [tdesktop](https://github.com/telegramdesktop/tdesktop)).
* Client Android — GPLv2+ (база [DrKLO/Telegram](https://github.com/DrKLO/Telegram)).

Неофициальный проект. Не используйте бренд/логотип Telegram; публикуйте исходники
форков согласно их лицензиям. Применяйте средства обхода блокировок только там, где
имеете на это право.
