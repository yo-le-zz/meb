import re
from pathlib import Path


def _parse_maven(pom: Path) -> dict:
    # Pas de dépendance XML externe : extraction best-effort par regex sur
    # les balises de premier niveau <project><name/artifactId/version/description>.
    # On ignore volontairement tout ce qui est imbriqué dans <parent>...</parent>
    # ou <dependencies>...</dependencies> pour éviter de récupérer la version
    # d'une dépendance à la place de celle du projet.
    text = pom.read_text(encoding="utf-8", errors="ignore")
    text = re.sub(r"<parent>.*?</parent>", "", text, flags=re.DOTALL)
    text = re.sub(r"<dependencies>.*?</dependencies>", "", text, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    def _field(tag: str) -> str | None:
        m = re.search(rf"<{tag}>(.*?)</{tag}>", text, flags=re.DOTALL)
        return m.group(1).strip() if m else None

    return {
        "name": _field("artifactId") or _field("name"),
        "version": _field("version"),
        "description": _field("description"),
    }


def _parse_gradle(build_file: Path) -> dict:
    text = build_file.read_text(encoding="utf-8", errors="ignore")

    def _field(pattern: str) -> str | None:
        m = re.search(pattern, text)
        return m.group(1).strip() if m else None

    return {
        "name": _field(r"rootProject\.name\s*=\s*['\"]([^'\"]+)['\"]"),
        "version": _field(r"version\s*=\s*['\"]([^'\"]+)['\"]"),
        "description": _field(r"description\s*=\s*['\"]([^'\"]+)['\"]"),
    }


def parse(project: Path) -> dict:
    pom = project / "pom.xml"
    if pom.exists():
        try:
            return _parse_maven(pom)
        except Exception:
            return {}

    settings = project / "settings.gradle"
    settings_kts = project / "settings.gradle.kts"
    build_gradle = project / "build.gradle"
    build_gradle_kts = project / "build.gradle.kts"

    for f in (settings, settings_kts, build_gradle, build_gradle_kts):
        if f.exists():
            try:
                data = _parse_gradle(f)
                if any(data.values()):
                    return data
            except Exception:
                continue

    return {}
