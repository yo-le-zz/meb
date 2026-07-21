import tomllib
import tomli_w
import questionary

from pathlib import Path
from rich.console import Console

from detector import detect_language, parse_project, detect_architecture

console = Console()

DEFAULT_CONFIG = {
    "name": "",
    "version": "1.0.0",
    "description": "",
    "language": "",

    "package": {
        "architecture": "amd64"
    },

    "app": {
        "icon": "",
        "exec": ""
    }
}


def load_existing(config_file: Path) -> dict:
    if config_file.exists():
        with open(config_file, "rb") as f:
            return tomllib.load(f)
    return {}


def run(path: str = "."):
    project = Path(path).resolve()

    if not project.exists() or not project.is_dir():
        console.print("[red]✘ Le dossier du projet n'existe pas[/red]")
        return

    config_file = project / "meb.toml"
    existing = load_existing(config_file)

    console.print(f"[cyan]Analyse du projet : {project}[/cyan]")

    # 1) Nom par défaut = nom du dossier (comme uv)
    detected_name = project.name

    # 2) Détection du langage
    language = detect_language(project)
    if language:
        console.print(f"[green]✔ Langage détecté : {language}[/green]")
    else:
        console.print("[yellow]! Aucun fichier de projet connu détecté[/yellow]")

    # 3) Extraction des infos du manifeste
    info = parse_project(project, language) if language else {}

    # 4) Architecture
    arch = detect_architecture()
    console.print(f"[green]✔ Architecture détectée : {arch}[/green]")

    config = {
        "name": existing.get("name") or info.get("name") or detected_name,
        "version": info.get("version") or existing.get("version") or "1.0.0",
        "description": info.get("description") or existing.get("description", ""),
        "language": language or existing.get("language", ""),
        "package": {
            "architecture": existing.get("package", {}).get("architecture") or arch
        },
        "app": {
            "icon": existing.get("app", {}).get("icon", ""),
            "exec": existing.get("app", {}).get("exec", ""),
        },
    }

    console.print("\n[bold]Résumé de la configuration :[/bold]")
    console.print(f"  name        : {config['name']}")
    console.print(f"  version     : {config['version']}")
    console.print(f"  description : {config['description']}")
    console.print(f"  language    : {config['language']}")
    console.print(f"  architecture: {config['package']['architecture']}")

    confirm = questionary.confirm("Écrire ce résultat dans meb.toml ?", default=True).ask()
    if not confirm:
        console.print("[yellow]Abandon[/yellow]")
        return

    try:
        with open(config_file, "wb") as f:
            tomli_w.dump(config, f)
    except PermissionError:
        console.print("[red]✘ Permission refusée : impossible d'écrire meb.toml[/red]")
        return
    except OSError as e:
        console.print(f"[red]✘ Échec de l'écriture du fichier de config : {e}[/red]")
        return

    console.print(f"[cyan]meb.toml mis à jour : {config_file}[/cyan]")


if __name__ == "__main__":
    run()