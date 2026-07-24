import re
from pathlib import Path

import questionary
from rich.console import Console
from rich.table import Table

console = Console()

MODE_RE = re.compile(r"^0?[0-7]{3,4}$")


def _valid_mode(mode: str) -> bool:
    return bool(mode) and bool(MODE_RE.match(mode.strip()))


# ---------------------------------------------------------------------------
# Ressources additionnelles (plugins .so, thèmes, fichiers de traduction,
# polices, modèles, sons... n'importe quel fichier/dossier à embarquer tel
# quel dans le paquet, hors exécutable/icône/config déjà gérés ailleurs).
# ---------------------------------------------------------------------------

def _print_resources(resources: list[dict]):
    if not resources:
        console.print("[yellow]Aucune ressource additionnelle définie.[/yellow]")
        return
    table = Table(title="Ressources embarquées")
    table.add_column("Source (projet)", style="cyan")
    table.add_column("Destination (paquet)")
    table.add_column("Mode")
    for r in resources:
        table.add_row(r.get("source", ""), r.get("dest", ""), r.get("mode") or "-")
    console.print(table)


def _prompt_resource(project: Path, existing: dict | None = None) -> dict | None:
    existing = existing or {}

    source = questionary.text(
        "Chemin source (relatif au projet, fichier ou dossier — thème, plugin .so, police, son, modèle...) :",
        default=existing.get("source", ""),
    ).ask()
    if not source:
        console.print("[yellow]Abandon : une source est requise.[/yellow]")
        return None
    if not (project / source).exists():
        console.print(f"[yellow]! Attention : {source} n'existe pas encore dans le projet (sera revérifié par 'meb check').[/yellow]")

    dest = questionary.text(
        "Chemin d'installation absolu dans le paquet (ex: /usr/share/monapp/themes) :",
        default=existing.get("dest", ""),
    ).ask()
    if not dest or not dest.startswith("/"):
        console.print("[red]✘ La destination doit être un chemin absolu (commençant par /).[/red]")
        return None

    mode = questionary.text(
        "Permissions Unix (octal, ex: 0755) — laisser vide pour garder les permissions d'origine :",
        default=existing.get("mode", ""),
    ).ask() or ""
    if mode and not _valid_mode(mode):
        console.print("[red]✘ Mode invalide, ignoré (attendu ex: 0644, 0755).[/red]")
        mode = ""

    return {"source": source, "dest": dest, "mode": mode}


def manage_resources(project: Path, resources: list[dict]) -> list[dict]:
    resources = [dict(r) for r in resources]
    while True:
        console.print("")
        _print_resources(resources)
        action = questionary.select(
            "Ressources additionnelles (thèmes, icônes annexes, JSON/YAML, traductions, polices, sons, modèles, plugins .so...) :",
            choices=["Ajouter une ressource", "Supprimer une ressource", "Retour"],
        ).ask()

        if action is None or action == "Retour":
            return resources

        if action == "Ajouter une ressource":
            new = _prompt_resource(project)
            if new:
                resources.append(new)
                console.print(f"[green]✔ Ressource ajoutée : {new['source']} -> {new['dest']}[/green]")
            continue

        if not resources:
            console.print("[yellow]Rien à supprimer.[/yellow]")
            continue

        labels = [f"{r['source']} -> {r['dest']}" for r in resources]
        target = questionary.select("Quelle ressource supprimer ?", choices=labels).ask()
        if target:
            idx = labels.index(target)
            removed = resources.pop(idx)
            console.print(f"[green]✔ Supprimé : {removed['source']}[/green]")


# ---------------------------------------------------------------------------
# Pages de manuel (man)
# ---------------------------------------------------------------------------

def _print_man(pages: list[dict]):
    if not pages:
        console.print("[yellow]Aucune page de manuel définie.[/yellow]")
        return
    table = Table(title="Pages de manuel")
    table.add_column("Source", style="cyan")
    table.add_column("Section")
    for p in pages:
        table.add_row(p.get("source", ""), str(p.get("section", 1)))
    console.print(table)


def _prompt_man_page(existing: dict | None = None) -> dict | None:
    existing = existing or {}
    source = questionary.text(
        "Chemin du fichier man source (troff, ex: docs/monapp.1) :",
        default=existing.get("source", ""),
    ).ask()
    if not source:
        return None
    section = questionary.select(
        "Section du manuel :",
        choices=[str(i) for i in range(1, 9)],
        default=str(existing.get("section", 1)),
    ).ask()
    return {"source": source, "section": int(section)}


