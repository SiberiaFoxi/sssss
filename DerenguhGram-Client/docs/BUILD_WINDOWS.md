# Сборка DerenguhGram-Client для Windows (.exe)

База — форк [telegramdesktop/tdesktop](https://github.com/telegramdesktop/tdesktop)
(C++, Qt, GPLv3). Модули DerenguhGram лежат в `desktop/src` и подключаются к сборке
tdesktop. Ниже — полный путь от чистого форка до `Telegram.exe` с нашими модулями.

> Актуальные требования upstream (ветка `dev`, ноябрь 2026): **Visual Studio 2026**,
> Windows SDK **10.0.26100.0**, **Python 3.10**, **Git**. Для x86/x64 используйте
> toolset `-vcvars_ver=14.44`. Сверяйтесь с
> [docs/building-win.md](https://github.com/telegramdesktop/tdesktop/blob/dev/docs/building-win.md).

## 1. Форк и credentials

1. Создайте форк `tdesktop` (например `DerenguhGram-Desktop`) на GitHub.
2. Получите `api_id` / `api_hash`: <https://my.telegram.org> → API development tools.
   Не используйте имя «Telegram» и стандартный логотип для публичного релиза.

## 2. Подготовка окружения

```bat
:: Пустая папка сборки, например D:\TBuild
mkdir D:\TBuild\ThirdParty D:\TBuild\Libraries
:: Установите VS 2026 (Desktop C++), SDK 10.0.26100.0, Python 3.10, Git.
:: Откройте терминал с окружением нужной архитектуры (x64):
%comspec% /k "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" -vcvars_ver=14.44
```

## 3. Клонирование и библиотеки

```bat
cd D:\TBuild
git clone --recursive https://github.com/<you>/DerenguhGram-Desktop.git tdesktop
tdesktop\Telegram\build\prepare\win.bat
```

`prepare\win.bat` соберёт Qt, OpenSSL, zlib и прочие зависимости в `Libraries`.
Наши модули используют именно эти bundled-библиотеки (Qt6, OpenSSL::Crypto, ZLIB).

## 4. Подключение модулей DerenguhGram

1. Скопируйте `desktop/` этого репозитория в форк, например в `tdesktop/Telegram/SourceFiles/derenguh/`
   (или держите как submodule и подключите путь).
2. В `tdesktop/Telegram/CMakeLists.txt` добавьте:
   ```cmake
   add_subdirectory(SourceFiles/derenguh derenguh)
   target_link_libraries(Telegram PRIVATE derenguh_desktop)
   ```
   (Если ваша раскладка иная — поправьте путь; цель `derenguh_desktop` описана в
   `desktop/CMakeLists.txt`.)
3. Примените точки интеграции из `docs/FORK_GUIDE.md` (новый тип прокси, пункт меню
   ClanSecrets, хуки приватности). Готовые иллюстративные патчи — в `desktop/patches/`.

## 5. Конфигурация и сборка

```bat
cd D:\TBuild\tdesktop\Telegram
configure.bat x64 -D TDESKTOP_API_ID=ВАШ_API_ID -D TDESKTOP_API_HASH=ВАШ_API_HASH
```

* Откройте `D:\TBuild\tdesktop\out\Telegram.slnx` в Visual Studio 2026.
* Выберите проект **Telegram**, конфигурация **Release**, соберите (Build → Build Telegram).
* Готовый `Telegram.exe` — в `D:\TBuild\tdesktop\out\Release`.

## 6. Проверка модуля прокси

Запустите сервер `DerenguhGram-Proxy`, вставьте `derenguh://`-ссылку в настройки прокси
клиента (новый тип «DerenguhGram Proxy»), выберите SNI и подключитесь. В окне
**ClanSecrets → Логи** должны появиться записи о рукопожатии и статусе прокси.

## Зависимости (системные)

| Компонент | Версия | Зачем |
|---|---|---|
| Visual Studio | 2026, toolset 14.44 (x64) | компилятор C++ |
| Windows SDK | 10.0.26100.0 | заголовки/либы Windows |
| Python | 3.10 | скрипты подготовки |
| Git | любая | submodule |
| Qt / OpenSSL / zlib | собираются `prepare\win.bat` | сеть, HMAC, сжатие |

> Полная пересборка зависимостей занимает время и место (~15–20 ГБ). Это нормальный
> процесс upstream-сборки; наши модули не добавляют тяжёлых зависимостей.
