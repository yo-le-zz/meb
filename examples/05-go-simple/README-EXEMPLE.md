# Exemple 5 — Go minimal

`go.mod` détecté comme langage "go" (nom déduit du dernier segment du
module path, ici "gohello" — Go n'expose ni version ni description dans
`go.mod`). Le binaire produit par `go build` est cherché directement à la
racine du projet, dans `bin/`, ou dans `cmd/<name>/`.

```bash
./scripts/dev.sh check --path examples/05-go-simple
./scripts/dev.sh build --path examples/05-go-simple
```
