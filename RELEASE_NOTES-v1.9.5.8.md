# RF Bridge v1.9.5.8

## Fixed
- Restored the confirmed-working v1.9.4.10 tinySA prompt-based serial read path.
- Removed the newer idle-window serial reader from the live UI/CLI command path.

## Kept
- Preserved the `--debug-serial` TX/RX logging added in v1.9.5.7.
- Preserved the v1.9.5 UI/sidebar/layout polish and graph stability fixes.

## Notes
This build is intended to recover tinySA UI/CLI connection behavior while keeping the newer troubleshooting logs available.
