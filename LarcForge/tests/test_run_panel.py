"""Tests du panneau Vérifications : scope depuis les cases, lancement, DB down."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from larcforge import config as cfg  # noqa: E402
from larcforge import database as pg  # noqa: E402
from larcforge.models import RunSummary  # noqa: E402
from larcforge.ui import workers  # noqa: E402
from larcforge.ui.main_window import AppContext  # noqa: E402
from larcforge.ui.panels.common import DbUnavailableCard  # noqa: E402
from larcforge.ui.panels.run_panel import RunPanel  # noqa: E402
from larcforge.ui.profiles import ProfilesStore  # noqa: E402


def _db_down(**kw):
    raise pg.DBUnavailable("base injoignable (mock)")


@pytest.fixture
def panel(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(pg, "connect", _db_down)
    store = ProfilesStore(path=tmp_path / "cfg.json")
    ctx = AppContext(root=str(tmp_path), timeout=30, store=store,
                     config=store.load())
    p = RunPanel(ctx)
    p.show()
    qtbot.addWidget(p)
    return p


def test_par_defaut_tout_est_coche(panel):
    assert panel._cmd_combo.currentIndex() == 0  # « run »
    assert all(c.isChecked() for c in panel._proj_checks.values())
    assert all(c.isChecked() for c in panel._lint_checks.values())
    assert all(c.isChecked() for c in panel._test_checks.values())
    assert panel._include_int.isChecked() is False


def test_scope_defaut_est_le_scope_canonique(panel):
    scope, is_full = panel._scope_from_ui()
    assert is_full is True
    assert scope.canonical() == workers.full_scope().canonical()


def test_decocher_un_projet_rend_scope_personnalise(panel):
    first = next(iter(panel._proj_checks.values()))
    first.setChecked(False)
    scope, is_full = panel._scope_from_ui()
    assert is_full is False
    assert len(scope.projects) == len(cfg.PROJETS) - 1


def test_bandeau_scope_suit_les_cases(panel, qtbot):
    assert "ACTIVE" in panel._scope_lbl.text()
    first = next(iter(panel._lint_checks.values()))
    first.setChecked(False)
    panel._update_scope_banner()
    assert "PAS active" in panel._scope_lbl.text()
    for c in panel._lint_checks.values():
        c.setChecked(True)
    panel._update_scope_banner()
    assert "ACTIVE" in panel._scope_lbl.text()


def test_tout_verifier_lance_et_affiche_resultat(panel, qtbot, monkeypatch):
    summary = RunSummary(nb_issues=2, nb_new=1, run_id=42)

    def fake_execute(*a, **k):
        return summary, 1, "2 issue(s) ouverte(s) ou régressée(s)"

    monkeypatch.setattr(workers, "_execute", fake_execute)
    panel._on_start_full()
    qtbot.waitUntil(lambda: not panel._worker.isRunning(), timeout=10000)
    assert panel._result_card.isVisible()
    assert "run #42" in panel._result_title.text()
    assert panel._btn_issues.isVisible()
    assert panel._btn_full.isEnabled()


def test_db_down_affiche_carte_retry(panel, qtbot, monkeypatch):
    def fake_execute(*a, **k):
        return RunSummary(), 4, "Connexion DB impossible : down"

    monkeypatch.setattr(workers, "_execute", fake_execute)
    panel._on_start_full()
    qtbot.waitUntil(lambda: not panel._worker.isRunning(), timeout=10000)
    assert panel._retry_card.isVisible()
    assert not panel._btn_issues.isVisible()
