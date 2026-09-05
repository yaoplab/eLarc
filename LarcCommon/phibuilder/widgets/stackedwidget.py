"""M3StackedWidget — wrapper phibuilder pour QStackedWidget."""
from PySide6.QtWidgets import QStackedWidget
from phibuilder.theme import Theme


class M3StackedWidget(QStackedWidget):
    def __init__(self, theme: Theme | None = None, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._update_style()

    def _update_style(self):
        if self._theme is None:
            return
        c = self._theme.colors
        self.setStyleSheet(
            f"M3StackedWidget {{ background: {c.surface}; }}"
        )
