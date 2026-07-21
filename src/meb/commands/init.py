import tomli_w

from pathlib import Path
from rich.console import Console

console = Console()

config = {
    "name": "",
    "version": "1.0.0",
    "description": "",
    
    "package": {
        "architecture": "amd64"
    },

    "app": {
        "icon": ""
    }
}

def run(path: str = "."):
    project = Path(path).resolve()

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



if __name__ == "__main__":
    run()