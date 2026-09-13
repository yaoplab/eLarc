"""Tests UI (qtbot) d'EventTypesPanel — écran d'administration des types d'événements."""
from __future__ import annotations

import larccommon  # noqa: F401 — initialiser larccommon AVANT phibuilder (import circulaire connu)

from PySide6.QtWidgets import QDialog

from LarcSuperviseur.views.panels.event_types_panel import EventTypesPanel


def test_construct_no_theme_warning(qtbot, mock_db, mock_session, mock_theme, recwarn):
    panel = EventTypesPanel()
    qtbot.addWidget(panel)

    theme_warnings = [x for x in recwarn.list if "cree sans theme=" in str(x.message)]
    assert not theme_warnings, [str(x.message) for x in theme_warnings]


def test_add_root_dialog_no_theme_warning(qtbot, mock_db, mock_session, mock_theme, recwarn, monkeypatch):
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.Rejected)

    panel = EventTypesPanel()
    qtbot.addWidget(panel)
    recwarn.clear()

    panel._on_add_root()

    theme_warnings = [x for x in recwarn.list if "cree sans theme=" in str(x.message)]
    assert not theme_warnings, [str(x.message) for x in theme_warnings]


def test_edit_dialog_restyle_all_no_crash(qtbot, mock_db, mock_session, mock_theme):
    from LarcSuperviseur.views.panels.event_types_panel import EventTypeEditDialog
    from LarcSuperviseur.views.core.event_type_repo import EventTypeRepo

    dlg = EventTypeEditDialog(EventTypeRepo(), mode="create", roots=[])
    qtbot.addWidget(dlg)

    dlg._restyle_all()  # ne doit pas lever d'exception


def test_edit_dialog_restyle_all_updates_colors_on_theme_changed(
    qtbot, mock_db, mock_session, mock_theme, monkeypatch
):
    # Assertion faible rejetee : "styleSheet() != ''" reste vrai meme si
    # _restyle_all n'existe pas / n'est jamais connectee (le styleSheet est
    # deja non-vide depuis __init__).
    #
    # mock_theme est INOPERANT ici : il patch l'attribut module
    # "LarcSuperviseur.common.theme.theme_manager", mais event_types_panel.py
    # fait `from LarcSuperviseur.common.theme import theme_manager` (ligne 28) —
    # ce nom est lie UNE FOIS a la collection des tests (avant que la fixture
    # ne patche quoi que ce soit) et reste bind sur le VRAI singleton
    # ThemeManager pour tout le reste du process. On mute donc directement les
    # attributs de la VRAIE Palette active (meme objet que celui lu par
    # theme_manager.palette dans le code de production) et on emet le VRAI
    # signal ds.theme_changed, pour exercer bout-en-bout le fil connect() de
    # __init__ sans dependre de la plomberie mock_theme (meme pattern que
    # test_event_dialog.py::test_restyle_all_updates_colors_on_theme_changed).
    from larccommon.design_system import ds
    from LarcSuperviseur.views.panels import event_types_panel as etp_mod
    from LarcSuperviseur.views.core.event_type_repo import EventTypeRepo

    dlg = etp_mod.EventTypeEditDialog(EventTypeRepo(), mode="create", roots=[])
    qtbot.addWidget(dlg)

    real_palette = etp_mod.theme_manager.palette
    old_surface = real_palette.surface
    assert old_surface in dlg.styleSheet()

    monkeypatch.setattr(real_palette, "surface", "#123456")

    ds.theme_changed.emit()  # signal reel : prouve que le connect() de __init__ fonctionne

    assert "#123456" in dlg.styleSheet()
    assert old_surface not in dlg.styleSheet()
