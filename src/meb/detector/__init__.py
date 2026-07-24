from pathlib import Path

from . import python as _python
from . import node as _node
from . import rust as _rust
from . import cpp as _cpp
from . import java as _java
from . import go as _go
from . import system as _system
from . import icons as _icons
from . import executable as _executable
from . import desktop as _desktop

PROJECT_FILES = {
    "python": ["pyproject.toml", "setup.py", "setup.cfg"],
    "node": ["package.json"],
    "rust": ["Cargo.toml"],
    "cpp": ["CMakeLists.txt", "Makefile"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"],
    "go": ["go.mod"],
}

PARSERS = {
    "python": _python.parse,
    "node": _node.parse,
    "rust": _rust.parse,
    "cpp": _cpp.parse,
    "java": _java.parse,
    "go": _go.parse,
}


def detect_language(project: Path):
    for language, files in PROJECT_FILES.items():
        for file in files:
            if (project / file).exists():
                return language
    return None


def parse_project(project: Path, language: str) -> dict:
    parser = PARSERS.get(language)
    if not parser:
        return {}
    try:
        return parser(project)
    except Exception:
        return {}


def detect_architecture() -> str:
    return _system.get_debian_architecture()


def detect_icon(project: Path, name: str) -> Path | None:
    return _icons.detect_icon(project, name)


def list_icons(project: Path) -> list[Path]:
    return _icons.list_icons(project)


def detect_executable(project: Path, language: str | None, name: str) -> Path | None:
    return _executable.detect_executable(project, language, name)


def detect_compiler(project: Path) -> str | None:
    return _executable.detect_compiler(project)


def is_jar_artifact(path: Path | None) -> bool:
    return _executable.is_jar_artifact(path)


def detect_icon_set(icon_path: Path) -> dict:
    """Résout un chemin d'icône (fichier unique ou dossier) en mapping
    {taille: chemin} pour l'installation multi-résolution (hicolor)."""
    return _icons.detect_icon_set(icon_path)


def detect_desktop_file(project: Path) -> Path | None:
    return _desktop.detect_desktop_file(project)


def parse_desktop_file(path: Path) -> dict:
    return _desktop.parse_desktop_file(path)