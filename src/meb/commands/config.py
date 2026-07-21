import tomllib
import tomli_w
import questionary

from pathlib import Path
from rich.console import Console
from rich.table import Table

from detector import (
    detect_language,
    parse_project,
    detect_architecture,
    detect_icon,
    detect_executable,
    list_icons,
)
from .services import manage_services
from info import APP_AUTHOR, APP_GITHUB, APP_WEBSITE

console = Console()

ARCHITECTURES = ["amd64", "arm64", "armhf", "i386"]
CATEGORIES = [
    "Utility", "Development", "Network", "Game", "Graphics",
    "Office", "System", "AudioVideo", "Education", "Other",
]


def load_existing(config_file: Path) -> dict:
    if config_file.exists():
        with open(config_file, "rb") as f:
            return tomllib.load(f)
    return {}


def _detect_all(project: Path, existing: dict) -> dict:
    """Détection automatique complète, utilisée comme base/suggestion."""
    detected_name = project.name
    language = detect_language(project)
    info = parse_project(project, language) if language else {}

    name = existing.get("name") or info.get("name") or detected_name
    arch = existing.get("package", {}).get("architecture") or detect_architecture()

    existing_icon = existing.get("app", {}).get("icon")
    icon_path = None
    if not existing_icon:
        icon_path = detect_icon(project, name)

    existing_exec = existing.get("app", {}).get("exec")
    exec_path = None
    if not existing_exec:
        exec_path = detect_executable(project, language, name)

    return {
        "name": name,
        "version": info.get("version") or existing.get("version") or "1.0.0",
        "description": info.get("description") or existing.get("description", ""),
        "language": language or existing.get("language", ""),
        "maintainer": existing.get("maintainer", ""),
        "package": {
            "architecture": arch,
        },
        "app": {
            "icon": existing_icon or (str(icon_path.relative_to(project)) if icon_path else ""),
            "exec": existing_exec or (str(exec_path.relative_to(project)) if exec_path else ""),
            "category": existing.get("app", {}).get("category") or "Utility",
        },
        "services": existing.get("services", []),
    }


def _print_summary(config: dict, project: Path):
    table = Table(title="Configuration meb.toml")
    table.add_column("Champ", style="cyan")
    table.add_column("Valeur")

    table.add_row("name", config["name"] or "-")
    table.add_row("version", config["version"] or "-")
    table.add_row("description", config["description"] or "-")
    table.add_row("language", config["language"] or "-")
    table.add_row("maintainer", config.get("maintainer") or "-")
    table.add_row("package.architecture", config["package"]["architecture"] or "-")
    table.add_row("app.icon", config["app"]["icon"] or "[yellow]non défini[/yellow]")
    table.add_row("app.exec", config["app"]["exec"] or "[yellow]non défini[/yellow]")
    table.add_row("app.category", config["app"]["category"] or "-")
    table.add_row("services", str(len(config.get("services", []))) + " défini(s)")

    console.print(table)


def _select_icon(project: Path, current: str) -> str:
    candidates = list_icons(project)
    choices = [str(c.relative_to(project)) for c in candidates]

    options = choices + ["Saisir un chemin manuellement", "Aucune icône"]
    default = current if current in choices else (choices[0] if choices else "Saisir un chemin manuellement")

    choice = questionary.select("Icône de l'application :", choices=options, default=default if default in options else None).ask()

    if choice == "Aucune icône":
        return ""
    if choice == "Saisir un chemin manuellement":
        manual = questionary.text("Chemin de l'icône (relatif au projet) :", default=current).ask()
        return manual or ""
    return choice


def _select_executable(project: Path, language: str, name: str, current: str) -> str:
    detected = detect_executable(project, language, name)
    suggestion = str(detected.relative_to(project)) if detected else ""

    if suggestion:
        use_detected = questionary.confirm(
            f"Exécutable détecté : {suggestion} — l'utiliser ?", default=True
        ).ask()
        if use_detected:
            return suggestion

    manual = questionary.text(
        "Chemin de l'exécutable compilé (relatif au projet) :", default=current
    ).ask()
    return manual or ""


