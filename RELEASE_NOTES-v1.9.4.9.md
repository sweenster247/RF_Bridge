# RF Bridge v1.9.4.9 — tinySA Serial Diagnostics

This patch adds a standalone tinySA diagnostic utility so serial communication issues can be inspected outside the full RF Bridge UI.

## Added
- `tinysa_diag.py` convenience diagnostic script
- `scripts/tinysa_diag.py` raw serial diagnostic helper
- Raw output capture for:
  - `version`
  - `frequencies`
  - `data 1`
- CR, LF, and CRLF line-ending tests
- Numeric parse counts and raw response previews

## Notes
No functional UI changes were made from v1.9.4.8. This release is intended to capture the exact tinySA serial responses before making another communication-path change.

## Usage

```bash
python3 tinysa_diag.py
```

Or force a port:

```bash
python3 tinysa_diag.py --port /dev/cu.usbmodem4001
```
