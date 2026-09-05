from typing import Optional
from phibuilder.phi.grid import PhiGrid
from phibuilder.phi.scale import SpacingToken, PhiScale

_qt_available = False
try:
    from PySide6.QtWidgets import QLayout, QBoxLayout, QHBoxLayout, QVBoxLayout, QGridLayout, QWidget, QSpacerItem
    from PySide6.QtCore import Qt, QMargins
    _qt_available = True
except ImportError:
    QLayout = QBoxLayout = QHBoxLayout = QVBoxLayout = QGridLayout = QWidget = QSpacerItem = object
    Qt = QMargins = object

class PhiLayout:
    def __init__(self, base_spacing: int = 4):
        self._scale = PhiScale(base_spacing)
        self._grid = PhiGrid(base_spacing=base_spacing)
    def hbox(self, parent: Optional[QWidget] = None) -> QHBoxLayout:
        return QHBoxLayout(parent)
    def vbox(self, parent: Optional[QWidget] = None) -> QVBoxLayout:
        return QVBoxLayout(parent)
    def set_contents_margins(self, layout: QLayout, token: SpacingToken) -> None:
        m = self._scale.spacing(token)
        layout.setContentsMargins(m, m, m, m)
    def set_spacing(self, layout: QBoxLayout, token: SpacingToken) -> None:
        layout.setSpacing(self._scale.spacing(token))
    def margins(self, token: SpacingToken) -> QMargins:
        m = self._scale.spacing(token)
        return QMargins(m, m, m, m)
    def add_stretch(self, layout: QBoxLayout, stretch: int = 1) -> None:
        layout.addStretch(stretch)
    def add_spacer(self, layout: QBoxLayout, token: SpacingToken) -> None:
        s = self._scale.spacing(token)
        layout.addSpacerItem(QSpacerItem(s, s))
    def add_with_margin(self, layout: QBoxLayout, widget: QWidget, token: SpacingToken) -> None:
        m = self._scale.spacing(token)
        layout.addWidget(widget)
        layout.setStretchFactor(widget, 0)

def is_qt_available() -> bool:
    return _qt_available
