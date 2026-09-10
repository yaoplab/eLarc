"""Tests UI (qtbot) d'EventActions.get_context_menu — seule méthode Qt-dépendante
de ce module (cf. test_event_actions.py pour les tests non-Qt)."""
from __future__ import annotations

import larccommon  # noqa: F401 — initialiser larccommon AVANT phibuilder (import circulaire connu)

from PySide6.QtWidgets import QWidget

from LarcSuperviseur.views.core.event_actions import EventActions


def test_get_context_menu_no_theme_warning(qtbot, mock_db, mock_session, mock_theme, recwarn):
    fake_cursor = mock_db.server_conn.cursor.return_value
    fake_cursor.fetchone.return_value = None

    parent = QWidget()
    qtbot.addWidget(parent)
    recwarn.clear()

    EventActions().get_context_menu(1, parent=parent)

    theme_warnings = [x for x in recwarn.list if "cree sans theme=" in str(x.message)]
    assert not theme_warnings, [str(x.message) for x in theme_warnings]
