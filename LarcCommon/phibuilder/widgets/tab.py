"""M3TabWidget — wrapper phibuilder pour QTabWidget."""
from PySide6.QtWidgets import QTabWidget
from phibuilder.theme import Theme
from phibuilder.phi.scale import SpacingToken


class M3TabWidget(QTabWidget):
    def __init__(self, theme: Theme | None = None, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._update_style()

    def _update_style(self):
        if self._theme is None:
            return
        c, s = self._theme.colors, self._theme.spacing
        self.setStyleSheet(
            f"M3TabWidget::pane {{ border: 1px solid {c.outline}; "
            f"border-radius: {s.spacing(SpacingToken.XXS)}px; background: {c.surface}; }}"
            f"M3TabBar::tab {{ padding: {s.spacing(SpacingToken.XXS) + s.spacing(SpacingToken.XXS) // 2}px {s.spacing(SpacingToken.XS) * 2}px; font-size: {s.spacing(SpacingToken.XL) // 4}px; "  # 6 16 13px
            f"border: none; border-bottom: {s.spacing(SpacingToken.XXS) // 2}px solid transparent; "
            f"color: {c.on_surface}; }}"
            f"M3TabBar::tab:selected {{ color: {c.primary}; "
            f"border-bottom: {s.spacing(SpacingToken.XXS) // 2}px solid {c.primary}; font-weight: bold; }}"
        )
