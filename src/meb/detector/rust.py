import tomllib
from pathlib import Path


def parse(project: Path) -> dict:
    cargo = project / "Cargo.toml"

    if not cargo.exists():
        return {}

    with open(cargo, "rb") as f:
        data = tomllib.load(f)

    package = data.get("package", {})
    return {
        "name": package.get("name"),
        "version": package.get("version"),
        "description": package.get("description"),
    }