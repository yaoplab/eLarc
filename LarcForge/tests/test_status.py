"""Tests du rapport status : diff de modules et contrôle « périmètre de correction ».

FakeConn/FakeCursor simulent PostgreSQL (voir conftest.py) — le SQL n'est pas
exécuté, mais les requêtes sont capturées et les réponses rejouées.
"""

from __future__ import annotations

from conftest import FakeConn

from larcforge import status as status_mod

# colonnes retournées par last_runs (cur.description)
COLS_RUN = [("id",), ("command",), ("status",), ("started_at",), ("finished_at",),
            ("nb_issues",), ("nb_new",), ("nb_regressed",), ("nb_resolved",),
            ("nb_errors",)]


def _conn_module_modifie() -> FakeConn:
    """Run #5 vs run #4 : LarcSuperviseur/views/main_window.py a changé."""
    return FakeConn(
        [
            [(5, "run", "issues", None, None, 665, 0, 0, 1, 0),
             (4, "run", "issues", None, None, 666, 0, 0, 0, 0)],      # last_runs
            [("LarcSuperviseur", "views/main_window.py", 100, 200)],   # snapshot #4
            [("LarcSuperviseur", "views/main_window.py", 105, 200)],   # snapshot #5
        ],
        description=COLS_RUN,
    )


def test_module_diffs_detecte_modification():
    conn = _conn_module_modifie()
    assert status_mod.module_diffs(conn) == ["views/main_window.py (modifié)"]


def test_scope_alerts_alerte_module_sans_issue_resolue():
    conn = _conn_module_modifie()
    conn._plans.append([])  # SELECT DISTINCT issues résolues → aucune
    alerts = status_mod.scope_alerts(conn)
    assert len(alerts) == 1
    assert "main_window.py" in alerts[0]
    assert "hors périmètre" in alerts[0]


def test_scope_alerts_silencieux_si_issue_resolue_du_module():
    conn = _conn_module_modifie()
    conn._plans.append([("LarcSuperviseur", "views/main_window.py")])  # résolue au dernier run
    assert status_mod.scope_alerts(conn) == []


def test_scope_alerts_pas_assez_de_runs():
    conn = FakeConn([[(5, "run", "issues", None, None, 1, 0, 0, 0, 0)]],
                    description=COLS_RUN)
    assert status_mod.scope_alerts(conn) == []
    assert status_mod.module_diffs(conn) == []


def test_scope_alerts_ignore_module_corrige():
    """Un module modifié + issue résolue du même module ce run → pas d'alerte."""
    conn = FakeConn(
        [
            [(5, "run", "issues", None, None, 665, 0, 0, 1, 0),
             (4, "run", "issues", None, None, 666, 0, 0, 0, 0)],
            [("LarcCommon", "larccommon/widgets/card.py", 10, 100)],
            [("LarcCommon", "larccommon/widgets/card.py", 11, 100)],
            [("LarcCommon", "larccommon/widgets/card.py")],  # résolue ce run
        ],
        description=COLS_RUN,
    )
    assert status_mod.scope_alerts(conn) == []


def test_render_affiche_section_perimetre(monkeypatch):
    monkeypatch.setattr(status_mod, "scope_alerts",
                        lambda conn: ["⚠ x.py (modifié) — aucune issue de ce "
                                      "module résolue au dernier run"])
    monkeypatch.setattr(status_mod, "conflict_alerts", lambda conn: [])
    out = status_mod.render(FakeConn())
    assert "Périmètre de correction" in out
    assert "x.py (modifié)" in out


def test_render_json_contient_scope_alerts(monkeypatch):
    monkeypatch.setattr(status_mod, "conflict_alerts", lambda conn: [])
    out = status_mod.render_json(FakeConn())
    assert "scope_alerts" in out


# ---------------------------------------------------------------------------
# Primitives IHM : running_run / list_issues / issue_detail
# ---------------------------------------------------------------------------

COLS_ISSUES = [("id",), ("status",), ("occurrences",), ("source",), ("app_name",),
               ("module",), ("func",), ("line",), ("level",), ("rule",),
               ("message",), ("last_seen",)]


def test_running_run_retourne_none_sans_run_en_cours():
    conn = FakeConn([[]], description=COLS_RUN)
    assert status_mod.running_run(conn) is None


def test_running_run_retourne_le_run_en_cours():
    cols = [("id",), ("command",), ("started_at",)]
    conn = FakeConn([[(3, "run", None)]], description=cols)
    r = status_mod.running_run(conn)
    assert r == {"id": 3, "command": "run", "started_at": None}
    sql, params = conn.cursors[0].calls[0]
    assert "status = 'running'" in sql
    assert params == ()


def test_list_issues_sans_filtre():
    conn = FakeConn(
        [[(1, "open", 2, "linter:R", "LarcCommon", "x.py", "R", 5, "WARNING",
           "R", "pb", None)]],
        description=COLS_ISSUES,
    )
    rows = status_mod.list_issues(conn)
    assert rows[0]["id"] == 1
    assert rows[0]["status"] == "open"
    sql, params = conn.cursors[0].calls[0]
    assert sql.endswith("ORDER BY last_seen DESC LIMIT %s")
    assert params == (500,)


def test_list_issues_applique_filtres():
    conn = FakeConn([[]], description=COLS_ISSUES)
    status_mod.list_issues(conn, status="resolved", app="LarcProf",
                           source="pytest", search="NameError")
    sql, params = conn.cursors[0].calls[0]
    assert "AND status = %s" in sql
    assert "AND app_name = %s" in sql
    assert "AND source = %s" in sql
    assert "AND (message ILIKE %s OR module ILIKE %s)" in sql
    assert params == ("resolved", "LarcProf", "pytest", "%NameError%", "%NameError%", 500)


def test_list_issues_source_linter_utilise_LIKE():
    """Le filtre « linter » couvre toutes les sources linter:R, linter:D…"""
    conn = FakeConn([[]], description=COLS_ISSUES)
    status_mod.list_issues(conn, source="linter")
    sql, params = conn.cursors[0].calls[0]
    assert "AND source LIKE %s" in sql
    assert params == ("linter:%", 500)


def test_list_apps_retourne_les_apps_du_registre():
    conn = FakeConn([[("LarcCommon",), ("LarcSuperviseur",), ("LarcSuperviseur",)]])
    apps = status_mod.list_apps(conn)
    assert apps == ["LarcCommon", "LarcSuperviseur", "LarcSuperviseur"]
    sql, params = conn.cursors[0].calls[0]
    assert "DISTINCT app_name" in sql
    assert "v_larc_issues" in sql
    assert params == ()


def test_issue_detail_retourne_les_colonnes():
    conn = FakeConn(
        [[(9, "open", 1, "linter:D", "LarcSecretaire", "a.py", "D1", 3,
           "ERROR", "D1", "msg", None)]],
        description=COLS_ISSUES,
    )
    detail = status_mod.issue_detail(conn, 9)
    assert detail is not None
    assert detail["id"] == 9
    assert detail["rule"] == "D1"
    sql, params = conn.cursors[0].calls[0]
    assert sql.startswith("SELECT * FROM public.larc_issue")
    assert params == (9,)


def test_issue_detail_absent():
    conn = FakeConn([[]], description=COLS_ISSUES)
    assert status_mod.issue_detail(conn, 999) is None
