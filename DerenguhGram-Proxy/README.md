# DerenguhGram-Proxy

Сервер-прокси для [DerenguhGram-Client](../DerenguhGram-Client/): маскирует трафик
Telegram под стриминговые сервисы РФ (Fake-TLS 1.3), сжимает поток (zlib / опционально
brotli) и прозрачно передаёт obfuscated-2 MTProto в дата-центры Telegram.

Архитектура Fake-TLS и маскировка незнакомых соединений основаны на
[alexbers/mtprotoproxy](https://github.com/alexbers/mtprotoproxy) (MIT), поверх добавлен
собственный протокол **DerenguhProto** (сжатие + явный выбор DC).

```
Telegram-клиент                    DerenguhGram-Proxy                 Telegram DC
     │                                   │                                 │
     │  TLS ClientHello (SNI=music.yandex.ru, HMAC-дайджест)                │
     ├──────────────────────────────────►│                                 │
     │  Fake-TLS ServerHello + fake cert │                                 │
     │◄──────────────────────────────────┤                                 │
     │  DG-контрольный кадр (codec, dc)  │                                 │
     ├──────────────────────────────────►│──── TCP connect DC N:443 ──────►│
     │  DG-ack (status OK)               │                                 │
     │◄──────────────────────────────────┤                                 │
     │  сжатые блоки ⇄ zlib-поток        │⇄  сырой obfuscated-2 поток     ⇄│
```

**Сканер DPI / чужой клиент** (нет валидного HMAC) → **TCP Splice**: соединение
без изменений пробрасывается на реальный IP стримингового сервиса из SNI, и сканер
получает легитимный TLS-ответ настоящего сервера.

## Возможности

- **DerenguhProto v1**: Fake-TLS рукопожатие → 8-байтовый контрольный кадр
  (кодек + номер DC) → ack → потоковое сжатие в TLS application-data рекордах.
- **Сжатие**: синхронные zlib-потоки (`Z_SYNC_FLUSH` на каждый блок); brotli —
  опционально, при отсутствии автоматически даунгрейд до zlib.
- **Маскировка**: allowlist SNI (`music.yandex.ru`, `vk.com`, `rutube.ru`,
  `yandex.ru`, `dzen.ru`, `vkvideo.ru`) + TCP Splice на реальный хост.
- **Анти-replay**: HMAC-SHA256 дайджест ClientHello с timestamp, как в mtprotoproxy.
- **128 МБ RAM**: потоковый relay (чанки 8 КБ, окно zlib 4 КБ, буферы сокетов 16 КБ,
  семафор на 64 соединения). Никакой буферизации целых сообщений.
- **Без root**: обычный asyncio-процесс, порт из `$SERVER_PORT` (default **3183**) —
  совместимо с Pterodactyl.
- **Не open-relay**: клиент может запросить только DC 1–5 (фиксированные адреса
  Telegram); splice — только на хосты из allowlist.
- Прозрачность шифрования: прокси **не видит** ключи MTProto — obfuscated-2 остаётся
  end-to-end между клиентом и Telegram.

## Структура

```
DerenguhGram-Proxy/
├── derenguh_proxy/
│   ├── __main__.py         # запуск, баннер, derenguh://-ссылка
│   ├── server.py           # жизненный цикл соединения
│   ├── faketls.py          # Fake-TLS: HMAC-аутентификация, ServerHello, рекорды
│   ├── compression.py      # потоковые zlib/brotli кодеки
│   ├── protocol.py         # контрольные кадры DerenguhProto
│   ├── relay.py            # ограниченный по памяти duplex-relay
│   ├── splice.py           # TCP Splice на реальный стриминг
│   ├── sni.py              # парсер SNI из ClientHello
│   ├── config.py           # env-конфигурация
│   ├── constants.py        # DC, SNI, wire-константы
│   ├── link.py             # секрет/ключ/ссылка (единый формат с клиентом)
│   └── reference_client.py # эталонный клиент = спецификация для портов
├── tests/                  # 22 теста, включая e2e с mock-DC и mock-сервисом
├── deploy/                 # Dockerfile, pterodactyl-egg, demo
└── requirements.txt
```

## Быстрый старт (без Docker)

```bash
cd DerenguhGram-Proxy
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # zlib входит в stdlib; brotli опционален

export SERVER_PORT=3183
export DERENGUH_PUBLIC_HOST=ваш.домен_или_IP
export DERENGUH_SECRET=$(python3 -c "from derenguh_proxy import generate_secret; print(generate_secret().hex())")
python3 -m derenguh_proxy
```

При запуске печатается порт, SNI и готовая ссылка:

```
derenguh://proxy?server=ваш.домен&port=3183&sni=music.yandex.ru&key=<base64url_key>
```

> Если `DERENGUH_SECRET` не задан, генерируется случайный — ссылка изменится после
> рестарта. Задайте переменную, чтобы ссылка была постоянной.

### Pterodactyl

1. Создайте сервер с лимитом памяти **128 МБ**, egg — Python Generic
   (или импортируйте `deploy/egg-derenguhgram-proxy.json`).
2. Startup command: `python3 -m derenguh_proxy`
3. Variables: `SERVER_PORT` = порт аллокации панели (панель выставляет сама),
   `DERENGUH_PUBLIC_HOST` = ваш IP/домен, `DERENGUH_SECRET` = 32-hex секрет.
4. Порт >1024, root не нужен. Логи и ссылка — в консоли панели.

### Docker

```bash
docker build -t derenguh-proxy -f deploy/Dockerfile .
docker run -d --name derenguh-proxy --memory=128m \
  -e SERVER_PORT=3183 -e DERENGUH_PUBLIC_HOST=example.org \
  -e DERENGUH_SECRET=<32hex> -p 3183:3183 derenguh-proxy
docker logs derenguh-proxy   # ссылка для клиента
```

## Конфигурация (переменные окружения)

| Переменная | Default | Назначение |
|---|---|---|
| `SERVER_PORT` / `PORT` | `3183` | Порт прослушивания (Pterodactyl: `SERVER_PORT`) |
| `SERVER_IP` | `0.0.0.0` | Адрес прослушивания |
| `DERENGUH_SECRET` | случайный | 32-hex или base64url (16 байт) |
| `DERENGUH_PUBLIC_HOST` | `your.server.host` | Хост в ссылке подключения |
| `DERENGUH_SNI` | `music.yandex.ru` | SNI по умолчанию в ссылке |
| `DERENGUH_ALLOWED_SNI` | список РФ-сервисов | Allowlist через запятую |
| `DERENGUH_CODEC` | `zlib` | Предпочитаемый кодек: `none`/`zlib`/`brotli` |
| `DERENGUH_MAX_CONN` | `64` | Лимит одновременных соединений |
| `DERENGUH_MASK` | `true` | TCP Splice для нераспознанных клиентов |
| `DERENGUH_MASK_HOST` | `music.yandex.ru` | Фолбэк-хост для splice |
| `DERENGUH_MASK_PORT` | `443` | Порт фолбэк-хоста |
| `DERENGUH_MASK_USE_SNI` | `true` | Splice на реальный IP из SNI сканера |
| `DERENGUH_PREFER_IPV6` | `false` | Предпочитать IPv6 при подключении к DC |
| `DERENGUH_IGNORE_TIME_SKEW` | `false` | Принимать клиентов с плохими часами |
| `DERENGUH_IDLE_TIMEOUT` | `300` | Таймаут неактивности, сек |
| `DERENGUH_LOG_LEVEL` | `info` | `debug`/`info`/`warning` |

## Тесты и демо

```bash
python3 -m unittest discover -s tests -v   # 22 теста, внешняя сеть не нужна
python3 deploy/demo_local.py               # live-демо + замер памяти (mock-DC)
```

Демо поднимает настоящий сервер с локальным echo-DC, гоняет 200 одновременных
соединений (50 МБ суммарно) и печатает пиковый RSS.

Проверка живого сервера эталонным клиентом:

```bash
python3 -m derenguh_proxy.reference_client --link 'derenguh://proxy?server=...&port=...&sni=...&key=...'
```

## Протокол

Полная спецификация — [docs/PROTOCOL.md](docs/PROTOCOL.md). Формат секрета един для
клиента и сервера: 16 байт, в ссылке — base64url без padding, в конфиге — hex или
base64url.

## Замечания по безопасности

- Секрет в ссылке = право пользоваться прокси. Передавайте ссылку по защищённому каналу.
- Fake-TLS не является настоящим TLS: конфиденциальность обеспечивает MTProto
  (obfuscated-2 + слой MTProto), маскировка — только от DPI/активного пробинга.
- Используйте этот прокси только для доступа к Telegram в сетях, где вы имеете
  право применять средства обхода блокировок.

## Лицензия

MIT (как и базовый mtprotoproxy). См. [LICENSE](LICENSE).
