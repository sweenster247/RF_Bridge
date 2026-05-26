# RF Bridge v1.9.4.5

RF Bridge v1.9.4.5 is a tinySA connection reliability patch release.

## Fixed

- Improved startup/connect behavior when the tinySA is slow to return its frequency table.
- Added pause/read/resume retry handling during frequency range initialization.
- Prevented transient empty frequency reads from blocking the app with modal warning dialogs.
- Keeps the main UI open so capture overlays, profiles, and manual reconnect remain usable even if the device is not ready.

## Retained

- Profile workflows
- Multi-capture overlays
- Mic Plot markers
- Help/About menu
- Unified release build script
- Dark logo-based app icon

## Build

```bash
./build_release.sh
```

Expected artifacts:

```text
dist/releases/RF-Bridge-v1.9.4.5-macOS-arm64.dmg
dist/releases/RF-Bridge-v1.9.4.5-macOS-arm64.zip
```
