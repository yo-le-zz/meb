# Exemples

Mini-projets factices pour tester rapidement chaque chemin de détection et
chaque fonctionnalité de meb, sans avoir besoin d'installer un compilateur
par langage. Les "exécutables compilés" (`dist/`, `target/release/`,
`build/`, ...) sont de simples scripts shell exécutables qui simulent la
sortie d'un vrai build — suffisants pour tester `meb init`/`config`/
`check`/`build`, mais qui n'ont évidemment pas le comportement réel de
l'application (sauf l'exemple 07, tous affichent juste un `echo`).

Lance les commandes depuis la racine du dépôt, avec le script de dev
(pas besoin de compiler meb) :

```bash
./scripts/dev.sh check --path examples/01-python-simple
./scripts/dev.sh build --path examples/01-python-simple
```

Ou en tout automatique sur l'ensemble des exemples :

```bash
for d in examples/*/; do
  echo "=== $d ==="
  ./scripts/dev.sh init  --path "$d" 2>/dev/null || true
  ./scripts/dev.sh check --path "$d"
  ./scripts/dev.sh build --path "$d"
done
```

## Sommaire

| Dossier                    | Démontre                                                        |
|-----------------------------|-------------------------------------------------------------------|
| `01-python-simple/`         | Détection Python (`pyproject.toml`), cas le plus simple           |
| `02-node-simple/`           | Détection Node.js (`package.json`)                                |
| `03-rust-simple/`           | Détection Rust (`Cargo.toml`)                                     |
| `04-cpp-simple/`            | Détection C++ via CMake (pas de métadonnées auto-détectées)       |
| `05-go-simple/`             | Détection Go (`go.mod`, nom déduit du module path)                |
| `06-java-simple/`           | Détection Java/Maven, uber-jar, lanceur + dépendance JRE auto      |
| `07-full-featured/`         | `meb.toml` complet : icônes multi-résolution, `.desktop`, README embarqué, ressources, man, complétion, conffiles, script `postinst`, permissions, service systemd |
| `08-c-makefile-simple/`     | Détection C via `Makefile` (variante sans CMake)                  |

Chaque dossier a son propre `README-EXEMPLE.md` avec le détail de ce qu'il
teste et les commandes exactes à lancer.

## Pour aller plus loin

Une fois `meb check` au vert sur un exemple, inspecte le `.deb` généré :

```bash
dpkg-deb -c examples/07-full-featured/dist/novaworker_1.4.0_amd64.deb   # contenu
dpkg-deb -e examples/07-full-featured/dist/novaworker_1.4.0_amd64.deb /tmp/ctrl  # métadonnées
cat /tmp/ctrl/control
```
