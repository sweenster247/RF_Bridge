# RF Bridge v1.9.5.6

This patch focuses on tinySA serial stability after v1.9.5 UI updates.

## Fixed
- Replaced the UI worker command read path with the diagnostic-proven serial capture method.
- Kept tinySA scan reads locked to `data 1`.
- Improved startup reliability when the tinySA USB serial device appears before the command console is fully responsive.

## Notes
This build preserves the v1.9.5 sidebar/layout polish while targeting the connection issue where RF Bridge could detect the tinySA but receive no frequency points.
