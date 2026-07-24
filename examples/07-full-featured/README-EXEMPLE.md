# Exemple 7 — Démo complète (toutes les sections)

Cet exemple embarque déjà un `meb.toml` entièrement rempli (pas besoin de
`meb init`/`meb config`) pour illustrer et tester en une fois :

- icônes multi-résolution (16x16, 32x32, 256x256, un dossier entier)
- lanceur `.desktop`
- README embarqué
- ressources additionnelles (deux thèmes JSON)
- page de manuel (`man novaworker`)
- auto-complétion (fish fourni, bash généré automatiquement via "auto")
- fichier de configuration (conffile)
- script `postinst` personnalisé
- permissions Unix personnalisées
- service systemd

```bash
./scripts/dev.sh check --path examples/07-full-featured
./scripts/dev.sh build --path examples/07-full-featured

# Inspecter le .deb généré :
dpkg-deb -c examples/07-full-featured/dist/novaworker_1.4.0_amd64.deb
dpkg-deb -e examples/07-full-featured/dist/novaworker_1.4.0_amd64.deb /tmp/novaworker-ctrl
cat /tmp/novaworker-ctrl/control
```
