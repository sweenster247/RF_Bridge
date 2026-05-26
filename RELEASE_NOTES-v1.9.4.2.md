# RF Bridge v1.9.4.2

Patch release focused on cleaner application exit behavior.

## Fixed
- Improved Python/Qt shutdown handling when closing RF Bridge.
- Stops the scan worker before the app exits.
- Waits briefly for the worker thread to close cleanly.
- Suppresses shutdown-time serial scan errors.
- Keeps v1.9.4.1 UI/layout, overlay controls, and expanded marker color options intact.

## Build

```bash
./build_release.sh
```

Expected artifacts:

```text
RF-Bridge-v1.9.4.2-macOS-arm64.dmg
RF-Bridge-v1.9.4.2-macOS-arm64.zip
```
