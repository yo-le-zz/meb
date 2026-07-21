#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# build.sh — Compile Meb (Nuitka) et le package en .deb installable partout
#
# Usage :
#   ./scripts/build.sh [--arch amd64|arm64|armhf] [--output dist]
#
# Note sur les architectures :
#   Nuitka produit un binaire NATIF à la machine qui exécute la compilation.
#   Ce script ne fait PAS de cross-compilation : pour produire un .deb arm64,
#   il faut lancer ce script sur une machine (ou un environnement QEMU/Docker)
#   arm64. --arch ne change que l'étiquette Debian du paquet, pas l'architecture
#   réelle du binaire compilé.
# ---------------------------------------------------------------------------

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$ROOT_DIR/src/meb"
OUTPUT_DIR="$ROOT_DIR/dist"
ARCH_OVERRIDE=""

NAME="meb"
MAINTAINER="yolezz <yolezz@example.com>"
DESCRIPTION="Meb est un outil permettant de faire des .deb rapidement et clairement en CLI."

usage() {
  echo "Usage: $0 [--arch amd64|arm64|armhf] [--output DIR]"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --arch) ARCH_OVERRIDE="$2"; shift 2 ;;
    --output) OUTPUT_DIR="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Option inconnue : $1"; usage ;;
  esac
done

detect_arch() {
  case "$(uname -m)" in
    x86_64|amd64) echo "amd64" ;;
    aarch64|arm64) echo "arm64" ;;
    armv7l|armv6l) echo "armhf" ;;
    i386|i686) echo "i386" ;;
    *) echo "$(uname -m)" ;;
  esac
}

ARCH="${ARCH_OVERRIDE:-$(detect_arch)}"
VERSION=$(python3 -c "import sys; sys.path.insert(0, '$SRC_DIR'); from info import APP_VERSION; print(APP_VERSION)")

echo "==> Meb build.sh"
echo "    Version      : $VERSION"
echo "    Architecture : $ARCH (host: $(uname -m))"
echo "    Sortie       : $OUTPUT_DIR"

if [[ -n "$ARCH_OVERRIDE" && "$ARCH_OVERRIDE" != "$(detect_arch)" ]]; then
  echo "!! Attention : --arch=$ARCH_OVERRIDE demandé mais la machine est $(detect_arch)."
  echo "   Le binaire compilé restera natif $(detect_arch) ; seul le label du paquet change."
fi

command -v python3 >/dev/null || { echo "✘ python3 introuvable"; exit 1; }
command -v dpkg-deb >/dev/null || { echo "✘ dpkg-deb introuvable (paquet 'dpkg')"; exit 1; }

echo "==> Installation des dépendances ..."
if command -v uv >/dev/null; then
  (cd "$ROOT_DIR" && uv sync)
  RUN_PY() { uv run python "$@"; }
else
  python3 -m pip install --quiet --upgrade -e "$ROOT_DIR"
  RUN_PY() { python3 "$@"; }
fi

echo "==> Compilation avec Nuitka ..."
BUILD_TMP="$ROOT_DIR/build"
rm -rf "$BUILD_TMP"
mkdir -p "$BUILD_TMP"

RUN_PY -m nuitka \
  --standalone \
  --onefile \
  --output-dir="$BUILD_TMP" \
  --output-filename="meb" \
  --assume-yes-for-downloads \
  "$SRC_DIR/meb.py"

BINARY="$BUILD_TMP/meb"
if [[ ! -f "$BINARY" ]]; then
  echo "✘ Compilation échouée : binaire introuvable dans $BUILD_TMP"
  exit 1
fi
chmod +x "$BINARY"
echo "✔ Binaire compilé : $BINARY"

echo "==> Construction du paquet .deb ..."
PKG_DIR="$BUILD_TMP/${NAME}_${VERSION}_${ARCH}"
rm -rf "$PKG_DIR"

mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor"
mkdir -p "$PKG_DIR/usr/share/doc/$NAME"

cp "$BINARY" "$PKG_DIR/usr/bin/$NAME"
chmod 755 "$PKG_DIR/usr/bin/$NAME"

if [[ -d "$ROOT_DIR/assets/icons/hicolor" ]]; then
  cp -r "$ROOT_DIR/assets/icons/hicolor/." "$PKG_DIR/usr/share/icons/hicolor/"
fi
if [[ -f "$ROOT_DIR/assets/icons/meb.svg" ]]; then
  mkdir -p "$PKG_DIR/usr/share/icons/hicolor/scalable/apps"
  cp "$ROOT_DIR/assets/icons/meb.svg" "$PKG_DIR/usr/share/icons/hicolor/scalable/apps/meb.svg"
fi

cat > "$PKG_DIR/usr/share/applications/${NAME}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Meb
Comment=$DESCRIPTION
Exec=$NAME
Icon=$NAME
Terminal=true
Categories=Utility;Development;
EOF

cp "$ROOT_DIR/README.md" "$PKG_DIR/usr/share/doc/$NAME/README.md" 2>/dev/null || true
cp "$ROOT_DIR/LICENSE" "$PKG_DIR/usr/share/doc/$NAME/copyright" 2>/dev/null || true

INSTALLED_SIZE=$(du -sk "$PKG_DIR" | cut -f1)

cat > "$PKG_DIR/DEBIAN/control" <<EOF
Package: $NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Maintainer: $MAINTAINER
Installed-Size: $INSTALLED_SIZE
Description: $DESCRIPTION
EOF

mkdir -p "$OUTPUT_DIR"
DEB_FILE="$OUTPUT_DIR/${NAME}_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$PKG_DIR" "$DEB_FILE"

echo ""
echo "✔ Paquet généré : $DEB_FILE"
echo ""
echo "Installation :"
echo "  sudo dpkg -i $DEB_FILE"
echo "  # ou : sudo apt install ./$DEB_FILE"
echo ""
echo "Une fois installé, la commande est disponible partout :"
echo "  meb --help"