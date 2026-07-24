#!/usr/bin/env bash
# sync-website-install.sh — scripts/install.sh est la source de vérité.
# La copie servie par le site (assets/meb website/install.sh, déployée sur
# meb-cli.pages.dev/install.sh) doit rester identique. On évite un symlink
# ici car certains hébergeurs de sites statiques (dont potentiellement
# Cloudflare Pages) ne préservent pas fiablement les liens symboliques lors
# du déploiement — une vraie copie est plus sûre.
#
# À lancer après toute modification de scripts/install.sh, avant de commit /
# déployer le site. Un check CI peut aussi appeler ce script avec --check
# pour échouer si les deux fichiers ont divergé.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT_DIR/scripts/install.sh"
DEST="$ROOT_DIR/assets/meb website/install.sh"

if [[ "${1:-}" == "--check" ]]; then
  if ! diff -q "$SRC" "$DEST" >/dev/null 2>&1; then
    echo "✘ assets/meb website/install.sh a divergé de scripts/install.sh"
    echo "  Lance ./scripts/sync-website-install.sh pour les resynchroniser."
    exit 1
  fi
  echo "✔ Les deux copies d'install.sh sont identiques."
  exit 0
fi

cp "$SRC" "$DEST"
echo "✔ assets/meb website/install.sh mis à jour depuis scripts/install.sh"
