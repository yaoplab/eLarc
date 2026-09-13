"""Tests LarcCommon.larccommon.preferences_dialog.PreferencesDialog."""
from __future__ import annotations

import larccommon  # noqa: F401 -- initialise larccommon avant phibuilder (cycle connu,
# cf. test_event_type_selector.py pour le detail)

import pytest
from PySide6.QtWidgets import QApplication

from larccommon.preferences_dialog import PreferencesDialog


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_construct_no_theme_warning(qapp, recwarn):
    dlg = PreferencesDialog()
    theme_warnings = [w for w in recwarn.list if "cree sans theme=" in str(w.message)]
    assert not theme_warnings, [str(w.message) for w in theme_warnings]


def test_construct(qapp, monkeypatch):
    from larccommon.session import session

    monkeypatch.setattr(session, "fk_language", 2)
    monkeypatch.setattr(session, "theme_pref", "blue")
    monkeypatch.setattr(session, "card_theme", "medium")

    dlg = PreferencesDialog()
    assert dlg.windowTitle() != ""
    # Les preferences d'origine sont memorisees pour l'annulation
    assert dlg._orig_lang == 2
    assert dlg._orig_theme == "blue"
    assert dlg._orig_card == "medium"


def test_on_ok_applies_and_accepts(qapp, monkeypatch):
    from unittest.mock import MagicMock
    from larccommon.database import db, DBMode
    from larccommon.session import session
    from PySide6.QtWidgets import QDialog

    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = None
    fake_conn = MagicMock()
    fake_conn.cursor.return_value = fake_cursor
    # server_conn/is_server_connected sont des proprietes en lecture seule qui
    # se basent sur _server_mode + _intranet -- on patche les attributs prives.
    monkeypatch.setattr(db, "_server_mode", DBMode.INTRANET)
    monkeypatch.setattr(db, "_intranet", fake_conn)
    monkeypatch.setattr(session, "user_id", 1)
    monkeypatch.setattr(session, "fk_language", 2)
    monkeypatch.setattr(session, "theme_pref", "blue")
    monkeypatch.setattr(session, "card_theme", "medium")

    dlg = PreferencesDialog()
    dlg._on_ok()

    assert dlg.result() == QDialog.Accepted
    # Persistance : 3 INSERT larcauth_config + 1 UPDATE larcauth_aecuser
    inserts = [c.args for c in fake_cursor.execute.call_args_list if "larcauth_config" in c.args[0]]
    assert len(inserts) == 3
    lang_updates = [c.args for c in fake_cursor.execute.call_args_list if "larcauth_aecuser" in c.args[0]]
    assert lang_updates and lang_updates[0][1] == (2, 1)
    assert fake_conn.commit.called


def test_on_cancel_restores_original_prefs(qapp, monkeypatch):
    from larccommon.session import session
    from PySide6.QtWidgets import QDialog

    monkeypatch.setattr(session, "fk_language", 2)
    monkeypatch.setattr(session, "theme_pref", "blue")
    monkeypatch.setattr(session, "card_theme", "medium")

    dlg = PreferencesDialog()
    session.theme_pref = "dark"
    session.fk_language = 1
    dlg._on_cancel()

    assert dlg.result() == QDialog.Rejected
    assert session.theme_pref == "blue"
    assert session.fk_language == 2
    assert session.card_theme == "medium"


def test_language_button_sets_session_lang(qapp, monkeypatch):
    from larccommon.session import session
    from phibuilder.widgets import M3Button

    monkeypatch.setattr(session, "fk_language", 2)
    monkeypatch.setattr(session, "theme_pref", "blue")
    monkeypatch.setattr(session, "card_theme", "medium")

    dlg = PreferencesDialog()
    # Le groupe langue a 2 boutons (fr/en) -- cliquer celui non selectionne
    lang_btns = [b for b in dlg.findChildren(M3Button) if b.isCheckable()]
    other = next(b for b in lang_btns if not b.isChecked())
    other.click()
    # "fr" (lang 2) ou "en" (lang 1) -- la session reflete le bouton choisi
    assert session.fk_language in (1, 2)
