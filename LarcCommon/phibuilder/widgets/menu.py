"""M3Menu — wrapper phibuilder pour QMenu."""
from PySide6.QtWidgets import QMenu
from phibuilder.theme import Theme
from phibuilder.phi.scale import SpacingToken


class M3Menu(QMenu):
    def __init__(self, title="", theme: Theme | None = None, parent=None):
        super().__init__(title, parent)
        self._theme = theme
        self._update_style()

    def _update_style(self):
        if self._theme is None:
            return
        c, s = self._theme.colors, self._theme.spacing
        self.setStyleSheet(
            f"M3Menu {{ background: {c.surface}; border: 1px solid {c.outline}; "
            f"border-radius: {s.spacing(SpacingToken.XXS)}px; padding: {s.spacing(SpacingToken.XXS)}px; }}"
            f"M3Menu::item {{ padding: {s.spacing(SpacingToken.XXS) + s.spacing(SpacingToken.XXS) // 2}px {s.spacing(SpacingToken.MD) + s.spacing(SpacingToken.XXS)}px; font-size: {s.spacing(SpacingToken.XL) // 4}px; "  # 6 24 13px
            f"color: {c.on_surface}; }}"
            f"M3Menu::item:selected {{ background: {c.primary_container}; "
            f"color: {c.on_primary_container}; }}"
            f"M3Menu::separator {{ height: 1px; background: {c.outline_variant}; "
            f"margin: {s.spacing(SpacingToken.XXS)}px {s.spacing(SpacingToken.XS)}px; }}"
        )
