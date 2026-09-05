from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QEasingCurve
from phibuilder.theme import Theme
from phibuilder.phi.scale import SpacingToken
from larccommon.safe_slot import safe_slot

class M3Snackbar(QFrame):
    _instance = None
    def __init__(self, parent, theme: Theme):
        super().__init__(parent)
        self._theme = theme
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._hide)
        c, s = theme.colors, theme.spacing
        self.setStyleSheet(f"""
M3Snackbar {{ background-color: {c.inverse_surface}; color: {c.inverse_on_surface};
  border-radius: {s.spacing(SpacingToken.XS)}px; padding: 0 {s.spacing(SpacingToken.LG)}px; }}
""")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(s.spacing(SpacingToken.LG), s.spacing(SpacingToken.SM),
                                        s.spacing(SpacingToken.LG), s.spacing(SpacingToken.SM))
        self._label = QLabel()
        self._label.setStyleSheet(f"font-size: {theme.typo.body_medium.size}px; color: {c.inverse_on_surface};")
        self._layout.addWidget(self._label)
        self.hide()
    @classmethod
    def show(cls, parent, message: str, theme: Theme, duration: int = 3000):
        if cls._instance is None:
            cls._instance = M3Snackbar(parent, theme)
        inst = cls._instance
        inst._label.setText(message)
        inst.setFixedHeight(theme.spacing.spacing(SpacingToken.XL) - theme.spacing.spacing(SpacingToken.XXS))  # 48px
        pw = parent.width() if parent else 400
        inst.setFixedWidth(min(int(pw * 0.618), 600))
        px = (pw - inst.width()) // 2
        ph = parent.height() if parent else 400
        inst.setGeometry(px, ph - theme.spacing.spacing(SpacingToken.MD) * 4, inst.width(),
                         theme.spacing.spacing(SpacingToken.XL) - theme.spacing.spacing(SpacingToken.XXS))  # 80, 48
        inst.show()
        QTimer.singleShot(30, lambda: inst._animate_in())
        inst._timer.stop()
        inst._timer.start(duration)
    def _animate_in(self):
        self.raise_()
    @safe_slot("M3Snackbar._hide")
    def _hide(self):
        self.hide()
    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            pw, ph = self.parent().width(), self.parent().height()
            w = min(int(pw * 0.618), 600)
            self.setFixedWidth(w)
            self.move((pw - w) // 2, ph - 80)
