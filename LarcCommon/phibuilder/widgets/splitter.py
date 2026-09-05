"""M3Splitter — wrapper phibuilder pour QSplitter."""
from PySide6.QtWidgets import QSplitter
from phibuilder.theme import Theme


class M3Splitter(QSplitter):
    def __init__(self, orientation, theme: Theme | None = None, parent=None):
        super().__init__(orientation, parent)
        self._theme = theme
        self._update_style()

    def _update_style(self):
        if self._theme is None:
            return
        c = self._theme.colors
        self.setStyleSheet(
            f"M3Splitter::handle {{ background: {c.outline_variant}; }}"
            f"M3Splitter::handle:horizontal {{ width: 2px; }}"
            f"M3Splitter::handle:vertical {{ height: 2px; }}"
            f"M3Splitter::handle:hover {{ background: {c.primary}; }}"
        )
