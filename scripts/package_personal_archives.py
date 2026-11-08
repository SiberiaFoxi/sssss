#!/usr/bin/env python3
"""Package DerenguhGram personal/public-demo archives.

This produces three source/build-kit archives (not APK/EXE binaries) using
public upstream demo credentials, as requested for personal experiments:

  - DerenguhGram-Proxy-personal.zip
  - DerenguhGram-Android-personal.zip
  - DerenguhGram-Desktop-personal.zip

It also writes a combined convenience zip, release notes, and SHA256SUMS.txt.
The proxy demo secret is generated randomly at packaging time and is not
printed to stdout.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import shutil
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ANDROID_UPSTREAM_COMMIT = "7be672ead283d022812d75c729d3a04dd4c2a2c6"
ANDROID_API_ID = 4
ANDROID_API_HASH = "014b35b6184100b085b0d0572f9b5103"
DESKTOP_TEST_API_ID = 17349
DESKTOP_TEST_API_HASH = "344583e45741c457fe1862106095a5eb"

IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".mypy_cache", ".ruff_cache")


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def copytree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=IGNORE)


def copyfile(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def zipdir(src: Path, zip_path: Path, arcroot: str) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                z.write(p, arcroot + "/" + p.relative_to(src).as_posix())
    with zipfile.ZipFile(zip_path) as z:
        assert z.testzip() is None
        bad = [n for n in z.namelist() if "__pycache__" in n or n.endswith(".pyc")]
        assert not bad, bad


def fetch_android_upstream_file(rel: str, local_upstream: Path | None) -> bytes:
    if local_upstream is not None:
        return (local_upstream / rel).read_bytes()
    url = (
        "https://api.github.com/repos/DrKLO/Telegram/contents/"
        + rel
        + "?ref="
        + ANDROID_UPSTREAM_COMMIT
    )
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "derenguh-personal-packager",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    if data.get("encoding") != "base64" or "content" not in data:
        raise RuntimeError(f"unexpected GitHub contents response for {rel}")
    return base64.b64decode(data["content"])


APPLY_PERSONAL_CONFIG = """#!/usr/bin/env python3
\"\"\"Apply the personal/public demo config to a checked-out DrKLO/Telegram tree.

Usage:
  python3 scripts/apply_personal_config.py /path/to/Telegram

This copies the DerenguhGram overlay and public demo signing/Firebase/API values.
It does not compile an APK and does not integrate every privacy/proxy UI hook.
\"\"\"
from pathlib import Path
import re, shutil, sys

kit = Path(__file__).resolve().parents[1]
if len(sys.argv) != 2:
    raise SystemExit('usage: apply_personal_config.py /path/to/Telegram')
root = Path(sys.argv[1]).resolve()
if not (root / 'TMessagesProj').is_dir():
    raise SystemExit('not a Telegram Android checkout: ' + str(root))

src = kit / 'overlay/src/main/java/org/derenguhgram'
dst = root / 'TMessagesProj/src/main/java/org/derenguhgram'
shutil.copytree(src, dst, dirs_exist_ok=True)

shutil.copy2(kit / 'personal/release.keystore', root / 'TMessagesProj/config/release.keystore')
shutil.copy2(kit / 'personal/gradle.properties', root / 'gradle.properties')

for rel in ['TMessagesProj', 'TMessagesProj_App', 'TMessagesProj_AppHockeyApp',
            'TMessagesProj_AppHuawei', 'TMessagesProj_AppStandalone']:
    target = root / rel / 'google-services.json'
    if target.parent.is_dir():
        shutil.copy2(kit / 'personal/google-services.json', target)

bv = root / 'TMessagesProj/src/main/java/org/telegram/messenger/BuildVars.java'
text = bv.read_text(encoding='utf-8')
text = re.sub(r'public static int APP_ID = \\d+;', 'public static int APP_ID = 4;', text)
text = re.sub(r'public static String APP_HASH = "[^"]*";',
              'public static String APP_HASH = "014b35b6184100b085b0d0572f9b5103";', text)
text = re.sub(r'public static boolean SUPPORTS_PASSKEYS = true;',
              'public static boolean SUPPORTS_PASSKEYS = false;', text)
