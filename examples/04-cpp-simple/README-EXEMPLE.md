# Exemple 4 — C++ minimal (CMake)

`CMakeLists.txt` détecté comme langage "cpp". Pas de nom/version/
description auto-détectés (CMake n'a pas de format standardisé pour ces
métadonnées) : `meb init`/`meb config` devront les demander manuellement,
ou compléter `meb.toml` toi-même — c'est le comportement attendu, pas un
bug.

```bash
./scripts/dev.sh check --path examples/04-cpp-simple
./scripts/dev.sh build --path examples/04-cpp-simple
```
