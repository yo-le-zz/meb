from pathlib import Path


def parse(project: Path) -> dict:
    # CMakeLists.txt / Makefile n'ont pas de format standardisé pour
    # les métadonnées : on se contente de détecter la présence du langage,
    # le nom/version restent à la charge de l'utilisateur (via meb init).
    return {}