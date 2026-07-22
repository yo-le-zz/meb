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

<p align="center">
  Créé par <b>yolezz</b> — <a href="https://github.com/yo-le-zz/meb">GitHub</a> · <a href="https://meb-cli.pages.dev">meb-cli.pages.dev</a>
</p>

---

## Qu'est-ce que Meb ?

Meb automatise la création de paquets Debian (`.deb`) : détection du projet (langage, icône, exécutable compilé), configuration interactive, définition de services systemd, vérification des assets et construction du paquet final — le tout depuis le terminal.

## Installation

### Via le script d'installation (recommandé)

```bash
curl -fsSL https://meb-cli.pages.dev/install.sh | sh
```

Le script détecte automatiquement ton architecture (`amd64`/`arm64`) et installe la dernière release depuis GitHub.

### Depuis un .deb pré-construit

```bash
sudo dpkg -i meb_1.0.0_amd64.deb
# ou
sudo apt install ./meb_1.0.0_amd64.deb
```

Une fois installé, `meb` est disponible partout dans le terminal.

### Depuis les sources (compilation multi-arch)

```bash
git clone https://github.com/yo-le-zz/meb.git
cd meb
chmod +x scripts/build.sh
./scripts/build.sh
```

`build.sh` compile Meb avec [Nuitka](https://nuitka.net) dans des conteneurs Docker (via QEMU) pour produire **amd64 et arm64** en une seule commande, puis assemble les deux `.deb` dans `dist/`.

Le script est optimisé pour ne pas repartir de zéro à chaque exécution :

- **Image de build persistante** (`scripts/Dockerfile.builder`) construite via `docker build` : grâce au cache de layers Docker, `apt-get`/`pip` ne sont réellement réexécutés que si le Dockerfile change — plus jamais à chaque run.
- **Cache ccache et uv** montés depuis `.build-cache/` (ignoré par git) : le C déjà compilé et les paquets Python déjà téléchargés sont réutilisés d'un build à l'autre.
- **`nuitka[onefile]`** (avec `zstandard`) pour un `--onefile` correctement compressé.
- **Barres de progression Nuitka classiques** : le conteneur reçoit un vrai pseudo-TTY (`-t`) quand le terminal le permet.
- **Ownership correct** : les fichiers créés dans le conteneur (`build/<arch>/`, caches) sont `chown` vers ton UID/GID hôte en fin de run — plus de `root:root` bloquant un `rm -rf`. Si tu lances `sudo ./scripts/build.sh` (pas nécessaire en temps normal si ton utilisateur est dans le groupe `docker`), le script détecte ton vrai utilisateur via `SUDO_UID`/`SUDO_GID` au lieu d'attribuer les fichiers à `root`.
- **Nettoyage robuste avant chaque compilation** : `build/<arch>/` est supprimé via un conteneur (root) plutôt qu'un `rm -rf` côté hôte, qui échouerait silencieusement sur d'anciens fichiers `root:root` laissés par un run précédent — c'est exactement ce qui provoquait un `AssertionError` de Nuitka sur un `.c` déjà présent dans un dossier de build incohérent.
- **Reprise intelligente** : une architecture déjà buildée (son `.deb` existe dans `dist/`) est sautée automatiquement ; en cas de timeout ou d'échec, le script continue sur les autres architectures puis résume à la fin.
- **Pas de pygments inutile** : `typer.Typer(pretty_exceptions_enable=False)` + `--nofollow-import-to=pygments` empêchent Nuitka de compiler les ~500 modules de lexers de `pygments` (tirés par défaut via les tracebacks colorés de Typer/Rich) — un outil jamais utilisé par `meb` qui, à lui seul, pouvait faire passer un build de quelques minutes à plus d'1h30 sous QEMU.
- **`--jobs`** réglable si la parallélisation sature la RAM de l'hôte sous émulation (par défaut : tous les cœurs vus par le conteneur).

⚠️ Compiler en arm64 depuis une machine amd64 (ou l'inverse) passe par l'émulation QEMU, intrinsèquement plus lente que du natif (le C généré est traduit instruction par instruction). Ce n'est pas un bug du script : pour des builds arm64 rapides, un vrai matériel arm64 (Raspberry Pi, VM, runner CI arm64) reste la meilleure option.

Prérequis : `docker` (avec support `--platform`) et QEMU enregistré pour l'émulation multi-arch :

```bash
docker run --privileged --rm tonistiigi/binfmt --install all
```

`build.sh` tente d'ailleurs cette installation automatiquement s'il détecte que l'émulation ne fonctionne pas.

Options :

```bash
./scripts/build.sh --arch amd64     # ne compile que amd64
./scripts/build.sh --arch arm64     # ne compile que arm64
./scripts/build.sh --arch all       # amd64 + arm64 (défaut)
./scripts/build.sh --output out/    # dossier de sortie personnalisé
./scripts/build.sh --force          # recompile même si un .deb existe déjà
./scripts/build.sh --timeout 3600   # ajuste le délai max par architecture (secondes)
./scripts/build.sh --no-cache       # reconstruit l'image et ignore les caches ccache/uv
./scripts/build.sh --jobs 4         # limite la parallélisation (utile si RAM limitée sous QEMU)
```

## Commandes

| Commande      | Description                                                        |
|---------------|----------------------------------------------------------------------|
| `meb version` | Affiche la version de Meb (et infos créateur)                        |
| `meb init`    | Analyse le projet avec le détecteur et génère un `meb.toml` de base  |
| `meb config`  | Menu interactif (rich/questionary) : détection auto ou réglages manuels, gestion des services |
| `meb check`   | Vérifie que `meb.toml` est valide (champs requis, icône, exécutable, services) |
| `meb build`   | Génère le paquet `.deb` du projet à partir de `meb.toml`             |

### `meb init` — base générée par le détecteur

`meb init` construit directement un `meb.toml` de base en s'appuyant sur le détecteur : nom, version, description, langage, architecture, icône et exécutable sont pré-remplis automatiquement quand c'est possible.

### `meb config` — menu interactif

`meb config` affiche un résumé de la détection automatique puis propose un menu :

- **Utiliser la détection automatique telle quelle**
- **Modifier certains champs manuellement** (sélection multiple des champs à éditer : nom, version, description, langage, maintainer, architecture, icône, exécutable, catégorie)
- **Gérer les services (systemd)** — ajouter/modifier/supprimer des services packagés avec l'app
- **Enregistrer et quitter**

### Détection du langage

| Langage | Fichiers détectés                       |
|---------|-------------------------------------------|
| Python  | `pyproject.toml`, `setup.py`, `setup.cfg` |
| Node.js | `package.json`                            |
| Rust    | `Cargo.toml`                              |
| C/C++   | `CMakeLists.txt`, `Makefile`               |

L'architecture Debian (`amd64`, `arm64`, `armhf`, ...) est déduite de l'architecture machine (`platform.machine()`).

### Détection de l'icône

Meb cherche dans les dossiers usuels (`assets/`, `assets/icons/`, `icons/`, `resources/`, `res/`, `data/`, ...) et priorise :

1. Un fichier dont le nom correspond exactement au nom de l'app
2. Un fichier dont le nom **contient** le nom de l'app
3. Un nom générique (`icon`, `app`, `logo`)
4. Le meilleur candidat trouvé (SVG > PNG > ICO, plus grande taille disponible)

### Détection de l'exécutable compilé

Si aucun `.exe` n'est trouvé, Meb regarde `dist/<name>`, puis affine selon le compilateur détecté :

| Compilateur         | Emplacement recherché                          |
|----------------------|-------------------------------------------------|
| PyInstaller          | `dist/<name>` ou `dist/<name>/<name>`            |
| Nuitka               | `<name>.dist/<name>`, `<name>.dist/<name>.bin`, `<name>.onefile-build/...` |
| Cargo (Rust)         | `target/release/<name>`, `target/debug/<name>`   |
| Node (pkg, etc.)     | `dist/<name>`, `bin/<name>`, `out/<name>`         |
| CMake/Make (C/C++)   | `build/<name>`, `build/bin/<name>`, `cmake-build-release/<name>` |

Le compilateur Python est deviné via un dossier `*.dist`/`*.build` (Nuitka), un fichier `*.spec` (PyInstaller), ou la présence de `nuitka`/`pyinstaller` dans les dépendances de `pyproject.toml`.

### Services systemd

Un `meb.toml` peut définir des services qui seront installés dans `/usr/lib/systemd/system/` et activés automatiquement à l'installation du `.deb` (via des scripts `postinst`/`prerm`/`postrm` générés automatiquement) :

```toml
[[services]]
name = "nova-worker"
description = "Worker en arrière-plan de Nova"
args = "--worker"        # ajouté après /usr/bin/<name>
type = "simple"           # simple | oneshot | notify | forking
user = "root"
restart = "on-failure"    # no | on-failure | always | on-abnormal
enable = true              # démarré automatiquement à l'install
```

### Exemple de `meb.toml`

```toml
name = "nova"
version = "1.2.0"
description = "AI assistant"
language = "python"
maintainer = "yolezz <yolezz@example.com>"

[package]
architecture = "amd64"

[app]
icon = "assets/icon.png"
exec = "dist/nova"
category = "Utility"

[[services]]
name = "nova-worker"
description = "Worker en arrière-plan de Nova"
args = "--worker"
type = "simple"
user = "root"
restart = "on-failure"
enable = true
```

## Pistes d'amélioration

- Support de dépendances Debian (`Depends:` configurables depuis `meb.toml`)
- Génération de changelog Debian (`debian/changelog`)
- Signature GPG des paquets et d'un dépôt APT hébergé sur `meb-cli.pages.dev`
- Support `.rpm`/`.pkg.tar.zst` en plus du `.deb`
- Détection d'icônes multi-résolutions (générer automatiquement les tailles `hicolor` manquantes à partir d'un SVG source)

## Créateur

Meb est développé par **yolezz**.

- GitHub : [https://github.com/yo-le-zz/meb](https://github.com/yo-le-zz/meb)
- Site web : [https://meb-cli.pages.dev](https://meb-cli.pages.dev)

## Licence

MIT — voir [LICENSE](LICENSE).
