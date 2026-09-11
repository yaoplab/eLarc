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


def test_no_theme_warning(qtbot, mock_db, mock_session, mock_theme, recwarn):
    fake = mock_db.server_conn.cursor.return_value
    fake.fetchone.return_value = (
        "Absence cours",
        None,
        datetime(2026, 7, 8, 8, 30),
        "Salle de cours",
        "Maths",
        "",
        "Dupont Jean",
    )
    fake.fetchall.return_value = [("Absence cours",), ("Sortie",)]
    recwarn.clear()

    # A filename-based filter does NOT work here: every M3 widget's
    # _update_style() calls warnings.warn(..., stacklevel=2), which always
    # attributes the warning's filename to the widget's own defining file
    # inside LarcCommon (e.g. phibuilder/widgets/label.py) — never to the
    # external caller (event_dialog.py) that instantiated it, no matter who
    # the caller is. So instead we assert the exact multiset of warning
    # classes: EventEditDialog constructs EventTypeSelectorWidget
    # (LarcCommon/larccommon/dialogs/event_type_selector.py), which
    # unconditionally emits exactly 3 known, out-of-scope warnings (one
    # M3TextField, one M3Label, one M3Button) — tracked separately, not part
    # of this task. event_dialog.py's own 5 widget sites (_info, _note_label,
    # _note_input, save_btn, cancel_btn) all pass theme=theme_manager.phi_theme
    # and must contribute 0 warnings on top of that baseline.
    #
    # This requires forcing the "always" filter: pytest's recwarn fixture
    # uses "default" (print-once-per-(message, category, module, lineno)).
    # Since every M3Button instantiation warns from the exact same line
    # inside button.py regardless of which call site created it, "default"
    # would silently dedup a second, genuinely distinct M3Button warning
    # (e.g. from event_dialog.py's own cancel_btn losing its theme=) against
    # the one already raised by EventTypeSelectorWidget's _confirm_btn —
    # making a regression invisible. "always" disables that dedup so each
    # instantiation is counted. (Verified empirically: without this line, a
    # deliberately reintroduced missing theme= on cancel_btn does NOT fail
    # this test — see task-2-report.md, Round 3.)
    import warnings

    warnings.simplefilter("always")

    _make_dlg(qtbot, mock_db)

    theme_warnings = [str(x.message) for x in recwarn.list if "cree sans theme=" in str(x.message)]
    classes = sorted(w.split()[0] for w in theme_warnings)
    assert classes == ["M3Button", "M3Label", "M3TextField"], theme_warnings
