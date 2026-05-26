#!/usr/bin/env bash
set -euo pipefail

# Build RF Bridge release artifacts for macOS Apple Silicon.
# Outputs:
#   dist/releases/RF-Bridge-v{version}-macOS-arm64.dmg
#   dist/releases/RF-Bridge-v{version}-macOS-arm64.zip
#
# Requirements:
#   python3 -m pip install -r requirements.txt
#   brew install create-dmg

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This release build script must be run on macOS." >&2
  exit 1
fi

VERSION=$(python3 - <<'PY'
from rf_bridge.version import __version__
print(__version__)
PY
)

APP_NAME="RF Bridge"
APP_PATH="dist/${APP_NAME}.app"
RELEASE_DIR="dist/releases"
STAGING_DIR="dist/dmg"
ARTIFACT_BASE="RF-Bridge-v${VERSION}-macOS-arm64"
DMG_PATH="${RELEASE_DIR}/${ARTIFACT_BASE}.dmg"
ZIP_PATH="${RELEASE_DIR}/${ARTIFACT_BASE}.zip"

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "Warning: this script is intended for macOS arm64 builds. Current architecture: $(uname -m)" >&2
fi

if ! command -v create-dmg >/dev/null 2>&1; then
  echo "Missing create-dmg. Install with: brew install create-dmg" >&2
  exit 1
fi

python3 -m pip install -r requirements.txt

if [[ ! -f "assets/rf-bridge.icns" || "assets/rf-bridge-icon-1024.png" -nt "assets/rf-bridge.icns" ]]; then
  ./scripts/create_icon.sh
fi

rm -rf build dist
mkdir -p "$RELEASE_DIR"

python3 -m PyInstaller rf-bridge.spec --clean --noconfirm

if [[ ! -d "$APP_PATH" ]]; then
  echo "Build failed: missing $APP_PATH" >&2
  exit 1
fi

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
cp -R "$APP_PATH" "$STAGING_DIR/"

create-dmg \
  --volname "RF Bridge v${VERSION}" \
  --window-pos 200 120 \
  --window-size 620 420 \
  --icon-size 110 \
  --icon "${APP_NAME}.app" 160 190 \
  --app-drop-link 460 190 \
  "$DMG_PATH" \
  "$STAGING_DIR"

# Zip the .app as an alternate distribution artifact.
# ditto preserves macOS bundle metadata better than plain zip.
rm -f "$ZIP_PATH"
ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"

echo ""
echo "Release artifacts created:"
echo "  $DMG_PATH"
echo "  $ZIP_PATH"
echo ""
echo "Unsigned build note: macOS may require right-click > Open on first launch."
