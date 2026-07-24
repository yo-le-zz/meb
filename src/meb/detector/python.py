import tomllib
from pathlib import Path


def parse(project: Path) -> dict:
    pyproject = project / "pyproject.toml"

    if pyproject.exists():
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)

        proj = data.get("project", {})
        return {
            "name": proj.get("name"),
            "version": proj.get("version"),
            "description": proj.get("description"),
        }

    # Support minimal en fallback : setup.cfg
    setup_cfg = project / "setup.cfg"
    if setup_cfg.exists():
        import configparser
        parser = configparser.ConfigParser()
        parser.read(setup_cfg)
        meta = parser["metadata"] if parser.has_section("metadata") else {}
        return {
            "name": meta.get("name"),
            "version": meta.get("version"),
            "description": meta.get("description"),
        }

    # Dernier fallback : setup.py. On n'exécute JAMAIS ce fichier (risque de
    # code arbitraire) — extraction best-effort par regex des kwargs
    # littéraux les plus courants de setup(name=..., version=..., ...).
    setup_py = project / "setup.py"
    if setup_py.exists():
        import re
        text = setup_py.read_text(encoding="utf-8", errors="ignore")

        def _kwarg(key: str) -> str | None:
            m = re.search(rf"{key}\s*=\s*['\"]([^'\"]+)['\"]", text)
            return m.group(1) if m else None

        data = {
            "name": _kwarg("name"),
            "version": _kwarg("version"),
            "description": _kwarg("description"),
        }
        return data if any(data.values()) else {}

    return {}