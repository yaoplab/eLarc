"""Tests de la taxonomie des types d'erreur : catégories, auto-découverte, couleurs.

Les linters sont lus par AST (pas d'import), les skills par leur frontmatter —
aucune base, aucun PySide6 requis ici (sauf les couleurs, gardées par skip).
"""

from __future__ import annotations

import pytest

from larcforge import taxonomy


# ── category_for ───────────────────────────────────────────────────────────


def test_category_for_sources_linter():
    assert taxonomy.category_for("linter:R") == "theme"
    assert taxonomy.category_for("linter:D") == "theme"
    assert taxonomy.category_for("linter:REACT") == "theme"
    assert taxonomy.category_for("linter:V") == "ui"
    assert taxonomy.category_for("linter:S") == "qt"
    assert taxonomy.category_for("linter:C") == "checklist"
    assert taxonomy.category_for("linter:FS") == "filesize"
    assert taxonomy.category_for("linter:DB") == "data"
    assert taxonomy.category_for("linter:AUTH") == "auth"
    assert taxonomy.category_for("linter:COV") == "tests"


def test_category_for_sources_non_linter():
    assert taxonomy.category_for("pytest") == "tests"
    assert taxonomy.category_for("errorlog") == "runtime"
    assert taxonomy.category_for("larcforge:build") == "build"


def test_category_for_inconnu_fallback_ui():
    assert taxonomy.category_for(None) == "ui"
    assert taxonomy.category_for("") == "ui"
    assert taxonomy.category_for("linter:ZZ") == "ui"


def test_all_categories_contient_les_dix():
    cats = taxonomy.all_categories()
    assert len(cats) == 10
    assert {"theme", "ui", "qt", "checklist", "filesize", "data",
            "auth", "tests", "runtime", "build"} <= set(cats)


def test_category_info_retourne_label_icone():
    info = taxonomy.category_info("theme")
    assert info["label"] == "Thème & Design"
    assert info["icon"]
    assert info["description"]


# ── discover_linters (auto-découverte AST) ─────────────────────────────────


LINTER_OK = '''
"""Doc."""
LINTER_META = {
    "key": "ZZ",
    "label": "Linter factice",
    "category": "tests",
    "description": "factice",
    "skill": "larc-testing",
}
print("effet de bord si importé — ne doit PAS s'exécuter")
'''

LINTER_SANS_META = '''
"""Doc."""
print("pas de meta")
'''

LINTER_PAS_DICT = '''
LINTER_META = "pas un dict"
'''

LINTER_CLE_MANQUANTE = '''
LINTER_META = {"key": "W", "label": "x"}  # category absente
'''


def test_discover_linters_trouve_meta(tmp_path):
    (tmp_path / "fake_linter.py").write_text(LINTER_OK, encoding="utf-8")
    found = taxonomy.discover_linters(tmp_path)
    assert len(found) == 1
    assert found[0]["key"] == "ZZ"
    assert found[0]["script"] == "fake_linter.py"
    assert found[0]["category"] == "tests"


def test_discover_linters_ignore_sans_meta(tmp_path):
    (tmp_path / "no_meta.py").write_text(LINTER_SANS_META, encoding="utf-8")
    assert taxonomy.discover_linters(tmp_path) == []


def test_discover_linters_ignore_meta_invalide(tmp_path):
    (tmp_path / "not_dict.py").write_text(LINTER_PAS_DICT, encoding="utf-8")
    (tmp_path / "missing.py").write_text(LINTER_CLE_MANQUANTE, encoding="utf-8")
    assert taxonomy.discover_linters(tmp_path) == []


def test_discover_linters_trie_par_cle(tmp_path):
    (tmp_path / "a.py").write_text(LINTER_OK.replace('"ZZ"', '"BB"'), encoding="utf-8")
    (tmp_path / "b.py").write_text(LINTER_OK.replace('"ZZ"', '"AA"'), encoding="utf-8")
    found = taxonomy.discover_linters(tmp_path)
    assert [m["key"] for m in found] == ["AA", "BB"]


def test_discover_linters_met_a_jour_la_taxonomie(tmp_path):
    (tmp_path / "fake_linter.py").write_text(LINTER_OK, encoding="utf-8")
    taxonomy.discover_linters(tmp_path)
    assert taxonomy.category_for("linter:ZZ") == "tests"


def test_discover_linters_dossier_absent(tmp_path):
    assert taxonomy.discover_linters(tmp_path / "inexistant") == []


# ── discover_skills (frontmatter .claude/skills) ───────────────────────────


SKILL = """---
name: dummy-skill
description: Une description de skill
category: design
trigger: dummy
---

# Dummy
"""

REVIEW = """---
name: dummy-review
description: Une revue (doit être exclue)
category: quality
trigger: revue dummy
---
"""


def test_discover_skills_parse_frontmatter(tmp_path):
    skills = tmp_path / ".claude" / "skills"
    skills.mkdir(parents=True)
    (skills / "dummy-skill.md").write_text(SKILL, encoding="utf-8")
    lookup = taxonomy.discover_skills(tmp_path)
    assert lookup["dummy-skill"] == "Une description de skill"


