from PySide6.QtWidgets import QListWidget, QListWidgetItem, QSizePolicy, QAbstractItemView
from PySide6.QtCore import Qt
from phibuilder.theme import Theme
from phibuilder.phi.scale import SpacingToken

class ListItemType:
    SINGLE_LINE = 0; TWO_LINE = 1; THREE_LINE = 2

class M3ListWidget(QListWidget):
    def __init__(self, theme: Theme | None = None, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAlternatingRowColors(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._update_style()
    def _update_style(self):
        if self._theme is None:
            return
        c, s = self._theme.colors, self._theme.spacing
        self.setStyleSheet(f"""
M3ListWidget {{ background-color: {c.surface}; border: 1px solid {c.outline}; border-radius: {s.spacing(SpacingToken.SM)}px;
  outline: none; color: {c.on_surface}; font-family: '{self._theme.typo.family}';
  font-size: {self._theme.typo.body_medium.size}px; padding: {s.spacing(SpacingToken.XS)}px; }}
M3ListWidget::item {{ padding: {s.spacing(SpacingToken.MD)}px {s.spacing(SpacingToken.LG)}px;
  border-radius: {s.spacing(SpacingToken.SM)}px; min-height: {s.spacing(SpacingToken.XXL)}px; }}
M3ListWidget::item:selected {{ background-color: {c.primary_container}; color: {c.on_primary_container};
  border-radius: {s.spacing(SpacingToken.SM)}px; }}
M3ListWidget::item:hover {{ background-color: {c.surface_container_highest}; }}
""")
    def add_item(self, text: str, item_type: int = ListItemType.SINGLE_LINE,
                 subtitle: str = "", data: dict | None = None) -> QListWidgetItem:
        item = QListWidgetItem(text)
        if subtitle:
            item.setToolTip(subtitle)
        if data:
            for k, v in data.items():
                item.setData(Qt.UserRole + hash(k) % 1000, v)
        self.addItem(item)
        return item
