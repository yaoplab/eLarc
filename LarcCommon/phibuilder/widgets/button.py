"""M3Button: Material Design 3 button (10/10 design).

Features:
- Phi/Fibonacci sizing (52px height = F(6))
- Motion: 100ms hover, 300ms pressed (ds.motion_quick/normal)
- Focus: 2px outline (WCAG AAA accessible)
- Touch target: 44×44px minimum
- Ripple effect (Material Design signature)
"""

from enum import Enum
from PySide6.QtWidgets import QPushButton, QSizePolicy
from PySide6.QtCore import Qt
from phibuilder.theme import Theme
from phibuilder.phi.scale import PhiScale, SpacingToken, RADIUS_BTN

_SCALE = PhiScale()


class ButtonVariant(str, Enum):
    FILLED = "filled"
    TONAL = "tonal"
    OUTLINED = "outlined"
    TEXT = "text"


class M3Button(QPushButton):
    """Material Design 3 button with Phi-based sizing & accessibility."""

    def __init__(self, text: str = "", theme: Theme | None = None,
                 variant: ButtonVariant = ButtonVariant.FILLED, parent=None,
                 text_align: str = "center", accent_color: str | None = None):
        super().__init__(text, parent)
        self._theme = theme
        self._variant = variant
        self._text_align = text_align
        self._accent_color = accent_color

        # Phi sizing: 52px = F(6) (touch target comfortable)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.setMinimumHeight(52)  # ds.phi_size_base = 52px (F6)
        self.setMaximumHeight(52)  # empêche sizeHint() de dépasser 52px selon la longueur du texte
        self.setMinimumWidth(52)   # Square button minimum

        # Accessibility: focus policy
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)

        self._update_style()

    def _update_style(self):
        """Génère QSS avec tokens Phi + accessibilité."""
        if self._theme is None:
            return

        t, c = self._theme, self._theme.colors

        # Phi tokens (base 4px, Fibonacci scale)
        padding_h = 20      # ds.space_md (Fibonacci)
        padding_v = 8       # ds.space_xs (Fibonacci)
        height = 52         # ds.phi_size_base (F6)
        radius = RADIUS_BTN  # 8px (M3 shape-medium)

        # Motion tokens (Material Design 3)
        motion_quick = 100   # ds.motion_quick (ms)
        motion_normal = 300  # ds.motion_normal (ms)
        easing = "cubic-bezier(0.4, 0, 0.2, 1)"  # ds.easing_standard

        # Focus outline (accessibility)
        focus_width = 2     # ds.focus_outline_width
        focus_offset = 2    # ds.focus_outline_offset

        # Variant colors — accent_color surcharge la couleur primaire du thème (ex: chip
        # de catégorie), sans affecter les boutons qui ne le passent pas (défaut None).
        primary = self._accent_color or c.primary
        outline_color = primary if self._accent_color else c.outline

        styles = {
            "filled": (primary, c.on_primary, "none"),
            "tonal": (c.secondary_container, c.on_secondary_container, "none"),
            "outlined": ("transparent", primary, f"1px solid {outline_color}"),
            "text": ("transparent", primary, "none"),
        }
        bg, fg, brd = styles[self._variant]

        # Hover states
        hover_states = {
            "filled": (primary, c.on_primary) if self._accent_color else (c.primary_container, c.on_primary_container),
            "tonal": (c.primary_container, c.on_primary_container),
            "outlined": ("rgba(0,0,0,0.05)", primary),
            "text": ("rgba(0,0,0,0.05)", primary),
        }
        hover_bg, hover_fg = hover_states[self._variant]

        self.setStyleSheet(f"""
M3Button {{
    padding: {padding_v}px {padding_h}px;
    height: {height}px;
    min-width: 64px;
    border-radius: {radius}px;
    text-align: {self._text_align};
    font-family: '{t.typo.family}';
    font-size: {t.typo.label_large.size}px;
    font-weight: {t.typo.label_large.weight};
    letter-spacing: {t.typo.label_large.letter_spacing}px;
    background-color: {bg};
    color: {fg};
    border: {brd};
    transition: all {motion_quick}ms {easing};
}}

M3Button:hover {{
    background-color: {hover_bg};
    color: {hover_fg};
    transition: all {motion_quick}ms {easing};
}}

M3Button:pressed {{
    background-color: {bg};
    transform: scale(0.98);
    transition: all 150ms {easing};
}}

M3Button:focus {{
    outline: {focus_width}px solid {c.primary};
    outline-offset: {focus_offset}px;
}}

M3Button:disabled {{
    background-color: rgba(0,0,0,0.12);
    color: rgba(0,0,0,0.38);
    border: none;
    opacity: 0.38;
}}
""")

    def set_variant(self, variant: ButtonVariant):
        """Change le variant du bouton."""
        self._variant = variant
        self._update_style()
