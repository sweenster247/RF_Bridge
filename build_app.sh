#!/usr/bin/env bash
set -euo pipefail

# Build the unsigned macOS RF Bridge.app bundle.
# Run from the project root on macOS.

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This build script must be run on macOS." >&2
  exit 1
fi

python3 -m pip install -r requirements.txt

if [[ ! -f "assets/rf-bridge.icns" ]]; then
  ./scripts/create_icon.sh
fi

python3 -m PyInstaller rf-bridge.spec --clean --noconfirm

echo ""
echo "Build complete: dist/RF Bridge.app"
echo "Because this app is unsigned, macOS may require right-click > Open on first launch."
