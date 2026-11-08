# DerenguhGram client integrations (pinned upstream overlays)

This directory contains the auditable overlay + patch scripts that turn the official
Telegram clients into DerenguhGram. CI fetches the exact upstream commits, applies the
overlay, builds real binaries and uploads them to the draft release `clients-v0.1.0`.

| Client | Upstream | Commit | Build |
|---|---|---|---|
| Android | DrKLO/Telegram 13.2.1 (7291) | `7be672ead283d022812d75c729d3a04dd4c2a2c6` | `:TMessagesProj_App:assembleAfatRelease` |
| Desktop | telegramdesktop/tdesktop 7.4.1 | `7381fb1df75d863eb3463fdddef57a2ac51f1d56` | official `win.bat skip-release silent qt6` + `configure.bat x64 … qt6` Release |

## What is integrated

- **DerenguhGram Proxy** as a real proxy type next to SOCKS5/HTTP/MTProto/WEB.
  - Android: `ProxySettings.Type.DERENGUH`, `derenguh://` links, persistence, and a
    bounded loopback SOCKS5→DerenguhProto bridge used by native tgnet (same pattern as
    upstream WEB proxy). Unknown/CDN DC endpoints fail closed.
  - Desktop: `MTP::ProxyData::Type::Derenguh`, native `AbstractSocket` transport with
    Fake-TLS + streaming zlib, correct DC selection from `protocolDcId`, proxy editor
    with SNI field, serialization, link import.
- **Privacy modes** wired into real request sites: Невидимка (presence), Нечиталка
  (readHistory/readDiscussion/readContents/mentions), Неписалка (setTyping/sendProgress).
- **ClanSecrets GUI** reachable from the main menu/settings: client logs, cache path/open,
  export of logs and ordinary downloaded media. Protected/self-destructing media is
  deliberately **not** bypassed; Telegram cache decryption is left to the official client.

## Credentials (public/demo, personal use)

- Android: upstream public `APP_ID=4` / `APP_HASH=014b35…`, upstream dummy release keystore
  (`android`/`androidkey`/`android`), applicationId `org.derenguhgram.personal`.
- Desktop: upstream nightly public `TDESKTOP_API_ID=611335` / hash from official `win.yml`.
  These are **not** private secrets and are unsuitable for mass distribution.

## Reproduce locally

```bash
git clone --recursive https://github.com/DrKLO/Telegram.git android && cd android
git checkout 7be672ead283d022812d75c729d3a04dd4c2a2c6 && git submodule update --init --recursive
python3 ../scripts/integrate_android.py .
python3 ../scripts/prepare_android_ci.py .
./gradlew :TMessagesProj_App:assembleAfatRelease
```

Desktop follows `docs/building-win.md` from the pinned tdesktop checkout, then
`python3 scripts/integrate_desktop.py <tdesktop>` before `configure.bat`.
