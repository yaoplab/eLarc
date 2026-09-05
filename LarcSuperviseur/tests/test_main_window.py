"""Tests UI (qtbot) de MainWindow — cf. docs/debug/CR-2026-08-14 §4.2.

Smoke tests : construction complète sur DB mockée + chemins thème/période/
validation. La donnée est vide (cursors mockés) — on vérifie l'absence de crash
et la présence des sous-composants.
"""
from __future__ import annotations

import larccommon  # noqa: F401 — initialiser larccommon AVANT phibuilder (import circulaire connu)


def _make_window(qtbot, mock_db, mock_session):
    # Import DANS la fonction + re-liaison explicite : le module garde le
    # binding from-import du PREMIER import (ou est re-lié au vrai db par le
    # teardown du conftest) — on fixe ici le mock du test courant.
    import LarcSuperviseur.views.main_window as mw

    mw.db = mock_db
    mw.session = mock_session
    w = mw.MainWindow()
    qtbot.addWidget(w)
    return w


def test_main_window_constructs(qtbot, mock_db, mock_session, mock_theme):
    w = _make_window(qtbot, mock_db, mock_session)
    assert w.windowTitle() != ""
    assert hasattr(w, "_top_bar")
    assert hasattr(w, "_sidebar")
    assert hasattr(w, "_student_detail")
    assert hasattr(w, "_actions")  # fix 2026-08-14 : initialisé dans __init__


def test_theme_change_no_crash(qtbot, mock_db, mock_session, mock_theme):
    w = _make_window(qtbot, mock_db, mock_session)
    w._restyle()


def test_period_click_no_crash(qtbot, mock_db, mock_session, mock_theme):
    w = _make_window(qtbot, mock_db, mock_session)
    w._on_period_clicked("day")


def test_toggle_validation_mock_db(qtbot, mock_db, mock_session, mock_theme):
    w = _make_window(qtbot, mock_db, mock_session)
    w._toggle_validation(42)  # méthode void — vérifie UPDATE + commit
    mc = mock_db.server_conn.cursor.return_value
    updates = [
        c.args for c in mc.execute.call_args_list if "UPDATE student_event" in c.args[0]
    ]
    assert updates, "aucun UPDATE student_event émis"
    assert updates[0][1] == (1, 42)  # session.user_id + event_id
    assert mock_db.server_conn.commit.called
