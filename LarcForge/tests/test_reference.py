"""Tests du rendu Markdown de la référence des contrôles (larcforge.reference).

Le rendu consomme discover_checks() — on verrouille ici la forme du document
généré (titre, compteurs, contenu linter + reviewer).
"""

from __future__ import annotations

from larcforge import reference

CHECKS = {
    "linters": [
        {"key": "D", "label": "Couleurs", "category": "theme",
         "description": "desc", "skill": "color-rules",
         "script": "lint_d1.py", "doc": "Vérifie X."},
    ],
    "reviewers": [
        {"name": "design-review", "description": "audit",
         "category": "quality", "trigger": "audit design",
         "body": "## Procédure\n\nÉtape 1."},
    ],
}


def test_render_markdown_contient_linters_et_reviewers():
    md = reference.render_markdown(CHECKS)
    assert "## Linters (1)" in md
    assert "## Reviewers (1)" in md
    assert "[D] Couleurs" in md
    assert "Vérifie X." in md
    assert "design-review" in md
    # Les titres du corps du reviewer sont rétrogradés pour ne pas casser
    # le plan du document (## → ####, rattaché au ### design-review).
    assert "#### Procédure" in md
    assert "\n## Procédure" not in md


def test_render_markdown_entete_generation():
    md = reference.render_markdown(CHECKS)
    assert md.startswith("# Référence des contrôles")
    assert "python -m larcforge docs" in md


def test_render_markdown_vide():
    md = reference.render_markdown({"linters": [], "reviewers": []})
    assert "## Linters (0)" in md
    assert "## Reviewers (0)" in md
    assert "Aucun linter découvert" in md
    assert "Aucun reviewer découvert" in md
