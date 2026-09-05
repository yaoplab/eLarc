"""M3HeaderView — wrapper phibuilder pour QHeaderView."""
from PySide6.QtWidgets import QHeaderView
from phibuilder.theme import Theme
from phibuilder.phi.scale import SpacingToken


class M3HeaderView(QHeaderView):
    def __init__(self, orientation, theme: Theme | None = None, parent=None):
        super().__init__(orientation, parent)
        self._theme = theme
        self._update_style()

    def _update_style(self):
        if self._theme is None:
            return
        c, s = self._theme.colors, self._theme.spacing
        self.setStyleSheet(
            f"M3HeaderView::section {{ background: {c.surface_variant}; "
            f"color: {c.on_surface}; padding: {s.spacing(SpacingToken.XXS) + s.spacing(SpacingToken.XXS) // 2}px {s.spacing(SpacingToken.XS)}px; border: none; "
            f"border-bottom: 1px solid {c.outline_variant}; "
            f"font-weight: bold; font-size: {self._theme.typo.label_medium.size}px; }}"  # 12px
        )
