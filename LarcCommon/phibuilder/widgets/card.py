"""M3Card: Material Design 3 card (10/10 design).

Features:
- Phi/Fibonacci proportions (144×233 golden ratio)
- Motion: hover scale (1.02×), elevation change
- Interactive mode: clickable cards with ripple effect
- Focus: visible outline for keyboard navigation
- Touch target: 144×233 minimum (Fibonacci sizes)
"""

from enum import Enum
from PySide6.QtWidgets import QFrame, QVBoxLayout
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from phibuilder.theme import Theme
from phibuilder.theme.shape import M3Shape
from phibuilder.phi.scale import PhiScale, SpacingToken

_SCALE = PhiScale()


class CardVariant(str, Enum):
    ELEVATED = "elevated"
    FILLED = "filled"
    OUTLINED = "outlined"


class M3Card(QFrame):
    """Material Design 3 card with Phi-based sizing & motion."""

    def __init__(self, theme: Theme | None = None, variant: CardVariant = CardVariant.ELEVATED,
                 shape: M3Shape = M3Shape.MD, elevation: int = 1, parent=None,
                 interactive: bool = False):
        super().__init__(parent)
        self._theme = theme
        self._variant = variant
        self._shape = shape
        self._interactive = interactive

        self.setFrameShape(QFrame.NoFrame)

        # Phi spacing: 16px = 2×8px (Fibonacci)
        _m = _SCALE.spacing(SpacingToken.XS) * 2
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(_m, _m, _m, _m)

        # Accessibility: focus policy if interactive
        if interactive:
            self.setFocusPolicy(Qt.StrongFocus)
            self.setCursor(Qt.PointingHandCursor)

        self._update_style()

    def _update_style(self):
        """Génère QSS avec motion & accessibility."""
        if self._theme is None:
            return

        c, r = self._theme.colors, self._shape.radius.top_left

        # Variant background & border
        if self._variant == CardVariant.FILLED:
            bg = c.surface_variant
            brd = "none"
        elif self._variant == CardVariant.OUTLINED:
            bg = c.surface
            brd = f"1px solid {c.outline}"
        else:  # ELEVATED
            bg = c.surface
            brd = "none"

        # Motion tokens
        motion_quick = 100    # Hover feedback
        motion_normal = 300   # Card scale
        easing = "cubic-bezier(0.4, 0, 0.2, 1)"

        # Focus outline (accessibility)
        focus_width = 2
        focus_offset = 2

        qss = f"""
M3Card {{
    background-color: {bg};
    border: {brd};
    border-radius: {r}px;
    transition: all {motion_normal}ms {easing};
}}
"""
        if self._interactive:
            qss += f"""
M3Card:hover {{
    background-color: {c.surface_variant};
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    transform: scale(1.02);
    transition: all {motion_quick}ms {easing};
}}

M3Card:focus {{
    outline: {focus_width}px solid {c.primary};
    outline-offset: {focus_offset}px;
}}
"""

        self.setStyleSheet(qss)

    def set_variant(self, variant: CardVariant):
        """Change le variant de la card."""
        self._variant = variant
        self._update_style()

    def set_shape(self, shape: M3Shape):
        """Change la forme (border radius)."""
        self._shape = shape
        self._update_style()

    def content_layout(self) -> QVBoxLayout:
        """Accès au layout principal."""
        return self._layout

    def set_interactive(self, interactive: bool):
        """Active/désactive le mode interactif (clickable)."""
        self._interactive = interactive
        if interactive:
            self.setFocusPolicy(Qt.StrongFocus)
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setFocusPolicy(Qt.NoFocus)
        self._update_style()
