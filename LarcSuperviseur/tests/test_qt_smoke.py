"""Smoke tests pytest-qt (qtbot) + PySide6 pour LarcSuperviseur.

Premier pas vers les tests UI recommandés au CR-2026-08-14 :
event_generator, top_bar, login, main_window (cf. docs/debug/CR-2026-08-14.md §4.2).
"""
from __future__ import annotations

from PySide6.QtCore import Qt

from phibuilder.widgets import M3Button


def test_m3button_click_qtbot(qtbot):
    """Un M3Button émet clicked quand qtbot clique dessus."""
    clicked = []
    btn = M3Button("Tester")
    qtbot.addWidget(btn)
    btn.show()
    btn.clicked.connect(lambda: clicked.append(True))
    qtbot.mouseClick(btn, Qt.LeftButton)
    assert clicked == [True]
