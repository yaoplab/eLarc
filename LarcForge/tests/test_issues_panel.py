"""Tests du panneau Registre des issues : filtres, détail, résolution, réouverture."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from larcforge import database as pg  # noqa: E402
from larcforge import status as status_mod  # noqa: E402
from larcforge import store  # noqa: E402
from larcforge.ui.main_window import AppContext  # noqa: E402
from larcforge.ui.panels import issues_panel as panel_mod  # noqa: E402
from larcforge.ui.panels.issues_panel import IssuesPanel  # noqa: E402
from larcforge.ui.profiles import ProfilesStore  # noqa: E402

_ISSUES = [
    {"id": 12, "status": "open", "occurrences": 3, "source": "linter:R",
     "app_name": "LarcCommon", "module": "larccommon/x.py", "func": None,
     "line": None, "level": "WARNING", "rule": "R", "message": "hardcoded px",
     "last_seen": None},
    {"id": 13, "status": "resolved", "occurrences": 1, "source": "pytest",
     "app_name": "LarcSuperviseur", "module": "views/a.py", "func": None,
     "line": None, "level": "ERROR", "rule": None, "message": "NameError",
     "last_seen": None},
]

_DETAIL_OPEN = {
    "id": 12, "status": "open", "occurrences": 3, "source": "linter:R",
    "app_name": "LarcCommon", "module": "larccommon/x.py", "func": "f",
    "line": 5, "level": "WARNING", "rule": "R", "message": "hardcoded px",
    "traceback": None, "resolution_note": None, "resolved_at": None,
    "first_seen": None, "last_seen": None, "regressed_count": None,
}

_DETAIL_RESOLVED = dict(_DETAIL_OPEN, status="resolved",
                        resolution_note="corrigé", resolved_at=None)


class _FakeConn:
    def close(self):
        pass


def _conn_ok(**kw):
    return _FakeConn()


@pytest.fixture
def panel(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(pg, "connect", _conn_ok)
    store_cfg = ProfilesStore(path=tmp_path / "cfg.json")
    ctx = AppContext(root=str(tmp_path), timeout=30, store=store_cfg,
                     config=store_cfg.load())

    def fake_list(conn, **kw):
        ctx._last_kwargs = kw
        return _ISSUES

    monkeypatch.setattr(status_mod, "list_issues", fake_list)
    monkeypatch.setattr(status_mod, "list_apps",
                        lambda conn: ["LarcCommon", "LarcSuperviseur"])
    p = IssuesPanel(ctx)
    p.show()
    qtbot.addWidget(p)
    return p


def test_db_down_montre_carte_retry(panel, qtbot, monkeypatch):
    def down(**kw):
        raise pg.DBUnavailable("base injoignable (mock)")

    monkeypatch.setattr(pg, "connect", down)
    panel.reload()
    assert panel._retry.isVisible()
    assert panel._table.rowCount() == 0


def test_reload_remplit_tableau_compteur_et_apps(panel):
    panel.reload()
    assert panel._table.rowCount() == 2
    assert panel._table.item(0, 0).text() == "12"
    assert panel._table.item(0, 3).text() == "LarcCommon"  # colonne App
    assert panel._table.item(1, 1).text() == "resolved"
    assert "2 fiches" in panel._count_lbl.text()
    # combo apps peuplé : « Toutes les apps » + 2 apps
    assert panel._app_combo.count() == 3
    assert panel._app_combo.itemText(1) == "LarcCommon"
    # aucun détail sélectionné → boutons masqués
    assert not panel._btn_resolve.isVisible()
    assert not panel._btn_reopen.isVisible()


def test_filtres_transmis_aux_requetes(panel):
    panel.reload()  # premier chargement : peuple le combo des apps
    panel._status_combo.setCurrentIndex(2)   # Résolues
    panel._app_combo.setCurrentIndex(1)      # LarcCommon
    panel._source_combo.setCurrentIndex(1)   # Linters
    panel._search.setText("NameError")
    panel.reload()
    kwargs = panel._ctx._last_kwargs
    assert kwargs["status"] == "resolved"
    assert kwargs["app"] == "LarcCommon"
    assert kwargs["source"] == "linter"
    assert kwargs["search"] == "NameError"
    assert kwargs["limit"] == 500


def test_selection_affiche_detail_et_bouton_resoudre(panel, qtbot, monkeypatch):
    monkeypatch.setattr(status_mod, "issue_detail",
                        lambda conn, iid: dict(_DETAIL_OPEN, id=iid))
    panel.reload()
    panel._table.selectRow(0)
    assert panel._detail["id"] == 12
    assert "Fiche #12" in panel._detail_title.text()
    assert panel._btn_resolve.isVisible()
    assert not panel._btn_reopen.isVisible()


def test_resoudre_avec_note(panel, qtbot, monkeypatch):
    monkeypatch.setattr(status_mod, "issue_detail",
                        lambda conn, iid: dict(_DETAIL_OPEN, id=iid))
    resolved = []
    monkeypatch.setattr(store, "resolve_issue",
                        lambda conn, iid, note: resolved.append((iid, note)))

    class _FakeNoteDialog:
        def __init__(self, title, message=""):
            self.title = title

        def exec_note(self):
            return "corrigé"

    monkeypatch.setattr(panel_mod, "NoteDialog", _FakeNoteDialog)
    panel.reload()
    panel._table.selectRow(0)
    panel._btn_resolve.click()
    assert resolved == [(12, "corrigé")]
    # reload a été relancé : le tableau est toujours rempli
    assert panel._table.rowCount() == 2


def test_resoudre_annule_ne_change_rien(panel, qtbot, monkeypatch):
    monkeypatch.setattr(status_mod, "issue_detail",
                        lambda conn, iid: dict(_DETAIL_OPEN, id=iid))
    resolved = []
    monkeypatch.setattr(store, "resolve_issue",
                        lambda conn, iid, note: resolved.append((iid, note)))

    class _FakeNoteDialog:
        def __init__(self, title, message=""):
            pass

        def exec_note(self):
            return None  # annulé

    monkeypatch.setattr(panel_mod, "NoteDialog", _FakeNoteDialog)
    panel.reload()
    panel._table.selectRow(0)
    panel._btn_resolve.click()
    assert resolved == []


def test_reouvrir_fiche_resolue(panel, qtbot, monkeypatch):
    monkeypatch.setattr(status_mod, "issue_detail",
                        lambda conn, iid: dict(_DETAIL_RESOLVED, id=iid))
    reopened = []
    monkeypatch.setattr(store, "reopen_issue",
                        lambda conn, iid: reopened.append(iid))
    panel.reload()
    panel._table.selectRow(0)
    assert panel._btn_reopen.isVisible()
    assert not panel._btn_resolve.isVisible()
    panel._btn_reopen.click()
    assert reopened == [12]


def test_restyle_sans_crash(panel):
    panel.reload()
    panel._restyle()