bv.write_text(text, encoding='utf-8')

print('Applied personal demo config to', root)
print('Next: register ClanSecretsActivity, wire proxy/privacy hooks, then ./gradlew :TMessagesProj_App:assembleAfatRelease')
"""


def public_credentials(proxy_secret: str) -> str:
    return f"""# Публичные / upstream demo-значения для ЛИЧНЫХ сборок

Это НЕ ваши секретные ключи и НЕ пригодно для массового релиза.

## Android — DrKLO/Telegram upstream dummy/public values
Источник: https://github.com/DrKLO/Telegram commit {ANDROID_UPSTREAM_COMMIT}

```text
APP_ID={ANDROID_API_ID}
APP_HASH={ANDROID_API_HASH}
RELEASE_KEY_PASSWORD=android
RELEASE_KEY_ALIAS=androidkey
RELEASE_STORE_PASSWORD=android
```

В архив Android добавлен upstream dummy `release.keystore` и dummy `google-services.json`.
Они публичные/тестовые: любой, у кого есть этот keystore, может подписывать совместимые обновления.
Для личной установки это допустимо как эксперимент, для публикации — замените на свои значения.

## Desktop — tdesktop upstream TEST ONLY values
Источник: https://github.com/telegramdesktop/tdesktop blob/dev/Telegram/SourceFiles/config.h

```text
TDESKTOP_API_ID={DESKTOP_TEST_API_ID}
TDESKTOP_API_HASH={DESKTOP_TEST_API_HASH}
```

Важно: upstream прямо помечает их как TEST ONLY и очень ограниченные Telegram API.
При логине возможны внутренние ошибки сервера. Для рабочей личной сборки лучше получить свои
api_id/api_hash на https://my.telegram.org, но в этот архив они не включены.

## Альтернативные публичные Android-значения
Иногда их пробуют и в desktop-сборках, но это не предназначено upstream для Desktop:

```text
PUBLIC_ANDROID_API_ID={ANDROID_API_ID}
PUBLIC_ANDROID_API_HASH={ANDROID_API_HASH}
```

## Proxy
Для proxy в личном архиве сгенерирован случайный demo-секрет:

```text
DERENGUH_SECRET={proxy_secret}
```

Если архив/ссылка когда-либо станут публичными, замените этот секрет.
"""


def build(out: Path, local_android_upstream: Path | None) -> None:
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    stage = out / "staging"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    proxy_secret = secrets.token_hex(16)
    creds = public_credentials(proxy_secret)

    # ---------------- Proxy ----------------
    proxy = stage / "DerenguhGram-Proxy"
    copytree(REPO / "DerenguhGram-Proxy", proxy)
    write(proxy / "PUBLIC-CREDENTIALS.md", creds)
    write(
        proxy / "personal/config.env",
        f"""# Личная demo-конфигурация DerenguhGram-Proxy.
# Замените DERENGUH_PUBLIC_HOST на IP/домен вашего сервера перед выдачей ссылки клиенту.
SERVER_PORT=3183
SERVER_IP=0.0.0.0
DERENGUH_PUBLIC_HOST=127.0.0.1
DERENGUH_SECRET={proxy_secret}
DERENGUH_SNI=music.yandex.ru
DERENGUH_ALLOWED_SNI=music.yandex.ru,vk.com,rutube.ru,yandex.ru,dzen.ru,vkvideo.ru
DERENGUH_CODEC=zlib
DERENGUH_MAX_CONN=64
DERENGUH_MASK=true
DERENGUH_MASK_HOST=music.yandex.ru
DERENGUH_MASK_PORT=443
DERENGUH_MASK_USE_SNI=true
DERENGUH_LOG_LEVEL=info
""",
    )
    write(
        proxy / "personal/START-HERE.ru.txt",
        """DerenguhGram-Proxy — личный архив с demo-секретом.

Запуск на Linux/Pterodactyl без root:
  1. Распакуйте архив.
  2. Загрузите переменные из personal/config.env в окружение или скопируйте их в .env.
  3. Замените DERENGUH_PUBLIC_HOST на внешний IP/домен, если клиент подключается не с этого же ПК.
  4. python3 -m derenguh_proxy

