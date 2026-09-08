"""M3Frame — wrapper phibuilder pour QFrame."""
from PySide6.QtWidgets import QFrame
from phibuilder.theme import Theme
from phibuilder.phi.scale import SpacingToken


class M3Frame(QFrame):
    def __init__(self, theme: Theme | None = None, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._update_style()

    def _update_style(self):
        if self._theme is None:
            import warnings
            warnings.warn(
                f"{type(self).__name__} cree sans theme= -- aucun style applique. "
                f"Passer theme=theme_manager.phi_theme.",
                stacklevel=2,
            )
            return
        c, s = self._theme.colors, self._theme.spacing
        self.setStyleSheet(
            f"M3Frame {{ background: {c.surface}; "
            f"border: 1px solid {c.outline_variant}; "
            f"border-radius: {s.spacing(SpacingToken.XXS)}px; }}"
        )
