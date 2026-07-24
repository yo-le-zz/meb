import re
from pathlib import Path


def parse(project: Path) -> dict:
    go_mod = project / "go.mod"
    if not go_mod.exists():
        return {}

    text = go_mod.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"^module\s+(\S+)", text, flags=re.MULTILINE)
    module_path = m.group(1) if m else None

    # go.mod ne porte ni version ni description : le nom de module est
    # souvent un chemin d'import complet (ex: github.com/user/app), on ne
    # garde que le dernier segment comme nom de projet.
    name = module_path.rstrip("/").split("/")[-1] if module_path else None

    return {
        "name": name,
        "version": None,
        "description": None,
    }
