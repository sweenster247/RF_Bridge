#!/usr/bin/env bash
set -euo pipefail

# Build only the unsigned RF Bridge.app bundle.
# For release artifacts, use ./build_release.sh.

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This build script must be run on macOS." >&2
  exit 1
fi

export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/private/tmp/rf_bridge_pycache}"

VERSION=$(python3 - <<'PY'
from rf_bridge.version import __version__
print(__version__)
PY
)

python3 -m pip install -r requirements.txt

if [[ ! -f "assets/rf-bridge.icns" || "assets/rf-bridge-icon-1024.png" -nt "assets/rf-bridge.icns" ]]; then
  ./scripts/create_icon.sh
fi

python3 -m PyInstaller rf-bridge.spec --clean --noconfirm

echo ""
echo "Build complete: dist/RF Bridge.app"
echo "Version: $VERSION"
echo "Because this app is unsigned, macOS may require right-click > Open on first launch."
