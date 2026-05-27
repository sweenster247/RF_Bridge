# RF Bridge v1.9.5.7

## Added
- Added `--debug-serial` mode for tinySA troubleshooting.
- Added TX/RX command logging, byte counts, response previews, and serial open/close lifecycle messages.

## Notes
Run with:

```bash
python3 rf-bridge.py --ui --debug-serial
```

This build is intended to diagnose the current tinySA startup issue without changing UI behavior.
