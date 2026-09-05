from enum import Enum
from PySide6.QtWidgets import QPushButton, QSizePolicy
from PySide6.QtCore import Qt
from phibuilder.theme import Theme
from phibuilder.phi.scale import PhiScale, SpacingToken, RADIUS_BTN

# Échelle phi partagée (base 4) pour les tailles indépendantes du thème
_SCALE = PhiScale()

class ButtonVariant(str, Enum):
    FILLED = "filled"; TONAL = "tonal"; OUTLINED = "outlined"; TEXT = "text"

class M3Button(QPushButton):
    def __init__(self, text: str = "", theme: Theme | None = None,
                 variant: ButtonVariant = ButtonVariant.FILLED, parent=None,
                 text_align: str = "center"):
        super().__init__(text, parent)
        self._theme = theme
        self._variant = variant
        # K26 (sidebar-spec) : "left" pour les boutons icône+texte — sans quoi
        # Qt centre le groupe icône+texte et l'icône dérive selon la longueur
        # du libellé. Gap icône↔texte natif Qt = ds.space_xs (8px).
        self._text_align = text_align
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.setMinimumHeight(_SCALE.spacing(SpacingToken.MD) * 2)  # 40px
        self.setCursor(Qt.PointingHandCursor)
        self._update_style()
    def _update_style(self):
        if self._theme is None:
            return
        t, c = self._theme, self._theme.colors
        # Radius boutons = F₅ (skill data-entry-ui)
        p, h, r = t.spacing.spacing(SpacingToken.MD), t.spacing.spacing(SpacingToken.MD) * 2, RADIUS_BTN  # p=20, h=40, r=5
        styles = {
            "filled":  (c.primary, c.on_primary, "none"),
            "tonal":   (c.secondary_container, c.on_secondary_container, "none"),
            "outlined":("transparent", c.primary, f"1px solid {c.outline}"),
            "text":    ("transparent", c.primary, "none"),
        }
        bg, fg, brd = styles[self._variant]
        hov_bg, hov_fg = {"filled": (c.primary_container, c.on_primary_container),
            "tonal": (c.primary_container, c.on_primary_container),
            "outlined": ("rgba(0,0,0,0.05)", c.primary),
            "text": ("rgba(0,0,0,0.05)", c.primary)}[self._variant]
        self.setStyleSheet(f"""
M3Button {{ padding: 0 {p}px; height: {h}px; border-radius: {r}px;
  text-align: {self._text_align};
  font-family: '{t.typo.family}'; font-size: {t.typo.label_large.size}px;
  font-weight: {t.typo.label_large.weight}; letter-spacing: {t.typo.label_large.letter_spacing}px;
  background-color: {bg}; color: {fg}; border: {brd}; }}
M3Button:hover {{ background-color: {hov_bg}; color: {hov_fg}; }}
M3Button:pressed {{ background-color: {bg}; }}
M3Button:disabled {{ background-color: rgba(0,0,0,0.12); color: rgba(0,0,0,0.38); border: none; }}
""")
    def set_variant(self, variant: ButtonVariant):
        self._variant = variant; self._update_style()
