import stat
import shutil
import subprocess
import tomllib

from pathlib import Path
from rich.console import Console

from info import APP_AUTHOR, APP_GITHUB, APP_WEBSITE

console = Console()

VALID_SERVICE_TYPES = {"simple", "oneshot", "notify", "forking"}
VALID_RESTART = {"no", "on-failure", "always", "on-abnormal"}


def _build_unit_content(service: dict, app_name: str, description_fallback: str) -> str:
    svc_type = service.get("type") or "simple"
    if svc_type not in VALID_SERVICE_TYPES:
        svc_type = "simple"

    restart = service.get("restart") or "on-failure"
    if restart not in VALID_RESTART:
        restart = "on-failure"

    user = service.get("user") or "root"
    args = service.get("args") or ""
    exec_start = f"/usr/bin/{app_name}" + (f" {args}" if args else "")
    description = service.get("description") or description_fallback

    lines = [
        "[Unit]",
        f"Description={description}",
        "After=network.target",
        "",
        "[Service]",
        f"Type={svc_type}",
        f"ExecStart={exec_start}",
        f"User={user}",
        f"Restart={restart}",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
        "",
    ]
    return "\n".join(lines)


def _write_services(build_root: Path, services: list[dict], app_name: str, description_fallback: str) -> list[str]:
    """Écrit les fichiers .service dans DEBIAN et renvoie la liste des noms d'unités."""
    if not services:
        return []

    systemd_dir = build_root / "usr" / "lib" / "systemd" / "system"
    systemd_dir.mkdir(parents=True, exist_ok=True)

    unit_names = []
    for service in services:
        name = service.get("name")
        if not name:
            continue
        unit_name = f"{name}.service"
        content = _build_unit_content(service, app_name, description_fallback)
        (systemd_dir / unit_name).write_text(content, encoding="utf-8")
        unit_names.append((unit_name, bool(service.get("enable", True))))

    return unit_names