def test_discover_skills_exclut_les_reviews(tmp_path):
    skills = tmp_path / ".claude" / "skills"
    skills.mkdir(parents=True)
    (skills / "dummy-review.md").write_text(REVIEW, encoding="utf-8")
    (skills / "dummy-skill.md").write_text(SKILL, encoding="utf-8")
    lookup = taxonomy.discover_skills(tmp_path)
    assert "dummy-review" not in lookup
    assert "dummy-skill" in lookup


def test_discover_skills_dossier_absent(tmp_path):
    assert taxonomy.discover_skills(tmp_path) == {}


# ── linter_checks (docstring = vérifications exactes) ──────────────────────


LINTER_AVEC_DOC = '''
"""Ligne 1.

Ligne 2 détaillée.
"""
LINTER_META = {"key": "ZZ", "label": "Linter factice",
               "category": "tests", "description": "factice",
               "skill": "larc-testing"}
'''


def test_linter_checks_extrait_docstring(tmp_path):
    (tmp_path / "fake_linter.py").write_text(LINTER_AVEC_DOC, encoding="utf-8")
    found = taxonomy.linter_checks(tmp_path)
    assert len(found) == 1
    assert found[0]["doc"] == "Ligne 1.\n\nLigne 2 détaillée."
    assert found[0]["script"] == "fake_linter.py"


def test_linter_checks_sans_doc(tmp_path):
    (tmp_path / "no_doc.py").write_text(LINTER_SANS_META, encoding="utf-8")
    assert taxonomy.linter_checks(tmp_path) == []


# ── discover_reviewers (.claude/skills/*-review.md) ────────────────────────


REVIEW_BODY = """---
name: design-review
description: Audit du design system
category: quality
trigger: audit design
---

# Procédure

Vérifier les tokens.
"""


def test_discover_reviewers_parse_frontmatter_et_corps(tmp_path):
    skills = tmp_path / ".claude" / "skills"
    skills.mkdir(parents=True)
    (skills / "design-review.md").write_text(REVIEW_BODY, encoding="utf-8")
    found = taxonomy.discover_reviewers(tmp_path)
    assert len(found) == 1
    assert found[0]["name"] == "design-review"
    assert found[0]["description"] == "Audit du design system"
    assert found[0]["category"] == "quality"
    assert found[0]["trigger"] == "audit design"
    assert "# Procédure" in found[0]["body"]
    assert found[0]["body"].endswith("Vérifier les tokens.")


def test_discover_reviewers_exclut_les_skills(tmp_path):
    skills = tmp_path / ".claude" / "skills"
    skills.mkdir(parents=True)
    (skills / "dummy-skill.md").write_text(SKILL, encoding="utf-8")
    (skills / "design-review.md").write_text(REVIEW_BODY, encoding="utf-8")
    found = taxonomy.discover_reviewers(tmp_path)
    assert [r["name"] for r in found] == ["design-review"]


def test_discover_reviewers_dossier_absent(tmp_path):
    assert taxonomy.discover_reviewers(tmp_path) == []


def test_discover_checks_combine_linters_et_reviewers(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "fake_linter.py").write_text(LINTER_OK, encoding="utf-8")
    skills = tmp_path / ".claude" / "skills"
    skills.mkdir(parents=True)
    (skills / "design-review.md").write_text(REVIEW_BODY, encoding="utf-8")
    checks = taxonomy.discover_checks(tmp_path)
    assert [m["key"] for m in checks["linters"]] == ["ZZ"]
    assert [r["name"] for r in checks["reviewers"]] == ["design-review"]


# ── resolve_type ───────────────────────────────────────────────────────────


def test_resolve_type_avec_skills():
    skills = {"theme-reactivity": "Pattern _STYLE + _restyle_all"}
    et = taxonomy.resolve_type("linter:REACT", skills=skills)
    assert et.key == "theme"
    assert et.label == "Thème & Design"
    assert et.skill == "theme-reactivity"
    assert et.skill_label == "Pattern _STYLE + _restyle_all"


def test_resolve_type_sans_skills():
    et = taxonomy.resolve_type("larcforge:build")
    assert et.key == "build"
    assert et.skill is None


# ── couleurs (palette centrale larccommon.theme) ───────────────────────────


def test_error_category_color_retourne_triplet():
    theme = pytest.importorskip("larccommon.theme")
    badge, conteneur, texte = theme.error_category_color("theme")
    assert all(c.startswith("#") for c in (badge, conteneur, texte))
    assert badge == theme.ERROR_CATEGORY_COLORS["theme"]["light"][0]


def test_error_category_color_inconnu_fallback_ui():
    theme = pytest.importorskip("larccommon.theme")
    assert theme.error_category_color("zzz") == \
        theme.ERROR_CATEGORY_COLORS["ui"]["light"]


def test_couleurs_alignees_sur_la_taxonomie():
    theme = pytest.importorskip("larccommon.theme")
    assert set(theme.ERROR_CATEGORY_COLORS) == set(taxonomy.all_categories())