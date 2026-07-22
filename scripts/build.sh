#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# build.sh — Compile Meb (Nuitka) et génère les paquets .deb amd64 + arm64
#
# Usage :
#   ./scripts/build.sh [--arch amd64|arm64|all] [--output dist] [--force]
#                       [--timeout SECONDS] [--no-cache]
#
# Fonctionnement :
#   Nuitka produit un binaire NATIF à l'architecture qui exécute la
#   compilation. Pour obtenir amd64 ET arm64 depuis une seule machine, ce
#   script compile chaque architecture dans un conteneur Docker dédié
#   (--platform linux/amd64 / linux/arm64), en s'appuyant sur QEMU (via
#   binfmt_misc, auto-configuré si besoin) pour émuler l'architecture cible.
#
#   /!\ Compiler sous QEMU est intrinsèquement plus lent que du natif
#   (le C généré par Nuitka est compilé instruction par instruction traduite
#   par QEMU) : compte plusieurs fois le temps d'un build amd64 natif pour
#   l'arm64 émulé. Ce n'est PAS un bug du script — c'est le prix de la
#   cross-compilation sans matériel arm64. Pour aller plus vite en arm64 :
#   un vrai Raspberry Pi / une VM arm64 / un runner arm64 (ex: GitHub
#   Actions) compilera nativement, sans overhead d'émulation.
#
# Optimisations appliquées pour limiter ce coût au maximum :
#   1. Image de build PERSISTANTE (scripts/Dockerfile.builder) construite via
#      `docker build`, qui bénéficie du cache de layers Docker : apt-get et
#      pip ne sont réellement réexécutés que si le Dockerfile change, plus
#      jamais à chaque `./scripts/build.sh`.
#   2. Cache ccache monté depuis l'hôte (.build-cache/ccache/<arch>) : les
#      fichiers C déjà compilés par Nuitka ne sont pas recompilés d'un build
#      à l'autre si le code source n'a pas changé.
#   3. Cache uv monté depuis l'hôte (.build-cache/uv/<arch>) : les paquets
#      Python ne sont pas retéléchargés à chaque run.
#   4. nuitka[onefile] (avec zstandard) au lieu de nuitka nu : le mode
#      --onefile compresse correctement au lieu de tomber en mode dégradé.
#   5. `-t` (pseudo-TTY) transmis au conteneur quand le terminal le permet :
#      Nuitka retrouve ses vraies barres de progression au lieu de logs
#      ligne par ligne.
#   6. Les fichiers/dossiers écrits par le conteneur (build/<arch>/,
#      caches) sont chown -R vers ton UID/GID hôte en fin de run — plus de
#      fichiers root:root impossibles à supprimer.
#   7. `pretty_exceptions_enable=False` sur l'app Typer (src/meb/meb.py) +
#      `--nofollow-import-to=pygments` côté Nuitka : sans ça, Typer importe
#      rich.traceback pour les tracebacks colorés, qui tire pygments et ses
#      ~500 modules de lexers — Nuitka les compilait TOUS (620 fichiers au
#      lieu d'une poignée), chacun prenant plusieurs minutes sous QEMU. Ce
#      seul point explique la quasi-totalité des builds arm64 qui dépassaient
#      1h30 pour un outil qui n'affiche jamais de traceback coloré.
#
# Reprise / résilience :
#   - Une architecture déjà compilée (son .deb existe dans le dossier de
#     sortie) est SAUTÉE automatiquement. --force pour tout recompiler.
#   - `timeout` encadre chaque compilation (5400s / 90 min par défaut,
#     réglable via --timeout) : au-delà, le conteneur est tué proprement au
#     lieu de rester bloqué indéfiniment, et le script passe à la suite.
#
# Prérequis sur la machine hôte :
#   - docker (avec le support --platform, donc buildx installé)
#   - binfmt_misc / qemu-user-static pour les architectures étrangères
#     (auto-installé par ce script si besoin via tonistiigi/binfmt)
# ---------------------------------------------------------------------------

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$ROOT_DIR/src/meb"
OUTPUT_DIR="$ROOT_DIR/dist"
CACHE_ROOT="$ROOT_DIR/.build-cache"
ARCH_OVERRIDE="all"
FORCE_REBUILD=0
NO_CACHE=0
JOBS_OVERRIDE=""
BUILD_TIMEOUT=5400   # 90 min par arch — QEMU (surtout arm64) est lent, on ne bloque pas indéfiniment