def _edit_fields(config: dict, project: Path):
    field_choices = [
        "name", "version", "description", "language", "maintainer",
        "package.architecture", "app.icon", "app.exec", "app.category",
    ]
    selected = questionary.checkbox(
        "Quels champs veux-tu modifier manuellement ?",
        choices=field_choices,
    ).ask()

    if not selected:
        return

    for field in selected:
        if field == "name":
            config["name"] = questionary.text("Nom de l'application :", default=config["name"]).ask() or config["name"]
        elif field == "version":
            config["version"] = questionary.text("Version :", default=config["version"]).ask() or config["version"]
        elif field == "description":
            config["description"] = questionary.text("Description :", default=config["description"]).ask() or config["description"]
        elif field == "language":
            config["language"] = questionary.text("Langage :", default=config["language"]).ask() or config["language"]
        elif field == "maintainer":
            config["maintainer"] = questionary.text(
                "Maintainer (ex: Nom <email@example.com>) :", default=config.get("maintainer", "")
            ).ask() or config.get("maintainer", "")
        elif field == "package.architecture":
            config["package"]["architecture"] = questionary.select(
                "Architecture cible :", choices=ARCHITECTURES,
                default=config["package"]["architecture"] if config["package"]["architecture"] in ARCHITECTURES else "amd64",
            ).ask()
        elif field == "app.icon":
            config["app"]["icon"] = _select_icon(project, config["app"]["icon"])
        elif field == "app.exec":
            config["app"]["exec"] = _select_executable(project, config["language"], config["name"], config["app"]["exec"])
        elif field == "app.category":
            cat_choice = questionary.select(
                "Catégorie de l'application (menu .desktop) :",
                choices=CATEGORIES + ["Autre..."],
                default=config["app"]["category"] if config["app"]["category"] in CATEGORIES else "Autre...",
            ).ask()
            if cat_choice == "Autre...":
                cat_choice = questionary.text("Catégorie personnalisée :", default=config["app"]["category"]).ask()
            config["app"]["category"] = cat_choice or config["app"]["category"]


def _save(config: dict, config_file: Path) -> bool:
    try:
        with open(config_file, "wb") as f:
            tomli_w.dump(config, f)
    except PermissionError:
        console.print("[red]✘ Permission refusée : impossible d'écrire meb.toml[/red]")
        return False
    except OSError as e:
        console.print(f"[red]✘ Échec de l'écriture du fichier de config : {e}[/red]")
        return False
    console.print(f"[cyan]meb.toml mis à jour : {config_file}[/cyan]")
    return True


def run(path: str = "."):
    project = Path(path).resolve()

    if not project.exists() or not project.is_dir():
        console.print("[red]✘ Le dossier du projet n'existe pas[/red]")
        return

    console.print(f"[dim]Meb — par {APP_AUTHOR} · {APP_GITHUB} · {APP_WEBSITE}[/dim]")
    console.print(f"[cyan]Analyse du projet : {project}[/cyan]")

    config_file = project / "meb.toml"
    existing = load_existing(config_file)

    config = _detect_all(project, existing)

    if config["language"]:
        console.print(f"[green]✔ Langage détecté : {config['language']}[/green]")
    else:
        console.print("[yellow]! Aucun fichier de projet connu détecté[/yellow]")
    console.print(f"[green]✔ Architecture détectée : {config['package']['architecture']}[/green]")

    console.print("")
    _print_summary(config, project)

    while True:
        console.print("")
        action = questionary.select(
            "Que veux-tu faire ?",
            choices=[
                "Utiliser la détection automatique telle quelle",
                "Modifier certains champs manuellement",
                "Gérer les services (systemd)",
                "Revoir le résumé",
                "Enregistrer et quitter",
                "Quitter sans enregistrer",
            ],
        ).ask()

        if action is None or action == "Quitter sans enregistrer":
            console.print("[yellow]Abandon, aucune modification enregistrée.[/yellow]")
            return

        if action == "Utiliser la détection automatique telle quelle":
            console.print("[green]✔ Détection automatique conservée.[/green]")
            continue

        if action == "Modifier certains champs manuellement":
            _edit_fields(config, project)
            _print_summary(config, project)
            continue

        if action == "Gérer les services (systemd)":
            config["services"] = manage_services(config.get("services", []))
            continue

        if action == "Revoir le résumé":
            _print_summary(config, project)
            continue

        if action == "Enregistrer et quitter":
            if not config["name"]:
                console.print("[red]✘ Le champ 'name' est requis.[/red]")
                continue
            _save(config, config_file)
            return


if __name__ == "__main__":
    run()
