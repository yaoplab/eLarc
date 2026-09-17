"""Panel Rôles — liste des utilisateurs."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHeaderView, QTableWidgetItem
from phibuilder.widgets import M3Label, M3TableWidget, M3ScrollArea
from phibuilder.phi.scale import SpacingToken
from larccommon.theme import theme_manager
from LarcConfig.common.db_access import get_roles


class RolesPanel(M3ScrollArea):
    def __init__(self, user: dict):
        super().__init__(theme=theme_manager.phi_theme)
        phi = theme_manager.phi_theme
        sp = phi.spacing.spacing

        container = QWidget()
        l = QVBoxLayout(container)
        l.setContentsMargins(sp(SpacingToken.LG), sp(SpacingToken.LG),
                             sp(SpacingToken.LG), sp(SpacingToken.LG))
        l.setSpacing(sp(SpacingToken.MD))
        l.addWidget(M3Label("Roles", theme=phi, style="headline_small"))

        table = M3TableWidget(theme=phi)
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["ID", "Nom", "Prenom", "Email", "Roles"])
        h = table.horizontalHeader()
        for i in range(5):
            h.setSectionResizeMode(i, QHeaderView.Stretch)
        table.setAlternatingRowColors(False)

        def _ro(text: str) -> QTableWidgetItem:
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            return item

        rows = get_roles()
        table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            table.setItem(i, 0, _ro(str(r['id'])))
            table.setItem(i, 1, _ro(r['last_name']))
            table.setItem(i, 2, _ro(r['first_name']))
            table.setItem(i, 3, _ro(r['email']))
            table.setItem(i, 4, _ro(r['roles']))

        l.addWidget(table)
        self.setWidget(container)
        self.setWidgetResizable(True)
