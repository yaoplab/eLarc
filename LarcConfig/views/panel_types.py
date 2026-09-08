"""Panel Types d'événements — éditeur (langue, parent, actif, libellé)."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QHeaderView, QTableWidgetItem,
    QDialog, QFormLayout, QLineEdit,
)
from PySide6.QtCore import Qt
from phibuilder.widgets import M3Label, M3TableWidget, M3ScrollArea, M3ComboBox, M3Button
from phibuilder.phi.scale import SpacingToken
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot
from LarcConfig.common.db_access import (
    get_event_types, set_event_type_active, set_event_type_label, activate_event_type,
)


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

        header_row = QHBoxLayout()
        header_row.addWidget(M3Label("Types d'evenements", theme=phi, style="headline_small"))
        header_row.addStretch()
        header_row.addWidget(M3Label("Langue :", theme=phi, style="body_medium"))
        self._lang_combo = M3ComboBox(["Français", "English"], theme=phi)
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        header_row.addWidget(self._lang_combo)
        create_btn = M3Button("Créer un type", theme=phi)
        create_btn.clicked.connect(self._on_create_type)
        header_row.addWidget(create_btn)
        l.addLayout(header_row)

        self._table = M3TableWidget(theme=phi)
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Catégorie", "Parent", "Libellé", "Code", "Actif"]
        )
        h = self._table.horizontalHeader()
        for i in range(6):
            h.setSectionResizeMode(i, QHeaderView.Stretch)
        self._table.setAlternatingRowColors(False)
        self._table.itemChanged.connect(self._on_item_changed)
        l.addWidget(self._table)

        self.setWidget(container)
        self.setWidgetResizable(True)

        self._rows: list[dict] = []
        self._loading = False
        self._reload(fk_language=2)

    def _fk_language(self) -> int:
        return 2 if self._lang_combo.currentIndex() == 0 else 1

    def _reload(self, fk_language: int):
        self._loading = True
        self._rows = get_event_types(fk_language)
        self._table.setRowCount(len(self._rows))
        for i, r in enumerate(self._rows):
            indent = "    " * r['depth']
            self._table.setItem(i, 0, self._readonly_item(str(r['id'])))
            self._table.setItem(i, 1, self._readonly_item(r['category'] or ''))
            self._table.setItem(i, 2, self._readonly_item(r['parent_label'] or ''))
            self._table.setItem(i, 3, QTableWidgetItem(f"{indent}{r['label'] or ''}"))
            self._table.setItem(i, 4, self._readonly_item(r['code'] or ''))
            active_item = QTableWidgetItem()
            active_item.setFlags(active_item.flags() | Qt.ItemIsUserCheckable)
            active_item.setCheckState(Qt.Checked if r.get('enabled') else Qt.Unchecked)
            self._table.setItem(i, 5, active_item)
        self._loading = False

    @staticmethod
    def _readonly_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    @safe_slot("TypesPanel._on_language_changed")
    def _on_language_changed(self, _index: int):
        self._reload(self._fk_language())

    @safe_slot("TypesPanel._on_item_changed")
    def _on_item_changed(self, item: QTableWidgetItem):
        if self._loading:
            return
        row = item.row()
        event_type_id = self._rows[row]['id']
        if item.column() == 5:
            set_event_type_active(event_type_id, item.checkState() == Qt.Checked)
        elif item.column() == 3:
            depth = self._rows[row]['depth']
            new_label = item.text()[len("    " * depth):]
            set_event_type_label(event_type_id, new_label)

    @safe_slot("TypesPanel._on_create_type")
    def _on_create_type(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Créer un type d'événement")
        form = QFormLayout(dlg)
        parent_edit = QLineEdit()
        parent_edit.setPlaceholderText("code du parent (vide = nouvelle racine)")
        suffix_edit = QLineEdit()
        label_fr_edit = QLineEdit()
        label_en_edit = QLineEdit()
        form.addRow("Parent (code) :", parent_edit)
        form.addRow("Suffixe code :", suffix_edit)
        form.addRow("Libellé FR :", label_fr_edit)
        form.addRow("Libellé EN :", label_en_edit)
        ok_btn = M3Button("Créer")
        ok_btn.clicked.connect(dlg.accept)
        form.addRow(ok_btn)
        if dlg.exec() == QDialog.Accepted:
            ok = activate_event_type(
                parent_code=parent_edit.text().strip() or None,
                code_suffix=suffix_edit.text().strip(),
                label_fr=label_fr_edit.text().strip(),
                label_en=label_en_edit.text().strip(),
            )
            if not ok:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, "Erreur",
                    "Aucun slot potentiel libre sous ce parent, dans l'une des 2 langues.",
                )
            self._reload(self._fk_language())
