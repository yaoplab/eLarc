"""Tests du collecteur build PyInstaller, de execute_build et de
resolve_build_issues — aucun PyInstaller réel, sous-processus mockés."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from larcforge import database as pg
from larcforge.collectors import build as build_mod
from larcforge.runner import execute_build
from larcforge.store import resolve_build_issues

from conftest import FakeConn


# ── Collecteur ────────────────────────────────────────────────────────


def test_supported_apps_v1():
    apps = build_mod.supported_apps()
    assert "LarcForge" in apps
    assert apps == sorted(apps)


def test_pyinstaller_absent(tmp_path, monkeypatch):
    (tmp_path / "LarcForge").mkdir()  # passe le check du dossier
    monkeypatch.setattr(build_mod, "pyinstaller_available", lambda py: False)
    cands, errors, info = build_mod.collect(tmp_path, "python")
    assert not cands
    assert any("PyInstaller absent" in e for e in errors)
    assert info["app"] == "LarcForge"


def test_app_non_supportee(tmp_path):
    cands, errors, info = build_mod.collect(tmp_path, "python", app="LarcSecretaire")
    assert not cands
    assert any("non supportée" in e for e in errors)


def test_commande_pyinstaller(tmp_path, monkeypatch):
    """La commande porte --name/--distpath/--hidden-import et le launcher."""
    called = {}

    def fake_run(cmd, cwd, timeout):
        called["cmd"] = cmd
        called["cwd"] = cwd
        # crée l'exe attendu par le collecteur (distpath/name.exe)
        exe = Path(cmd[cmd.index("--distpath") + 1]) / "LarcForge.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"PE")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(build_mod, "pyinstaller_available", lambda py: True)
    monkeypatch.setattr(build_mod, "run_subprocess", fake_run)

    root = tmp_path
    (root / "LarcForge").mkdir()
    cands, errors, info = build_mod.collect(root, "python", onefile=True)

    assert not cands and not errors
    cmd = called["cmd"]
    assert cmd[0] == "python" and cmd[2] == "PyInstaller"
    assert "--onefile" in cmd
    assert "--hidden-import" in cmd
    assert "larcforge.ui.panels.run_panel" in cmd
    assert called["cwd"] == root / "LarcForge"
    launcher = Path(cmd[-1])
    assert launcher.read_text(encoding="utf-8").startswith("from larcforge.cli import main")
    assert info["out"].replace("\\", "/") == "dist/LarcForge/LarcForge.exe"


def test_echec_produit_candidat(tmp_path, monkeypatch):
    def fake_run(cmd, cwd, timeout):
        return subprocess.CompletedProcess(cmd, 1, stderr="ERREUR: module introuvable\n" * 5)

    monkeypatch.setattr(build_mod, "pyinstaller_available", lambda py: True)
    monkeypatch.setattr(build_mod, "run_subprocess", fake_run)

    (tmp_path / "LarcForge").mkdir()
    cands, errors, info = build_mod.collect(tmp_path, "python")
    assert errors == []
    assert len(cands) == 1
    assert cands[0].source == "larcforge:build"
    assert cands[0].app_name == "LarcForge"
    assert "ERREUR" in (cands[0].traceback or "")
    assert info["out"] is None


def test_dossier_introuvable(tmp_path):
    cands, errors, info = build_mod.collect(tmp_path, "python")
    assert any("dossier introuvable" in e for e in errors)


# ── execute_build (DB simulée) ────────────────────────────────────────


def test_execute_build_echec_upsert(tmp_path, monkeypatch):
    """Échec → issue upsertée (created), run fini avec statut issues."""
    fake = FakeConn(plans=[  # start_run → id 7 ; upsert SELECT → None ; count_open → 1
        [(7,)], [None], [(1,)],
    ])
    monkeypatch.setattr(pg, "connect", lambda **kw: fake)
    monkeypatch.setattr(build_mod, "pyinstaller_available", lambda py: True)

    def fake_run(cmd, cwd, timeout):
        return subprocess.CompletedProcess(cmd, 1, stderr="boom")

    monkeypatch.setattr(build_mod, "run_subprocess", fake_run)
    (tmp_path / "LarcForge").mkdir()

    summary, code, message = execute_build(tmp_path, app="LarcForge",
                                           python="python", timeout=60)
    assert code == 1
    assert summary.run_id == 7
    assert summary.nb_new == 1 and summary.nb_issues == 1
    # upsert INSERT visible dans les curseurs
    inserts = [c for c in fake.cursors if any(
        q.startswith("INSERT INTO public.larc_issue") for q, _ in c.calls)]
    assert inserts
    # finish_run exécuté avec 'issues'
    updates = [c for c in fake.cursors if any(
        "UPDATE public.larc_run SET finished_at" in q for q, _ in c.calls)]
    assert updates
    assert fake.closed


def test_execute_build_succes_resout(tmp_path, monkeypatch):
    """Succès → resolve_build_issues sélectionne et résout les issues de l'app."""
    fake = FakeConn(plans=[
        [(8,)],             # start_run → id 8
        [(42,)],            # resolve_build_issues SELECT → issue 42
        [0],                # resolve_issue (UPDATE — plan inutilisé)
        [(0,)],             # count_open → 0
    ], rowcounts=[0, 0, 1, 0])  # resolve_issue → 1
    monkeypatch.setattr(pg, "connect", lambda **kw: fake)
    monkeypatch.setattr(build_mod, "pyinstaller_available", lambda py: True)

    def fake_run(cmd, cwd, timeout):
        exe = tmp_path / "dist" / "LarcForge" / "LarcForge.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"PE")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(build_mod, "run_subprocess", fake_run)
    (tmp_path / "LarcForge").mkdir()

    summary, code, message = execute_build(tmp_path, app="LarcForge",
                                           python="python", timeout=60)
    assert code == 0
    assert "Build OK" in message and "dist" in message
    assert summary.nb_resolved == 1
    # la résolution (UPDATE status='resolved') a été émise pour l'issue 42
    resolves = [c for c in fake.cursors if any(
        "SET status = 'resolved'" in q and "%s" in q for q, _ in c.calls)]
    assert resolves


def test_execute_build_db_down(tmp_path, monkeypatch):
    def down(**kw):
        raise pg.DBUnavailable("refusée (mock)")

    monkeypatch.setattr(pg, "connect", down)
    summary, code, message = execute_build(tmp_path, app="LarcForge")
    assert code == 4
    assert "Connexion DB impossible" in message


# ── resolve_build_issues (store) ──────────────────────────────────────


def test_resolve_build_issues_scope_app(tmp_path, monkeypatch):
    """Ne touche que les issues larcforge:build open/regressed de l'app."""
    fake = FakeConn(plans=[[(10,), (11,)], [0], [0]],
                    rowcounts=[0, 1, 1])  # deux resolve_issue réussis
    n = resolve_build_issues(fake, "LarcForge", run_id=99)
    assert n == 2
    # SELECT filtré sur source + app_name + statuts
    select = fake.cursors[0].calls[0]
    assert "source = 'larcforge:build'" in select[0]
    assert select[1] == ("LarcForge",)
    # deux UPDATE resolve_issue
    assert sum(1 for c in fake.cursors for q, _ in c.calls
               if "SET status = 'resolved'" in q) == 2
