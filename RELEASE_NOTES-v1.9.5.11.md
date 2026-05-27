# RF Bridge v1.9.5.11

## Fixed
- Removed blocking prompt reads from the tinySA command path.
- Removed serial flush calls that could stall on some USB serial sessions.
- Added a write timeout so serial writes fail instead of freezing the app.

## Notes
tinySA commands now use bounded diagnostic-style reads with CR, LF, and CRLF line endings.
