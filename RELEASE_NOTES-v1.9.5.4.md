# RF Bridge v1.9.5.6

## Fixed
- Restored the known-good tinySA serial command path from v1.9.4.10.
- Hard-locked live scan reads to `data 1`.
- Removed aggressive serial retry/fallback behavior that could cause startup hangs or Python crashes.

## Retained
- v1.9.5 sidebar/logo/layout polish.
- Axis lock and cursor stability fixes.
- Capture overlay toggle stability fixes.
- Existing mic plot, capture overlay, profile, and build-release workflows.

## Notes
This patch prioritizes deterministic tinySA communication over smart retry logic. The intended tinySA command flow is now the boring/reliable path: `version`, `frequencies`, and `data 1`.
