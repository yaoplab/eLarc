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


def test_restyle_all_updates_colors_on_theme_changed(qtbot, mock_db, mock_session, mock_theme, monkeypatch):
    # Assertion faible rejetee : "styleSheet() != ''" reste vrai meme si
    # _restyle_all n'existe pas / n'est jamais connectee (le styleSheet est
    # deja non-vide depuis __init__).
    #
    # mock_theme est INOPERANT ici : il patch l'attribut module
    # "LarcSuperviseur.common.theme.theme_manager", mais event_dialog.py fait
    # `from LarcSuperviseur.common.theme import theme_manager` (ligne 16) —
    # ce nom est lie UNE FOIS a la collection des tests (avant que la fixture
    # ne patche quoi que ce soit) et reste bind sur le VRAI singleton
    # ThemeManager pour tout le reste du process. On mute donc directement les
    # attributs de la VRAIE Palette active (meme objet que celui lu par
    # theme_manager.palette dans le code de production) et on emet le VRAI
    # signal ds.theme_changed, pour exercer bout-en-bout le fil connect() de
    # __init__ sans dependre de la plomberie mock_theme (meme pattern que
    # test_timetable_editor.py::test_restyle_all_updates_colors_on_theme_changed).
    from larccommon.design_system import ds
    from LarcSuperviseur.views.core import event_dialog as ed_mod

    fake = mock_db.server_conn.cursor.return_value
    fake.fetchone.return_value = (
        "Absence cours", None, datetime(2026, 7, 8, 8, 30),
        "Salle de cours", "Maths", "", "Dupont Jean",
    )
    fake.fetchall.return_value = [("Absence cours",)]

    dlg = _make_dlg(qtbot, mock_db)

    real_palette = ed_mod.theme_manager.palette
    old_primary = real_palette.primary
    old_surface = real_palette.surface
    assert old_primary in dlg._save_btn.styleSheet()
    assert old_surface in dlg.styleSheet()

    monkeypatch.setattr(real_palette, "primary", "#ABCDEF")
    monkeypatch.setattr(real_palette, "surface", "#123456")

    ds.theme_changed.emit()  # signal reel : prouve que le connect() de __init__ fonctionne

    assert "#ABCDEF" in dlg._save_btn.styleSheet()
    assert old_primary not in dlg._save_btn.styleSheet()
    assert "#123456" in dlg.styleSheet()
    assert old_surface not in dlg.styleSheet()


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

    # EventEditDialog constructs EventTypeSelectorWidget
    # (LarcCommon/larccommon/dialogs/event_type_selector.py). That widget used
    # to have 3 of its own unfixed theme= sites (M3TextField/M3Label/M3Button),
    # which required tolerating exactly those 3 out-of-scope warnings here.
    # It was fixed on 2026-09-11 (commit 166f370) — EventTypeSelectorWidget now
    # contributes 0 warnings, so this test asserts a plain empty list like the
    # other tasks' tests. If this ever needs the class-count workaround again
    # (a new unfixed shared widget introduced upstream), see git history on
    # this test for the pattern (multiset of warning classes) and why a
    # filename-based filter cannot discriminate (every M3 widget's
    # _update_style() calls warnings.warn(stacklevel=2), which always
    # attributes the filename to the widget's own defining file in LarcCommon,
    # never to the external caller).
    #
    # "always" is still required: pytest's recwarn fixture uses "default"
    # (print-once-per-(message, category, module, lineno)), and every
    # M3Button instantiation warns from the exact same line inside button.py
    # regardless of call site — "default" would silently dedup a second,
    # genuinely distinct M3Button warning (e.g. event_dialog.py's own
    # cancel_btn losing its theme=) if any earlier M3Button in this test
    # process already warned once. "always" disables that dedup so each
    # instantiation is counted.
    import warnings

    warnings.simplefilter("always")

    _make_dlg(qtbot, mock_db)

    theme_warnings = [str(x.message) for x in recwarn.list if "cree sans theme=" in str(x.message)]
    assert not theme_warnings, theme_warnings
