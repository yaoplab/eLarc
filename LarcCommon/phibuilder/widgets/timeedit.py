"""M3TimeEdit — wrapper phibuilder pour QTimeEdit."""
from PySide6.QtWidgets import QTimeEdit
from PySide6.QtCore import QTime
from phibuilder.theme import Theme
from phibuilder.phi.scale import SpacingToken


class M3TimeEdit(QTimeEdit):
    def __init__(self, time=None, theme: Theme | None = None, parent=None):
        super().__init__(time or QTime.currentTime(), parent)
        self._theme = theme
        self.setDisplayFormat("HH:mm")
        self._update_style()

    def _update_style(self):
        if self._theme is None:
            return
        c, s = self._theme.colors, self._theme.spacing
        self.setStyleSheet(
            f"M3TimeEdit {{ padding: {s.spacing(SpacingToken.XS)}px; border: 1px solid {c.outline_variant}; "
            f"border-radius: {s.spacing(SpacingToken.XXS)}px; font-size: {s.spacing(SpacingToken.XL) // 4}px; "  # 13px — pas de token typo M3 exact
            f"background: {c.surface}; color: {c.on_surface}; font-weight: bold; }}"
        )
