"""Tests des primitives IHM du store (résolution manuelle) — sans PostgreSQL.

Vérifie le SQL capturé : resolve_issue ne touche que les issues open/regressed,
reopen_issue ne touche que les issues resolved.
"""

from __future__ import annotations

from larcforge import store

from conftest import FakeConn


def test_resolve_issue_passe_a_resolved_avec_note():
    conn = FakeConn([], rowcounts=[1])
    n = store.resolve_issue(conn, issue_id=42, note="Corrigé manuellement")
    assert n == 1
    sql, params = conn.cursors[0].calls[0]
    assert "status = 'resolved'" in sql
    assert "resolution_note = %s" in sql
    assert "status IN ('open', 'regressed')" in sql
    assert params == ("Corrigé manuellement", 42)


def test_resolve_issue_retourne_zero_si_deja_resolue():
    conn = FakeConn([], rowcounts=[0])
    assert store.resolve_issue(conn, 42, "note") == 0


def test_reopen_issue_remet_a_open():
    conn = FakeConn([], rowcounts=[1])
    n = store.reopen_issue(conn, issue_id=7)
    assert n == 1
    sql, params = conn.cursors[0].calls[0]
    assert "status = 'open'" in sql
    assert "resolution_note = NULL" in sql
    assert "resolved_at = NULL" in sql
    assert "status = 'resolved'" in sql
    assert params == (7,)


def test_reopen_issue_retourne_zero_si_pas_resolved():
    conn = FakeConn([], rowcounts=[0])
    assert store.reopen_issue(conn, 7) == 0


def test_abort_run_marque_le_run_courant_comme_error():
    conn = FakeConn([], rowcounts=[1])
    n = store.abort_run(conn, run_id=99)
    assert n == 1
    sql, params = conn.cursors[0].calls[0]
    assert "status = 'error'" in sql
    assert "id = %s" in sql
    assert "status = 'running'" in sql
    assert params == (99,)


def test_abort_run_ignore_un_run_pas_en_cours():
    conn = FakeConn([], rowcounts=[0])
    assert store.abort_run(conn, 99) == 0
