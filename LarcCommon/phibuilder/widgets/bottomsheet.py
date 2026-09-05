from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QPropertyAnimation, QRect, QEasingCurve
from phibuilder.theme import Theme
from phibuilder.phi.scale import SpacingToken

class M3BottomSheet(QFrame):
    def __init__(self, parent, theme: Theme, title: str = ""):
        super().__init__(parent)
        self._theme = theme
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.setDuration(300)
        self._visible = False
        self.setStyleSheet(f"M3BottomSheet {{ background-color: {theme.colors.surface}; border-top: 1px solid {theme.colors.outline}; border-radius: {theme.spacing.spacing(SpacingToken.LG)}px {theme.spacing.spacing(SpacingToken.LG)}px 0 0; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.spacing.spacing(SpacingToken.LG), theme.spacing.spacing(SpacingToken.MD),
                                  theme.spacing.spacing(SpacingToken.LG), theme.spacing.spacing(SpacingToken.LG))
        handle = QFrame()
        handle.setFixedSize(theme.spacing.spacing(SpacingToken.LG), theme.spacing.spacing(SpacingToken.XXS))  # 32×4
        handle.setStyleSheet(f"background-color: {theme.colors.outline}; border-radius: {theme.spacing.spacing(SpacingToken.XXS) // 2}px;")
        hl = QHBoxLayout(); hl.addStretch(); hl.addWidget(handle); hl.addStretch()
        layout.addLayout(hl)
        if title:
            self.title_label = QLabel(title)
            self.title_label.setStyleSheet(f"font-size: {theme.typo.title_large.size}px; font-weight: {theme.typo.title_large.weight}; color: {theme.colors.on_surface};")
            layout.addWidget(self.title_label)
        self.content_layout = QVBoxLayout()
        layout.addLayout(self.content_layout)
        pw = parent.width() if parent else 400
        ph = parent.height() if parent else 600
        self_h = 300
        self.setGeometry(0, ph, pw, self_h)
        self.show()
    def toggle(self):
        p = self.parent()
        if not p: return
        pw, ph = p.width(), p.height()
        self_h = 300
        start_y = ph if not self._visible else ph - self_h
        end_y = ph - self_h if not self._visible else ph
        self._anim.stop()
        self._anim.setStartValue(QRect(0, start_y, pw, self_h))
        self._anim.setEndValue(QRect(0, end_y, pw, self_h))
        self._anim.start()
        self._visible = not self._visible
