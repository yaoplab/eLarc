"""M3ScrollArea — wrapper phibuilder pour QScrollArea."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea
from phibuilder.theme import Theme


class M3ScrollArea(QScrollArea):
    def __init__(self, theme: Theme | None = None, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.setWidgetResizable(True)
        self._update_style()

    def _update_style(self):
        if self._theme is None:
            return
        c = self._theme.colors
        self.setStyleSheet(
            f"M3ScrollArea {{ background: {c.surface}; border: none; }}"
            f"M3ScrollArea::viewport {{ background: {c.surface}; }}"
        )


class AdaptiveScrollArea(M3ScrollArea):
    """Scrollbar verticale SEULEMENT si la hauteur < 768px (skill data-entry-ui).

    Zéro défilement visible dans le corps principal sur les grands écrans ;
    la barre s'active automatiquement sur les petits viewports (< 768px).
    """

    THRESHOLD = 768

    def __init__(self, theme: Theme | None = None, parent=None):
        super().__init__(theme, parent)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def resizeEvent(self, event):
        if event.size().height() < self.THRESHOLD:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        else:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        super().resizeEvent(event)
