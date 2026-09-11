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
