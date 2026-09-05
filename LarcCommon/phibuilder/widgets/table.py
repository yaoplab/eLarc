from PySide6.QtWidgets import QTableWidget, QHeaderView, QSizePolicy, QAbstractItemView, QTableWidgetItem
from PySide6.QtCore import Qt
from phibuilder.theme import Theme
from phibuilder.phi.scale import SpacingToken

class M3TableWidget(QTableWidget):
    def __init__(self, rows: int = 0, columns: int = 0, theme: Theme | None = None, parent=None):
        super().__init__(rows, columns, parent)
        self._theme = theme
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        h = self.horizontalHeader()
        h.setStretchLastSection(True)
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setMinimumSectionSize(80)
        v = self.verticalHeader()
        v.setDefaultSectionSize(48)
        v.setVisible(False)
        self._update_style()
    def _update_style(self):
        if self._theme is None:
            return
        c, s, t = self._theme.colors, self._theme.spacing, self._theme.typo
        self.setStyleSheet(f"""
M3TableWidget {{ background-color: {c.surface}; border: 1px solid {c.outline}; border-radius: {s.spacing(SpacingToken.SM)}px;
  gridline-color: {c.outline_variant}; outline: none; font-family: '{t.family}';
  font-size: {t.body_medium.size}px; color: {c.on_surface}; }}
M3TableWidget::item {{ padding: {s.spacing(SpacingToken.MD)}px; border-bottom: 1px solid {c.outline_variant}; }}
M3TableWidget::item:selected {{ background-color: {c.primary_container}; color: {c.on_primary_container}; }}
M3TableWidget::item:hover {{ background-color: {c.surface_container_highest}; }}
""")
        self.horizontalHeader().setStyleSheet(f"""
QHeaderView::section {{ background-color: {c.surface}; color: {c.on_surface}; padding: {s.spacing(SpacingToken.MD)}px;
  border: none; border-bottom: 2px solid {c.outline}; font-family: '{t.family}';
  font-size: {t.label_large.size}px; font-weight: {t.label_large.weight}; }}
QHeaderView::section:hover {{ background-color: {c.surface_container_highest}; }}
""")
    def set_headers(self, headers: list[str]):
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
    def refresh(self):
        """Relit les couleurs du thème courant (restyle thème sans recréer
        le widget — les styles sont figés à la construction)."""
        self._update_style()
    def add_row(self, values: list[str]) -> int:
        row = self.rowCount()
        self.insertRow(row)
        for col, val in enumerate(values):
            self.setItem(row, col, QTableWidgetItem(str(val)))
        return row
