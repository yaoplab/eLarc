"""Tests des collecteurs : parsing des formats JSON linters, junitxml, spool SQLite."""

from __future__ import annotations

import json
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

from larcforge.collectors import errorlog
from larcforge.collectors import linters
from larcforge.collectors.base import module_of
from larcforge.collectors.pytest_collector import _parse_junit

ROOT = Path("F:/projets")


# ---------------------------------------------------------------------------
# module_of
# ---------------------------------------------------------------------------


def test_module_of_relatif_deja_prefixe():
    assert module_of("LarcCommon/larccommon/x.py", "LarcCommon", ROOT) == \
        "LarcCommon/larccommon/x.py"


def test_module_of_relatif_projet_rajoute_prefixe():
    assert module_of("views/main_window.py", "LarcSuperviseur", ROOT) == \
        "LarcSuperviseur/views/main_window.py"


def test_module_of_dot_slash_stripe():
    assert module_of("./views/x.py", "A", ROOT) == "A/views/x.py"


def test_module_of_backslashes():
    assert module_of(r"views\main.py", "A", ROOT) == "A/views/main.py"


def test_module_of_vide():
    assert module_of("", "A", ROOT) is None


# ---------------------------------------------------------------------------
# _iter_entries — formats JSON des linters
# ---------------------------------------------------------------------------


def test_iter_entries_format_RD():
    payload = {"results": {"groupe1": [{"file": "a.py", "rule": "R"}],
                           "groupe2": [{"file": "b.py"}]}, "total": 2}
    entries = linters._iter_entries("R", payload)
    assert len(entries) == 2
    assert entries[0]["file"] == "a.py"


def test_iter_entries_format_react():
    payload = {"moduleA": {"results": [
        {"file": "x.py", "total_vulnerable": 3},
        {"file": "y.py", "total_vulnerable": 0},  # exclu
    ]}}
    entries = linters._iter_entries("REACT", payload)
    assert len(entries) == 1
    assert entries[0]["file"] == "x.py"


def test_iter_entries_format_fs():
    payload = {"violations": [{"file": "a.py"}], "stats": {"scanned": 10}}
    assert len(linters._iter_entries("FS", payload)) == 1


def test_iter_entries_liste_plate():
    payload = [{"file": "a.py"}, {"file": "b.py"}, "pas un dict"]
    assert len(linters._iter_entries("C", payload)) == 2


def test_iter_entries_payload_invalide():
    assert linters._iter_entries("R", "pas du json") == []


# ---------------------------------------------------------------------------
# _level_for
# ---------------------------------------------------------------------------


def test_level_for_C_toujours_error():
    assert linters._level_for("C", "WARNING") == "ERROR"


def test_level_for_severites():
    assert linters._level_for("S", "P0") == "ERROR"
    assert linters._level_for("S", "ERROR") == "ERROR"
    assert linters._level_for("S", "HIGH") == "ERROR"
    assert linters._level_for("S", "LOW") == "WARNING"
    assert linters._level_for("R", "") == "WARNING"


# ---------------------------------------------------------------------------
# _candidates
# ---------------------------------------------------------------------------


def test_candidates_format_R():
    payload = {"results": {"a": [{"file": "views/x.py", "rule": "R",
                                  "context": "setSpacing(2)"}]}}
    cands = linters._candidates("R", payload, "LarcSuperviseur", ROOT)
    assert len(cands) == 1
    c = cands[0]
    assert c.source == "linter:R"
    assert c.app_name == "LarcSuperviseur"
    assert c.message == "setSpacing(2)"
    assert c.level == "WARNING"
    assert c.module == "LarcSuperviseur/views/x.py"


def test_candidates_message_fallback():
    payload = {"results": {"a": [{"file": "x.py", "rule": "D1",
                                  "detail": "couleur invalide"}]}}
    cands = linters._candidates("D", payload, "A", ROOT)
    assert cands[0].message == "couleur invalide"


# ---------------------------------------------------------------------------
# _parse_junit
# ---------------------------------------------------------------------------


def test_parse_junit_failure(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(
        """<testsuites><testsuite><testcase classname="tests.test_sync" name="test_a">
        <failure message="assert 1 == 2">Traceback...\\nassert 1 == 2</failure>
        </testcase></testsuite></testsuites>""",
        encoding="utf-8",
    )
    cands = _parse_junit(junit, "LarcProf")
    assert len(cands) == 1
    c = cands[0]
    assert c.source == "pytest"
    assert c.app_name == "LarcProf"
    assert c.module == "tests/test_sync"
    assert c.func == "test_a"
    assert c.message.startswith("assert 1 == 2")


def test_parse_junit_error_sans_message(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(
        """<testsuites><testcase classname="mod" name="t">
        <error>ModuleNotFoundError: No module named 'LarcProf'</error>
        </testcase></testsuites>""",
        encoding="utf-8",
    )
    cands = _parse_junit(junit, "LarcProf")
    assert len(cands) == 1
    assert "ModuleNotFoundError" in cands[0].message


def test_parse_junit_passe_ignore(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text("<testsuites><testcase name=\"ok\"/></testsuites>", encoding="utf-8")
    assert _parse_junit(junit, "A") == []


# ---------------------------------------------------------------------------
# collect_spool (fallback SQLite sans PG)
# ---------------------------------------------------------------------------


def test_collect_spool(tmp_path):
    app_dir = tmp_path / "LarcRH"
    spool = app_dir / ".error_spool"
    spool.mkdir(parents=True)
    db_path = spool / "spool.db"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE pending (id INTEGER PRIMARY KEY, payload TEXT)")
    con.execute(
        "INSERT INTO pending (payload) VALUES (?)",
        (json.dumps({"app_name": "LarcRH", "module": "views/staff_form.py",
                     "message": "boom", "level": "ERROR", "func": "f", "line": 12}),
         ),
    )
    con.commit()
    con.close()

    cands = errorlog.collect_spool(tmp_path, limit=50)
    assert len(cands) == 1
    c = cands[0]
    assert c.source == "errorlog"
    assert c.app_name == "LarcRH"
    assert c.message == "boom"
    assert c.line == 12


def test_collect_spool_aucun_spool(tmp_path):
    assert errorlog.collect_spool(tmp_path) == []
