import os
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


def detect_executable(project: Path, language: str | None, name: str) -> Path | None:
    """Détecte l'exécutable Linux compilé du projet.

    Stratégie générale :
      1. dist/<name> ou dist/<name>/<name> (convention la plus courante,
         tous langages confondus)
      2. Selon le langage détecté, chemins spécifiques au compilateur
         (pyinstaller -> dist/, nuitka -> <name>.dist/, cargo -> target/release/, ...)
      3. Dernier recours : n'importe quel binaire présent dans dist/
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

    # Dernier recours : tout binaire non-Windows trouvé dans dist/
    for cand in _linux_binary_candidates(dist_dir, name):
        return cand

    return None
