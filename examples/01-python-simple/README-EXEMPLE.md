# Exemple 1 — Python minimal

Cas le plus simple : un `pyproject.toml` + un exécutable déjà "compilé"
dans `dist/` (ici un script shell qui simule un binaire PyInstaller/Nuitka,
pour ne pas dépendre d'un vrai compilateur dans cet exemple).

Teste avec :

```bash
./scripts/dev.sh init  --path examples/01-python-simple
./scripts/dev.sh check --path examples/01-python-simple
./scripts/dev.sh build --path examples/01-python-simple
```

Vérifie que `meb init` détecte bien `language = "python"`,
`name = "pyhello"`, `version = "1.0.0"` et `app.exec = "dist/pyhello"`
automatiquement.
