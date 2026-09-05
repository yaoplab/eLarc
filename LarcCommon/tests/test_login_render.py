#!/usr/bin/env python
"""Test de rendu — LoginWindow (LarcCommon).

Vérifie que la fenêtre de connexion partagée se construit correctement.
Anciennement un script interactif (BaseLoginWindow, API disparue lors du
refactoring) — remplacé par un vrai test pytest sur la nouvelle API.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton, QTabWidget

from larccommon.database import db
from larccommon.login import LoginWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def login_window(monkeypatch, qapp):
    # Ne pas toucher la vraie PostgreSQL pendant le test
    monkeypatch.setattr(db, "connect_intranet", lambda: True)
    monkeypatch.setattr(db, "connect_cloud", lambda: False)
    win = LoginWindow(on_success=lambda: None)
    win.show()
    yield win
    win.close()


def test_fenetre_construite_avec_titre(login_window):
    assert login_window.windowTitle()  # "préfixe - Connexion"


def test_onglets_de_connexion_presents(login_window):
    assert login_window.findChildren(QTabWidget), "onglets de connexion manquants"


def test_champs_identifiants_et_bouton(login_window):
    assert len(login_window.findChildren(QLineEdit)) >= 2, "champs identifiants manquants"
    assert login_window.findChildren(QPushButton), "bouton de connexion manquant"
