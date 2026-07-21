import typer

# Importes des fonction de puis le __init__.py de commands
from commands import version, init, config, check, build

app = typer.Typer()

app.command(name="version")(version.run)
app.command(name="init")(init.run)
app.command(name="config")(config.run)
app.command(name="check")(check.run)
app.command(name="build")(build.run)


if __name__ == "__main__":
    app()