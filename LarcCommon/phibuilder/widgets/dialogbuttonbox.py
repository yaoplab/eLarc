"""M3DialogButtonBox — wrapper phibuilder pour QDialogButtonBox."""
from PySide6.QtWidgets import QDialogButtonBox
from phibuilder.theme import Theme


class M3DialogButtonBox(QDialogButtonBox):
    def __init__(self, buttons, theme: Theme | None = None, parent=None):
        super().__init__(buttons, parent)
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
            f"M3DialogButtonBox {{ spacing: 8px; }}"
        )