NAME="meb"
MAINTAINER="yolezz <yolezz@example.com>"
DESCRIPTION="Meb est un outil permettant de faire des .deb rapidement et clairement en CLI."
HOMEPAGE="https://github.com/yo-le-zz/meb"
BUILDER_IMAGE_PREFIX="meb-builder"
DOCKERFILE="$ROOT_DIR/scripts/Dockerfile.builder"

usage() {
  echo "Usage: $0 [--arch amd64|arm64|all] [--output DIR] [--force] [--timeout SECONDS] [--no-cache] [--jobs N]"
  echo ""
  echo "  --arch      Architecture(s) à compiler (défaut : all = amd64 + arm64)"
  echo "  --output    Dossier de sortie des .deb (défaut : dist/)"
  echo "  --force     Recompile même si un .deb existe déjà pour cette version/arch"
  echo "  --timeout   Délai max par architecture en secondes avant abandon (défaut : 5400)"
  echo "  --no-cache  Reconstruit l'image Docker et ignore le cache ccache/uv"
  echo "  --jobs      Force le nombre de jobs de compilation parallèles (défaut : nproc du conteneur)"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --arch) ARCH_OVERRIDE="$2"; shift 2 ;;
    --output) OUTPUT_DIR="$2"; shift 2 ;;
    --force) FORCE_REBUILD=1; shift ;;
    --timeout) BUILD_TIMEOUT="$2"; shift 2 ;;
    --no-cache) NO_CACHE=1; shift ;;
    --jobs) JOBS_OVERRIDE="$2"; shift 2 ;;
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
# Si le script est lancé via `sudo`, id -u/-g renverraient 0:0 (root) — on
# récupère le vrai UID/GID de l'utilisateur via SUDO_UID/SUDO_GID pour que les
# fichiers produits restent utilisables sans sudo par la suite.
HOST_UID="${SUDO_UID:-$(id -u)}"
HOST_GID="${SUDO_GID:-$(id -g)}"

echo "==> Meb build.sh"
echo "    Version      : $VERSION"
echo "    Architectures: ${ARCHS[*]}"
echo "    Sortie       : $OUTPUT_DIR"

command -v docker >/dev/null || { echo "✘ docker introuvable"; exit 1; }
command -v dpkg-deb >/dev/null || { echo "✘ dpkg-deb introuvable (paquet 'dpkg')"; exit 1; }
command -v timeout >/dev/null || { echo "✘ 'timeout' introuvable (paquet coreutils)"; exit 1; }

mkdir -p "$OUTPUT_DIR"

already_built() {
  local arch="$1"
  local deb_file="$OUTPUT_DIR/${NAME}_${VERSION}_${arch}.deb"
  [[ -f "$deb_file" && "$FORCE_REBUILD" -eq 0 ]]
}

ensure_platform_support() {
  local arch="$1"
  local platform="${PLATFORM_MAP[$arch]}"

  # x86_64 natif n'a besoin d'aucune émulation
  if [[ "$arch" == "amd64" && "$(uname -m)" == "x86_64" ]]; then
    return 0
  fi

  if docker run --rm --platform "$platform" python:3.13-slim true >/dev/null 2>&1; then
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

  if docker run --rm --platform "$platform" python:3.13-slim true >/dev/null 2>&1; then
    echo "✔ [$arch] Émulation QEMU opérationnelle."
    return 0
  fi

  echo "✘ [$arch] L'émulation $platform ne fonctionne toujours pas après installation de binfmt."
  echo "   Vérifie que qemu-user-static et binfmt-support sont bien installés sur l'hôte, puis :"
  echo "     docker run --privileged --rm tonistiigi/binfmt --install all"
  exit 1
}

# Construit (ou réutilise via le cache de layers Docker) l'image de
# compilation pour une architecture donnée. Rapide dès le 2e appel tant que
# scripts/Dockerfile.builder n'a pas changé.
build_image() {
  local arch="$1"
  local platform="${PLATFORM_MAP[$arch]}"
  local image="${BUILDER_IMAGE_PREFIX}:${arch}"

  echo ""
  echo "==> [$arch] Préparation de l'image de build ($image) ..."

  local cache_flag=()
  [[ "$NO_CACHE" -eq 1 ]] && cache_flag=(--no-cache --pull)

  docker build \
    --platform "$platform" \
    -t "$image" \
    -f "$DOCKERFILE" \
    "${cache_flag[@]}" \
    "$ROOT_DIR"
}

