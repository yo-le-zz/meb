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

    return {}