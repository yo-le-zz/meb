#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# build.sh — Compile Meb (Nuitka) et génère les paquets .deb amd64 + arm64
#
# Usage :
#   ./scripts/build.sh [--arch amd64|arm64|all] [--output dist]
#
# Fonctionnement :
#   Nuitka produit un binaire NATIF à l'architecture qui exécute la
#   compilation. Pour obtenir des binaires amd64 ET arm64 depuis une seule
#   machine, ce script compile chaque architecture dans un conteneur Docker
#   dédié (--platform linux/amd64 / linux/arm64), en s'appuyant sur QEMU
#   (via binfmt_misc / docker-buildx, déjà configuré sur la machine) pour
#   émuler l'architecture cible pendant la compilation.
#
#   Le packaging .deb (dpkg-deb) se fait ensuite côté hôte, à partir du
#   binaire compilé dans le conteneur — dpkg-deb n'a pas besoin d'émulation
#   puisqu'il ne fait qu'assembler des fichiers.
#
# Reprise / résilience :
#   - Une architecture déjà compilée (son .deb existe dans le dossier de
#     sortie) est SAUTÉE automatiquement — relancer le script après une
#     coupure ne recompile que ce qui manque. --force pour tout recompiler.
#   - Pendant la compilation Docker/QEMU (longue et silencieuse, surtout en
#     arm64 émulé), le script affiche un signe de vie régulier au lieu de
#     paraître figé, et abandonne proprement après --timeout secondes
#     (5400 par défaut) plutôt que de rester bloqué indéfiniment.
#
# Prérequis sur la machine hôte :
#   - docker (avec le support --platform, donc buildx installé)
#   - binfmt_misc / qemu-user-static enregistré pour les architectures
#     étrangères, ex :
#       docker run --privileged --rm tonistiigi/binfmt --install all
# ---------------------------------------------------------------------------

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$ROOT_DIR/src/meb"
OUTPUT_DIR="$ROOT_DIR/dist"
ARCH_OVERRIDE="all"
FORCE_REBUILD=0
BUILD_TIMEOUT=5400   # 90 min par arch — QEMU (surtout arm64) est lent, on ne bloque pas indéfiniment
HEARTBEAT_INTERVAL=20 # secondes entre deux messages "toujours en cours"

NAME="meb"
MAINTAINER="yolezz <yolezz@example.com>"
DESCRIPTION="Meb est un outil permettant de faire des .deb rapidement et clairement en CLI."
HOMEPAGE="https://github.com/yo-le-zz/meb"
DOCKER_IMAGE="python:3.13-slim"

usage() {
  echo "Usage: $0 [--arch amd64|arm64|all] [--output DIR] [--force] [--timeout SECONDS]"
  echo ""
  echo "  --arch      Architecture(s) à compiler (défaut : all = amd64 + arm64)"
  echo "  --output    Dossier de sortie des .deb (défaut : dist/)"
  echo "  --force     Recompile même si un .deb existe déjà pour cette version/arch"
  echo "  --timeout   Délai max par architecture en secondes avant abandon (défaut : 5400)"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --arch) ARCH_OVERRIDE="$2"; shift 2 ;;
    --output) OUTPUT_DIR="$2"; shift 2 ;;
    --force) FORCE_REBUILD=1; shift ;;
    --timeout) BUILD_TIMEOUT="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Option inconnue : $1"; usage ;;
  esac
done

case "$ARCH_OVERRIDE" in
  amd64) ARCHS=(amd64) ;;
  arm64) ARCHS=(arm64) ;;
  all)   ARCHS=(amd64 arm64) ;;
  *) echo "✘ --arch invalide : $ARCH_OVERRIDE (amd64|arm64|all)"; exit 1 ;;
esac

declare -A PLATFORM_MAP=( [amd64]="linux/amd64" [arm64]="linux/arm64" )

VERSION=$(python3 -c "import sys; sys.path.insert(0, '$SRC_DIR'); from info import APP_VERSION; print(APP_VERSION)")

echo "==> Meb build.sh"
echo "    Version      : $VERSION"
echo "    Architectures: ${ARCHS[*]}"
echo "    Sortie       : $OUTPUT_DIR"

command -v docker >/dev/null || { echo "✘ docker introuvable"; exit 1; }
command -v dpkg-deb >/dev/null || { echo "✘ dpkg-deb introuvable (paquet 'dpkg')"; exit 1; }

mkdir -p "$OUTPUT_DIR"

already_built() {
  local arch="$1"
  local deb_file="$OUTPUT_DIR/${NAME}_${VERSION}_${arch}.deb"
  [[ -f "$deb_file" && "$FORCE_REBUILD" -eq 0 ]]
}