def manage_man_pages(pages: list[dict]) -> list[dict]:
    pages = [dict(p) for p in pages]
    while True:
        console.print("")
        _print_man(pages)
        action = questionary.select(
            "Pages de manuel (installées en /usr/share/man/man<section>/, lisibles via 'man') :",
            choices=["Ajouter une page", "Supprimer une page", "Retour"],
        ).ask()
        if action is None or action == "Retour":
            return pages
        if action == "Ajouter une page":
            new = _prompt_man_page()
            if new:
                pages.append(new)
                console.print(f"[green]✔ Page man ajoutée : {new['source']} (section {new['section']})[/green]")
            continue
        if not pages:
            console.print("[yellow]Rien à supprimer.[/yellow]")
            continue
        labels = [f"{p['source']} (section {p['section']})" for p in pages]
        target = questionary.select("Quelle page supprimer ?", choices=labels).ask()
        if target:
            pages.pop(labels.index(target))


# ---------------------------------------------------------------------------
# Auto-complétion shell (bash / zsh / fish)
# ---------------------------------------------------------------------------

def manage_completions(completions: dict) -> dict:
    completions = dict(completions)
    console.print("")
    console.print("[dim]Laisse vide pour ignorer un shell. Un chemin fourni est copié tel quel ; "
                  "'auto' génère un stub minimal basé sur les commandes typer connues.[/dim]")
    for shell in ("bash", "zsh", "fish"):
        value = questionary.text(
            f"Script de complétion {shell} (chemin projet, ou 'auto') :",
            default=completions.get(shell, ""),
        ).ask() or ""
        if value:
            completions[shell] = value
        else:
            completions.pop(shell, None)
    return completions


# ---------------------------------------------------------------------------
# Fichiers de configuration (conffiles) — modifiables par l'utilisateur
# après installation, préservés lors des mises à jour du paquet.
# ---------------------------------------------------------------------------

def _print_conffiles(conffiles: list[dict]):
    if not conffiles:
        console.print("[yellow]Aucun fichier de configuration défini.[/yellow]")
        return
    table = Table(title="Fichiers de configuration (conffiles)")
    table.add_column("Source (projet)", style="cyan")
    table.add_column("Destination (/etc/...)")
    for c in conffiles:
        table.add_row(c.get("source", ""), c.get("dest", ""))
    console.print(table)


def _prompt_conffile(existing: dict | None = None) -> dict | None:
    existing = existing or {}
    source = questionary.text(
        "Fichier de config source (relatif au projet) :",
        default=existing.get("source", ""),
    ).ask()
    if not source:
        return None
    dest = questionary.text(
        "Destination dans le paquet (généralement sous /etc/) :",
        default=existing.get("dest") or f"/etc/{Path(source).name}",
    ).ask()
    if not dest or not dest.startswith("/"):
        console.print("[red]✘ La destination doit être un chemin absolu.[/red]")
        return None
    if not dest.startswith("/etc/"):
        console.print("[yellow]! Convention Debian : les conffiles vivent normalement sous /etc/ — poursuite quand même.[/yellow]")
    return {"source": source, "dest": dest}


def manage_conffiles(conffiles: list[dict]) -> list[dict]:
    conffiles = [dict(c) for c in conffiles]
    while True:
        console.print("")
        _print_conffiles(conffiles)
        action = questionary.select(
            "Fichiers de configuration (préservés par dpkg lors des mises à jour/désinstallations) :",
            choices=["Ajouter un fichier de config", "Supprimer un fichier de config", "Retour"],
        ).ask()
        if action is None or action == "Retour":
            return conffiles
        if action == "Ajouter un fichier de config":
            new = _prompt_conffile()
            if new:
                conffiles.append(new)
                console.print(f"[green]✔ Ajouté : {new['dest']}[/green]")
            continue
        if not conffiles:
            console.print("[yellow]Rien à supprimer.[/yellow]")
            continue
        labels = [c["dest"] for c in conffiles]
        target = questionary.select("Quel fichier supprimer ?", choices=labels).ask()
        if target:
            conffiles.pop(labels.index(target))


# ---------------------------------------------------------------------------
# Scripts de maintainer exécutés par dpkg (preinst/postinst/prerm/postrm)
# ---------------------------------------------------------------------------

