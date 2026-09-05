from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal
from phibuilder.theme import Theme
from phibuilder.phi.scale import PhiScale, SpacingToken
from phibuilder.widgets.button import M3Button, ButtonVariant

# Échelle phi partagée (base 4) pour les tailles indépendantes du thème
_SCALE = PhiScale()

class M3Dialog(QDialog):
    confirmed = Signal(); cancelled = Signal()
    def __init__(self, parent=None, title: str = "", message: str = "",
                 theme: Theme | None = None):
        super().__init__(parent)
        self._theme = theme
        self.setWindowTitle(title)
        self.setMinimumWidth(_SCALE.spacing(SpacingToken.MD) * 20)  # 400px
        self.setModal(True)
        if theme is None:
            return
        c, s = theme.colors, theme.spacing
        self.setStyleSheet(f"M3Dialog {{ background-color: {c.surface}; border-radius: {s.spacing(SpacingToken.LG)}px; }}")
        layout = QVBoxLayout(self)
        layout.setSpacing(s.spacing(SpacingToken.LG))
        layout.setContentsMargins(s.spacing(SpacingToken.LG), s.spacing(SpacingToken.XL), s.spacing(SpacingToken.LG), s.spacing(SpacingToken.MD))
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"font-size: {theme.typo.headline_small.size}px; font-weight: {theme.typo.headline_small.weight}; color: {c.on_surface};")
        layout.addWidget(self.title_label)
        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet(f"font-size: {theme.typo.body_medium.size}px; color: {c.on_surface_variant};")
        layout.addWidget(self.message_label)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = M3Button("Cancel", theme, ButtonVariant.TEXT)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        self.confirm_btn = M3Button("Confirm", theme)
        self.confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.confirm_btn)
        layout.addLayout(btn_layout)
    def accept(self) -> None:
        self.confirmed.emit(); super().accept()
    def reject(self) -> None:
        self.cancelled.emit(); super().reject()
