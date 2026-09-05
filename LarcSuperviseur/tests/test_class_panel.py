"""Tests UI (qtbot) de ClassPanel — grille de cartes élèves d'une classe."""
from __future__ import annotations

import larccommon  # noqa: F401 — initialiser larccommon AVANT phibuilder (import circulaire connu)

from PySide6.QtWidgets import QWidget

from LarcSuperviseur.views.panels.class_panel import ClassPanel


def _make_panel(qtbot, mock_db):
    import LarcSuperviseur.views.panels.class_panel as cp

    cp.db = mock_db
    panel = cp.ClassPanel()
    qtbot.addWidget(panel)
    return panel


def test_construct(qtbot, mock_db, mock_session, mock_theme):
    panel = _make_panel(qtbot, mock_db)
    assert panel._class_id == 0
    assert panel._students == []


def test_load_empty_class(qtbot, mock_db, mock_session, mock_theme):
    panel = _make_panel(qtbot, mock_db)
    mock_db.server_conn.cursor.return_value.fetchall.return_value = []

    panel.load(5, "2026-01-01", "2026-08-14")

    assert panel._class_id == 5
    assert not panel._loading.isVisible()  # le loader est masqué en fin de load


def test_card_click_emits_signal(qtbot, mock_db, mock_session, mock_theme):
    panel = _make_panel(qtbot, mock_db)
    received = []
    panel.student_selected.connect(lambda sid: received.append(sid))

    panel._on_card_click(123)

    assert received == [123]


def test_reflow_no_crash(qtbot, mock_db, mock_session, mock_theme):
    panel = _make_panel(qtbot, mock_db)
    # Quelques widgets non-StudentCard dans la grille → supprimés par reflow
    for _ in range(3):
        panel._grid_layout.addWidget(QWidget())
    panel.reflow()  # ne doit pas lever (fix 2026-08-14 : _unused)
