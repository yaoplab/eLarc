"""Onglet « Autres-matières » — TDC, Mémoire (EE), CAS, Projet personnel.

Contrairement aux matières classiques (groupes, pistes croisées), le lien
élève ↔ slot est direct : `larcauth_learner_has_termothersubject.enabled`
est piloté par le tuteur : `ref_teacher` réel = inscrit (enabled=true),
aucun/placeholder = non inscrit. Écritures UPDATE-only (principe gabarit).

Grille élèves × slots : la cellule affiche le tuteur ; double-clic sur une
cellule = choisir le tuteur de l'élève, double-clic sur un en-tête =
l'affecter à toute la classe active ; clic sur un en-tête = tri.
"""
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from phibuilder.phi.scale import SpacingToken
from phibuilder.widgets import M3ComboBox, M3Dialog, M3Label, M3ListWidget, M3TableWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QListWidgetItem, QMessageBox, QTableWidgetItem, QVBoxLayout, QWidget,
)

from LarcConfig.common import db_enrolment, db_othersubjects
from LarcConfig.views.effectifs_grille import _size_list_to_items
from LarcConfig.views.table_rows import cell_combo_height, fix_row_height

_COL_ACTIVE, _COL_LABEL, _COL_SUPERVISOR, _COL_ENROLLED = range(4)
_MAX_SLOT_ROWS = 4  # au-delà, le tableau des slots défile : l'espace va à la grille élèves


