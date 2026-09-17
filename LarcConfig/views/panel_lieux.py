"""Panel Lieux."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHeaderView, QTableWidgetItem
from phibuilder.widgets import M3Label, M3TableWidget, M3ScrollArea
from phibuilder.phi.scale import SpacingToken
from larccommon.theme import theme_manager
from LarcConfig.common.db_access import get_locations


class LieuxPanel(M3ScrollArea):
    def __init__(self, user: dict):
        super().__init__(theme=theme_manager.phi_theme)
        phi = theme_manager.phi_theme
        sp = phi.spacing.spacing

        container = QWidget()
        l = QVBoxLayout(container)
        l.setContentsMargins(sp(SpacingToken.LG), sp(SpacingToken.LG),
                             sp(SpacingToken.LG), sp(SpacingToken.LG))
        l.setSpacing(sp(SpacingToken.MD))
        l.addWidget(M3Label("Lieux", theme=phi, style="headline_small"))

        table = M3TableWidget(theme=phi)
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["ID", "Lieu", "Langue"])
        h = table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        table.setAlternatingRowColors(False)

        def _ro(text: str) -> QTableWidgetItem:
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            return item

        rows = get_locations()
        table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            table.setItem(i, 0, _ro(str(r['id'])))
            table.setItem(i, 1, _ro(r.get('nom', '') or ''))
            langue = {1: 'EN', 2: 'FR'}.get(r.get('langue'), str(r.get('langue', '')))
            table.setItem(i, 2, _ro(langue))

        l.addWidget(table)
        self.setWidget(container)
        self.setWidgetResizable(True)
