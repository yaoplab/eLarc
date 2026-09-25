"""Onglet A — Classes & matières de classe (Phase 1).

Écritures UPDATE-only (principe gabarit) : label/enabled de la classe et de
chaque slot `classroom_termsubject`. Désactiver un slot inscrit propose la
cascade (désinscrire les élèves) — jamais en silence.
"""
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from phibuilder.phi.scale import SpacingToken
from phibuilder.widgets import M3Button, M3ComboBox, M3Label, M3ScrollArea, M3TableWidget
from phibuilder.widgets.button import ButtonVariant
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QHeaderView, QMessageBox, QTableWidgetItem, QVBoxLayout, QWidget

from LarcConfig.common import db_enrolment
from LarcConfig.views.table_rows import cell_combo_height, fix_row_height

_COL_ACTIVE, _COL_LABEL, _COL_NIVEAU, _COL_CROSS, _COL_TEACHER, _COL_ENROLLED, _COL_GROUP = range(7)
_GENERIC_PREFIX = 'matiere_supl'


def _row_sort_key(r: dict, col: int):
    """Tri géré en Python, pas via le tri natif Qt : les colonnes Actif/Piste
    croisée sont des cases à cocher sans texte (le tri par défaut, basé sur
    le texte affiché, ne les distinguerait pas) et Inscrits est numérique
    (en texte, "10" trierait avant "2"). Une sous-classe QTableWidgetItem
    avec un `__lt__` maison a été testée puis abandonnée : elle fait planter
    Qt (segfault) dès que `sortItems()` la manipule."""
    if col == _COL_ACTIVE:
        return r['enabled']
    if col == _COL_LABEL:
        return r['label'].lower()
    if col == _COL_NIVEAU:
        return r['niv_sup']
    if col == _COL_CROSS:
        return bool(r.get('cross_track'))
    if col == _COL_TEACHER:
        return f"{(r.get('teacher_last_name') or '').lower()} {(r.get('teacher_first_name') or '').lower()}"
    if col == _COL_ENROLLED:
        return r['enrolled_count']
    if col == _COL_GROUP:
        return r['group_label'].lower()
    return 0


