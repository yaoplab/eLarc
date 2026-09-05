"""Tests du store (upsert + transitions de statut) — sans PostgreSQL réelle.

FakeConn/FakeCursor (conftest) simulent la connexion : le SQL réel n'est pas
exécuté, mais les requêtes sont capturées et les réponses rejouées selon le
plan fourni. On teste la LOGIQUE de branchement des transitions.
"""

from __future__ import annotations

from larcforge import store
from larcforge.models import IssueCandidate, RunSummary

from conftest import FakeConn

CANONICAL = ('{"command": "lints", "include_integration": false, "level": null, '
             '"linters": ["R"], "projects": ["LarcCommon"], "since_h": null}')

# Ce que psycopg2 retourne pour une colonne JSONB : un dict Python
SCOPE_DICT = {"command": "lints", "linters": ["R"], "projects": ["LarcCommon"],
              "include_integration": False, "since_h": None, "level": None}


class FakeScope:
    command = "lints"
    linters = ["R"]
    projects = ["LarcCommon"]
    include_integration = False
    since_h = None
    level = None

    def canonical(self):
        return CANONICAL


def _cand(message="pb", **kw):
    base = dict(source="linter:R", app_name="A", module="m.py", func="R",
                rule="R", message=message)
    base.update(kw)
    return IssueCandidate(**base)


def test_start_run_retourne_id_et_insere():
    conn = FakeConn([[(42,)]])
    rid = store.start_run(conn, FakeScope(), "1.0", "F:/projets", "py")
    assert rid == 42
    sql, params = conn.cursors[0].calls[0]
    assert sql.startswith("INSERT INTO public.larc_run")
    assert params[0] == "lints"
    assert params[2] == "py"  # python


def test_upsert_cree_si_absente():
    conn = FakeConn([[None]])  # SELECT signature → aucune ligne
    action = store.upsert_candidate(conn, _cand(), run_id=1)
    assert action == "created"
    sql, params = conn.cursors[0].calls[1]  # calls[0]=SELECT, calls[1]=INSERT
    assert sql.startswith("INSERT INTO public.larc_issue")
    assert params[0] is not None  # signature
    assert params[1] == 1 and params[2] == 1  # first/last_seen_run


def test_upsert_regresse_si_resolved():
    conn = FakeConn([[(12, "resolved")]])
    action = store.upsert_candidate(conn, _cand(), run_id=2)
    assert action == "regressed"
    sql = conn.cursors[0].calls[1][0]
    assert "status = 'regressed'" in sql
    assert "regressed_count = regressed_count + 1" in sql
    assert "resolved_at = NULL" in sql
    assert "resolution_note = NULL" in sql


def test_upsert_update_si_open():
    conn = FakeConn([[(12, "open")]])
    action = store.upsert_candidate(conn, _cand(), run_id=2)
    assert action == "updated"
    sql = conn.cursors[0].calls[1][0]
    assert "occurrences = occurrences + 1" in sql
    assert "last_seen_run = %s" in sql


def test_upsert_update_si_regressed():
    conn = FakeConn([[(12, "regressed")]])
    assert store.upsert_candidate(conn, _cand(), run_id=3) == "updated"


def test_upsert_met_a_jour_line_et_message():
    conn = FakeConn([[(12, "open")]])
    store.upsert_candidate(conn, _cand(message="nouveau texte"), run_id=3)
    sql, params = conn.cursors[0].calls[1]
    assert params[2] == "nouveau texte"  # message = EXCLUDED


def test_resolve_missing_pas_de_run_precedent():
    conn = FakeConn([[None]])  # aucun run antérieur valide
    assert store.resolve_missing(conn, run_id=5, scope=FakeScope()) == 0


def test_resolve_missing_scope_different_bloque():
    conn = FakeConn([[(3, {"command": "tests"})]])  # scope ≠ lints
    assert store.resolve_missing(conn, run_id=5, scope=FakeScope()) == 0
    assert len(conn.cursors) == 1  # pas d'UPDATE


def test_resolve_missing_run_en_erreur_ignore():
    # le SELECT ne retourne que les runs status <> 'error'
    conn = FakeConn([[None]])
    assert store.resolve_missing(conn, run_id=5, scope=FakeScope()) == 0


def test_resolve_missing_scope_identique_resout():
    # un seul curseur : SELECT run précédent puis UPDATE (rowcount 4)
    c = FakeConn([[(3, SCOPE_DICT)]], rowcounts=[4])
    n = store.resolve_missing(c, run_id=5, scope=FakeScope())
    assert n == 4  # rowcount du curseur
    sql, params = c.cursors[0].calls[1]
    assert "status = 'resolved'" in sql
    assert params[2] == 3  # last_seen_run = run précédent


def test_count_open():
    conn = FakeConn([[(7,)]])
    assert store.count_open(conn) == 7
    assert "status IN ('open', 'regressed')" in conn.cursors[0].calls[0][0]


def test_finish_run_met_a_jour_compteurs():
    conn = FakeConn([])
    summary = RunSummary(nb_issues=3, nb_new=2, nb_regressed=1, nb_resolved=0, nb_errors=0)
    store.finish_run(conn, run_id=1, summary=summary, status="issues")
    sql, params = conn.cursors[0].calls[0]
    assert "nb_issues = %s" in sql
    assert params[0] == "issues"
    assert params[6] == 1  # run_id
