#!/bin/sh
# Stoppe le script immédiatement si une commande échoue
set -e

echo "==> Installation de MEB CLI..."

# 1. Vérifier si l'utilisateur est sur Linux
if [ "$(uname)" != "Linux" ]; then
    echo "Erreur : MEB est actuellement disponible uniquement sous Linux."
    exit 1
fi

# 2. Détecter l'architecture (x86_64 / arm64)
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)  DEB_ARCH="amd64" ;;
    aarch64) DEB_ARCH="arm64" ;;
    *)
        echo "Erreur : Architecture non supportée ($ARCH)."
        exit 1
        ;;
esac

# 3. Récupérer la dernière version depuis l'API GitHub
echo "--> Recherche de la dernière version..."
GITHUB_REPO="yo-le-zz/meb"
LATEST_URL=$(curl -s "https://api.github.com/repos/$GITHUB_REPO/releases/latest" \
    | grep "browser_download_url" \
    | grep "_${DEB_ARCH}.deb" \
    | cut -d '"' -f 4)

if [ -z "$LATEST_URL" ]; then
    echo "Erreur : Impossible de trouver le paquet .deb pour $DEB_ARCH."
    exit 1
fi

# 4. Télécharger et installer
TMP_DEB="/tmp/meb_latest.deb"
echo "--> Téléchargement du paquet..."
curl -fsSL "$LATEST_URL" -o "$TMP_DEB"

echo "--> Installation avec dpkg (mot de passe sudo requis)..."
sudo dpkg -i "$TMP_DEB"

# 5. Nettoyage
rm -f "$TMP_DEB"

echo "==> MEB CLI a été installé avec succès !"