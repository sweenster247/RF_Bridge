#!/usr/bin/env bash
set -euo pipefail
python3 -m PyInstaller rf-bridge.spec --clean --noconfirm
