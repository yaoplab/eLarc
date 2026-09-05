"""Tests du worker : garde-fou scope (canonique CLI) + signaux de fin."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from larcforge import config as cfg  # noqa: E402
from larcforge.models import RunScope, RunSummary  # noqa: E402
from larcforge.ui import workers  # noqa: E402


def test_full_scope_matche_le_scope_cli_defaut():
    """GARDE-FOU : « Tout vérifier » doit égaler le scope CLI par défaut,
    sinon la résolution automatique des fiches ne se déclenche pas."""
    cli_scope = RunScope(command="run", linters=cfg.LINTER_KEYS,
                         projects=cfg.PROJETS, include_integration=False,
                         since_h=None, level="ERROR,WARNING")
    assert workers.full_scope().canonical() == cli_scope.canonical()


def test_custom_scope_est_different():
    s = workers.custom_scope("run", cfg.PROJETS, cfg.LINTER_KEYS)
    assert s.since_h == 24
    assert s.canonical() != workers.full_scope().canonical()
    assert s.include_integration is False


def test_worker_emmet_run_finished(monkeypatch):
    summary = RunSummary(nb_issues=3, run_id=7)
    monkeypatch.setattr(workers, "_execute",
                        lambda *a, **k: (summary, 1, "issues trouvées"))
    w = workers.RunWorker("F:\\projets", workers.full_scope())
    received = {}
    w.run_finished.connect(lambda s, c, m: received.update(s=s, c=c, m=m))
    w.run()  # appel direct : pas de boucle d'événements nécessaire
    assert received["c"] == 1
    assert received["s"].run_id == 7
    assert received["m"] == "issues trouvées"


def test_worker_emmet_run_failed(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("collecteur explosé")

    monkeypatch.setattr(workers, "_execute", boom)
    w = workers.RunWorker("F:\\projets", workers.full_scope())
    got = {}
    w.run_failed.connect(lambda m: got.update(m=m))
    w.run()
    assert "collecteur explosé" in got["m"]


def test_worker_passe_le_scope_et_les_options(monkeypatch):
    seen = {}

    def fake(root, scope, timeout, use_db, keys, include_integration,
             since_h, levels, limit):
        seen.update(root=root, scope=scope, timeout=timeout, use_db=use_db,
                    keys=keys, include_integration=include_integration,
                    since_h=since_h, levels=levels, limit=limit)
        return RunSummary(), 0, "ok"

    monkeypatch.setattr(workers, "_execute", fake)
    w = workers.RunWorker("F:\\projets", workers.full_scope(), timeout=60)
    w.run()
    assert seen["scope"] is workers.full_scope() or \
        seen["scope"].canonical() == workers.full_scope().canonical()
    assert seen["use_db"] is True
    assert seen["since_h"] == 24  # execute attend 24 (scope None = CLI)
    assert seen["levels"] == ("ERROR", "WARNING")
    assert seen["timeout"] == 60
