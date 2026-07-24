import re
from pathlib import Path

ICON_EXTENSIONS = [".png", ".svg", ".ico", ".xpm"]

# Dossiers usuels où trainent les icônes d'une app
ICON_SEARCH_DIRS = [
    ".",
    "assets",
    "assets/icons",
    "assets/icon",
    "icon",
    "icons",
    "resources",
    "resources/icons",
    "res",
    "data",
    "data/icons",
    "packaging",
    "packaging/icons",
    "build/icons",
]

GENERIC_ICON_NAMES = ["icon", "app", "logo", "appicon", "app-icon"]


def _find_candidates(project: Path) -> list[Path]:
    found = []
    seen = set()
    for d in ICON_SEARCH_DIRS:
        base = (project / d).resolve()
        if not base.is_dir():
            continue
        try:
            for f in base.iterdir():
                if f.is_file() and f.suffix.lower() in ICON_EXTENSIONS:
                    if f not in seen:
                        seen.add(f)
                        found.append(f)
        except PermissionError:
            continue
    return found


def _priority(path: Path) -> tuple:
    # SVG (vectoriel) > PNG > ICO > XPM. À égalité, on privilégie la plus
    # grande taille déclarée dans le chemin (ex: 256x256).
    ext_priority = {".svg": 0, ".png": 1, ".ico": 2, ".xpm": 3}
    size = 0
    for part in path.parts:
        if "x" in part:
            head = part.split("x")[0]
            if head.isdigit():
                size = -int(head)
    return (ext_priority.get(path.suffix.lower(), 9), size)


def detect_icon(project: Path, name: str) -> Path | None:
    """Détecte automatiquement l'icône la plus probable du projet.

    Ordre de préférence :
      1. Un fichier dont le nom correspond exactement au nom de l'app
      2. Un fichier dont le nom CONTIENT le nom de l'app
      3. Un fichier au nom générique (icon, app, logo...)
      4. Le premier fichier trouvé, trié par format/qualité
    """
    candidates = _find_candidates(project)
    if not candidates:
        return None

    name_lower = (name or "").strip().lower()

    if name_lower:
        exact = [c for c in candidates if c.stem.lower() == name_lower]
        if exact:
            exact.sort(key=_priority)
            return exact[0]

        contains_name = [c for c in candidates if name_lower in c.stem.lower()]
        if contains_name:
            contains_name.sort(key=_priority)
            return contains_name[0]

    for generic in GENERIC_ICON_NAMES:
        generic_matches = [c for c in candidates if c.stem.lower() == generic]
        if generic_matches:
            generic_matches.sort(key=_priority)
            return generic_matches[0]

    candidates.sort(key=_priority)
    return candidates[0]


def list_icons(project: Path) -> list[Path]:
    """Retourne toutes les icônes trouvées, triées par pertinence brute."""
    candidates = _find_candidates(project)
    candidates.sort(key=_priority)
    return candidates


def _size_from_path(path: Path) -> int | None:
    """Cherche un indice de taille (ex: '256x256', 'icon-48.png') dans le
    chemin ou le nom de fichier. Retourne le côté (carré supposé) en px."""
    for part in (*path.parts, path.stem):
        m = re.search(r"(\d{2,4})x\1", part)
        if m:
            return int(m.group(1))
    m = re.search(r"[-_](\d{2,4})$", path.stem)
    if m:
        val = int(m.group(1))
        if 8 <= val <= 1024:
            return val
    return None


def _png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with open(path, "rb") as f:
            header = f.read(24)
        if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        return (width, height)
    except OSError:
        return None


def _ico_dimensions(path: Path) -> list[tuple[int, int]]:
    """Un .ico peut embarquer plusieurs résolutions : renvoie toutes celles
    déclarées dans le répertoire d'images (0 signifie 256 par convention)."""
    sizes = []
    try:
        with open(path, "rb") as f:
            header = f.read(6)
            if len(header) < 6 or header[2:4] != b"\x01\x00":
                return []
            count = int.from_bytes(header[4:6], "little")
            for i in range(min(count, 64)):
                entry = f.read(16)
                if len(entry) < 16:
                    break
                w = entry[0] or 256
                h = entry[1] or 256
                sizes.append((w, h))
    except OSError:
        return []
    return sizes


def detect_icon_dimensions(path: Path) -> list[int]:
    """Retourne les tailles carrées (px) détectées pour un fichier icône
    unique. Une liste vide signifie 'indéterminé' (SVG, ou lecture échouée)."""
    hint = _size_from_path(path)
    suffix = path.suffix.lower()

    if suffix == ".png":
        dims = _png_dimensions(path)
        if dims:
            return [dims[0]]
        return [hint] if hint else []

    if suffix == ".ico":
        dims = _ico_dimensions(path)
        if dims:
            return sorted({w for w, h in dims})
        return [hint] if hint else []

    if suffix == ".svg":
        return []  # vectoriel : va dans scalable/, pas dans une taille fixe

    return [hint] if hint else []


def detect_icon_set(icon_path: Path) -> dict:
    """Résout un chemin d'icône (fichier ou dossier) en mapping
    {'scalable' | '<n>x<n>': Path} prêt à installer dans hicolor/.

    - Fichier SVG           -> {'scalable': path}
    - Fichier PNG/ICO       -> taille lue dans les métadonnées de l'image
                                (fallback 256x256 si indétectable)
    - Dossier (déjà en forme hicolor, ex: 16x16/apps/x.png, ou plat avec
      des noms/tailles variés) -> une entrée par fichier icône trouvé,
      taille déduite du chemin puis des métadonnées de chaque fichier.
    """
    if icon_path.is_file():
        if icon_path.suffix.lower() == ".svg":
            return {"scalable": icon_path}
        sizes = detect_icon_dimensions(icon_path)
        if not sizes:
            return {"256x256": icon_path}
        # .ico multi-résolution : on ne peut pas extraire chaque sous-image
        # sans lib de décodage image, donc on installe le fichier entier à
        # la plus grande taille déclarée (la plus représentative).
        return {f"{max(sizes)}x{max(sizes)}": icon_path}

    if not icon_path.is_dir():
        return {}

    result: dict[str, Path] = {}
    for f in icon_path.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in ICON_EXTENSIONS:
            continue
        if f.suffix.lower() == ".svg":
            result.setdefault("scalable", f)
            continue
        size = _size_from_path(f)
        if size is None:
            dims = detect_icon_dimensions(f)
            size = max(dims) if dims else 256
        key = f"{size}x{size}"
        # En cas de doublon sur une même taille, on garde le premier trouvé
        # (les dossiers hicolor bien formés n'ont qu'un fichier par taille).
        result.setdefault(key, f)

    return result