Сервер напечатает готовую ссылку derenguh://proxy?... .
Секрет в personal/config.env случайный, но если вы опубликуете архив — замените его.

Проверка:
  python3 -m unittest discover -s tests -v
""",
    )

    # ---------------- Android ----------------
    android = stage / "DerenguhGram-Android"
    android.mkdir(parents=True)
    write(android / "PUBLIC-CREDENTIALS.md", creds)
    write(
        android / "upstream.lock.json",
        json.dumps(
            {
                "upstream": "https://github.com/DrKLO/Telegram",
                "commit": ANDROID_UPSTREAM_COMMIT,
                "version_name": "13.2.1",
                "version_code": 7291,
                "note": "Personal build kit overlay; not a compiled APK.",
            },
            indent=2,
        )
        + "\n",
    )
    copytree(REPO / "DerenguhGram-Client/android", android / "overlay")
    copytree(REPO / "DerenguhGram-Client/shared", android / "shared")
    for name in ["PROTOCOL.md", "FORK_GUIDE.md", "PRIVACY_MODES.md", "CLANSECRETS.md", "BUILD_ANDROID.md"]:
        copyfile(REPO / "DerenguhGram-Client/docs" / name, android / "docs" / name)
    copyfile(REPO / "DerenguhGram-Client/LICENSE", android / "LICENSE")

    personal = android / "personal"
    personal.mkdir(parents=True, exist_ok=True)
    (personal / "release.keystore").write_bytes(
        fetch_android_upstream_file("TMessagesProj/config/release.keystore", local_android_upstream)
    )
    gs = json.loads(
        fetch_android_upstream_file("TMessagesProj_App/google-services.json", local_android_upstream)
    )
    for client in gs.get("client", []):
        info = client.get("client_info", {}).get("android_client_info", {})
        pkg = info.get("package_name", "")
        if pkg.startswith("org.telegram.messenger"):
            info["package_name"] = pkg.replace("org.telegram.messenger", "org.derenguhgram.personal", 1)
    write(personal / "google-services.json", json.dumps(gs, indent=2) + "\n")
    write(
        personal / "gradle.properties",
        """APP_VERSION_CODE=7291
APP_VERSION_NAME=13.2.1
APP_PACKAGE=org.derenguhgram.personal
IS_PRIVATE=false
RELEASE_KEY_PASSWORD=android
RELEASE_KEY_ALIAS=androidkey
RELEASE_STORE_PASSWORD=android
org.gradle.jvmargs=-Xmx8g -XX:MaxMetaspaceSize=1g
org.gradle.daemon=true
org.gradle.parallel=true
org.gradle.configureondemand=false
android.useAndroidX=true
android.enableJetifier=true
android.defaults.buildfeatures.buildconfig=true
android.enableR8.fullMode=true
android.r8.optimizedResourceShrinking=true
android.enableResourceOptimizations=true
org.gradle.tooling.parallel=true
""",
    )
    write(
        personal / "api.env",
        f"""DERENGUH_API_ID={ANDROID_API_ID}
DERENGUH_API_HASH={ANDROID_API_HASH}
DERENGUH_KEYSTORE_PASSWORD=android
DERENGUH_KEY_ALIAS=androidkey
DERENGUH_STORE_PASSWORD=android
""",
    )
    write(
        personal / "local.properties.example",
        """# Замените на путь к вашему Android SDK.
sdk.dir=/path/to/Android/Sdk
""",
    )
    write(android / "scripts/apply_personal_config.py", APPLY_PERSONAL_CONFIG)
    write(
        android / "scripts/fetch_upstream.sh",
        f"""#!/usr/bin/env bash
set -euo pipefail
# Fetch the pinned upstream source with submodules. This is large.
git clone --recursive https://github.com/DrKLO/Telegram.git upstream-telegram
cd upstream-telegram
git checkout {ANDROID_UPSTREAM_COMMIT}
git submodule update --init --recursive --depth=1
""",
    )
    write(
        android / ".github/workflows/android-personal-release.yml",
        """name: Android personal release (public demo values)
