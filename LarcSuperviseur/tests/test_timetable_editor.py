"""Tests UI (qtbot) de TimetableEditor — grille EDT et sauvegarde."""
from __future__ import annotations

from datetime import time

import larccommon  # noqa: F401 — initialiser larccommon AVANT phibuilder (import circulaire connu)

from PySide6.QtWidgets import QDialog, QMessageBox

from LarcSuperviseur.views.dialogs.timetable_editor import TimetableEditor


def _make_editor(qtbot, mock_db):
    import LarcSuperviseur.views.dialogs.timetable_editor as tte

    tte.db = mock_db
    dlg = TimetableEditor(5, "PEI-1", 7)
    qtbot.addWidget(dlg)
    return dlg


def test_construct_empty_data(qtbot, mock_db, mock_session, mock_theme):
    dlg = _make_editor(qtbot, mock_db)
    assert dlg._tt_grid.columnCount() == 6  # heure + 5 jours
    assert dlg._tt_grid.rowCount() == 0  # aucun créneau


def test_build_grid_with_slots(qtbot, mock_db, mock_session, mock_theme):
    fake = mock_db.server_conn.cursor.return_value
    # get_timeperiods → get_classroom_timetable → get_available_subjects
    fake.fetchall.side_effect = [
        [(1, time(8, 0), time(8, 55), 1), (2, time(9, 0), time(9, 55), 1)],
        [(11, 1, 1, "Maths")],
        [("Maths",), ("Anglais",)],
    ]

    dlg = _make_editor(qtbot, mock_db)

    assert dlg._tt_grid.rowCount() == 2  # 2 créneaux le lundi
    assert dlg._tt_grid.item(0, 0).text() == "08:00-08:55"
    combo = dlg._tt_grid.cellWidget(0, 1)
    assert combo is not None
    assert combo.currentText() == "Maths"


def test_save_updates_slots_and_accepts(qtbot, mock_db, mock_session, mock_theme, monkeypatch):
    monkeypatch.setattr(
        QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.Ok)
    )
    fake = mock_db.server_conn.cursor.return_value
    fake.fetchall.side_effect = [
        [(1, time(8, 0), time(8, 55), 1)],
        [(11, 1, 1, "Maths")],
        [("Maths",), ("Anglais",)],
    ]
    fake.fetchone.return_value = (9,)  # get_subject_id_by_label("Maths")

    dlg = _make_editor(qtbot, mock_db)
    dlg._save()

    assert dlg.result() == QDialog.Accepted
    updates = [
        c.args
        for c in fake.execute.call_args_list
        if "UPDATE larcauth_classroom_has_timeperiod" in c.args[0]
    ]
    assert updates and updates[0][1] == (9, 11)
    assert mock_db.server_conn.commit.called


def test_restyle_all_updates_colors_on_theme_changed(qtbot, mock_db, mock_session, mock_theme, monkeypatch):
    # Assertions plus faibles rejetees : "styleSheet() != ''" reste vrai meme si
    # _restyle_all n'existe pas / n'est jamais appelee (le styleSheet est deja
    # non-vide depuis __init__), et appeler editor._restyle_all() directement
    # ne prouve pas que ds.theme_changed.connect(self._restyle_all) a bien eu
    # lieu en __init__.
    #
    # mock_theme est INOPERANT ici : il patch l'attribut module
    # "LarcSuperviseur.common.theme.theme_manager", mais timetable_editor.py
    # fait `from LarcSuperviseur.common.theme import theme_manager` (ligne 13)
    # — ce nom est lie UNE FOIS a la collection des tests (avant que la
    # fixture ne patche quoi que ce soit) et reste bind sur le VRAI singleton
    # ThemeManager reel pour tout le reste du process (verifie empiriquement :
    # avec mock_theme.palette.primary = "#1976d2", le styleSheet produit
    # contenait quand meme "#1F4494", la vraie couleur de marque). On mute
    # donc directement les attributs de la VRAIE Palette active (meme objet
    # que celui lu par theme_manager.palette dans le code de production) et on
    # emet le VRAI signal ds.theme_changed, pour exercer bout-en-bout le fil
    # connect() de la ligne 40 sans dependre du plomberie mock_theme.
    from larccommon.design_system import ds
    from LarcSuperviseur.views.dialogs import timetable_editor as tte_mod

    fake = mock_db.server_conn.cursor.return_value
    fake.fetchall.side_effect = [[], [], []]

    editor = _make_editor(qtbot, mock_db)

    real_palette = tte_mod.theme_manager.palette
    old_primary = real_palette.primary
    old_surface = real_palette.surface
    assert old_primary in editor._save_btn.styleSheet()
    assert old_surface in editor.styleSheet()

    monkeypatch.setattr(real_palette, "primary", "#ABCDEF")
    monkeypatch.setattr(real_palette, "surface", "#123456")

    ds.theme_changed.emit()  # signal reel : prouve que le connect() de __init__ fonctionne

    assert "#ABCDEF" in editor._save_btn.styleSheet()
    assert old_primary not in editor._save_btn.styleSheet()
    assert "#123456" in editor.styleSheet()
    assert old_surface not in editor.styleSheet()


def test_no_theme_warning(qtbot, mock_db, mock_session, mock_theme, recwarn):
    fake = mock_db.server_conn.cursor.return_value
    fake.fetchall.side_effect = [
        [(1, time(8, 0), time(8, 55), 1), (2, time(9, 0), time(9, 55), 1)],
        [(11, 1, 1, "Maths")],
        [("Maths",), ("Anglais",)],
    ]
    recwarn.clear()

    _make_editor(qtbot, mock_db)

    theme_warnings = [x for x in recwarn.list if "cree sans theme=" in str(x.message)]
    assert not theme_warnings, [str(x.message) for x in theme_warnings]
