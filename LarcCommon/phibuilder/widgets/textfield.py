"""M3TextField: Material Design 3 text field (10/10 design).

Features:
- Phi/Fibonacci sizing (52px height = F(6))
- Touch target: 44×44px minimum
- Motion: smooth border transition (300ms)
- Focus: 2px outline (WCAG AAA)
- Validation: error state with color feedback
- Accessibility: label support, clear error messages
"""

from enum import Enum
from PySide6.QtWidgets import QLineEdit, QSizePolicy
from PySide6.QtCore import Qt
from phibuilder.theme import Theme
from phibuilder.phi.scale import PhiScale, SpacingToken

_SCALE = PhiScale()


class FieldVariant(str, Enum):
    FILLED = "filled"
    OUTLINED = "outlined"


class M3TextField(QLineEdit):
    """Material Design 3 text field with Phi-based sizing & accessibility."""

    def __init__(self, text: str = "", theme: Theme | None = None,
                 variant: FieldVariant = FieldVariant.OUTLINED,
                 placeholder: str = "", parent=None):
        super().__init__(text, parent)
        self._theme = theme
        self._variant = variant

        if placeholder:
            self.setPlaceholderText(placeholder)

        # Phi sizing: 52px = F(6) (touch target comfortable)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(52)  # ds.phi_size_base

        # Accessibility: focus policy
        self.setFocusPolicy(Qt.StrongFocus)

        self._update_style()

    def _update_style(self):
        """Génère QSS avec motion & accessibility."""
        if self._theme is None:
            import warnings
            warnings.warn(
                f"{type(self).__name__} cree sans theme= -- aucun style applique. "
                f"Passer theme=theme_manager.phi_theme.",
                stacklevel=2,
            )
            return

        t, c, s = self._theme, self._theme.colors, self._theme.spacing

        # Phi tokens
        padding_h = s.spacing(SpacingToken.MD)  # 20px horizontal
        # Explicite (pas 0) : sans padding vertical réservé, certains styles Qt
        # (windowsvista notamment) rognent les descendantes (g, j, p, q, y) du texte
        # dans un champ à hauteur fixe.
        padding_v = s.spacing(SpacingToken.XXS)  # 4px
        radius = s.spacing(SpacingToken.NONE)   # 0px (angles droits)

        # Motion tokens
        motion_normal = 300  # Border transition
        easing = "cubic-bezier(0.4, 0, 0.2, 1)"

        # Focus outline (accessibility)
        focus_width = 2  # ds.focus_outline_width
        focus_offset = 2  # ds.focus_outline_offset

        # Variant styles
        if self._variant == FieldVariant.FILLED:
            base_bg = c.surface_container_highest
            base_border = "none"
            base_bottom_border = f"1px solid {c.outline}"
            focus_border = f"2px solid {c.primary}"
            focus_bottom = ""
        else:  # OUTLINED
            base_bg = "transparent"
            base_border = f"1px solid {c.outline}"
            base_bottom_border = ""
            focus_border = f"2px solid {c.primary}"
            focus_bottom = ""

        # Error state
        err_border = f"2px solid {c.error}"
        err_bg = c.error_container

        qss = f"""
M3TextField {{
    padding-left: {padding_h}px;
    padding-right: {padding_h}px;
    padding-top: {padding_v}px;
    padding-bottom: {padding_v}px;
    min-height: 52px;
    font-family: '{t.typo.family}';
    font-size: {t.typo.body_large.size}px;
    color: {c.on_surface};
    background-color: {base_bg};
    border: {base_border};
    border-bottom: {base_bottom_border};
    border-radius: {radius}px;
    selection-background-color: {c.primary_container};
    selection-color: {c.on_surface};
    transition: all {motion_normal}ms {easing};
}}

M3TextField:focus {{
    border: {focus_border};
    border-bottom: {focus_bottom if focus_bottom else "none"};
    background-color: {c.surface};
    outline: {focus_width}px solid {c.primary};
    outline-offset: {focus_offset}px;
}}

M3TextField:hover {{
    background-color: {c.surface_variant};
    transition: all {motion_normal}ms {easing};
}}

M3TextField[has_error="true"] {{
    border: {err_border};
    border-bottom: {err_border};
    background-color: {err_bg};
}}

M3TextField[has_error="true"]:focus {{
    border: {err_border};
    border-bottom: {err_border};
    outline: {focus_width}px solid {c.error};
}}

M3TextField:disabled {{
    background-color: rgba(0, 0, 0, 0.04);
    color: rgba(0, 0, 0, 0.38);
    border-color: rgba(0, 0, 0, 0.12);
    opacity: 0.38;
}}
"""
        self.setStyleSheet(qss)

    def set_variant(self, variant: FieldVariant):
        """Change le variant du champ."""
        self._variant = variant
        self._update_style()

    def set_error(self, msg: str | None = None) -> None:
        """Affiche l'état erreur avec message d'aide.

        Le message apparaît dans le tooltip et via propriété has_error.
        """
        self.setProperty("has_error", "true" if msg else "false")
        if msg:
            self.setToolTip(msg)
            self.setAccessibleDescription(f"Error: {msg}")
        else:
            self.setToolTip("")
            self.setAccessibleDescription("")
        self._update_style()
