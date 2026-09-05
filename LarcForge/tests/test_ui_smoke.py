"""Smoke test de la coquille IHM : ouverture, navigation, réactivité thème.

La base PostgreSQL est mockée (toujours DBUnavailable) : la coquille ne doit
jamais avoir besoin de la base réelle.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from larcforge import database as pg  # noqa: E402
from larcforge.ui.main_window import MainWindow  # noqa: E402
from larcforge.ui.profiles import ProfilesStore  # noqa: E402


def _db_down(**kw):
    raise pg.DBUnavailable("base injoignable (mock)")


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(pg, "connect", _db_down)
    store = ProfilesStore(path=tmp_path / "cfg.json")
    win = MainWindow(root=str(tmp_path), timeout=30, store=store,
                     config=store.load())
    qtbot.addWidget(win)
    return win


def test_ouverture_panel_accueil(window):
    assert window._current == "accueil"
    assert window._stack.count() == 1
    assert "accueil" in window._panels


def test_navigation_charge_chaque_panel(window):
    for key in ("verifs", "issues", "config", "aide", "accueil"):
        window._switch(key)
        assert window._current == key
        assert window._stack.currentWidget() is window._panels[key]
    assert window._stack.count() == 5


def test_chaque_panel_a_reload_et_restyle(window):
    for key in ("verifs", "issues", "config", "aide"):
        window._switch(key)
    for key, panel in window._panels.items():
        assert callable(getattr(panel, "reload", None))
        assert callable(getattr(panel, "_restyle", None))


def test_restyle_sans_crash(window):
    window._switch("config")
    window._restyle_all()  # thème changé → chrome + panels re-stylés
    assert window._stack.currentWidget() is window._panels["config"]
