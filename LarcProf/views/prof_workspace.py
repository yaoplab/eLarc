"""ProfWorkspace — pont entre HomeWidget et MainWindow pour LarcHub.

Gère la navigation HomeWidget↔MainWindow dans un QStackedWidget,
permettant à LarcHub d'embarquer LarcProf comme une section standard.
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from PySide6.QtCore import Signal

from larccommon.design_system import ds
from larccommon.safe_slot import safe_slot


class ProfWorkspace(QWidget):
    """Espace de travail enseignant embarquable dans LarcHub.

    Page 0 : HomeWidget (tableau de bord prof)
    Page 1 : MainWindow (grille de notes)
    """

    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._home = None
        self._main_window = None
        self._stack = QStackedWidget()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._stack, 1)

        self._init_home()

    # ------------------------------------------------------------------
    # Page 0 — Home Dashboard
    # ------------------------------------------------------------------
    def _init_home(self):
        from .home_widget import HomeWidget

        self._home = HomeWidget()
        self._home.navigation_requested.connect(self._on_navigate)
        self._stack.addWidget(self._home)

    # ------------------------------------------------------------------
    # Page 1 — Notes Grid (MainWindow)
    # ------------------------------------------------------------------
    @safe_slot("ProfWorkspace._on_navigate")
    def _on_navigate(self, focus: str):
        """Quand le prof clique sur un bouton programme, charger MainWindow."""
        from .main_window import MainWindow

        if self._main_window is not None:
            idx = self._stack.indexOf(self._main_window)
            if idx >= 0:
                self._stack.removeWidget(self._main_window)
            self._main_window.deleteLater()
            self._main_window = None

        self._main_window = MainWindow()
        self._main_window.setWindowTitle("")

        # Intercepter la fermeture → revenir au dashboard
        original_close = self._main_window.closeEvent

        def _intercept_close(event):
            if not self._main_window._confirm_leave():
                event.ignore()
                return
            self._stack.setCurrentIndex(0)
            if self._home:
                self._home._load_sync()
                self._home._load_profile()
            event.ignore()

        self._main_window.closeEvent = _intercept_close

        # Masquer la statusbar
        sb = self._main_window.statusBar()
        if sb:
            sb.hide()

        self._stack.addWidget(self._main_window)
        self._stack.setCurrentWidget(self._main_window)

    def refresh_home(self):
        """Rafraîchir le dashboard après un retour de MainWindow."""
        if self._home:
            self._home._load_sync()
            self._home._load_profile()
