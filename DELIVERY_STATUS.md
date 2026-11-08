# DerenguhGram delivery status

## Delivered
- Source/config archives (not installers): draft release `personal-2026-11-08`
  https://github.com/SiberiaFoxi/sssss/releases/tag/untagged-8596401ecb38dd58b5b5
- DerenguhGram-Proxy Python server: 23 tests passing, 200-conn demo RSS ~72.8 MB.

## In progress: real client binaries
Draft release `clients-v0.1.0`:
https://github.com/SiberiaFoxi/sssss/releases/tag/untagged-55aeab518cc76b708b10

CI builds official Telegram sources with the DerenguhGram overlay:
- Android release APK (afat, signed with upstream demo keystore) — workflow `build-android.yml`.
- Windows x64 EXE (official tdesktop prepare/configure recipe) — workflow `build-desktop.yml`.

No APK/EXE is claimed until the corresponding workflow succeeds and `apksigner verify` /
file inspection passes. Assets are uploaded only from successful build steps.

## Scope guardrails
- Ordinary media/log/cache export only. Protected and self-destructing media is not
  intercepted; sender privacy choices are respected.
- Public/demo API credentials and keystore are labelled as such; replace for any public
  distribution.
