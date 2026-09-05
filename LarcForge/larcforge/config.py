"""Configuration LarcForge : racine du monorepo, projets, linters, versions.

La racine n'est jamais hardcodée : elle est dérivée de l'emplacement du package
(LarcForge est enfant direct de la racine). Priorité : --root > LARCFORGE_ROOT > détection.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path

from .taxonomy import discover_linters

_DEFAULT_ROOT = Path(__file__).resolve().parents[2]


def find_root(override: str | None = None) -> Path:
    """Racine du monorepo (validation : LarcCommon présent)."""
    root = Path(override) if override else Path(os.environ.get("LARCFORGE_ROOT") or _DEFAULT_ROOT)
    if not (root / "LarcCommon").is_dir():
        raise SystemExit(
            f"ERREUR : {root} n'est pas la racine du monorepo (LarcCommon introuvable).\n"
            "Utilisez --root <chemin> ou la variable LARCFORGE_ROOT."
        )
    return root


# Repos scannés par les linters
PROJETS = [
    "LarcCommon",
    "LarcSuperviseur",
    "LarcSecretaire",
    "LarcProf",
    "LarcHub",
    "LarcConfig",
    "LarcRH",
    "LarcCompta",
]

# Fallback statique si scripts/ est absent (découverte via LINTER_META sinon).
# audit_design_system.py exclu (pas de --json) jusqu'à une étape ultérieure.
_FALLBACK_LINTERS = [
    ("R", "lint_qss_hardcoding.py"),
    ("D", "lint_d1_color_checker.py"),
    ("V", "lint_ui_quality.py"),
    ("C", "lint_preflight.py"),
    ("S", "lint_safe_slot.py"),
    ("FS", "lint_file_size.py"),
    ("DB", "lint_db_checker.py"),
    ("AUTH", "lint_auth_checker.py"),
    ("COV", "lint_test_coverage.py"),
    ("REACT", "audit_theme_reactive.py"),
    ("CTR", "lint_palette_contrast.py"),
]


def _discover_linters() -> list[tuple[str, str]]:
    """(clé, script) auto-découverts via LINTER_META ; fallback statique sinon.

    Déposer un linter dans scripts/ avec un header LINTER_META suffit à le voir
    apparaître ici — aucun code à modifier. Retourne une liste de tuples (clé,
    script) car c'est le contrat attendu par collectors/linters.py et l'IHM.
    """
    metas = discover_linters(_DEFAULT_ROOT / "scripts")
    if metas:
        return [(m["key"], m["script"]) for m in metas]
    return _FALLBACK_LINTERS


LINTERS = _discover_linters()

LINTER_KEYS = [k for k, _ in LINTERS]

# Repos avec un dossier tests/ (pytest)
TEST_PROJECTS = ["LarcCommon", "LarcSuperviseur", "LarcProf", "LarcPhibuilder"]

# Dossiers exclus du snapshot de modules et du scan
EXCLUDE_DIRS = {"tests", "__pycache__", ".venv", ".git", "node_modules", "dist",
                ".pytest_cache", ".ruff_cache", "egg-info", "docs", "algo", "specificationsMobile"}

EXCLUDE_SUFFIXES = {".png", ".jpg", ".svg", ".json", ".sql", ".ini", ".toml", ".md", ".bat"}


def larc_version(root: Path) -> str:
    """Version LarcCommon : VERSION à la racine, sinon config.ini [App] Version."""
    try:
        v = (root / "VERSION").read_text(encoding="utf-8").strip()
        if v:
            return v
    except OSError:
        pass
    try:
        cp = configparser.ConfigParser()
        cp.read(root / "LarcCommon" / "config.ini", encoding="utf-8")
        return cp.get("App", "Version", fallback="inconnue")
    except Exception:
        return "inconnue"
