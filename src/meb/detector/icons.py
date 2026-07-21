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
