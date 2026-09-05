from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy
from PySide6.QtCore import Qt, Signal
from phibuilder.theme import Theme
from phibuilder.phi.scale import PhiScale, SpacingToken
from phibuilder.widgets.button import M3Button, ButtonVariant

# Échelle phi partagée (base 4) pour les tailles indépendantes du thème
_SCALE = PhiScale()


class M3ChipBar(QFrame):
    """Barre de chips horizontale M3 — boutons de section filtrables."""

    current_changed = Signal(int)

    def __init__(self, items: list[str], theme: Theme | None = None, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._items = items
        self._buttons: list[M3Button] = []
        self._current = 0
        self._build()

    def _build(self):
        self.setObjectName("chip_bar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_SCALE.spacing(SpacingToken.XXS))  # 4px
        for i, label in enumerate(self._items):
            variant = ButtonVariant.FILLED if i == 0 else ButtonVariant.OUTLINED
            btn = M3Button(label, theme=self._theme, variant=variant)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked, idx=i: self.set_current(idx))
            layout.addWidget(btn)
            self._buttons.append(btn)
        layout.addStretch()

    def set_current(self, index: int):
        if index == self._current:
            return
        self._current = index
        for i, btn in enumerate(self._buttons):
            btn.set_variant(ButtonVariant.FILLED if i == index else ButtonVariant.OUTLINED)
        self.current_changed.emit(index)

    def current_index(self) -> int:
        return self._current
