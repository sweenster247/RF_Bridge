# RF Bridge v1.9.4.6 — tinySA Connect Regression Fix

This patch release restores the more conservative tinySA startup command flow used by earlier working builds.

## Fixed

- Fixed a connection regression where some tinySA units returned no frequency points during startup.
- Removed aggressive pause/resume startup handling added in recent v1.9.4 patches.
- Restored the simple, proven frequency read behavior from the v1.8 connection path.
- Kept retry handling so the UI remains usable if the device is not immediately ready.

## Notes

If the app starts but the tinySA does not immediately return data, the UI remains open so the device can be reconnected or retried manually.