compile_in_docker() {
  local arch="$1"
  local platform="${PLATFORM_MAP[$arch]}"
  local build_tmp="$ROOT_DIR/build/$arch"
  local image="${BUILDER_IMAGE_PREFIX}:${arch}"

  local ccache_dir="$CACHE_ROOT/ccache/$arch"
  local uv_cache_dir="$CACHE_ROOT/uv/$arch"
  mkdir -p "$ccache_dir" "$uv_cache_dir"

  # Nettoyage du dossier de build via un conteneur (root) plutôt qu'un simple
  # `rm -rf` côté hôte : si un run précédent a laissé des fichiers root:root
  # (ex: avant le fix chown, ou après un run via sudo), un rm -rf non-root
  # échouerait silencieusement sur certains fichiers et laisserait Nuitka
  # tomber sur un dossier de build incohérent (AssertionError sur un .c déjà
  # présent). Le conteneur, lui, peut toujours supprimer ce qu'il a créé.
  echo "==> [$arch] Nettoyage de build/$arch ..."
  docker run --rm --platform "$platform" \
    -v "$ROOT_DIR":/workspace \
    "$image" \
    rm -rf "/workspace/build/$arch" 2>/dev/null \
    || rm -rf "$build_tmp" 2>/dev/null || true
  mkdir -p "$build_tmp"

  if [[ "$NO_CACHE" -eq 1 ]]; then
    rm -rf "${ccache_dir:?}"/* "${uv_cache_dir:?}"/* 2>/dev/null || true
  fi

  # -t : garde un vrai pseudo-terminal pour que Nuitka affiche ses barres de
  # progression classiques plutôt que des logs ligne par ligne. On ne
  # l'active que si le terminal courant en est vraiment un.
  local tty_flags=()
  [[ -t 1 ]] && tty_flags=(-t)

  # --jobs : par défaut on laisse Nuitka utiliser tous les cœurs vus par le
  # conteneur (nproc, évalué DANS le conteneur). --jobs permet de forcer une
  # valeur plus basse si la parallélisation sous QEMU sature la RAM de l'hôte.
  local nuitka_jobs
  if [[ -n "$JOBS_OVERRIDE" ]]; then
    nuitka_jobs="$JOBS_OVERRIDE"
  else
    nuitka_jobs='$(nproc)'
  fi

  echo ""
  echo "==> [$arch] Compilation ($platform) ..."

  local rc=0
  timeout --kill-after=30 "${BUILD_TIMEOUT}s" \
    docker run --rm \
      "${tty_flags[@]}" \
      --platform "$platform" \
      -v "$ROOT_DIR":/workspace \
      -v "$ccache_dir":/root/.ccache \
      -v "$uv_cache_dir":/root/.cache/uv \
      -e HOST_UID="$HOST_UID" \
      -e HOST_GID="$HOST_GID" \
      "$image" \
      bash -lc "
        set -euo pipefail
        cd /workspace
        uv sync
        uv run python -m nuitka \
          --standalone \
          --onefile \
          --output-dir=build/$arch \
          --output-filename=meb \
          --assume-yes-for-downloads \
          --jobs=${nuitka_jobs} \
          --nofollow-import-to=pygments \
          --nofollow-import-to=IPython \
          --nofollow-import-to=jedi \
          src/meb/meb.py
        chown -R \"\$HOST_UID:\$HOST_GID\" build/$arch /root/.ccache /root/.cache/uv 2>/dev/null || true
      " || rc=$?

  if [[ "$rc" -eq 124 ]]; then
    echo ""
    echo "✘ [$arch] Timeout après ${BUILD_TIMEOUT}s — arrêt du conteneur (--timeout pour ajuster)."
    echo "   Relance ./scripts/build.sh : le cache ccache/uv déjà produit sera réutilisé, ça repartira plus vite."
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

  if ! build_image "$arch"; then
    echo "!! [$arch] Construction de l'image Docker échouée, passage à l'architecture suivante."
    FAILED_ARCHS+=("$arch")
    continue
  fi

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
  echo "   Relance simplement ./scripts/build.sh : les architectures déjà terminées ci-dessus seront sautées,"
  echo "   et le cache ccache/uv déjà produit accélérera la reprise sur celles en échec."
  exit 1
fi

echo ""
echo "Installation locale :"
echo "  sudo dpkg -i $OUTPUT_DIR/${NAME}_${VERSION}_${BUILT_ARCHS[0]}.deb"
echo ""
echo "Ces .deb sont compatibles avec scripts/install.sh (détection auto de l'architecture)."
