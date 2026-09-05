"""Tests de la CLI : parsing (flags globaux avant/après), codes de sortie.

Aucune PostgreSQL ni aucun linter n'est réellement exécuté : execute() est
mocké pour tester la propagation des codes de retour.
"""

from __future__ import annotations

import argparse

import pytest

from larcforge import cli
from larcforge import config as cfg
from larcforge.models import RunScope, RunSummary


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_flags_globaux_avant_et_apres_sous_commande():
    parser = cli.build_parser()
    a = parser.parse_args(["--no-db", "--json", "run"])
    b = parser.parse_args(["run", "--no-db", "--json"])
    assert a.command == "run" and a.no_db and a.json
    assert b.command == "run" and b.no_db and b.json


def test_flags_status_apres_sous_commande():
    parser = cli.build_parser()
    a = parser.parse_args(["status", "--app", "LarcSuperviseur", "--open", "--csv"])
    assert a.command == "status"
    assert a.app == "LarcSuperviseur" and a.open and a.csv


def test_parse_linters_all():
    assert cli._parse_linters("all") == cfg.LINTER_KEYS


def test_parse_linters_selection_avec_espaces():
    assert cli._parse_linters("R, d") == ["R", "D"]


def test_parse_linters_inconnu_SystemExit():
    with pytest.raises(SystemExit):
        cli._parse_linters("R,ZZZ")


def test_parse_list():
    assert cli._parse_list(None) is None
    assert cli._parse_list("A, B, C") == ["A", "B", "C"]
    assert cli._parse_list("") is None


def test_scope_for_defauts():
    args = argparse.Namespace(linters="all", projects=None,
                              include_integration=False, since=None, level=None)
    scope = cli._scope_for(args, "run")
    assert scope.command == "run"
    assert scope.linters == cfg.LINTER_KEYS
    assert scope.projects == cfg.PROJETS
    assert scope.level == "ERROR,WARNING"


# ---------------------------------------------------------------------------
# Codes de sortie
# ---------------------------------------------------------------------------


def test_main_version(capsys):
    assert cli.main(["--version"]) == 0
    assert "larcforge" in capsys.readouterr().out


def test_main_sans_commande():
    assert cli.main([]) == 2


def test_main_commande_inconnue():
    with pytest.raises(SystemExit):
        cli.main(["xyz"])


def test_main_status_sans_db_retourne_2(capsys):
    assert cli.main(["status", "--no-db"]) == 2
    assert "nécessite la base" in capsys.readouterr().err


def test_run_and_report_propage_code(monkeypatch, capsys):
    def fake_execute(root, scope, **kw):
        return (RunSummary(nb_issues=2, nb_new=1, nb_regressed=0, nb_resolved=0,
                           nb_errors=0, run_id=7), 1, "2 problèmes ouverts")
    monkeypatch.setattr(cli, "execute", fake_execute)
    args = argparse.Namespace(root="F:/projets", timeout=300, no_db=False, json=False)
    code = cli._run_and_report(args, RunScope(command="run"), "run")
    assert code == 1
    assert "run #7" in capsys.readouterr().out


def test_report_json(monkeypatch, capsys):
    args = argparse.Namespace(root="F:/projets", timeout=300, no_db=False, json=True)
    summary = RunSummary(nb_issues=1, nb_new=1, run_id=3)
    code = cli._report(args, summary, 1, "1 problème", "run")
    assert code == 1
    out = capsys.readouterr().out
    assert '"run_id": 3' in out
    assert '"exit_code": 1' in out


def test_parser_build():
    parser = cli.build_parser()
    a = parser.parse_args(["build", "--app", "LarcForge", "--onefile"])
    assert a.command == "build"
    assert a.app == "LarcForge" and a.onefile
    b = parser.parse_args(["build"])
    assert b.app == "LarcForge" and not b.onefile


def test_cmd_build_app_non_supportee(capsys):
    args = argparse.Namespace(root="F:/projets", timeout=300, no_db=True,
                              json=False, app="LarcSecretaire", onefile=False)
    assert cli.cmd_build(args) == 2
    assert "non supportée" in capsys.readouterr().err


def test_cmd_build_propage_rapport(monkeypatch, capsys):
    """cmd_build → execute_build (timeout relevé à 900) → rapport."""
    calls = {}

    def fake_execute_build(root, app, timeout, onefile, use_db):
        calls.update(root=root, app=app, timeout=timeout, onefile=onefile,
                     use_db=use_db)
        return (RunSummary(nb_issues=0, run_id=9), 0, "Build OK")

    monkeypatch.setattr("larcforge.runner.execute_build", fake_execute_build)
    args = argparse.Namespace(root="F:/projets", timeout=60, no_db=True,
                              json=False, app="LarcForge", onefile=True)
    assert cli.cmd_build(args) == 0
    assert calls == {"root": "F:/projets", "app": "LarcForge", "timeout": 900,
                     "onefile": True, "use_db": False}
    assert "Build OK" in capsys.readouterr().out
