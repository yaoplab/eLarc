"""M3GroupBox — wrapper phibuilder pour QGroupBox."""
from PySide6.QtWidgets import QGroupBox
from phibuilder.theme import Theme
from phibuilder.phi.scale import SpacingToken


class M3GroupBox(QGroupBox):
    def __init__(self, title="", theme: Theme | None = None, parent=None):
        super().__init__(title, parent)
        self._theme = theme
        self._update_style()

    def _update_style(self):
        if self._theme is None:
            return
        c, s = self._theme.colors, self._theme.spacing
        self.setStyleSheet(
            f"M3GroupBox {{ font-weight: bold; font-size: {s.spacing(SpacingToken.XL) // 4}px; "  # 13px — pas de token typo M3 exact
            f"border: 1px solid {c.outline_variant}; border-radius: {s.spacing(SpacingToken.XXS)}px; "
            f"margin-top: {s.spacing(SpacingToken.XS)}px; padding: {s.spacing(SpacingToken.SM)}px {s.spacing(SpacingToken.XS)}px {s.spacing(SpacingToken.XS)}px; color: {c.on_surface}; }}"
            f"M3GroupBox::title {{ subcontrol-origin: margin; "
            f"subcontrol-position: top left; padding: 0 {s.spacing(SpacingToken.XXS) + s.spacing(SpacingToken.XXS) // 2}px; color: {c.primary}; }}"
        )
