# RF Bridge v1.9.5.10

## Fixed
- Added a tinySA command fallback when the v1.9.4.10 prompt-based read path returns no bytes.
- The fallback uses the same read-window approach and CR/LF/CRLF command ending checks as the standalone diagnostic helper.

## Notes
This build keeps the v1.9.5.9 UI auto-connect fix and should provide better logs when launched with `--debug-serial`.
