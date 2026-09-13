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
            import warnings
            warnings.warn(
                f"{type(self).__name__} cree sans theme= -- aucun style applique. "
                f"Passer theme=theme_manager.phi_theme.",
                stacklevel=2,
            )
            return
        c = self._theme.colors
        self.setStyleSheet(
            f"M3StackedWidget {{ background: {c.surface}; }}"
        )
