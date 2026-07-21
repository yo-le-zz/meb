<p align="center">
  <img src="assets/icons/meb.png" alt="Meb logo" width="120">
</p>

<h1 align="center">Meb</h1>

<p align="center">
  Un outil CLI pour construire des paquets <code>.deb</code> rapidement et clairement, quel que soit le langage de ton projet.
</p>

<p align="center">
  <img alt="version" src="https://img.shields.io/badge/version-1.0.0-blue">
  <img alt="python" src="https://img.shields.io/badge/python-3.13%2B-blue">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-green">
  <img alt="platform" src="https://img.shields.io/badge/platform-linux-lightgrey">
</p>

---

## Qu'est-ce que Meb ?

Meb automatise la création de paquets Debian (`.deb`) : détection du projet, génération de `meb.toml`, vérification des assets (icônes, exécutable) et construction du paquet final — le tout depuis le terminal.

## Installation

### Depuis un .deb pré-construit

```bash
sudo dpkg -i meb_1.0.0_amd64.deb
# ou
sudo apt install ./meb_1.0.0_amd64.deb
```

Une fois installé, `meb` est disponible partout dans le terminal.

### Depuis les sources (compilation)

```bash
git clone <ton-repo>
cd meb
chmod +x scripts/build.sh
./scripts/build.sh
sudo dpkg -i dist/meb_1.0.0_amd64.deb
```

`build.sh` compile Meb avec [Nuitka](https://nuitka.net) puis assemble le `.deb`.

Options :

```bash
./scripts/build.sh --arch arm64     # change le label d'architecture du paquet
./scripts/build.sh --output out/    # dossier de sortie personnalisé
```

> ⚠️ Nuitka compile un binaire natif : pour produire un `.deb` `arm64`, lance le script sur une machine (ou un environnement QEMU/Docker) `arm64`. `--arch` ne fait que changer l'étiquette du paquet, pas l'architecture réelle du binaire.

## Commandes

| Commande      | Description                                                        |
|---------------|----------------------------------------------------------------------|
| `meb version` | Affiche la version de Meb                                            |
| `meb init`    | Crée un `meb.toml` vide dans le projet                                |
| `meb config`  | Détecte automatiquement nom, version, langage et architecture du projet, et met à jour `meb.toml` |
| `meb check`   | Vérifie que `meb.toml` est valide (champs requis, icône, exécutable) |
| `meb build`   | Génère le paquet `.deb` du projet à partir de `meb.toml`             |

### `meb config` — détection automatique

Comme `uv`, `meb config` prend le nom du dossier comme nom par défaut, puis cherche un fichier de manifeste connu pour affiner les informations :

| Langage | Fichiers détectés                       |
|---------|-------------------------------------------|
| Python  | `pyproject.toml`, `setup.py`, `setup.cfg` |
| Node.js | `package.json`                            |
| Rust    | `Cargo.toml`                              |
| C/C++   | `CMakeLists.txt`, `Makefile`               |

L'architecture Debian (`amd64`, `arm64`, `armhf`, ...) est déduite de l'architecture machine (`platform.machine()`).

### Exemple de `meb.toml`

```toml
name = "nova"
version = "1.2.0"
description = "AI assistant"
language = "python"

[package]
architecture = "amd64"

[app]
icon = "assets/icon.png"
exec = "dist/nova"
```

## Licence

MIT — voir [LICENSE](LICENSE).