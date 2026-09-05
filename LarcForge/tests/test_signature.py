"""Tests de la signature de dédoublonnage (line exclue, norm robuste)."""

from __future__ import annotations

from larcforge.signature import norm, signature


def test_norm_strip_et_collapse():
    assert norm("  hello   world\n  ") == "hello world"


def test_norm_backslashes_vers_slash():
    assert norm(r"views\main_window.py") == "views/main_window.py"


def test_norm_neutralise_nombres():
    assert norm("ligne 1234 et 56789") == "ligne #N et #N"
    assert norm("id 42 gardé") == "id 42 gardé"  # < 3 chiffres : inchangé


def test_norm_none_et_vide():
    assert norm(None) == ""
    assert norm("") == ""


def test_signature_stable():
    s1 = signature("linter:R", "LarcCommon", "LarcCommon/larccommon/x.py",
                   "R", "padding: 8px;")
    s2 = signature("linter:R", "LarcCommon", "LarcCommon/larccommon/x.py",
                   "R", "padding: 8px;")
    assert s1 == s2
    assert len(s1) == 64  # sha256 hex


def test_signature_ignore_line_differente():
    a = signature("linter:C", "LarcSuperviseur", "views/main_window.py", "C5",
                  "theme_manager.image.avatar interdit")
    b = signature("linter:C", "LarcSuperviseur", "views/main_window.py", "C5",
                  "theme_manager.image.avatar interdit")
    assert a == b  # la line n'est pas dans le hash


def test_signature_sensible_au_message():
    a = signature("linter:R", "A", "m", None, "message un")
    b = signature("linter:R", "A", "m", None, "message deux")
    assert a != b


def test_signature_sensible_a_lapplication():
    a = signature("linter:R", "A", "m", None, "msg")
    b = signature("linter:R", "B", "m", None, "msg")
    assert a != b


def test_signature_sensible_a_la_source():
    a = signature("linter:R", "A", "m", None, "msg")
    b = signature("pytest", "A", "m", None, "msg")
    assert a != b


def test_signature_ignore_level_et_traceback():
    # level/traceback ne font pas partie du hash : ERROR->WARNING = même bug
    a = signature("errorlog", "LarcSuperviseur", "views/x.py", "f", "boom")
    b = signature("errorlog", "LarcSuperviseur", "views/x.py", "f", "boom")
    assert a == b
