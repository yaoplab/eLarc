"""ContractList — liste des contrats d'un employé avec actions."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QMessageBox, QHeaderView,
)

from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.icons import icon as md3_icon
from larccommon.safe_slot import safe_slot
from phibuilder.phi.scale import SpacingToken
from phibuilder.widgets import M3TableWidget

from LarcRH.common.hr_database import HRDatabase
from LarcRH.views.contract_form import ContractFormDialog, CONTRACT_TYPES, CONTRACT_LABELS


class ContractList(QWidget):
    """Liste des contrats + bouton ajout."""

    def __init__(self, staff_data: dict, parent=None):
        super().__init__(parent)
        self._staff = staff_data
        self._contracts: list[dict] = []
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.space_sm)
        p = theme_manager.palette

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Contrats")
        title.setStyleSheet(f"font-weight: bold; font-size: {theme_manager.font_size(14)}px; color: {p.text_strong}; border: none;")
        hdr.addWidget(title)
        hdr.addStretch()

        add_btn = QPushButton("+ Nouveau contrat")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setFixedHeight(ds.field_height)
        add_btn.setStyleSheet(f"""
            QPushButton {{ background: {p.primary}; color: white; border: none;
            border-radius: {ds.radius_xs}px; padding: {ds.space_xxs}px {ds.space_sm}px;
            font-size: {theme_manager.font_size(12)}px; font-weight: bold; }}
            QPushButton:hover {{ background: {p.primary}; }}
        """)
        add_btn.clicked.connect(self._on_add)
        hdr.addWidget(add_btn)
        layout.addLayout(hdr)

        # Table
        self._table = M3TableWidget()
        self._table.set_headers(["ID", "Type", "Début", "Fin", "Essai fin", "Salaire", "Statut", "Modifié par", ""])
        self._table.setColumnHidden(0, True)
        self._table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setDefaultSectionSize(ds.field_height)
        self._table.setStyleSheet(ds.table_qss())
        layout.addWidget(self._table)

    def refresh(self):
        staff_id = self._staff.get("id", 0)
        self._contracts = HRDatabase.get_contracts(staff_id)
        self._table.setRowCount(0)

        for i, c in enumerate(self._contracts):
            self._table.setRowCount(i + 1)
            from PySide6.QtWidgets import QTableWidgetItem

            type_label = CONTRACT_LABELS[CONTRACT_TYPES.index(c["contract_type"])] if c["contract_type"] in CONTRACT_TYPES else c["contract_type"]
            self._table.setItem(i, 0, QTableWidgetItem(str(c.get("id", ""))))
            self._table.setItem(i, 1, QTableWidgetItem(type_label))
            self._table.setItem(i, 2, QTableWidgetItem(str(c.get("date_debut", ""))))
            self._table.setItem(i, 3, QTableWidgetItem(str(c.get("date_fin", "") or "—")))
            self._table.setItem(i, 4, QTableWidgetItem(str(c.get("periode_essai_fin", "") or "—")))

            salary = f"{c['salaire_brut']:,.0f} F" if c.get("salaire_brut") else "—"
            self._table.setItem(i, 5, QTableWidgetItem(salary))

            status_item = QTableWidgetItem(c.get("statut", "actif"))
            p = theme_manager.palette
            if c.get("statut") == "actif":
                from PySide6.QtGui import QColor
                status_item.setForeground(QColor(p.success))
            elif c.get("statut") == "rompu":
                from PySide6.QtGui import QColor
                status_item.setForeground(QColor(p.error))
            self._table.setItem(i, 6, status_item)
            self._table.setItem(i, 7, QTableWidgetItem(c.get("modified_by_name", "—")))

            # Actions
            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(0, 0, 0, 0)
            al.setSpacing(ds.space_xxs)

            edit_btn = QPushButton()
            edit_btn.setIcon(md3_icon("edit", color=p.primary, size=14))
            edit_btn.setFixedSize(ds.icon_btn_size, ds.icon_btn_size)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setToolTip("Modifier")
            edit_btn.clicked.connect(lambda checked, idx=i: self._on_edit(idx))
            edit_btn.setStyleSheet(f"QPushButton {{ border: none; background: transparent; }}")
            al.addWidget(edit_btn)

            if c.get("statut") == "actif":
                end_btn = QPushButton()
                end_btn.setIcon(md3_icon("cancel", color=p.error, size=14))
                end_btn.setFixedSize(ds.icon_btn_size, ds.icon_btn_size)
                end_btn.setCursor(Qt.PointingHandCursor)
                end_btn.setToolTip("Rompre le contrat")
                end_btn.clicked.connect(lambda checked, idx=i: self._on_terminate(idx))
                end_btn.setStyleSheet(f"QPushButton {{ border: none; background: transparent; }}")
                al.addWidget(end_btn)

            al.addStretch()
            self._table.setCellWidget(i, 8, actions)

        h = self._table.horizontalHeader()
        # IE8 : seule la colonne Type s'étire ; les autres au contenu
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setStretchLastSection(False)
        h.resizeSection(2, ds.sp(SpacingToken.XXL) + ds.sp(SpacingToken.XS))
        h.resizeSection(3, ds.sp(SpacingToken.XXL) + ds.sp(SpacingToken.XS))
        h.resizeSection(4, ds.sp(SpacingToken.XXL) + ds.sp(SpacingToken.XS))
        h.resizeSection(5, ds.sp(SpacingToken.XXL) + ds.space_m3)
        h.resizeSection(6, ds.sp(SpacingToken.XXL))
        h.resizeSection(7, ds.field_height + ds.space_xs)
        self._table.setSortingEnabled(True)  # IE8d : tri par clic

    @safe_slot("ContractList._on_add")
    def _on_add(self):
        dlg = ContractFormDialog(self._staff.get("id", 0), parent=self)
        if dlg.exec():
            self.refresh()
            QMessageBox.information(self, "LarcRH", "Contrat enregistré.")

    @safe_slot("ContractList._on_edit")
    def _on_edit(self, idx: int):
        if 0 <= idx < len(self._contracts):
            dlg = ContractFormDialog(self._staff.get("id", 0), self._contracts[idx], parent=self)
            if dlg.exec():
                self.refresh()
                QMessageBox.information(self, "LarcRH", "Contrat modifié.")

    @safe_slot("ContractList._on_terminate")
    def _on_terminate(self, idx: int):
        if 0 <= idx < len(self._contracts):
            c = self._contracts[idx]
            c["statut"] = "rompu"
            HRDatabase.save_contract(c)
            self.refresh()
