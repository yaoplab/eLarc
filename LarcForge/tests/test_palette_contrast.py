"""Tests du linter contraste palette (scripts/lint_palette_contrast.py).

Le linter vit dans scripts/ (hors package) — importé par chemin via importlib.
On verrouille l'invariant central : la palette ne doit JAMAIS contenir de
contraste P0 (texte inversé ou illisible — < 3:1 sur un texte lisible).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]  # F:\projets
LINTER = ROOT / "scripts" / "lint_palette_contrast.py"


@pytest.fixture(scope="module")
def linter():
    spec = importlib.util.spec_from_file_location("lint_palette_contrast", LINTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_contrast_ratio_noir_sur_blanc(linter):
    assert linter.contrast_ratio("#FFFFFF", "#000000") == pytest.approx(21.0, abs=0.01)
    assert linter.contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0, abs=0.01)


def test_relative_luminance_extremes(linter):
    assert linter.relative_luminance("#FFFFFF") == pytest.approx(1.0, abs=0.001)
    assert linter.relative_luminance("#000000") == pytest.approx(0.0, abs=0.001)


def test_read_themes_quatre_palettes(linter):
    is_dark, palettes = linter.read_themes()
    assert {"blue", "dark", "sobre", "contrast"} <= set(palettes)
    assert is_dark["dark"] is True
    assert is_dark["blue"] is False
    assert is_dark["sobre"] is False


def test_scan_palette_sans_p0(linter):
    """Invariant : aucun contraste inversé ou illisible dans la palette centrale."""
    violations = linter.scan_palette()
    p0 = [v for v in violations if v.get("severity") == "P0"]
    assert p0 == [], f"Contraste P0 détecté dans la palette : {p0}"
