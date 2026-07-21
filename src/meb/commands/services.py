import questionary
from rich.console import Console
from rich.table import Table

console = Console()

SERVICE_TYPES = ["simple", "oneshot", "notify", "forking"]
RESTART_POLICIES = ["no", "on-failure", "always", "on-abnormal"]


def _print_services(services: list[dict]):
    if not services:
        console.print("[yellow]Aucun service défini.[/yellow]")
        return

    table = Table(title="Services définis")
    table.add_column("Nom", style="cyan")
    table.add_column("Type")
    table.add_column("Utilisateur")
    table.add_column("Restart")
    table.add_column("Auto-démarrage")
    table.add_column("Description")

    for svc in services:
        table.add_row(
            svc.get("name", ""),
            svc.get("type", "simple"),
            svc.get("user", "root"),
            svc.get("restart", "on-failure"),
            "oui" if svc.get("enable", True) else "non",
            svc.get("description", ""),
        )
    console.print(table)


def _prompt_service(existing: dict | None = None) -> dict | None:
    existing = existing or {}

    name = questionary.text(
        "Nom du service (identifiant, sans espaces) :",
        default=existing.get("name", ""),
    ).ask()
    if not name:
        console.print("[yellow]Abandon : un nom est requis.[/yellow]")
        return None

    description = questionary.text(
        "Description :",
        default=existing.get("description", ""),
    ).ask()

    args = questionary.text(
        "Arguments passés au binaire installé (ex: --worker), laisser vide si aucun :",
        default=existing.get("args", ""),
    ).ask()

    service_type = questionary.select(
        "Type de service systemd :",
        choices=SERVICE_TYPES,
        default=existing.get("type", "simple") if existing.get("type", "simple") in SERVICE_TYPES else "simple",
    ).ask()

    user = questionary.text(
        "Utilisateur système d'exécution :",
        default=existing.get("user", "root"),
    ).ask()

    restart = questionary.select(
        "Politique de redémarrage :",
        choices=RESTART_POLICIES,
        default=existing.get("restart", "on-failure") if existing.get("restart", "on-failure") in RESTART_POLICIES else "on-failure",
    ).ask()

    enable = questionary.confirm(
        "Activer et démarrer automatiquement ce service à l'installation du .deb ?",
        default=existing.get("enable", True),
    ).ask()

    return {
        "name": name.strip(),
        "description": description or "",
        "args": args or "",
        "type": service_type,
        "user": user or "root",
        "restart": restart,
        "enable": bool(enable),
    }


def manage_services(services: list[dict]) -> list[dict]:
    """Boucle de gestion interactive des services. Retourne la liste mise à jour."""
    services = [dict(s) for s in services]

    while True:
        console.print("")
        _print_services(services)
        action = questionary.select(
            "Gestion des services systemd :",
            choices=[
                "Ajouter un service",
                "Modifier un service",
                "Supprimer un service",
                "Retour",
            ],
        ).ask()

        if action is None or action == "Retour":
            return services

        if action == "Ajouter un service":
            new_service = _prompt_service()
            if new_service:
                if any(s["name"] == new_service["name"] for s in services):
                    console.print(f"[red]✘ Un service nommé '{new_service['name']}' existe déjà.[/red]")
                else:
                    services.append(new_service)
                    console.print(f"[green]✔ Service '{new_service['name']}' ajouté.[/green]")
            continue

        if not services:
            console.print("[yellow]Aucun service à modifier/supprimer.[/yellow]")
            continue

        names = [s["name"] for s in services]

        if action == "Modifier un service":
            target = questionary.select("Quel service modifier ?", choices=names).ask()
            if not target:
                continue
            idx = names.index(target)
            updated = _prompt_service(services[idx])
            if updated:
                services[idx] = updated
                console.print(f"[green]✔ Service '{updated['name']}' mis à jour.[/green]")

        elif action == "Supprimer un service":
            target = questionary.select("Quel service supprimer ?", choices=names).ask()
            if not target:
                continue
            confirm = questionary.confirm(f"Supprimer '{target}' ?", default=False).ask()
            if confirm:
                services = [s for s in services if s["name"] != target]
                console.print(f"[green]✔ Service '{target}' supprimé.[/green]")
