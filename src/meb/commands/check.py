import os
import tomllib
from pathlib import Path
from rich.console import Console

console = Console()

REQUIRED_ROOT_FIELDS = ["name", "version"]
REQUIRED_APP_FIELDS = ["exec"]


def run(path: str = "."):
    project = Path(path).resolve()
    config_file = project / "meb.toml"

    if not config_file.exists():
        console.print("[red]✘ meb.toml introuvable. Lance 'meb init' ou 'meb config' d'abord.[/red]")
        raise SystemExit(1)

    with open(config_file, "rb") as f:
        config = tomllib.load(f)

    errors = []
    warnings = []

    for field in REQUIRED_ROOT_FIELDS:
        if not config.get(field):
            errors.append(f"Champ requis manquant : {field}")

    app = config.get("app", {})
    for field in REQUIRED_APP_FIELDS:
        if not app.get(field):
            errors.append(f"Champ requis manquant : app.{field}")

    icon = app.get("icon")
    if icon:
        icon_path = (project / icon).resolve()
        if not icon_path.exists():
            errors.append(f"Icône introuvable : {icon}")
        else:
            console.print(f"[green]✔ Icône trouvée : {icon}[/green]")
    else:
        warnings.append("Aucune icône définie (app.icon)")

    exec_value = app.get("exec")
    if exec_value:
        exec_path = (project / exec_value).resolve()
        if exec_path.exists():
            if os.access(exec_path, os.X_OK):
                console.print(f"[green]✔ Exécutable trouvé et exécutable : {exec_value}[/green]")
            else:
                warnings.append(f"{exec_value} existe mais n'est pas exécutable (chmod +x)")
        else:
            errors.append(f"Exécutable introuvable : {exec_value}")

    arch = config.get("package", {}).get("architecture")
    if arch not in ("amd64", "arm64", "armhf", "i386"):
        warnings.append(f"Architecture inconnue ou non standard : {arch}")

    console.print("")
    if warnings:
        console.print("[yellow]Avertissements :[/yellow]")
        for w in warnings:
            console.print(f"  [yellow]![/yellow] {w}")

    if errors:
        console.print("[red]Erreurs :[/red]")
        for e in errors:
            console.print(f"  [red]✘[/red] {e}")
        console.print("\n[red]La configuration contient des erreurs.[/red]")
        raise SystemExit(1)

    console.print("[green]✔ Configuration valide, prêt pour 'meb build'[/green]")


if __name__ == "__main__":
    run()