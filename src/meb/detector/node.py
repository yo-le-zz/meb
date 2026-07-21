import json
from pathlib import Path


def parse(project: Path) -> dict:
    package = project / "package.json"

    if not package.exists():
        return {}

    with open(package, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "name": data.get("name"),
        "version": data.get("version"),
        "description": data.get("description"),
    }