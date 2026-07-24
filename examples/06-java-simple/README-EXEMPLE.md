# Exemple 6 — Java minimal (Maven, uber-jar)

`pom.xml` détecté comme langage "java" — la balise `<parent>` (version
99.0.0, volontairement absurde) est ignorée pour ne pas polluer la version
du projet, seule celle du `<project>` racine compte (4.0.1).

`target/javahello-4.0.1-shaded.jar` est un .jar minimal valide (juste un
META-INF/MANIFEST.MF, sans .class compilé — suffisant pour tester la
détection et l'empaquetage meb, mais il ne s'exécutera pas réellement avec
`java -jar`). Le suffixe `-shaded` est reconnu en priorité (convention
uber-jar auto-suffisant).

```bash
./scripts/dev.sh check --path examples/06-java-simple
./scripts/dev.sh build --path examples/06-java-simple
```

Vérifie que `meb build` génère bien un lanceur `/usr/bin/javahello`
(`exec java -jar ...`) et ajoute une dépendance JRE automatiquement.
