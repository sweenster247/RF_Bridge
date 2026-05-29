#!/usr/bin/env bash
set -euo pipefail

# Build only the unsigned macOS DMG for RF Bridge.
# For both DMG + zipped app release artifacts, use ./build_release.sh.

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This DMG script must be run on macOS." >&2
  exit 1
fi

export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/private/tmp/rf_bridge_pycache}"

VERSION=$(python3 - <<'PY'
from rf_bridge.version import __version__
print(__version__)
PY
)

APP="dist/RF Bridge.app"
DMG_DIR="dist/dmg"
RELEASE_DIR="dist/releases"
DMG_NAME="RF-Bridge-v${VERSION}-macOS-arm64.dmg"

if [[ ! -d "$APP" ]]; then
  echo "Missing $APP. Run ./build_app.sh first." >&2
  exit 1
fi

if ! command -v create-dmg >/dev/null 2>&1; then
  echo "Missing create-dmg. Install with: brew install create-dmg" >&2
  exit 1
fi

mkdir -p "$RELEASE_DIR"
rm -rf "$DMG_DIR" "$RELEASE_DIR/$DMG_NAME"
mkdir -p "$DMG_DIR"
cp -R "$APP" "$DMG_DIR/"

create-dmg \
  --volname "RF Bridge v${VERSION}" \
  --window-pos 200 120 \
  --window-size 620 420 \
  --icon-size 110 \
  --icon "RF Bridge.app" 160 190 \
  --app-drop-link 460 190 \
  "$RELEASE_DIR/$DMG_NAME" \
  "$DMG_DIR"

echo "Created $RELEASE_DIR/$DMG_NAME"
