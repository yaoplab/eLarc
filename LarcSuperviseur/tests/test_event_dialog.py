"""Tests UI (qtbot) d'EventEditDialog — édition d'un événement.

QMessageBox patché (modaux bloquants) pour les chemins no-connection/not-found.
"""
from __future__ import annotations

from datetime import datetime

import larccommon  # noqa: F401 — initialiser larccommon AVANT phibuilder (import circulaire connu)

from PySide6.QtWidgets import QDialog, QMessageBox

from LarcSuperviseur.views.core.event_dialog import EventEditDialog


def _noop_warning(monkeypatch):
    monkeypatch.setattr(
        QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.Ok)
    )


def _make_dlg(qtbot, mock_db):
    import LarcSuperviseur.views.core.event_dialog as ed

    ed.db = mock_db
    dlg = EventEditDialog(42)
    qtbot.addWidget(dlg)
    return dlg


def test_load_event_populates(qtbot, mock_db, mock_session, mock_theme):
    fake = mock_db.server_conn.cursor.return_value
    fake.fetchone.return_value = (
        "Absence cours",
        datetime(2026, 7, 8, 8, 30),
        "Salle de cours",
        "Maths",
        "",
        "Dupont Jean",
    )
    fake.fetchall.return_value = [("Absence cours",), ("Sortie",)]

    dlg = _make_dlg(qtbot, mock_db)

    assert dlg._type_input.currentText() == "Absence cours"
    assert "Dupont Jean" in dlg._info.text()
    assert dlg._note_input.toPlainText() == ""


def test_no_connection_rejects(qtbot, mock_db, mock_session, mock_theme, monkeypatch):
    _noop_warning(monkeypatch)
    mock_db.server_conn = None

    dlg = _make_dlg(qtbot, mock_db)

    assert dlg.result() == QDialog.Rejected


def test_not_found_rejects(qtbot, mock_db, mock_session, mock_theme, monkeypatch):
    _noop_warning(monkeypatch)
    mock_db.server_conn.cursor.return_value.fetchone.return_value = None

    dlg = _make_dlg(qtbot, mock_db)

    assert dlg.result() == QDialog.Rejected


def test_save_updates_and_accepts(qtbot, mock_db, mock_session, mock_theme):
    fake = mock_db.server_conn.cursor.return_value
    fake.fetchone.return_value = (
        "Absence cours",
        datetime(2026, 7, 8, 8, 30),
        "Salle de cours",
        "Maths",
        "Note",
        "Dupont Jean",
    )
    fake.fetchall.return_value = [("Absence cours",)]

    dlg = _make_dlg(qtbot, mock_db)
    dlg._note_input.setText("  Justifiée  ")  # strip vérifié

    dlg._save()

    assert dlg.result() == QDialog.Accepted
    updates = [c.args for c in fake.execute.call_args_list if "UPDATE student_event" in c.args[0]]
    assert updates[0][1] == ("Absence cours", "Justifiée", 42)
    assert mock_db.server_conn.commit.called