def _write_maintainer_scripts(debian_dir: Path, unit_names: list[tuple]):
    if not unit_names:
        return

    enable_lines = [
        f"    systemctl enable --now {unit_name} >/dev/null 2>&1 || true"
        for unit_name, enable in unit_names
        if enable
    ]
    enable_block = ("\n" + "\n".join(enable_lines)) if enable_lines else ""

    postinst = "#!/bin/sh\nset -e\n\nif command -v systemctl >/dev/null 2>&1; then\n    systemctl daemon-reload >/dev/null 2>&1 || true" + enable_block + "\nfi\n\nexit 0\n"

    stop_lines = "\n".join(f"    systemctl stop {unit_name} >/dev/null 2>&1 || true\n    systemctl disable {unit_name} >/dev/null 2>&1 || true" for unit_name, _ in unit_names)
    prerm = "#!/bin/sh\nset -e\n\nif command -v systemctl >/dev/null 2>&1; then\n" + stop_lines + "\nfi\n\nexit 0\n"

    postrm = "#!/bin/sh\nset -e\n\nif command -v systemctl >/dev/null 2>&1; then\n    systemctl daemon-reload >/dev/null 2>&1 || true\nfi\n\nexit 0\n"

    for filename, content in (("postinst", postinst), ("prerm", prerm), ("postrm", postrm)):
        target = debian_dir / filename
        target.write_text(content, encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def run(path: str = ".", output: str = "dist"):
    project = Path(path).resolve()
    config_file = project / "meb.toml"

    if not config_file.exists():
        console.print("[red]✘ meb.toml introuvable. Lance 'meb config' d'abord.[/red]")
        raise SystemExit(1)

    with open(config_file, "rb") as f:
        config = tomllib.load(f)

    name = config.get("name")
    version = config.get("version", "1.0.0")
    description = config.get("description", "")
    arch = config.get("package", {}).get("architecture", "amd64")
    app = config.get("app", {})
    exec_rel = app.get("exec")
    icon_rel = app.get("icon")
    maintainer = config.get("maintainer") or "unknown <unknown@example.com>"
    category = app.get("category", "Utility")
    services = config.get("services", [])

    if not name or not exec_rel:
        console.print("[red]✘ Configuration incomplète (name / app.exec requis). Lance 'meb check'.[/red]")
        raise SystemExit(1)

    exec_path = project / exec_rel
    if not exec_path.exists():
        console.print(f"[red]✘ Exécutable introuvable : {exec_rel}[/red]")
        raise SystemExit(1)

    pkg_dirname = f"{name}_{version}_{arch}"
    out_dir = project / output
    build_root = out_dir / pkg_dirname

    console.print(f"[cyan]Construction du paquet : {pkg_dirname}.deb[/cyan]")

    if build_root.exists():
        shutil.rmtree(build_root)

    debian_dir = build_root / "DEBIAN"
    bin_dir = build_root / "usr" / "bin"
    apps_dir = build_root / "usr" / "share" / "applications"
    icons_base = build_root / "usr" / "share" / "icons" / "hicolor"

    debian_dir.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    apps_dir.mkdir(parents=True)

    # Exécutable
    dest_exec = bin_dir / name
    shutil.copy2(exec_path, dest_exec)
    dest_exec.chmod(dest_exec.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # Icône
    icon_installed_name = None
    if icon_rel:
        icon_path = project / icon_rel
        if icon_path.exists():
            if icon_path.is_dir():
                shutil.copytree(icon_path, icons_base, dirs_exist_ok=True)
                icon_installed_name = name
            else:
                size_dir = icons_base / "256x256" / "apps"
                size_dir.mkdir(parents=True, exist_ok=True)
                dest_icon = size_dir / f"{name}{icon_path.suffix}"
                shutil.copy2(icon_path, dest_icon)
                icon_installed_name = name
        else:
            console.print(f"[yellow]! Icône introuvable, ignorée : {icon_rel}[/yellow]")

    # Fichier .desktop
    desktop_file = apps_dir / f"{name}.desktop"
    desktop_content = f"""[Desktop Entry]
Type=Application
Name={name}
Comment={description}
Exec={name}
Icon={icon_installed_name or name}
Terminal=true
Categories={category};
"""
    desktop_file.write_text(desktop_content, encoding="utf-8")

    # Services systemd (optionnels)
    unit_names = _write_services(build_root, services, name, description)
    if unit_names:
        _write_maintainer_scripts(debian_dir, unit_names)
        console.print(f"[green]✔ {len(unit_names)} service(s) systemd empaqueté(s)[/green]")

    # DEBIAN/control
    installed_size_kb = max(1, dest_exec.stat().st_size // 1024)
    control_content = f"""Package: {name}
Version: {version}
Section: utils
Priority: optional
Architecture: {arch}
Maintainer: {maintainer}
Installed-Size: {installed_size_kb}
Homepage: {APP_GITHUB}
Description: {description}
"""
    if unit_names:
        control_content += "Depends: systemd\n"
    (debian_dir / "control").write_text(control_content, encoding="utf-8")

    # dpkg-deb
    deb_path = out_dir / f"{pkg_dirname}.deb"
    try:
        subprocess.run(
            ["dpkg-deb", "--build", "--root-owner-group", str(build_root), str(deb_path)],
            check=True,
        )
    except FileNotFoundError:
        console.print("[red]✘ dpkg-deb introuvable. Installe le paquet 'dpkg'.[/red]")
        raise SystemExit(1)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✘ Échec de dpkg-deb : {e}[/red]")
        raise SystemExit(1)

    console.print(f"[green]✔ Paquet créé : {deb_path}[/green]")
    console.print(f"[dim]Meb — par {APP_AUTHOR} · {APP_GITHUB} · {APP_WEBSITE}[/dim]")


if __name__ == "__main__":
    run()
