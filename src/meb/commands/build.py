import stat
import shutil
import subprocess
import tomllib

from pathlib import Path
from rich.console import Console

console = Console()


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
    maintainer = config.get("maintainer", "unknown <unknown@example.com>")
    category = app.get("category", "Utility")

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

    # DEBIAN/control
    installed_size_kb = max(1, dest_exec.stat().st_size // 1024)
    control_content = f"""Package: {name}
Version: {version}
Section: utils
Priority: optional
Architecture: {arch}
Maintainer: {maintainer}
Installed-Size: {installed_size_kb}
Description: {description}
"""
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


if __name__ == "__main__":
    run()