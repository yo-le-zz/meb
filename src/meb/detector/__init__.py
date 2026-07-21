from pathlib import Path

from . import python as _python
from . import node as _node
from . import rust as _rust
from . import cpp as _cpp
from . import system as _system

PROJECT_FILES = {
    "python": ["pyproject.toml", "setup.py", "setup.cfg"],
    "node": ["package.json"],
    "rust": ["Cargo.toml"],
    "cpp": ["CMakeLists.txt", "Makefile"],
}

PARSERS = {
    "python": _python.parse,
    "node": _node.parse,
    "rust": _rust.parse,
    "cpp": _cpp.parse,
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