class ClassesPanel(M3ScrollArea):
    def __init__(self, user: dict):
        super().__init__(theme=theme_manager.phi_theme)
        phi = theme_manager.phi_theme
        sp = phi.spacing.spacing
        self._classroom_id = None
        self._term_id = 1
        self._is_dp = False
        self._loading = False
        self._rows = []
        self._rows_by_id = {}
        self._teachers = []
        self._sort_col = None
        self._sort_ascending = True

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(sp(SpacingToken.LG), sp(SpacingToken.LG),
                                sp(SpacingToken.LG), sp(SpacingToken.LG))
        lay.setSpacing(sp(SpacingToken.MD))

        head = QHBoxLayout()
        self._class_title = M3Label("Choisissez une classe", theme=phi, style="headline_small")
        head.addWidget(self._class_title)
        head.addStretch()
        self._enabled_btn = M3Button("Classe active", theme=phi, variant=ButtonVariant.TEXT)
        self._enabled_btn.setCheckable(True)
        self._enabled_btn.clicked.connect(self._on_toggle_classroom_enabled)
        head.addWidget(self._enabled_btn)
        lay.addLayout(head)

        self._table = M3TableWidget(theme=phi)
        fix_row_height(self._table)
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(
            ["Actif", "Matière", "Niveau", "Piste croisée", "Enseignant", "Inscrits", "Groupe"])
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(_COL_ACTIVE, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(_COL_LABEL, QHeaderView.Stretch)
        h.setSectionResizeMode(_COL_NIVEAU, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(_COL_CROSS, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(_COL_TEACHER, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(_COL_ENROLLED, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(_COL_GROUP, QHeaderView.ResizeToContents)
        h.setStretchLastSection(False)
        h.setSortIndicatorShown(True)
        h.sectionClicked.connect(self._on_header_clicked)
        self._table.setAlternatingRowColors(False)
        self._table.itemChanged.connect(self._on_item_changed)
        lay.addWidget(self._table)

        self.setWidget(container)
        self.setWidgetResizable(True)

    def _ro(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    @staticmethod
    def _teacher_label(t: dict) -> str:
        # Le compte placeholder "en attente" a le même last_name/first_name
        # (cf. db_enrolment.PLACEHOLDER_TEACHER_ID) : éviter de le dupliquer.
        last, first = (t.get('last_name') or '').strip(), (t.get('first_name') or '').strip()
        return last if last == first else f"{last} {first}".strip()

    def _make_teacher_combo(self, cts_id: int, current_id, current_name: str) -> M3ComboBox:
        combo = M3ComboBox(theme=theme_manager.phi_theme)
        combo.setFixedHeight(cell_combo_height())
        combo.blockSignals(True)
        found = False
        # Le placeholder "en attente" est épinglé en premier, plutôt que
        # noyé dans le tri alphabétique des vrais enseignants.
        ordered = sorted(self._teachers,
                          key=lambda t: (t['id'] != db_enrolment.PLACEHOLDER_TEACHER_ID,
                                          t['last_name'], t['first_name']))
        for t in ordered:
            combo.addItem(self._teacher_label(t), t['id'])
            found = found or t['id'] == current_id
        if current_id is not None and not found:
            combo.addItem(current_name or f"ID {current_id}", current_id)
        idx = combo.findData(current_id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.blockSignals(False)
        combo.currentIndexChanged.connect(
            lambda _idx, cid=cts_id, cb=combo: self._on_teacher_changed(cid, cb))
        return combo

    def set_context(self, classroom_id: int, classroom_label: str,
                     classroom_enabled: bool, term_id: int, program_sigle: str | None = None):
        self._classroom_id = classroom_id
        self._term_id = term_id
        self._is_dp = bool(program_sigle) and program_sigle.upper().startswith('DP')
        self._class_title.setText(classroom_label or "—")
        self._enabled_btn.blockSignals(True)
        self._enabled_btn.setChecked(bool(classroom_enabled))
        self._enabled_btn.setText("Classe active" if classroom_enabled else "Classe désactivée")
        self._enabled_btn.blockSignals(False)
        self.reload()

    @safe_slot("ClassesPanel.reload")
    def reload(self):
        if self._classroom_id is None:
            self._table.setRowCount(0)
            return
        self._teachers = db_enrolment.get_teachers()
        self._rows = db_enrolment.get_classroom_subjects(self._classroom_id, self._term_id)
        if self._sort_col is not None:
            self._rows.sort(key=lambda r: _row_sort_key(r, self._sort_col), reverse=not self._sort_ascending)
        self._table.setColumnHidden(_COL_NIVEAU, not self._is_dp)
        self._populate_rows()

    @safe_slot("ClassesPanel._on_header_clicked")
    def _on_header_clicked(self, logical_index: int):
        if self._sort_col == logical_index:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_col = logical_index
            self._sort_ascending = True
        self._rows.sort(key=lambda r: _row_sort_key(r, logical_index), reverse=not self._sort_ascending)
        order = Qt.SortOrder.AscendingOrder if self._sort_ascending else Qt.SortOrder.DescendingOrder
        self._table.horizontalHeader().setSortIndicator(logical_index, order)
        self._populate_rows()

    def _populate_rows(self):
        self._loading = True
        self._rows_by_id = {r['id']: r for r in self._rows}
        self._table.setRowCount(len(self._rows))
        variant_color = theme_manager.phi_theme.colors.on_surface_variant
        for i, r in enumerate(self._rows):
            active_item = QTableWidgetItem()
            active_item.setFlags((active_item.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
            active_item.setCheckState(Qt.Checked if r['enabled'] else Qt.Unchecked)
            self._table.setItem(i, _COL_ACTIVE, active_item)

            self._table.setItem(i, _COL_LABEL, QTableWidgetItem(r['label']))
            self._table.setItem(i, _COL_NIVEAU, self._ro('NS' if r['niv_sup'] else 'NM'))

            cross_item = QTableWidgetItem()
            cross_item.setFlags((cross_item.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
            cross_item.setCheckState(Qt.Checked if r.get('cross_track') else Qt.Unchecked)
            self._table.setItem(i, _COL_CROSS, cross_item)

            teacher = f"{r.get('teacher_first_name') or ''} {r.get('teacher_last_name') or ''}".strip()
            self._table.setItem(i, _COL_TEACHER, self._ro(teacher))
            self._table.setCellWidget(i, _COL_TEACHER,
                                       self._make_teacher_combo(r['id'], r.get('fk_teacher_id'), teacher))
            self._table.setItem(i, _COL_ENROLLED, self._ro(str(r['enrolled_count'])))
            self._table.setItem(i, _COL_GROUP, self._ro(r['group_label']))

            # Identification par id (Qt.UserRole), jamais par position de ligne :
            # le tri déplace les lignes.
            for col in range(7):
                item = self._table.item(i, col)
                item.setData(Qt.UserRole, r['id'])
                if r['label'].lower().startswith(_GENERIC_PREFIX):
                    item.setForeground(QColor(variant_color))
        self._loading = False

    @safe_slot("ClassesPanel._on_toggle_classroom_enabled")
    def _on_toggle_classroom_enabled(self, checked: bool):
        if self._classroom_id is None:
            return
        if not db_enrolment.set_classroom_enabled(self._classroom_id, checked):
            QMessageBox.warning(self, "Erreur", "La mise à jour de la classe a échoué.")
            checked = not checked
        self._enabled_btn.blockSignals(True)
        self._enabled_btn.setChecked(checked)
        self._enabled_btn.setText("Classe active" if checked else "Classe désactivée")
        self._enabled_btn.blockSignals(False)

    @safe_slot("ClassesPanel._on_item_changed")
    def _on_item_changed(self, item: QTableWidgetItem):
        if self._loading:
            return
        cts = self._rows_by_id.get(item.data(Qt.UserRole))
        if cts is None:
            return
        if item.column() == _COL_ACTIVE:
            self._on_active_toggled(cts, item.checkState() == Qt.Checked)
        elif item.column() == _COL_LABEL:
            self._on_label_edited(cts, item)
        elif item.column() == _COL_CROSS:
            self._on_cross_track_toggled(cts, item.checkState() == Qt.Checked)

    def _on_active_toggled(self, cts: dict, enabled: bool):
        if enabled == cts['enabled']:
            return
        cascade = False
        if not enabled:
            n = db_enrolment.count_classroom_termsubject_enrolment(cts['id'])
            if n > 0:
                resp = QMessageBox.question(
                    self, "Désinscrire les élèves ?",
                    f"{n} élève(s) sont inscrits sur « {cts['label']} ». "
                    "Les désinscrire en même temps que la désactivation du slot ?",
                    QMessageBox.Yes | QMessageBox.No)
                cascade = resp == QMessageBox.Yes
        result = db_enrolment.set_classroom_termsubject_enabled(cts['id'], enabled, cascade=cascade)
        if not result['subject_updated']:
            QMessageBox.warning(self, "Erreur", "La mise à jour du slot a échoué.")
        else:
            cts['enabled'] = enabled
            if result['enrolment_disabled']:
                QMessageBox.information(
                    self, "Désinscription effectuée",
                    f"{result['enrolment_disabled']} élève(s) désinscrit(s).")
        self.reload()

    def _on_cross_track_toggled(self, cts: dict, cross_track: bool):
        if cross_track == cts.get('cross_track', False):
            return
        if db_enrolment.set_classroom_termsubject_cross_track(cts['id'], cross_track):
            cts['cross_track'] = cross_track
        else:
            QMessageBox.warning(self, "Erreur", "La mise à jour a échoué.")
            self.reload()

    @safe_slot("ClassesPanel._on_teacher_changed")
    def _on_teacher_changed(self, cts_id: int, combo: M3ComboBox):
        if self._loading:
            return
        cts = self._rows_by_id.get(cts_id)
        if cts is None:
            return
        new_teacher_id = combo.currentData()
        if new_teacher_id == cts.get('fk_teacher_id'):
            return
        if db_enrolment.set_classroom_termsubject_teacher(cts_id, new_teacher_id):
            cts['fk_teacher_id'] = new_teacher_id
            t = next((t for t in self._teachers if t['id'] == new_teacher_id), None)
            if t is not None:
                cts['teacher_first_name'] = t['first_name']
                cts['teacher_last_name'] = t['last_name']
        else:
            QMessageBox.warning(self, "Erreur", "La mise à jour de l'enseignant a échoué.")
            self.reload()

    def _on_label_edited(self, cts: dict, item: QTableWidgetItem):
        new_label = item.text().strip()
        if not new_label:
            new_label = cts['label']
        elif new_label != cts['label'] and db_enrolment.set_classroom_termsubject_label(cts['id'], new_label):
            cts['label'] = new_label
        self._loading = True
        item.setText(cts['label'])
        self._loading = False
