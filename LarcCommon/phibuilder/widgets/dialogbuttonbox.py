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
            return
        c = self._theme.colors
        self.setStyleSheet(
            f"M3DialogButtonBox {{ spacing: 8px; }}"
        )
