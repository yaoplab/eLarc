"""Tests de la sous-commande `ui` : parsing + comportement sans PySide6."""

from __future__ import annotations

import sys

import pytest

from larcforge import cli


def test_parse_commande_ui():
    args = cli.build_parser().parse_args(["ui"])
    assert args.command == "ui"
    assert args.func is cli.cmd_ui
    assert args.no_db is False
    assert args.timeout == 300


def test_cmd_ui_sans_pyside6_retourne_2(monkeypatch, capsys):
    # simule un environnement sans PySide6 : l'import de .ui.app échoue.
    # sys.modules[...] = None lève ImportError de façon fiable, même si les
    # sous-modules PySide6 ont déjà été chargés par d'autres tests de la suite.
    monkeypatch.setitem(sys.modules, "larcforge.ui.app", None)
    args = cli.build_parser().parse_args(["ui"])
    code = cli.cmd_ui(args)
    assert code == 2
    err = capsys.readouterr().err
    assert "PySide6 manquant" in err
    assert "larcforge[gui]" in err


def test_ui_help_ne_lance_pas_qt():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["ui", "--help"])
