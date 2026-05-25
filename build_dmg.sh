#!/usr/bin/env bash
set -euo pipefail

# Build an unsigned macOS DMG for RF Bridge.
# Requires create-dmg: brew install create-dmg

APP="dist/RF Bridge.app"
DMG_DIR="dist/dmg"
DMG_NAME="RF-Bridge-v1.8-macOS.dmg"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This DMG script must be run on macOS." >&2
  exit 1
fi

if [[ ! -d "$APP" ]]; then
  echo "Missing $APP. Run ./build_app.sh first." >&2
  exit 1
fi

if ! command -v create-dmg >/dev/null 2>&1; then
  echo "Missing create-dmg. Install with: brew install create-dmg" >&2
  exit 1
fi

rm -rf "$DMG_DIR" "dist/$DMG_NAME"
mkdir -p "$DMG_DIR"
cp -R "$APP" "$DMG_DIR/"

create-dmg \
  --volname "RF Bridge v1.8" \
  --window-pos 200 120 \
  --window-size 620 420 \
  --icon-size 110 \
  --icon "RF Bridge.app" 160 190 \
  --app-drop-link 460 190 \
  "dist/$DMG_NAME" \
  "$DMG_DIR"

echo "Created dist/$DMG_NAME"
