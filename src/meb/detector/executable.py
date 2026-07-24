import os
import re
from pathlib import Path


def _is_usable(path: Path) -> bool:
    """Un binaire Linux valide : fichier existant, pas un .exe/.dll Windows."""
    if not path.is_file():
        return False
    if path.suffix.lower() in (".exe", ".dll", ".pdb"):
        return False
    return True


def _linux_binary_candidates(directory: Path, name: str) -> list[Path]:
    if not directory.is_dir():
        return []
    candidates = []
    for f in directory.iterdir():
        if f.is_file() and f.suffix.lower() not in (".exe", ".dll", ".pdb", ".so", ".dylib"):
            candidates.append(f)
    # Priorité au fichier qui porte exactement le nom de l'app
    candidates.sort(key=lambda f: (f.name != name, f.name))
    return candidates


def detect_compiler(project: Path) -> str | None:
    """Devine le compilateur/packager Python utilisé (pyinstaller, nuitka)."""
    # Nuitka laisse un dossier <name>.dist / <name>.build / <name>.onefile-build
    for suffix in (".dist", ".build", ".onefile-build"):
        if list(project.glob(f"*{suffix}")):
            return "nuitka"

    # PyInstaller laisse un fichier .spec à la racine
    if list(project.glob("*.spec")):
        return "pyinstaller"

    pyproject = project / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib
            with open(pyproject, "rb") as fh:
                data = tomllib.load(fh)
            deps = " ".join(data.get("project", {}).get("dependencies", [])).lower()
            deps += " ".join(
                data.get("dependency-groups", {}).get("dev", [])
            ).lower() if isinstance(data.get("dependency-groups", {}).get("dev"), list) else ""
            if "nuitka" in deps:
                return "nuitka"
            if "pyinstaller" in deps:
                return "pyinstaller"
        except Exception:
            pass

    return None


def _detect_python_executable(project: Path, name: str) -> Path | None:
    compiler = detect_compiler(project)

    if compiler in ("pyinstaller", None):
        dist_dir = project / "dist"
        for candidate in (dist_dir / name, dist_dir / name / name):
            if _is_usable(candidate):
                return candidate

    if compiler in ("nuitka", None):
        for suffix in (".dist", ".onefile-build", ".build"):
            nuitka_dir = project / f"{name}{suffix}"
            if nuitka_dir.is_dir():
                for candidate in (nuitka_dir / name, nuitka_dir / f"{name}.bin"):
                    if _is_usable(candidate):
                        return candidate
        # Nuitka --onefile produit parfois directement <name> à la racine
        onefile = project / name
        if _is_usable(onefile) and os.access(onefile, os.X_OK):
            return onefile

    return None


def _detect_java_artifact(project: Path, name: str) -> Path | None:
    """Java n'a pas de binaire natif : on cherche le .jar exécutable produit
    par Maven (target/*.jar) ou Gradle (build/libs/*.jar). meb enveloppera
    ce .jar dans un lanceur shell (voir commands/build.py)."""
    search_dirs = (project / "target", project / "build" / "libs")
    jars = []
    for d in search_dirs:
        if d.is_dir():
            jars.extend(d.glob("*.jar"))

    if not jars:
        return None

    # On écarte les jars "sources"/"javadoc" et on privilégie celui qui
    # porte le nom de l'app ou le suffixe -shaded/-all/-fat (fréquent pour
    # les uber-jars auto-suffisants).
    jars = [j for j in jars if not re.search(r"(sources|javadoc)\.jar$", j.name)]
    if not jars:
        return None

    def _score(j: Path) -> tuple:
        stem = j.stem.lower()
        exact = stem != name.lower()
        fat = 0 if re.search(r"(shaded|all|fat)$", stem) else 1
        return (exact, fat, stem)

    jars.sort(key=_score)
    return jars[0]


def _detect_go_executable(project: Path, name: str) -> Path | None:
    candidates = [
        project / name,
        project / "bin" / name,
        project / "cmd" / name / name,
    ]
    for candidate in candidates:
        if _is_usable(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def detect_executable(project: Path, language: str | None, name: str) -> Path | None:
    """Détecte l'exécutable Linux compilé du projet.

    Stratégie générale :
      1. dist/<name> ou dist/<name>/<name> (convention la plus courante,
         tous langages confondus)
      2. Selon le langage détecté, chemins spécifiques au compilateur
         (pyinstaller -> dist/, nuitka -> <name>.dist/, cargo -> target/release/, ...)
      3. Dernier recours : n'importe quel binaire présent dans dist/

    Pour "java", retourne un .jar (pas un binaire natif) — voir
    `is_jar_artifact()` : c'est à `meb build` d'en générer un lanceur.
    """
    name = name or ""
    if not name:
        return None

    dist_dir = project / "dist"
    if dist_dir.is_dir():
        for candidate in (dist_dir / name, dist_dir / name / name):
            if _is_usable(candidate):
                return candidate

    if language == "python":
        found = _detect_python_executable(project, name)
        if found:
            return found

    if language == "rust":
        for profile in ("release", "debug"):
            candidate = project / "target" / profile / name
            if _is_usable(candidate):
                return candidate

    if language == "node":
        for candidate in (dist_dir / name, project / "bin" / name, project / "out" / name):
            if _is_usable(candidate):
                return candidate

    if language == "cpp":
        for candidate in (
            project / "build" / name,
            project / "build" / "bin" / name,
            project / "cmake-build-release" / name,
            project / name,
        ):
            if _is_usable(candidate):
                return candidate

    if language == "go":
        found = _detect_go_executable(project, name)
        if found:
            return found

    if language == "java":
        found = _detect_java_artifact(project, name)
        if found:
            return found

    # Dernier recours : tout binaire non-Windows trouvé dans dist/
    for cand in _linux_binary_candidates(dist_dir, name):
        return cand

    return None


def is_jar_artifact(path: Path | None) -> bool:
    return bool(path) and path.suffix.lower() == ".jar"
