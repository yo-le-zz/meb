import configparser
from pathlib import Path

DESKTOP_SEARCH_DIRS = [
    ".",
    "assets",
    "packaging",
    "packaging/linux",
    "linux",
    "data",
    "resources",
]


def detect_desktop_file(project: Path) -> Path | None:
    """Scanne le projet à la recherche d'un fichier .desktop déjà fourni
    (souvent versionné par les apps GTK/Qt pour leur propre packaging)."""
    for d in DESKTOP_SEARCH_DIRS:
        base = (project / d).resolve()
        if not base.is_dir():
            continue
        try:
            matches = sorted(base.glob("*.desktop"))
        except PermissionError:
            continue
        if matches:
            return matches[0]
    return None


def parse_desktop_file(path: Path) -> dict:
    """Extrait les champs utiles d'un .desktop existant pour pré-remplir
    meb.toml. Best-effort : un .desktop invalide renvoie un dict vide."""
    if not path or not path.exists():
        return {}

    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read(path, encoding="utf-8")
    except configparser.Error:
        return {}

    if "Desktop Entry" not in parser:
        return {}

    entry = parser["Desktop Entry"]
    return {
        "name": entry.get("Name"),
        "comment": entry.get("Comment"),
        "exec": entry.get("Exec"),
        "icon": entry.get("Icon"),
        "categories": entry.get("Categories"),
        "terminal": entry.get("Terminal", "false").strip().lower() == "true",
        "startup_wm_class": entry.get("StartupWMClass"),
    }