on:
  workflow_dispatch:
jobs:
  build:
    runs-on: ubuntu-24.04
    timeout-minutes: 360
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '17'
      - uses: android-actions/setup-android@v3
      - name: Install SDK/NDK
        run: sdkmanager "platforms;android-36" "build-tools;36.0.0" "ndk;27.2.12479018" "cmake;3.22.1"
      - name: Fetch upstream
        run: bash scripts/fetch_upstream.sh
      - name: Apply personal overlay/config
        run: python3 scripts/apply_personal_config.py upstream-telegram
      - name: Build release APK
        working-directory: upstream-telegram
        run: ./gradlew :TMessagesProj_App:assembleAfatRelease --no-daemon
      - uses: actions/upload-artifact@v4
        with:
          name: DerenguhGram-personal-release-apk
          path: upstream-telegram/TMessagesProj_App/build/outputs/apk/afat/release/*.apk
""",
    )
    write(
        android / "START-HERE.ru.txt",
        f"""DerenguhGram-Android — ЛИЧНЫЙ build-kit, НЕ готовый APK.

Внутри:
  overlay/       модули DerenguhGram (Kotlin) для Telegram Android
  personal/      публичные demo API_ID/API_HASH, dummy keystore, dummy google-services
  scripts/       получение upstream и применение личной конфигурации
  docs/          интеграция и сборка
  .github/       workflow для попытки release-сборки на GitHub Actions

Публичные значения:
  APP_ID={ANDROID_API_ID}
  APP_HASH={ANDROID_API_HASH}
  keystore: upstream dummy, пароль android, alias androidkey

Быстрый путь к исходникам:
  bash scripts/fetch_upstream.sh
  python3 scripts/apply_personal_config.py upstream-telegram
  cd upstream-telegram
  # завершите интеграцию по docs/FORK_GUIDE.md и docs/PRIVACY_MODES.md
  ./gradlew :TMessagesProj_App:assembleAfatRelease

Это не массовый релиз: dummy keystore и google-services публичные, push может не работать,
а интеграция модулей ещё требует проверки на устройстве.
""",
    )

    # ---------------- Desktop ----------------
    desktop = stage / "DerenguhGram-Desktop"
    desktop.mkdir(parents=True)
    write(desktop / "PUBLIC-CREDENTIALS.md", creds)
    copytree(REPO / "DerenguhGram-Client/desktop", desktop / "module")
    copytree(REPO / "DerenguhGram-Client/shared", desktop / "shared")
    for name in ["PROTOCOL.md", "FORK_GUIDE.md", "PRIVACY_MODES.md", "CLANSECRETS.md", "BUILD_WINDOWS.md"]:
        copyfile(REPO / "DerenguhGram-Client/docs" / name, desktop / "docs" / name)
    copyfile(REPO / "DerenguhGram-Client/LICENSE", desktop / "LICENSE")
    write(
        desktop / "personal/api.env",
        f"""# tdesktop upstream TEST ONLY values. Very limited; login may fail.
TDESKTOP_API_ID={DESKTOP_TEST_API_ID}
TDESKTOP_API_HASH={DESKTOP_TEST_API_HASH}

# Alternative public upstream Android values (experiments only, not intended for Desktop):
PUBLIC_ANDROID_API_ID={ANDROID_API_ID}
PUBLIC_ANDROID_API_HASH={ANDROID_API_HASH}
""",
    )
    write(
        desktop / "personal/configure-test-only.bat",
        f"""@echo off
REM Run from BuildPath\\tdesktop\\Telegram after integrating the DerenguhGram module.
configure.bat x64 -D TDESKTOP_API_ID={DESKTOP_TEST_API_ID} -D TDESKTOP_API_HASH={DESKTOP_TEST_API_HASH}
""",
    )
    write(
        desktop / "personal/configure-public-android.bat",
        f"""@echo off
REM Experimental: public upstream Android values, not intended by upstream for Desktop.
configure.bat x64 -D TDESKTOP_API_ID={ANDROID_API_ID} -D TDESKTOP_API_HASH={ANDROID_API_HASH}
""",
    )
    write(
        desktop / "START-HERE.ru.txt",
        f"""DerenguhGram-Desktop — ЛИЧНЫЙ build-kit, НЕ готовый EXE.

Внутри:
  module/    C++/Qt-модули DerenguhGram для tdesktop
  personal/  публичные/test API_ID/API_HASH и примеры configure.bat
  docs/      интеграция и сборка Windows
  shared/    тестовые векторы протокола

По умолчанию использованы tdesktop TEST ONLY значения:
  TDESKTOP_API_ID={DESKTOP_TEST_API_ID}
  TDESKTOP_API_HASH={DESKTOP_TEST_API_HASH}

Upstream предупреждает: они очень ограничены, при логине возможны ошибки сервера.
Для рабочей личной сборки лучше получить свои api_id/api_hash, но вы попросили публичные,
поэтому ваши личные ключи сюда не включены.

Сборка:
  1. Склонируйте полный форк tdesktop с субмодулями.
  2. Интегрируйте module/ по docs/FORK_GUIDE.md и docs/BUILD_WINDOWS.md.
  3. Запустите personal/configure-test-only.bat (или experimental public-android вариант).
  4. Соберите Telegram.slnx в Visual Studio.
""",
    )

    # ---------------- Zip packages ----------------
    packages = [
        (proxy, out / "DerenguhGram-Proxy-personal.zip", "DerenguhGram-Proxy"),
        (android, out / "DerenguhGram-Android-personal.zip", "DerenguhGram-Android"),
        (desktop, out / "DerenguhGram-Desktop-personal.zip", "DerenguhGram-Desktop"),
    ]
    for src, zpath, rootname in packages:
        zipdir(src, zpath, rootname)

    write(
        out / "RELEASE-NOTES.ru.md",
        f"""# DerenguhGram — личные архивы с публичными demo-значениями

Три архива:
1. `DerenguhGram-Proxy-personal.zip` — исходники proxy + личная demo-конфигурация.
2. `DerenguhGram-Android-personal.zip` — Android build-kit: модули, публичные APP_ID/APP_HASH, dummy keystore/google-services, скрипты и CI workflow. **Не APK.**
3. `DerenguhGram-Desktop-personal.zip` — Desktop build-kit: C++/Qt-модули и публичные/test API_ID/API_HASH. **Не EXE.**

Использованы публичные/upstream значения:
- Android: `APP_ID={ANDROID_API_ID}`, `APP_HASH={ANDROID_API_HASH}`, dummy keystore `android/androidkey/android`.
- Desktop: tdesktop TEST ONLY `TDESKTOP_API_ID={DESKTOP_TEST_API_ID}`, `TDESKTOP_API_HASH={DESKTOP_TEST_API_HASH}`.
- Proxy: случайный demo-секрет в `personal/config.env`.

Предупреждения:
- Это для личных экспериментов, не для массового релиза.
- Dummy keystore публичный: не используйте для доверенных обновлений.
- Desktop TEST ONLY ключи ограничены Telegram API; логин может не работать.
- Android/Desktop архивы пока не являются собранными клиентами; интеграция и сборка требуют проверки.
""",
    )

    with zipfile.ZipFile(out / "DerenguhGram-3-personal-archives.zip", "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for _, zpath, _ in packages:
            z.write(zpath, zpath.name)
        z.write(out / "RELEASE-NOTES.ru.md", "RELEASE-NOTES.ru.md")

    checksums = []
    for p in sorted(out.glob("*.zip")):
        checksums.append(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name)
    write(out / "SHA256SUMS.txt", "\n".join(checksums) + "\n")

    print("Generated archives:")
    for p in sorted(out.glob("*.zip")):
        print(p.name, p.stat().st_size)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=REPO / "delivery")
    ap.add_argument(
        "--android-upstream",
        type=Path,
        default=None,
        help="Optional local DrKLO/Telegram checkout to read dummy keystore/google-services from.",
    )
    args = ap.parse_args()
    build(args.out, args.android_upstream)


if __name__ == "__main__":
    main()
