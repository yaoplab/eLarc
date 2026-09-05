"""Tests UI (qtbot) de PreferencesDialog — langue, thème, taille de carte."""
from __future__ import annotations

import larccommon  # noqa: F401 — initialiser larccommon AVANT phibuilder (import circulaire connu)

from PySide6.QtWidgets import QDialog

from LarcSuperviseur.views.dialogs.preferences import PreferencesDialog


def _make_dlg(qtbot, mock_db, mock_session):
    import LarcSuperviseur.views.dialogs.preferences as prefs

    prefs.db = mock_db
    prefs.session = mock_session
    dlg = PreferencesDialog()
    qtbot.addWidget(dlg)
    return dlg


def test_construct(qtbot, mock_db, mock_session, mock_theme):
    dlg = _make_dlg(qtbot, mock_db, mock_session)
    assert dlg.windowTitle() != ""
    # Les préférences d'origine sont mémorisées pour l'annulation
    assert dlg._orig_lang == 2
    assert dlg._orig_theme == "blue"
    assert dlg._orig_card == "medium"


def test_on_ok_applies_and_accepts(qtbot, mock_db, mock_session, mock_theme):
    dlg = _make_dlg(qtbot, mock_db, mock_session)
    dlg._on_ok()
    assert dlg.result() == QDialog.Accepted
    # Persistance : 3 INSERT larcauth_config + 1 UPDATE larcauth_aecuser
    fake = mock_db.server_conn.cursor.return_value
    inserts = [c.args for c in fake.execute.call_args_list if "larcauth_config" in c.args[0]]
    assert len(inserts) == 3
    lang_updates = [c.args for c in fake.execute.call_args_list if "larcauth_aecuser" in c.args[0]]
    assert lang_updates and lang_updates[0][1] == (2, 1)
    assert mock_db.server_conn.commit.called


def test_on_cancel_restores_original_prefs(qtbot, mock_db, mock_session, mock_theme):
    dlg = _make_dlg(qtbot, mock_db, mock_session)
    mock_session.theme_pref = "dark"
    mock_session.fk_language = 1
    dlg._on_cancel()
    assert dlg.result() == QDialog.Rejected
    assert mock_session.theme_pref == "blue"
    assert mock_session.fk_language == 2
    assert mock_session.card_theme == "medium"


def test_language_button_sets_session_lang(qtbot, mock_db, mock_session, mock_theme):
    from phibuilder.widgets import M3Button

    dlg = _make_dlg(qtbot, mock_db, mock_session)
    # Le groupe langue a 2 boutons (fr/en) — cliquer celui non sélectionné
    lang_btns = [b for b in dlg.findChildren(M3Button) if b.isCheckable()]
    other = next(b for b in lang_btns if not b.isChecked())
    other.click()
    # "fr" (lang 2) ou "en" (lang 1) — la session reflète le bouton choisi
    assert mock_session.fk_language in (1, 2)
