#!/usr/bin/env bash
# dev.sh — Lance meb directement depuis les sources (interprété, sans Nuitka
# ni Docker) pour itérer rapidement pendant le développement.
#
# Usage : ./scripts/dev.sh <commande> [options]
# Exemple : ./scripts/dev.sh check --path ~/mon-projet
#
# Ce n'est PAS un remplacement du .deb final (produit par build.sh) : c'est
# uniquement un raccourci pour tester ses changements sans attendre une
# compilation Nuitka complète.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v uv >/dev/null 2>&1; then
  cd "$ROOT_DIR" && uv run python src/meb/meb.py "$@"
else
  cd "$ROOT_DIR" && python3 src/meb/meb.py "$@"
fi