# Exécute une commande en tâche de fond, affiche un signe de vie régulier
# (pour ne jamais avoir l'impression que le script est figé), et tue le
# processus s'il dépasse BUILD_TIMEOUT secondes au lieu de rester bloqué
# indéfiniment.
run_with_heartbeat() {
  local label="$1"; shift
  local start_ts elapsed last_heartbeat pid rc

  "$@" &
  pid=$!

  start_ts=$(date +%s)
  last_heartbeat=$start_ts

  while kill -0 "$pid" 2>/dev/null; do
    sleep 2
    local now
    now=$(date +%s)
    elapsed=$((now - start_ts))

    if (( elapsed >= BUILD_TIMEOUT )); then
      echo ""
      echo "✘ [$label] Timeout après ${elapsed}s — arrêt du conteneur (--timeout pour ajuster)."
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      return 124
    fi

    if (( now - last_heartbeat >= HEARTBEAT_INTERVAL )); then
      echo "   ... [$label] compilation toujours en cours (${elapsed}s écoulées, PID $pid)"
      last_heartbeat=$now
    fi
  done

  rc=0
  wait "$pid" || rc=$?
  return $rc
}

ensure_platform_support() {
  local arch="$1"
  local platform="${PLATFORM_MAP[$arch]}"

  # x86_64 natif n'a besoin d'aucune émulation
  if [[ "$arch" == "amd64" && "$(uname -m)" == "x86_64" ]]; then
    return 0
  fi

  if docker run --rm --platform "$platform" "$DOCKER_IMAGE" true >/dev/null 2>&1; then
    return 0
  fi

  echo "!! [$arch] L'émulation QEMU ($platform) ne fonctionne pas (exec format error)."
  echo "   Tentative d'installation automatique des handlers binfmt (tonistiigi/binfmt) ..."
  if ! docker run --privileged --rm tonistiigi/binfmt --install all >/dev/null 2>&1; then
    echo "✘ [$arch] Échec de l'installation automatique de binfmt."
    echo "   Lance manuellement :"
    echo "     docker run --privileged --rm tonistiigi/binfmt --install all"
    echo "   puis relance ./scripts/build.sh"
    exit 1
  fi

  if docker run --rm --platform "$platform" "$DOCKER_IMAGE" true >/dev/null 2>&1; then
    echo "✔ [$arch] Émulation QEMU opérationnelle."
    return 0
  fi

  echo "✘ [$arch] L'émulation $platform ne fonctionne toujours pas après installation de binfmt."
  echo "   Vérifie que qemu-user-static et binfmt-support sont bien installés sur l'hôte, puis :"
  echo "     docker run --privileged --rm tonistiigi/binfmt --install all"
  exit 1
}

compile_in_docker() {
  local arch="$1"
  local platform="${PLATFORM_MAP[$arch]}"
  local build_tmp="$ROOT_DIR/build/$arch"

  echo ""
  echo "==> [$arch] Compilation via Docker ($platform, image $DOCKER_IMAGE) ..."
  rm -rf "$build_tmp"
  mkdir -p "$build_tmp"

  local rc=0
  run_with_heartbeat "$arch" docker run --rm \
    --platform "$platform" \
    -v "$ROOT_DIR":/workspace \
    -w /workspace \
    -e PIP_DISABLE_PIP_VERSION_CHECK=1 \
    -e DEBIAN_FRONTEND=noninteractive \
    "$DOCKER_IMAGE" \
    bash -lc "
      set -euo pipefail
      apt-get update -qq
      apt-get install -y -qq --no-install-recommends build-essential ccache patchelf gcc ca-certificates >/dev/null
      pip install --quiet --upgrade pip uv
      uv sync --quiet
      uv run python -m nuitka \
        --standalone \
        --onefile \
        --output-dir=build/$arch \
        --output-filename=meb \
        --assume-yes-for-downloads \
        src/meb/meb.py
    " || rc=$?

  if [[ "$rc" -eq 124 ]]; then
    echo "✘ [$arch] Compilation abandonnée (timeout). Relance avec --timeout <secondes> pour laisser plus de temps,"
    echo "   ou relance simplement ./scripts/build.sh : les architectures déjà terminées seront sautées."
    return 124
  elif [[ "$rc" -ne 0 ]]; then
    echo "✘ [$arch] La compilation Docker a échoué (code $rc)."
    return "$rc"
  fi

  local binary="$build_tmp/meb"
  if [[ ! -f "$binary" ]]; then
    echo "✘ [$arch] Compilation échouée : binaire introuvable dans $build_tmp"
    return 1
  fi
  chmod +x "$binary"
  echo "✔ [$arch] Binaire compilé : $binary"
}

