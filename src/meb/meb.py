import typer

# Importes des fonction de puis le __init__.py de commands
from commands import version, init, config, check, build

# pretty_exceptions_enable=False : évite que Typer/Click importe rich.traceback
# (qui tire pygments et ses ~500 modules de lexers) juste pour la coloration
# des tracebacks en cas d'erreur — inutile ici, et ça multiplie par un facteur
# énorme le temps de compilation Nuitka (surtout sous QEMU en cross-arch).
app = typer.Typer(pretty_exceptions_enable=False)

app.command(name="version")(version.run)
app.command(name="init")(init.run)
app.command(name="config")(config.run)
app.command(name="check")(check.run)
app.command(name="build")(build.run)


if __name__ == "__main__":
    app()