class OtherSubjectsPanel(QWidget):
    def __init__(self, user: dict):
        super().__init__()
        phi = theme_manager.phi_theme
        sp = phi.spacing.spacing
        self._classroom_id = None
        self._term_id = 1
        self._loading = False
        self._slots = []
        self._slots_by_id = {}
        self._supervisors = []
        self._students = []
        self._links = {}  # (student_id, cts_id) -> ref_teacher (None/placeholder = non inscrit)
        self._grid_slots = []  # slots actifs, une colonne chacun (colonne = index + 1)
        self._slot_sort_col = None
        self._slot_sort_asc = True

        lay = QVBoxLayout(self)
        lay.setContentsMargins(sp(SpacingToken.LG), sp(SpacingToken.LG),
                                sp(SpacingToken.LG), sp(SpacingToken.LG))
        lay.setSpacing(sp(SpacingToken.MD))

        self._title = M3Label("Choisissez une classe", theme=phi, style="headline_small")
        lay.addWidget(self._title)

        lay.addWidget(M3Label(
            "Élèves × slots actifs — double-clic sur une cellule pour choisir le tuteur "
            "de l'élève, sur un en-tête pour l'affecter à toute la classe, clic sur un "
            "en-tête pour trier", theme=phi, style="body_small"))
        self._grid = M3TableWidget(theme=phi)
        fix_row_height(self._grid)
        self._grid.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._grid.setSortingEnabled(True)
        self._grid.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self._grid.horizontalHeader().sectionDoubleClicked.connect(self._on_header_double_clicked)
        lay.addWidget(self._grid, 1)

        lay.addWidget(M3Label(
            "Slots (TDC, Mémoire, CAS, Projet personnel…)", theme=phi, style="body_small"))
        self._slots_table = M3TableWidget(theme=phi)
        fix_row_height(self._slots_table)
        self._slots_table.setColumnCount(4)
        self._slots_table.setHorizontalHeaderLabels(["Actif", "Matière", "Superviseur", "Inscrits"])
        h = self._slots_table.horizontalHeader()
        h.setSectionResizeMode(_COL_ACTIVE, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(_COL_LABEL, QHeaderView.Stretch)
        h.setSectionResizeMode(_COL_SUPERVISOR, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(_COL_ENROLLED, QHeaderView.ResizeToContents)
        h.setStretchLastSection(False)
        h.setSortIndicatorShown(True)
        h.sectionClicked.connect(self._on_slots_header_clicked)
        self._slots_table.setAlternatingRowColors(False)
        self._slots_table.itemChanged.connect(self._on_slot_item_changed)
        lay.addWidget(self._slots_table)

    def _ro(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def set_context(self, classroom_id: int, classroom_label: str, term_id: int,
                     program_sigle: str | None = None):
        self._classroom_id = classroom_id
        self._term_id = term_id
        self._title.setText(classroom_label or "—")
        self.reload()

    @safe_slot("OtherSubjectsPanel.reload")
    def reload(self):
        if self._classroom_id is None:
            self._slots_table.setRowCount(0)
            self._grid.setRowCount(0)
            self._grid.setColumnCount(0)
            return
        self._supervisors = db_othersubjects.get_supervisors()
        self._slots = db_othersubjects.get_classroom_othersubjects(self._classroom_id, self._term_id)
        self._students = db_enrolment.get_active_students(self._classroom_id)
        links = db_othersubjects.get_othersubject_links(self._classroom_id, self._term_id)
        self._links = {(l['fk_student_id'], l['fk_termothersubject_id']): l['ref_teacher'] for l in links}
        self._populate_slots()
        self._populate_grid()

    def _make_supervisor_combo(self, cts_id: int, current_id, current_name: str) -> M3ComboBox:
        combo = M3ComboBox(theme=theme_manager.phi_theme)
        combo.setFixedHeight(cell_combo_height())
        combo.blockSignals(True)
        found = False
        ordered = sorted(self._supervisors, key=lambda t: (t['last_name'], t['first_name']))
        for t in ordered:
            combo.addItem(f"{t['last_name']} {t['first_name']}".strip(), t['id'])
            found = found or t['id'] == current_id
        if current_id is not None and not found:
            combo.addItem(current_name or f"ID {current_id}", current_id)
        idx = combo.findData(current_id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.blockSignals(False)
        combo.currentIndexChanged.connect(
            lambda _idx, cid=cts_id, cb=combo: self._on_supervisor_changed(cid, cb))
        return combo

    def _slot_sort_key(self, s: dict):
        if self._slot_sort_col == _COL_ACTIVE:
            return bool(s['enabled'])
        if self._slot_sort_col == _COL_LABEL:
            return s['label'].lower()
        if self._slot_sort_col == _COL_SUPERVISOR:
            return f"{(s.get('supervisor_last_name') or '').lower()} {(s.get('supervisor_first_name') or '').lower()}"
        return s['enrolled_count']

    def _sorted_slots(self) -> list[dict]:
        if self._slot_sort_col is None:
            return self._slots
        return sorted(self._slots, key=self._slot_sort_key, reverse=not self._slot_sort_asc)

    @safe_slot("OtherSubjectsPanel._on_slots_header_clicked")
    def _on_slots_header_clicked(self, logical_index: int):
        if self._slot_sort_col == logical_index:
            self._slot_sort_asc = not self._slot_sort_asc
        else:
            self._slot_sort_col = logical_index
            self._slot_sort_asc = True
        order = Qt.SortOrder.AscendingOrder if self._slot_sort_asc else Qt.SortOrder.DescendingOrder
        self._slots_table.horizontalHeader().setSortIndicator(logical_index, order)
        self._populate_slots()

    def _populate_slots(self):
        self._loading = True
        self._slots_by_id = {s['id']: s for s in self._slots}
        rows = self._sorted_slots()
        self._slots_table.setRowCount(len(rows))
        for i, s in enumerate(rows):
            active_item = QTableWidgetItem()
            active_item.setFlags((active_item.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
            active_item.setCheckState(Qt.Checked if s['enabled'] else Qt.Unchecked)
            self._slots_table.setItem(i, _COL_ACTIVE, active_item)

            self._slots_table.setItem(i, _COL_LABEL, QTableWidgetItem(s['label']))

            supervisor_name = f"{s.get('supervisor_first_name') or ''} {s.get('supervisor_last_name') or ''}".strip()
            self._slots_table.setItem(i, _COL_SUPERVISOR, self._ro(supervisor_name))
            self._slots_table.setCellWidget(
                i, _COL_SUPERVISOR,
                self._make_supervisor_combo(s['id'], s.get('fk_supervisor_id'), supervisor_name))

            self._slots_table.setItem(i, _COL_ENROLLED, self._ro(str(s['enrolled_count'])))

            for col in range(4):
                self._slots_table.item(i, col).setData(Qt.UserRole, s['id'])
        vh = self._slots_table.verticalHeader()
        self._slots_table.setFixedHeight(
            self._slots_table.horizontalHeader().height()
            + min(len(self._slots), _MAX_SLOT_ROWS) * vh.defaultSectionSize() + 2)
        self._loading = False

    @safe_slot("OtherSubjectsPanel._on_slot_item_changed")
    def _on_slot_item_changed(self, item: QTableWidgetItem):
        if self._loading:
            return
        s = self._slots_by_id.get(item.data(Qt.UserRole))
        if s is None:
            return
        if item.column() == _COL_ACTIVE:
            self._on_slot_active_toggled(s, item.checkState() == Qt.Checked)
        elif item.column() == _COL_LABEL:
            self._on_slot_label_edited(s, item)

    def _on_slot_active_toggled(self, s: dict, enabled: bool):
        if enabled == s['enabled']:
            return
        cascade = False
        if not enabled:
            n = db_othersubjects.count_othersubject_enrolment(s['id'])
            if n > 0:
                resp = QMessageBox.question(
                    self, "Désinscrire les élèves ?",
                    f"{n} élève(s) sont inscrits sur « {s['label']} ». "
                    "Les désinscrire en même temps que la désactivation du slot ?",
                    QMessageBox.Yes | QMessageBox.No)
                cascade = resp == QMessageBox.Yes
        result = db_othersubjects.set_othersubject_enabled(s['id'], enabled, cascade=cascade)
        if not result['subject_updated']:
            QMessageBox.warning(self, "Erreur", "La mise à jour du slot a échoué.")
        self.reload()

    def _on_slot_label_edited(self, s: dict, item: QTableWidgetItem):
        new_label = item.text().strip()
        if not new_label:
            new_label = s['label']
        elif new_label != s['label'] and db_othersubjects.set_othersubject_label(s['id'], new_label):
            s['label'] = new_label
        self._loading = True
        item.setText(s['label'])
        self._loading = False

    @safe_slot("OtherSubjectsPanel._on_supervisor_changed")
    def _on_supervisor_changed(self, cts_id: int, combo: M3ComboBox):
        if self._loading:
            return
        s = self._slots_by_id.get(cts_id)
        if s is None:
            return
        new_id = combo.currentData()
        if new_id == s.get('fk_supervisor_id'):
            return
        if db_othersubjects.set_othersubject_supervisor(cts_id, new_id):
            s['fk_supervisor_id'] = new_id
            t = next((t for t in self._supervisors if t['id'] == new_id), None)
            if t is not None:
                s['supervisor_first_name'] = t['first_name']
                s['supervisor_last_name'] = t['last_name']
        else:
            QMessageBox.warning(self, "Erreur", "La mise à jour du superviseur a échoué.")
            self.reload()

    def _teacher_name(self, teacher_id) -> str:
        t = next((t for t in self._supervisors if t['id'] == teacher_id), None)
        if t is not None:
            return f"{t['last_name']} {t['first_name']}".strip()
        return f"ID {teacher_id}"

    def _populate_grid(self):
        header = self._grid.horizontalHeader()
        sort_col, sort_order = header.sortIndicatorSection(), header.sortIndicatorOrder()
        self._grid_slots = [s for s in self._slots if s['enabled']]
        self._grid.setSortingEnabled(False)
        self._grid.setColumnCount(1 + len(self._grid_slots))
        self._grid.setHorizontalHeaderLabels(["Élève"] + [s['label'] for s in self._grid_slots])
        for col in range(1, 1 + len(self._grid_slots)):
            self._grid.horizontalHeaderItem(col).setToolTip(
                "Double-cliquer pour affecter un tuteur à toute la classe active")
        for col in range(1 + len(self._grid_slots)):
            header.setSectionResizeMode(col, QHeaderView.Stretch)
        header.setStretchLastSection(False)
        self._grid.setWordWrap(True)

        enrolled_bg = QBrush(QColor(theme_manager.phi_theme.colors.primary_container))
        self._grid.setRowCount(len(self._students))
        for row, student in enumerate(self._students):
            name_item = self._ro(f"{student['last_name']} {student['first_name']}")
            name_item.setData(Qt.UserRole, student['aecuser_ptr_id'])
            self._grid.setItem(row, 0, name_item)
            for col, s in enumerate(self._grid_slots, start=1):
                ref = self._links.get((student['aecuser_ptr_id'], s['id']))
                enrolled = db_othersubjects.is_enrolled(ref)
                item = self._ro(self._teacher_name(ref) if enrolled else "")
                if enrolled:
                    item.setBackground(enrolled_bg)
                self._grid.setItem(row, col, item)
        self._grid.setSortingEnabled(True)
        if sort_col >= 0:
            self._grid.sortItems(sort_col, sort_order)

    def _pick_tutor(self, title: str, subtitle: str, current_id, default_id):
        """Dialogue de choix du tuteur. Retourne (validé, tutor_id | None)."""
        phi = theme_manager.phi_theme
        dlg = M3Dialog(self, title, subtitle, theme=phi)
        dlg.confirm_btn.setText("Valider")
        dlg.cancel_btn.setText("Annuler")
        lst = M3ListWidget(theme=phi, compact=True)
        lst.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        none_item = QListWidgetItem("— Aucun (non inscrit) —")
        none_item.setData(Qt.UserRole, None)
        lst.addItem(none_item)
        tutors = [t for t in self._supervisors if t['id'] != db_enrolment.PLACEHOLDER_TEACHER_ID]
        preselect = current_id if db_othersubjects.is_enrolled(current_id) else default_id
        lst.setCurrentItem(none_item)
        for t in sorted(tutors, key=lambda t: (t['last_name'], t['first_name'])):
            it = QListWidgetItem(f"{t['last_name']} {t['first_name']}".strip())
            it.setData(Qt.UserRole, t['id'])
            lst.addItem(it)
            if t['id'] == preselect:
                lst.setCurrentItem(it)
        _size_list_to_items(lst, lst.count(), phi, max_visible=10)
        dlg.layout().insertWidget(2, lst)
        if dlg.exec() != dlg.DialogCode.Accepted or lst.currentItem() is None:
            return False, None
        return True, lst.currentItem().data(Qt.UserRole)

    @safe_slot("OtherSubjectsPanel._on_cell_double_clicked")
    def _on_cell_double_clicked(self, row: int, col: int):
        slot_idx = col - 1
        if not (0 <= slot_idx < len(self._grid_slots)):
            return
        name_item = self._grid.item(row, 0)
        if name_item is None:
            return
        student_id = name_item.data(Qt.UserRole)
        slot = self._grid_slots[slot_idx]
        current = self._links.get((student_id, slot['id']))
        ok, tutor_id = self._pick_tutor(
            f"{name_item.text()} — {slot['label']}",
            "Choisissez le tuteur (ou Aucun pour désinscrire l'élève).",
            current, slot.get('fk_supervisor_id'))
        if not ok:
            return
        if db_othersubjects.set_learner_othersubject_tutor(student_id, slot['id'], tutor_id):
            self._links[(student_id, slot['id'])] = tutor_id
        else:
            QMessageBox.warning(self, "Erreur", "La mise à jour a échoué.")
        self.reload()

    @safe_slot("OtherSubjectsPanel._on_header_double_clicked")
    def _on_header_double_clicked(self, logical_index: int):
        slot_idx = logical_index - 1
        if not (0 <= slot_idx < len(self._grid_slots)):
            return
        slot = self._grid_slots[slot_idx]
        ok, tutor_id = self._pick_tutor(
            f"Toute la classe — {slot['label']}",
            "Tuteur à affecter à tous les élèves actifs de la classe.",
            None, slot.get('fk_supervisor_id'))
        if not ok:
            return
        n = db_othersubjects.count_class_active_students(self._classroom_id)
        if db_othersubjects.is_enrolled(tutor_id):
            msg = f"{n} élève(s) actif(s) seront inscrits avec {self._teacher_name(tutor_id)} comme tuteur."
        else:
            msg = f"{n} élève(s) actif(s) seront désinscrits de « {slot['label']} »."
        resp = QMessageBox.question(self, "Confirmer", msg + " Confirmer ?", QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            return
        changed = db_othersubjects.set_class_othersubject_tutor(self._classroom_id, slot['id'], tutor_id)
        QMessageBox.information(self, "Terminé", f"{changed} ligne(s) modifiée(s).")
        self.reload()
