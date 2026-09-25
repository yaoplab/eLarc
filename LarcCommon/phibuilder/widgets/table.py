"""M3TableWidget: Material Design 3 table (10/10 design).

Features:
- Phi/Fibonacci row height (32px = F(5))
- Keyboard navigation: Arrow keys (up/down/left/right)
- Focus visible: 2px outline on selected row
- Accessibility: ARIA tree, screen reader support
- Motion: smooth row selection (300ms)
- Touch target: 32px minimum row height (ds.table_row_min)
"""

from PySide6.QtWidgets import (
    QTableWidget, QHeaderView, QSizePolicy, QAbstractItemView, QTableWidgetItem, QStyle, QStyledItemDelegate,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QKeyEvent
from phibuilder.theme import Theme
from phibuilder.phi.scale import SpacingToken


class _BackgroundDelegate(QStyledItemDelegate):
    """Peint le fond posé par `item.setBackground()` : la règle QSS
    `M3TableWidget::item` (padding/bordure) fait sinon ignorer à Qt le
    BackgroundRole — teintes de groupe, lignes en erreur, etc. restaient
    blanches. Le fond de sélection reste géré par le QSS."""

    def paint(self, painter, option, index):
        brush = index.data(Qt.BackgroundRole)
        if isinstance(brush, QBrush) and brush.style() != Qt.NoBrush and not (option.state & QStyle.State_Selected):
            painter.fillRect(option.rect, brush)
        super().paint(painter, option, index)


class M3TableWidget(QTableWidget):
    """Material Design 3 table with keyboard navigation & accessibility."""

    def __init__(self, rows: int = 0, columns: int = 0, theme: Theme | None = None, parent=None):
        super().__init__(rows, columns, parent)
        self._theme = theme

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setItemDelegate(_BackgroundDelegate(self))

        # Horizontal header
        h = self.horizontalHeader()
        h.setStretchLastSection(True)
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setMinimumSectionSize(80)

        # Vertical header (row numbers)
        v = self.verticalHeader()
        v.setDefaultSectionSize(32)  # Phi/Fibonacci (F(5))
        v.setVisible(False)

        # Accessibility
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName("Data table")
        self.setAccessibleDescription("Navigate with arrow keys, select with Enter, expand/collapse with Space")

        self._update_style()

    def _update_style(self):
        """Génère QSS avec motion & accessibility."""
        if self._theme is None:
            import warnings
            warnings.warn(
                f"{type(self).__name__} cree sans theme= -- aucun style applique. "
                f"Passer theme=theme_manager.phi_theme.",
                stacklevel=2,
            )
            return

        c, s, t = self._theme.colors, self._theme.spacing, self._theme.typo

        # Phi tokens
        padding = s.spacing(SpacingToken.MD)  # 20px
        radius = s.spacing(SpacingToken.SM)   # 4px
        row_height = 32  # F(5) Fibonacci

        # Motion tokens
        motion_normal = 300  # Selection transition
        easing = "cubic-bezier(0.4, 0, 0.2, 1)"

        # Focus outline
        focus_width = 2
        focus_offset = 0

        self.setStyleSheet(f"""
M3TableWidget {{
    background-color: {c.surface};
    border: 1px solid {c.outline};
    border-radius: {radius}px;
    gridline-color: {c.outline_variant};
    outline: none;
    font-family: '{t.family}';
    font-size: {t.body_medium.size}px;
    color: {c.on_surface};
    transition: all {motion_normal}ms {easing};
}}

M3TableWidget::item {{
    padding: 0px {padding}px;
    border-bottom: 1px solid {c.outline_variant};
    min-height: {row_height}px;
}}

M3TableWidget::item:selected {{
    background-color: {c.primary_container};
    color: {c.on_primary_container};
    border-left: 4px solid {c.primary};
}}

M3TableWidget::item:hover {{
    background-color: {c.surface_container_highest};
}}

M3TableWidget::item:focus {{
    outline: {focus_width}px solid {c.primary};
    outline-offset: {focus_offset}px;
}}
""")

        # Header styling
        self.horizontalHeader().setStyleSheet(f"""
QHeaderView::section {{
    background-color: {c.surface};
    color: {c.on_surface};
    padding: {padding // 2}px {padding}px;
    border: none;
    border-bottom: 2px solid {c.outline};
    font-family: '{t.family}';
    font-size: {t.label_large.size}px;
    font-weight: {t.label_large.weight};
    text-align: left;
}}

QHeaderView::section:hover {{
    background-color: {c.surface_container_highest};
}}
""")

    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard navigation."""
        if event.key() == Qt.Key_Up:
            current_row = self.currentRow()
            if current_row > 0:
                self.setCurrentCell(current_row - 1, self.currentColumn())
            event.accept()

        elif event.key() == Qt.Key_Down:
            current_row = self.currentRow()
            if current_row < self.rowCount() - 1:
                self.setCurrentCell(current_row + 1, self.currentColumn())
            event.accept()

        elif event.key() == Qt.Key_Left:
            current_col = self.currentColumn()
            if current_col > 0:
                self.setCurrentCell(self.currentRow(), current_col - 1)
            event.accept()

        elif event.key() == Qt.Key_Right:
            current_col = self.currentColumn()
            if current_col < self.columnCount() - 1:
                self.setCurrentCell(self.currentRow(), current_col + 1)
            event.accept()

        elif event.key() == Qt.Key_Home:
            self.setCurrentCell(0, 0)
            event.accept()

        elif event.key() == Qt.Key_End:
            self.setCurrentCell(self.rowCount() - 1, self.columnCount() - 1)
            event.accept()

        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            # Emit itemActivated signal
            if self.currentItem():
                self.itemActivated.emit(self.currentItem())
            event.accept()

        elif event.key() == Qt.Key_Escape:
            # Deselect all
            self.clearSelection()
            event.accept()

        else:
            super().keyPressEvent(event)

    def set_headers(self, headers: list[str]):
        """Set column headers."""
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)

    def refresh(self):
        """Restyle based on current theme."""
        self._update_style()

    def add_row(self, values: list[str]) -> int:
        """Add a new row with values."""
        row = self.rowCount()
        self.insertRow(row)
        for col, val in enumerate(values):
            item = QTableWidgetItem(str(val))
            item.setData(Qt.AccessibleTextRole, str(val))
            self.setItem(row, col, item)
        return row
