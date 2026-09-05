from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from phibuilder.theme import Theme
from phibuilder.phi.scale import SpacingToken

class M3NavigationBar(QFrame):
    current_changed = Signal(int)
    def __init__(self, items: list[dict], theme: Theme | None = None, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._items = items
        self._buttons: list[QPushButton] = []
        self._current_index = 0
        c = theme.colors
        self.setStyleSheet(f"M3NavigationBar {{ background-color: {c.surface}; border-top: 1px solid {c.outline}; }}")
        self.setFixedHeight(theme.spacing.spacing(SpacingToken.MD) * 4)  # 80px
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for i, item in enumerate(items):
            btn = QPushButton(item.get("label", ""))
            btn.setProperty("nav_index", i)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self._select(idx))
            self._buttons.append(btn)
            layout.addWidget(btn)
        self._update_style()
    def _update_style(self):
        if self._theme is None:
            return
        c, t, s = self._theme.colors, self._theme.typo, self._theme.spacing
        for i, btn in enumerate(self._buttons):
            is_active = i == self._current_index
            bg, fg = (c.primary_container, c.on_primary_container) if is_active else ("transparent", c.on_surface_variant)
            btn.setStyleSheet(f"""
QPushButton {{ background: {bg}; color: {fg}; border: none; border-radius: {s.spacing(SpacingToken.SM)}px;
  font-family: '{t.family}'; font-size: {t.label_medium.size}px; font-weight: {"700" if is_active else "500"}; }}
QPushButton:hover {{ background: {c.primary_container}; color: {c.on_primary_container}; }}
""")
    def _select(self, index: int):
        self._current_index = index
        self._update_style()
        self.current_changed.emit(index)
    def set_current(self, index: int):
        self._select(index)

class M3Sidebar(QFrame):
    current_changed = Signal(int)
    def __init__(self, items: list[dict], theme: Theme | None = None, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._items = items
        self._current_index = 0
        c = theme.colors
        self.setStyleSheet(f"M3Sidebar {{ background-color: {c.surface}; border-right: 1px solid {c.outline}; }}")
        self.setFixedWidth(theme.spacing.spacing(SpacingToken.XXXL) * 2 + theme.spacing.spacing(SpacingToken.XS))  # 280px
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.spacing.spacing(SpacingToken.SM), theme.spacing.spacing(SpacingToken.SM),
                                  theme.spacing.spacing(SpacingToken.SM), theme.spacing.spacing(SpacingToken.SM))  # 12px
        layout.setSpacing(theme.spacing.spacing(SpacingToken.XXS))  # 4px
        header = QLabel(items[0].get("header", "")) if items and "header" in items[0] else None
        if header:
            header.setStyleSheet(
                f"font-size: {theme.typo.title_small.size}px; color: {c.primary}; "
                f"padding: {theme.spacing.spacing(SpacingToken.XS) * 2}px {theme.spacing.spacing(SpacingToken.SM)}px {theme.spacing.spacing(SpacingToken.XS)}px;"  # 16 12 8
            )
            layout.addWidget(header)
        start = 1 if header else 0
        self._buttons: list[QPushButton] = []
        for i, item in enumerate(items[start:], start):
            btn = QPushButton(item.get("label", ""))
            btn.setProperty("sidebar_index", i)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setMinimumHeight(theme.spacing.spacing(SpacingToken.MD) * 2)  # 40px
            btn.clicked.connect(lambda checked, idx=i: self._select(idx))
            self._buttons.append(btn)
            layout.addWidget(btn)
        layout.addStretch()
        self._update_style()
    def _update_style(self):
        if self._theme is None:
            return
        c, t, s = self._theme.colors, self._theme.typo, self._theme.spacing
        for i, btn in enumerate(self._buttons):
            is_active = i == self._current_index
            bg, fg = (c.secondary_container, c.on_secondary_container) if is_active else ("transparent", c.on_surface)
            btn.setStyleSheet(f"""
QPushButton {{ background: {bg}; color: {fg}; border: none; border-radius: {s.spacing(SpacingToken.SM)}px;
  text-align: left; padding: 0 {s.spacing(SpacingToken.LG)}px;
  font-family: '{t.family}'; font-size: {t.label_large.size}px; font-weight: {"700" if is_active else "500"}; }}
QPushButton:hover {{ background: {c.surface_container_highest}; }}
""")
    def _select(self, index: int):
        self._current_index = index
        self._update_style()
        self.current_changed.emit(index)
    def set_current(self, index: int):
        self._select(index)
