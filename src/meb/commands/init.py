import tomli_w

from pathlib import Path
from rich.console import Console

from detector import (
    detect_language,
    parse_project,
    detect_architecture,
    detect_icon,
    detect_executable,
)
from info import APP_AUTHOR, APP_GITHUB, APP_WEBSITE

console = Console()


def build_base_config(project: Path) -> dict:
    """Construit une config de base à partir de la détection automatique.

    Réutilisé par `meb init` (première génération) et `meb config`
    (rafraîchissement interactif).
    """
    detected_name = project.name

    language = detect_language(project)
    info = parse_project(project, language) if language else {}

    name = info.get("name") or detected_name
    arch = detect_architecture()

    icon_path = detect_icon(project, name)
    exec_path = detect_executable(project, language, name)

    return {
        "name": name,
        "version": info.get("version") or "1.0.0",
        "description": info.get("description") or "",
        "language": language or "",
        "maintainer": "",

        "package": {
            "architecture": arch,
        },

        "app": {
            "icon": str(icon_path.relative_to(project)) if icon_path else "",
            "exec": str(exec_path.relative_to(project)) if exec_path else "",
            "category": "Utility",
        },

        "services": [],
    }


def run(path: str = "."):
    project = Path(path).resolve()

    console.print(f"[dim]Meb — par {APP_AUTHOR} · {APP_GITHUB} · {APP_WEBSITE}[/dim]")
    console.print(f"[cyan]Initializing on : {project}[/cyan]")

    # Folder verification and creation
    if not project.exists():
        console.print("[red]Project directory does not exist[/red]")
        create = console.input("[yellow]Do you want to create it ?[y/n] (n) : [/yellow]")
        if create.lower() == "y":
            try:
                project.mkdir(parents=True, exist_ok=True)
                console.print("[green]✔ Project directory created[/green]")
            except PermissionError:
                console.print("[red]✘ Permission denied: cannot create directory here[/red]")
                return

            except OSError as e:
                console.print(f"[red]✘ Failed to create directory: {e}[/red]")
                return
        else:
            return

    if not project.is_dir():
        console.print("[red]✘ Path is not a directory[/red]")
        return

    config_file = project / "meb.toml"

    if config_file.exists():
        console.print("[yellow]meb.toml already exists[/yellow]")
        return

    console.print("[cyan]Analyse du projet (détecteur)...[/cyan]")
    config = build_base_config(project)

    if config["language"]:
        console.print(f"[green]✔ Langage détecté : {config['language']}[/green]")
    else:
        console.print("[yellow]! Aucun fichier de projet connu détecté[/yellow]")

    console.print(f"[green]✔ Architecture détectée : {config['package']['architecture']}[/green]")

    if config["app"]["icon"]:
        console.print(f"[green]✔ Icône détectée : {config['app']['icon']}[/green]")
    else:
        console.print("[yellow]! Aucune icône détectée[/yellow]")

    if config["app"]["exec"]:
        console.print(f"[green]✔ Exécutable détecté : {config['app']['exec']}[/green]")
    else:
        console.print("[yellow]! Aucun exécutable détecté (compile ton projet, puis relance 'meb config')[/yellow]")

    try:
        with open(config_file, "wb") as f:
            tomli_w.dump(config, f)

    except PermissionError:
        console.print("[red]✘ Permission denied: cannot create file here[/red]")
        return

    except OSError as e:
        console.print(f"[red]✘ Failed to write config file: {e}[/red]")
        return

    console.print(f"[cyan]Config file : {config_file}[/cyan]")
    console.print("[dim]Astuce : lance 'meb config' pour affiner interactivement chaque champ.[/dim]")


if __name__ == "__main__":
    run()
