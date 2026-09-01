#!/usr/bin/env bash
# Build SpectroRB.app with a self-contained Python runtime inside the bundle.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="$ROOT/build"
DIST="$ROOT/dist"
APP="$DIST/SpectroRB.app"

PBS_TAG="${PBS_TAG:-20260825}"
PY_VERSION="${PY_VERSION:-3.12.14}"
ARCH="$(uname -m)"
case "$ARCH" in
  arm64) PBS_ARCH="aarch64" ;;
  x86_64) PBS_ARCH="x86_64" ;;
  *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac
PBS_FILE="cpython-${PY_VERSION}+${PBS_TAG}-${PBS_ARCH}-apple-darwin-install_only.tar.gz"
PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/${PBS_FILE}"

echo "==> Building Swift app"
(cd "$ROOT/app" && swift build -c release)
SWIFT_BIN="$ROOT/app/.build/release/SpectroRB"

echo "==> Preparing bundle"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$SWIFT_BIN" "$APP/Contents/MacOS/SpectroRB"
cp "$ROOT/app/Resources/Info.plist" "$APP/Contents/Info.plist"

echo "==> Fetching standalone Python ($PBS_FILE)"
mkdir -p "$BUILD/cache"
if [[ ! -f "$BUILD/cache/$PBS_FILE" ]]; then
  curl -fL --progress-bar -o "$BUILD/cache/$PBS_FILE" "$PBS_URL"
fi

echo "==> Installing Python runtime into the bundle"
rm -rf "$BUILD/python"
mkdir -p "$BUILD/python"
tar -xzf "$BUILD/cache/$PBS_FILE" -C "$BUILD/python" --strip-components=1
cp -R "$BUILD/python" "$APP/Contents/Resources/python"

BUNDLED_PY="$APP/Contents/Resources/python/bin/python3"
echo "==> Installing spectro-rb and dependencies"
"$BUNDLED_PY" -m pip install --quiet --upgrade pip
"$BUNDLED_PY" -m pip install --quiet "$ROOT"

echo "==> Writing relocatable launcher"
cat > "$APP/Contents/Resources/python/bin/spectro-rb" <<'LAUNCHER'
#!/bin/sh
# Relocatable launcher: always uses the interpreter next to this script.
DIR=$(cd "$(dirname "$0")" && pwd)
exec "$DIR/python3" -m spectro_rb.cli "$@"
LAUNCHER
chmod +x "$APP/Contents/Resources/python/bin/spectro-rb"

echo "==> Trimming runtime"
rm -rf "$APP/Contents/Resources/python/lib/python3.12/test" \
       "$APP/Contents/Resources/python/lib/python3.12/idlelib" \
       "$APP/Contents/Resources/python/lib/python3.12/tkinter" \
       "$APP/Contents/Resources/python/share/man" || true
find "$APP/Contents/Resources/python" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo "==> Signing (ad-hoc)"
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || \
  echo "    (ad-hoc signing failed; the app will still run locally)"

echo "==> Smoke test"
"$APP/Contents/Resources/python/bin/spectro-rb" doctor --json >/dev/null

SIZE=$(du -sh "$APP" | cut -f1)
echo
echo "Built $APP ($SIZE)"
echo "Run it with: open \"$APP\""
