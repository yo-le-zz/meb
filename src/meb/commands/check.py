import os
import re
import tomllib
from pathlib import Path
from rich.console import Console

console = Console()

REQUIRED_ROOT_FIELDS = ["name", "version"]
REQUIRED_APP_FIELDS = ["exec"]
MODE_RE = re.compile(r"^0?[0-7]{3,4}$")
KNOWN_SHELLS = ("bash", "zsh", "fish")
MAINTAINER_RE = re.compile(r"^[^<>]+<[^<>@\s]+@[^<>@\s]+>$")
PLACEHOLDER_MAINTAINERS = {"unknown <unknown@example.com>", ""}


def _mode_is_overly_permissive(mode: str) -> bool:
    """Avertit sur un mode world-writable (dernier chiffre 2/3/6/7) ou
    carrement 0777/0666 - souvent une erreur de copier-coller plutot qu'une
    intention (un binaire/config accessible en ecriture a tout le monde)."""
    digits = mode.lstrip("0") or "0"
    last = digits[-1]
    return last in ("2", "3", "6", "7")


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

    # --- Maintainer -----------------------------------------------------
    maintainer = config.get("maintainer", "")
    if maintainer in PLACEHOLDER_MAINTAINERS:
        warnings.append(
            "Aucun maintainer défini — le paquet sera généré avec "
            "'unknown <unknown@example.com>' (champ 'maintainer' dans meb.toml)"
        )
    elif not MAINTAINER_RE.match(maintainer.strip()):
        warnings.append(f"Format de maintainer inhabituel (attendu 'Nom <email>') : {maintainer}")

    # --- Icône ------------------------------------------------------------
    icon = app.get("icon")
    if icon:
        icon_path = (project / icon).resolve()
        if not icon_path.exists():
            errors.append(f"Icône introuvable : {icon}")
        else:
            console.print(f"[green]✔ Icône trouvée : {icon}[/green]")
    else:
        warnings.append("Aucune icône définie (app.icon)")

    # --- Exécutable ---------------------------------------------------------
    exec_value = app.get("exec")
    language = config.get("language", "")
    if exec_value:
        exec_path = (project / exec_value).resolve()
        if exec_path.exists():
            is_jar = exec_path.suffix.lower() == ".jar"
            if is_jar:
                console.print(f"[green]✔ Archive Java trouvée : {exec_value} (lanceur généré automatiquement)[/green]")
                if language != "java":
                    warnings.append(".jar détecté comme app.exec mais language != 'java' — vérifie meb.toml")
            elif os.access(exec_path, os.X_OK):
                console.print(f"[green]✔ Exécutable trouvé et exécutable : {exec_value}[/green]")
            else:
                warnings.append(f"{exec_value} existe mais n'est pas exécutable (chmod +x)")
        else:
            errors.append(f"Exécutable introuvable : {exec_value}")

    arch = config.get("package", {}).get("architecture")
    if arch not in ("amd64", "arm64", "armhf", "i386"):
        warnings.append(f"Architecture inconnue ou non standard : {arch}")

    # --- Dépendances Debian -------------------------------------------------
    depends = config.get("package", {}).get("depends", [])
    for d in depends:
        if not d.strip():
            warnings.append("Une entrée 'depends' est vide")

    # --- Services systemd -----------------------------------------------
    services = config.get("services", [])
    seen_names = set()
    for svc in services:
        svc_name = svc.get("name")
        if not svc_name:
            errors.append("Un service défini n'a pas de nom (services[].name)")
            continue
        if svc_name in seen_names:
            errors.append(f"Nom de service en double : {svc_name}")
        seen_names.add(svc_name)
        if svc.get("type") not in (None, "simple", "oneshot", "notify", "forking"):
            warnings.append(f"Type de service inconnu pour '{svc_name}' : {svc.get('type')}")
    if services:
        console.print(f"[green]✔ {len(services)} service(s) défini(s)[/green]")

    # --- Toutes les destinations "dans le paquet" (résolution de collisions) --
    all_dests: dict[str, str] = {}

    def _register_dest(dest: str, origin: str):
        norm = dest.rstrip("/")
        if norm in all_dests:
            errors.append(f"Destination en double dans le paquet : {norm} ({origin} vs {all_dests[norm]})")
        else:
            all_dests[norm] = origin

    # --- Ressources additionnelles --------------------------------------
    resources = config.get("resources", [])
    for r in resources:
        source = r.get("source")
        dest = r.get("dest")
        if not source or not dest:
            errors.append("Une entrée 'resources' doit avoir 'source' et 'dest'")
            continue
        if not (project / source).exists():
            errors.append(f"Ressource introuvable : {source}")
        if not dest.startswith("/"):
            errors.append(f"Destination de ressource non absolue : {dest}")
        else:
            _register_dest(dest, f"resources:{source}")
        mode = r.get("mode")
        if mode and not MODE_RE.match(mode):
            errors.append(f"Mode invalide pour la ressource '{source}' : {mode}")
        elif mode and _mode_is_overly_permissive(mode):
            warnings.append(f"Permission potentiellement trop permissive pour '{source}' : {mode} (accessible en écriture à tous ?)")
    if resources:
        console.print(f"[green]✔ {len(resources)} ressource(s) additionnelle(s) définie(s)[/green]")

    # --- Pages de manuel --------------------------------------------------
    man_pages = config.get("man", [])
    for m in man_pages:
        source = m.get("source")
        section = m.get("section", 1)
        if not source:
            errors.append("Une entrée 'man' doit avoir 'source'")
            continue
        if not (project / source).exists():
            errors.append(f"Page de manuel introuvable : {source}")
        if not isinstance(section, int) or not (1 <= section <= 8):
            errors.append(f"Section de manuel invalide pour '{source}' : {section} (attendu 1-8)")
    if man_pages:
        console.print(f"[green]✔ {len(man_pages)} page(s) de manuel définie(s)[/green]")

    # --- Auto-complétion ----------------------------------------------------
    completions = config.get("completions", {})
    for shell, value in completions.items():
        if shell not in KNOWN_SHELLS:
            warnings.append(f"Shell de complétion inconnu : {shell} (attendu {', '.join(KNOWN_SHELLS)})")
        if value and value != "auto" and not (project / value).exists():
            errors.append(f"Script de complétion {shell} introuvable : {value}")
    if completions:
        console.print(f"[green]✔ Complétion shell définie pour : {', '.join(completions.keys())}[/green]")

    # --- Fichiers de configuration (conffiles) -----------------------------
    conffiles = config.get("conffiles", [])
    for c in conffiles:
        source = c.get("source")
        dest = c.get("dest")
        if not source or not dest:
            errors.append("Une entrée 'conffiles' doit avoir 'source' et 'dest'")
            continue
        if not (project / source).exists():
            errors.append(f"Fichier de configuration introuvable : {source}")
        if not dest.startswith("/"):
            errors.append(f"Destination de conffile non absolue : {dest}")
        else:
            if not dest.startswith("/etc/"):
                warnings.append(f"Conffile hors de /etc/, inhabituel pour Debian : {dest}")
            _register_dest(dest, f"conffiles:{source}")
    if conffiles:
        console.print(f"[green]✔ {len(conffiles)} fichier(s) de configuration défini(s)[/green]")

    # --- Scripts de maintainer -----------------------------------------
    scripts = config.get("scripts", {})
    for hook, rel in scripts.items():
        if hook not in ("preinst", "postinst", "prerm", "postrm"):
            warnings.append(f"Hook de script inconnu : {hook} (attendu preinst/postinst/prerm/postrm)")
            continue
        script_path = project / rel
        if not script_path.exists():
            errors.append(f"Script '{hook}' introuvable : {rel}")
            continue
        try:
            first_line = script_path.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
            if not first_line.startswith("#!"):
                warnings.append(f"Script '{hook}' sans shebang (#!/bin/sh) en première ligne : {rel}")
        except IndexError:
            warnings.append(f"Script '{hook}' vide : {rel}")
    if scripts:
        console.print(f"[green]✔ Script(s) de maintainer personnalisé(s) : {', '.join(scripts.keys())}[/green]")

    # --- Permissions personnalisées ---------------------------------------
    permissions = config.get("permissions", [])
    seen_perm_paths = set()
    for p in permissions:
        perm_path = p.get("path", "")
        mode = p.get("mode", "")
        if not perm_path or not mode:
            errors.append("Une entrée 'permissions' doit avoir 'path' et 'mode'")
            continue
        if perm_path.startswith("/"):
            warnings.append(f"'permissions[].path' doit être relatif à la racine du paquet, pas absolu : {perm_path}")
        if not MODE_RE.match(mode):
            errors.append(f"Mode invalide pour '{perm_path}' : {mode}")
        elif _mode_is_overly_permissive(mode):
            warnings.append(f"Permission potentiellement trop permissive : {perm_path} -> {mode}")
        if perm_path in seen_perm_paths:
            warnings.append(f"Permission définie plusieurs fois pour : {perm_path}")
        seen_perm_paths.add(perm_path)
    if permissions:
        console.print(f"[green]✔ {len(permissions)} permission(s) personnalisée(s) définie(s)[/green]")

    # --- README embarqué --------------------------------------------------
    readme = app.get("readme")
    if readme and not (project / readme).exists():
        errors.append(f"README introuvable : {readme}")

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
