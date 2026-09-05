"""Panel Types d'événements."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHeaderView, QTableWidgetItem
from phibuilder.widgets import M3Label, M3TableWidget, M3ScrollArea
from phibuilder.phi.scale import SpacingToken
from larccommon.theme import theme_manager
from LarcConfig.common.db_access import get_event_types


class TypesPanel(M3ScrollArea):
    def __init__(self, user: dict):
        super().__init__(theme=theme_manager.phi_theme)
        phi = theme_manager.phi_theme
        sp = phi.spacing.spacing

        container = QWidget()
        l = QVBoxLayout(container)
        l.setContentsMargins(sp(SpacingToken.LG), sp(SpacingToken.LG),
                             sp(SpacingToken.LG), sp(SpacingToken.LG))
        l.setSpacing(sp(SpacingToken.MD))
        l.addWidget(M3Label("Types d'evenements", theme=phi, style="headline_small"))

        table = M3TableWidget(theme=phi)
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["ID", "Categorie", "Niveau 2", "Niveau 3", "Actif"])
        h = table.horizontalHeader()
        for i in range(5):
            h.setSectionResizeMode(i, QHeaderView.Stretch)
        table.setAlternatingRowColors(False)

        rows = get_event_types()
        table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(str(r['id'])))
            table.setItem(i, 1, QTableWidgetItem(r['cat'] or ''))
            table.setItem(i, 2, QTableWidgetItem(r.get('niv2', '') or ''))
            table.setItem(i, 3, QTableWidgetItem(r.get('niv3', '') or ''))
            table.setItem(i, 4, QTableWidgetItem('Oui' if r.get('enabled') else 'Non'))

        l.addWidget(table)
        self.setWidget(container)
        self.setWidgetResizable(True)
