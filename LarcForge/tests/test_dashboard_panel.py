"""Tests du panneau Accueil : KPIs, alertes, DB down, retry."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from larcforge import database as pg  # noqa: E402
from larcforge import status as status_mod  # noqa: E402
from larcforge.ui.main_window import AppContext  # noqa: E402
from larcforge.ui.panels.dashboard_panel import DashboardPanel  # noqa: E402
from larcforge.ui.profiles import ProfilesStore  # noqa: E402

_DATA_OK = {
    "counts": {"open": 12, "regressed": 3, "resolved": 45},
    "by_app": [],
    "runs": [{"id": 8, "command": "run", "status": "issues", "nb_issues": 536,
              "nb_new": 2, "nb_regressed": 0, "nb_resolved": 0, "nb_errors": 0,
              "started_at": None}],
    "regressed": [],
    "modules_changed": ["LarcCommon/larccommon/x.py (modifié)"],
    "scope_alerts": ["warn scope"],
    "conflict_alerts": ["⚠ issue #3 : module modifié"],
    "open_issues": [],
}


@pytest.fixture
def panel(qtbot, tmp_path):
    store = ProfilesStore(path=tmp_path / "cfg.json")
    ctx = AppContext(root=str(tmp_path), timeout=30, store=store,
                     config=store.load())
    p = DashboardPanel(ctx)
    p.show()
    qtbot.addWidget(p)
    return p


class _FakeConn:
    """Connexion factice : render_json est mocké, close() doit exister."""

    def close(self):
        pass


def _conn_ok(**kw):
    return _FakeConn()


def test_db_down_montre_carte_retry(panel, qtbot, monkeypatch):
    def down(**kw):
        raise pg.DBUnavailable("base injoignable (mock)")

    monkeypatch.setattr(pg, "connect", down)
    panel.reload()
    assert panel._retry.isVisible()
    assert not panel._runs_card.isVisible()


def test_reload_affiche_kpis_et_sections(panel, qtbot, monkeypatch):
    monkeypatch.setattr(pg, "connect", _conn_ok)
    monkeypatch.setattr(status_mod, "render_json", lambda conn: _DATA_OK)
    panel.reload()
    assert panel._kpis["open"]._value_lbl.text() == "12"
    assert panel._kpis["regressed"]._value_lbl.text() == "3"
    assert panel._kpis["resolved"]._value_lbl.text() == "45"
    assert panel._kpis["total"]._value_lbl.text() == "60"
    assert panel._alerts_card.isVisible()
    assert "Aucune alerte" not in panel._alerts_box.itemAt(0).widget().text()
    assert "warn scope" in panel._alerts_box.itemAt(0).widget().text()
    assert panel._runs_card.isVisible()
    assert "#8" in panel._runs_box.itemAt(0).widget().text()
    assert panel._mods_card.isVisible()


def test_retry_relance_apres_db_down(panel, qtbot, monkeypatch):
    calls = {"n": 0}

    def connect_factory(**kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise pg.DBUnavailable("down (mock)")
        return _FakeConn()

    monkeypatch.setattr(pg, "connect", connect_factory)
    monkeypatch.setattr(status_mod, "render_json", lambda conn: _DATA_OK)
    panel.reload()
    assert panel._retry.isVisible()
    panel._retry._btn.click()  # Réessayer → reload
    assert panel._kpis["total"]._value_lbl.text() == "60"
    assert not panel._retry.isVisible()