package_deb() {
  local arch="$1"
  local build_tmp="$ROOT_DIR/build/$arch"
  local binary="$build_tmp/meb"

  echo "==> [$arch] Construction du paquet .deb ..."
  local pkg_dir="$build_tmp/${NAME}_${VERSION}_${arch}"
  rm -rf "$pkg_dir"

  mkdir -p "$pkg_dir/DEBIAN"
  mkdir -p "$pkg_dir/usr/bin"
  mkdir -p "$pkg_dir/usr/share/applications"
  mkdir -p "$pkg_dir/usr/share/icons/hicolor"
  mkdir -p "$pkg_dir/usr/share/doc/$NAME"

  cp "$binary" "$pkg_dir/usr/bin/$NAME"
  chmod 755 "$pkg_dir/usr/bin/$NAME"

  if [[ -d "$ROOT_DIR/assets/icons/hicolor" ]]; then
    cp -r "$ROOT_DIR/assets/icons/hicolor/." "$pkg_dir/usr/share/icons/hicolor/"
  fi
  if [[ -f "$ROOT_DIR/assets/icons/meb.svg" ]]; then
    mkdir -p "$pkg_dir/usr/share/icons/hicolor/scalable/apps"
    cp "$ROOT_DIR/assets/icons/meb.svg" "$pkg_dir/usr/share/icons/hicolor/scalable/apps/meb.svg"
  fi

  cat > "$pkg_dir/usr/share/applications/${NAME}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Meb
Comment=$DESCRIPTION
Exec=$NAME
Icon=$NAME
Terminal=true
Categories=Utility;Development;
EOF

  cp "$ROOT_DIR/README.md" "$pkg_dir/usr/share/doc/$NAME/README.md" 2>/dev/null || true
  cp "$ROOT_DIR/LICENSE" "$pkg_dir/usr/share/doc/$NAME/copyright" 2>/dev/null || true

  local installed_size
  installed_size=$(du -sk "$pkg_dir" | cut -f1)

  cat > "$pkg_dir/DEBIAN/control" <<EOF
Package: $NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $arch
Maintainer: $MAINTAINER
Installed-Size: $installed_size
Homepage: $HOMEPAGE
Description: $DESCRIPTION
EOF

  local deb_file="$OUTPUT_DIR/${NAME}_${VERSION}_${arch}.deb"
  dpkg-deb --build --root-owner-group "$pkg_dir" "$deb_file"
  echo "✔ [$arch] Paquet généré : $deb_file"
}

FAILED_ARCHS=()
BUILT_ARCHS=()

for arch in "${ARCHS[@]}"; do
  if already_built "$arch"; then
    echo ""
    echo "== [$arch] ${NAME}_${VERSION}_${arch}.deb existe déjà dans $OUTPUT_DIR, ignoré (--force pour recompiler)."
    BUILT_ARCHS+=("$arch")
    continue
  fi

  ensure_platform_support "$arch"

  if ! compile_in_docker "$arch"; then
    echo "!! [$arch] Compilation échouée ou interrompue, passage à l'architecture suivante."
    FAILED_ARCHS+=("$arch")
    continue
  fi

  if ! package_deb "$arch"; then
    echo "!! [$arch] Packaging .deb échoué, passage à l'architecture suivante."
    FAILED_ARCHS+=("$arch")
    continue
  fi

  BUILT_ARCHS+=("$arch")
done

echo ""
if [[ ${#BUILT_ARCHS[@]} -gt 0 ]]; then
  echo "✔ Paquets disponibles dans $OUTPUT_DIR :"
  for arch in "${BUILT_ARCHS[@]}"; do
    echo "  - ${NAME}_${VERSION}_${arch}.deb"
  done
fi

if [[ ${#FAILED_ARCHS[@]} -gt 0 ]]; then
  echo ""
  echo "✘ Architecture(s) en échec : ${FAILED_ARCHS[*]}"
  echo "   Relance simplement ./scripts/build.sh : les architectures déjà terminées ci-dessus seront sautées"
  echo "   et seules celles en échec seront retentées."
  exit 1
fi

echo ""
echo "Installation locale :"
echo "  sudo dpkg -i $OUTPUT_DIR/${NAME}_${VERSION}_${BUILT_ARCHS[0]}.deb"
echo ""
echo "Ces .deb sont compatibles avec scripts/install.sh (détection auto de l'architecture)."
