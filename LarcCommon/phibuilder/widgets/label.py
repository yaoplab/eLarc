from PySide6.QtWidgets import QLabel
from phibuilder.theme import Theme
from phibuilder.theme.typo import TypeStyle

class M3Label(QLabel):
    def __init__(self, text: str = "", theme: Theme | None = None,
                 style: str = "body_medium", parent=None):
        super().__init__(text, parent)
        self._theme = theme; self._style_name = style
        self._update_style()
    def _update_style(self):
        if self._theme is None:
            return
        s: TypeStyle = getattr(self._theme.typo, self._style_name)
        self.setStyleSheet(f"M3Label {{ font-family: '{s.family}'; font-size: {s.size}px; font-weight: {s.weight}; letter-spacing: {s.letter_spacing}px; color: {self._theme.colors.on_surface}; }}")
    def set_style(self, name: str):
        self._style_name = name; self._update_style()

    def set_color(self, color: str):
        """Re-pose la QSS complète (typo M3 + couleur) — préserve la
        typographie contrairement à un setStyleSheet(f"color: ...")."""
        if self._theme is None:
            return
        s: TypeStyle = getattr(self._theme.typo, self._style_name)
        self.setStyleSheet(
            f"M3Label {{ font-family: '{s.family}'; font-size: {s.size}px; "
            f"font-weight: {s.weight}; letter-spacing: {s.letter_spacing}px; "
            f"color: {color}; }}")
