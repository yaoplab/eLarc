from enum import Enum
from PySide6.QtWidgets import QLineEdit, QSizePolicy
from phibuilder.theme import Theme
from phibuilder.phi.scale import PhiScale, SpacingToken

# Échelle phi partagée (base 4) pour les tailles indépendantes du thème
_SCALE = PhiScale()

class FieldVariant(str, Enum):
    FILLED = "filled"; OUTLINED = "outlined"

class M3TextField(QLineEdit):
    def __init__(self, text: str = "", theme: Theme | None = None,
                 variant: FieldVariant = FieldVariant.OUTLINED,
                 placeholder: str = "", parent=None):
        super().__init__(text, parent)
        self._theme = theme; self._variant = variant
        if placeholder:
            self.setPlaceholderText(placeholder)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(_SCALE.spacing(SpacingToken.XL) + _SCALE.spacing(SpacingToken.XXS))  # 56px = 52+4
        self._update_style()
    def _update_style(self):
        if self._theme is None:
            return
        t, c, s = self._theme, self._theme.colors, self._theme.spacing
        # Angles droits sur les champs (skill data-entry-ui)
        p, r = s.spacing(SpacingToken.MD), s.spacing(SpacingToken.NONE)
        if self._variant == FieldVariant.FILLED:
            base = f"background-color: {c.surface_container_highest}; border: none; border-bottom: 1px solid {c.outline}; border-radius: {r}px {r}px 0 0;"
            focus = f"border-bottom: 2px solid {c.primary};"
        else:
            base = f"background-color: transparent; border: 1px solid {c.outline}; border-radius: {r}px;"
            focus = f"border: 2px solid {c.primary};"
        err = (f'M3TextField[has_error="true"], '
               f'M3TextField[has_error="true"]:focus '
               f'{{ border: 2px solid {c.error}; }}')
        self.setStyleSheet(f"""
M3TextField {{ padding: 0 {p}px; font-family: '{t.typo.family}'; font-size: {t.typo.body_large.size}px;
  color: {c.on_surface}; selection-background-color: {c.primary_container};
  selection-color: {c.on_surface}; {base} }}
M3TextField:focus {{ {focus} background-color: {c.surface}; }}
M3TextField:disabled {{ background-color: rgba(0,0,0,0.04); color: rgba(0,0,0,0.38); border-color: rgba(0,0,0,0.12); }}
{err}
""")
    def set_variant(self, variant: FieldVariant):
        self._variant = variant; self._update_style()

    def set_error(self, msg: str | None = None) -> None:
        """Validation in-line (skill data-entry-ui) : bordure erreur + has_error.

        Le message d'erreur s'affiche via un QLabel#errorMessage sous le champ
        (pattern form-pattern ; le champ porte la propriété has_error="true").
        """
        self.setProperty("has_error", "true" if msg else "false")
        self.setToolTip(msg or "")
        self._update_style()