def manage_scripts(scripts: dict) -> dict:
    scripts = dict(scripts)
    console.print("")
    console.print("[dim]Scripts shell exécutés par dpkg. Doivent commencer par un shebang (#!/bin/sh) "
                  "et se terminer par 'exit 0'. Fusionnés automatiquement avec les scripts systemd "
                  "générés par meb si des services sont définis. Laisse vide pour ignorer.[/dim]")
    for hook in ("preinst", "postinst", "prerm", "postrm"):
        value = questionary.text(
            f"Script '{hook}' (chemin projet) :",
            default=scripts.get(hook, ""),
        ).ask() or ""
        if value:
            scripts[hook] = value
        else:
            scripts.pop(hook, None)
    return scripts


# ---------------------------------------------------------------------------
# Permissions Unix personnalisées sur des fichiers installés
# ---------------------------------------------------------------------------

def _print_permissions(perms: list[dict]):
    if not perms:
        console.print("[yellow]Aucune permission personnalisée définie.[/yellow]")
        return
    table = Table(title="Permissions personnalisées")
    table.add_column("Chemin (dans le paquet)", style="cyan")
    table.add_column("Mode")
    for p in perms:
        table.add_row(p.get("path", ""), p.get("mode", ""))
    console.print(table)


def _prompt_permission(existing: dict | None = None) -> dict | None:
    existing = existing or {}
    path = questionary.text(
        "Chemin installé à corriger (relatif à la racine du paquet, ex: usr/bin/monapp) :",
        default=existing.get("path", ""),
    ).ask()
    if not path:
        return None
    mode = questionary.text(
        "Mode octal (ex: 0755, 0644, 0640) :",
        default=existing.get("mode", "0644"),
    ).ask()
    if not _valid_mode(mode or ""):
        console.print("[red]✘ Mode invalide (attendu ex: 0644).[/red]")
        return None
    return {"path": path.lstrip("/"), "mode": mode.strip()}


def manage_permissions(perms: list[dict]) -> list[dict]:
    perms = [dict(p) for p in perms]
    while True:
        console.print("")
        _print_permissions(perms)
        action = questionary.select(
            "Permissions Unix personnalisées (appliquées après copie, avant la construction du .deb) :",
            choices=["Ajouter une permission", "Supprimer une permission", "Retour"],
        ).ask()
        if action is None or action == "Retour":
            return perms
        if action == "Ajouter une permission":
            new = _prompt_permission()
            if new:
                perms.append(new)
                console.print(f"[green]✔ {new['path']} -> {new['mode']}[/green]")
            continue
        if not perms:
            console.print("[yellow]Rien à supprimer.[/yellow]")
            continue
        labels = [p["path"] for p in perms]
        target = questionary.select("Quelle entrée supprimer ?", choices=labels).ask()
        if target:
            perms.pop(labels.index(target))


# ---------------------------------------------------------------------------
# Dépendances Debian (control: Depends:)
# ---------------------------------------------------------------------------

def manage_depends(depends: list[str]) -> list[str]:
    console.print("")
    console.print(f"[dim]Dépendances actuelles : {', '.join(depends) if depends else '(aucune)'}[/dim]")
    console.print("[dim]Format Debian, ex: libc6 (>= 2.34), python3 (>= 3.10). Une par ligne, ligne vide pour terminer.[/dim]")
    raw = questionary.text(
        "Dépendances (séparées par des virgules) :",
        default=", ".join(depends),
    ).ask() or ""
    return [d.strip() for d in raw.split(",") if d.strip()]


# ---------------------------------------------------------------------------
# README embarqué dans /usr/share/doc/<name>/
# ---------------------------------------------------------------------------

README_CANDIDATES = ["README.md", "README", "README.rst", "README.txt", "readme.md"]


def detect_readme(project: Path) -> Path | None:
    for candidate in README_CANDIDATES:
        p = project / candidate
        if p.is_file():
            return p
    return None


def select_readme(project: Path, current: str) -> str:
    detected = detect_readme(project)
    suggestion = str(detected.relative_to(project)) if detected else ""
    if suggestion:
        use_it = questionary.confirm(
            f"README détecté : {suggestion} — l'embarquer dans le paquet (/usr/share/doc/<name>/) ?",
            default=True,
        ).ask()
        if use_it:
            return suggestion
    manual = questionary.text("Chemin du README à embarquer (vide pour aucun) :", default=current).ask()
    return manual or ""
