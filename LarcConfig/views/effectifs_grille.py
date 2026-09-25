"""Onglet B — Grille élèves × groupes de matières (Phase 2).

Grille unique pour PEI/MYP et DP (cf. plan 2026-09-19, section 3, révisé le
2026-09-22 : les colonnes sont les groupes propres de la classe — pas de
fusion avec une autre classe, les slots « piste croisée » vivent déjà dans
la même classe, cf. migration_20260922_cross_track.sql).

Tri par clic sur un en-tête (natif Qt) + filtre façon Excel (choisir une
colonne puis une valeur pour n'afficher que les lignes correspondantes) —
d'où la colonne « Élève » explicite en position 0 : le tri déplace les
lignes, on ne peut donc plus s'appuyer sur une position fixe ni sur l'en-tête
vertical (identification par `Qt.UserRole` sur la cellule, jamais par index).

Écritures UPDATE-only, scopées classe+trimestre côté serveur
(`db_enrolment.set_student_subject` / `set_class_subject`).
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QListWidgetItem, QMessageBox, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from larccommon.icons import icon as md3_icon
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from phibuilder.phi.scale import SpacingToken
from phibuilder.widgets import M3Button, M3ComboBox, M3Dialog, M3Label, M3ListWidget, M3ScrollArea, M3TableWidget
from phibuilder.widgets.button import ButtonVariant

from LarcConfig.common import db_enrolment
from LarcConfig.views.table_font import TableFontControl
from LarcConfig.views.table_rows import fix_row_height
from LarcConfig.common.enrolment_rules import MAX_SUBJECTS_PER_GROUP, Subject, dp_status, dp_status_reasons, entry_text

_NAME_COL = 0
_STATUS_HEADER = "Statut DP"
_FILTER_NONE = "(Aucun)"
_FILTER_ALL = "(Toutes)"

# Palette de repli quand `couleur` vaut la chaîne 'false' (cf. plan 2.4) —
# une couleur stable par rang de groupe (1-8), pas de hardcoding QSS ailleurs.
_FALLBACK_PALETTE = [
    "#9BC6F5", "#28A745", "#D0AA39", "#002A9A",
    "#DC3545", "#6EDB6E", "#9A72FF", "#F5A623",
]


def _group_color(couleur: str, nr_group_in_pgm: int) -> str:
    if couleur and couleur.lower() != 'false':
        return couleur
    return _FALLBACK_PALETTE[(nr_group_in_pgm - 1) % len(_FALLBACK_PALETTE)]


def _pastel(hex_color: str, surface_hex: str, weight: float = 0.78) -> str:
    """Teinte pastel : mélange la couleur du groupe vers la couleur de fond
    *du thème actif* (jamais blanc en dur) — reste correct en thème sombre."""
    def _rgb(h):
        h = h.lstrip('#')
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    r1, g1, b1 = _rgb(hex_color)
    r2, g2, b2 = _rgb(surface_hex)
    mix = lambda a, b: round(a * (1 - weight) + b * weight)
    return f"#{mix(r1, r2):02X}{mix(g1, g2):02X}{mix(b1, b2):02X}"


def _size_list_to_items(lst: M3ListWidget, count: int, phi, max_visible: int = 5):
    """M3ListWidget est en SizePolicy.Expanding et son sizeHint() par défaut
    ignore la hauteur réelle des lignes : avec 1 ou 2 matières seulement, on
    obtenait une boîte à moitié vide, ou un 2e élément coupé. On dimensionne
    donc sur le nombre réel d'éléments et sur la hauteur de ligne *mesurée*
    (sizeHintForRow — les items doivent déjà être ajoutés), avec un plafond
    au-delà duquel ça défile."""
    sp = phi.spacing.spacing
    row_h = max(lst.sizeHintForRow(0), sp(SpacingToken.LG))
    frame = sp(SpacingToken.XS) * 2 + 2  # padding + bordure de la liste elle-même
    visible = max(1, min(count, max_visible))
    lst.setFixedHeight(visible * row_h + frame)


class GridPanel(M3ScrollArea):
    def __init__(self, user: dict):
        super().__init__(theme=theme_manager.phi_theme)
        phi = theme_manager.phi_theme
        sp = phi.spacing.spacing
        self._classroom_id = None
        self._term_id = 1
        self._is_dp = False
        self._groups = []
        self._students = []
        self._students_by_id = {}
        self._enrolments = {}  # (student_id, nr_group_in_pgm) -> [entry, ...]

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(sp(SpacingToken.LG), sp(SpacingToken.LG),
                                sp(SpacingToken.LG), sp(SpacingToken.LG))
        lay.setSpacing(sp(SpacingToken.MD))

        head = QHBoxLayout()
        self._title = M3Label("Choisissez une classe", theme=phi, style="headline_small")
        head.addWidget(self._title)
        head.addStretch()
        self._font_smaller_btn = M3Button("A−", theme=phi, variant=ButtonVariant.TEXT)
        self._font_smaller_btn.setToolTip("Réduire la taille du texte du tableau")
        self._font_normal_btn = M3Button("A", theme=phi, variant=ButtonVariant.TEXT)
        self._font_normal_btn.setToolTip("Taille normale du texte du tableau")
        head.addWidget(self._font_smaller_btn)
        head.addWidget(self._font_normal_btn)
        lay.addLayout(head)
        lay.addWidget(M3Label(
            "Double-cliquez une cellule pour choisir les matières d'un élève. "
            "Double-cliquez un en-tête de colonne pour l'appliquer à toute la classe active. "
            "Cliquez un en-tête pour trier.",
            theme=phi, style="body_small"))

        filter_row = QHBoxLayout()
        filter_row.addWidget(M3Label("Filtrer", theme=phi, style="body_small"))
        self._filter_col_combo = M3ComboBox([], theme=phi)
        self._filter_col_combo.currentIndexChanged.connect(self._on_filter_column_changed)
        filter_row.addWidget(self._filter_col_combo)
        filter_row.addWidget(M3Label("=", theme=phi, style="body_small"))
        self._filter_val_combo = M3ComboBox([], theme=phi)
        self._filter_val_combo.currentIndexChanged.connect(self._on_filter_value_changed)
        filter_row.addWidget(self._filter_val_combo)
        filter_row.addStretch()
        lay.addLayout(filter_row)

        self._table = M3TableWidget(theme=phi)
        # 2 lignes : la 2e matière d'un groupe passe à la ligne ; le détail complet
        # d'une cellule plus longue est dans son infobulle (moins de défilement).
        fix_row_height(self._table, lines=2)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self._table.horizontalHeader().sectionDoubleClicked.connect(self._on_header_double_clicked)
        lay.addWidget(self._table)

        self._font = TableFontControl(self._table, "grille_eleves", lines=2)
        self._font_smaller_btn.clicked.connect(self._on_font_smaller)
        self._font_normal_btn.clicked.connect(self._on_font_normal)

        self.setWidget(container)
        self.setWidgetResizable(True)

    @safe_slot("GridPanel._on_font_smaller")
    def _on_font_smaller(self, _checked: bool = False):
        self._font.reduce()

    @safe_slot("GridPanel._on_font_normal")
    def _on_font_normal(self, _checked: bool = False):
        self._font.reset()

    def set_context(self, classroom_id: int, classroom_label: str, term_id: int,
                     program_sigle: str | None = None):
        self._classroom_id = classroom_id
        self._term_id = term_id
        self._is_dp = bool(program_sigle) and program_sigle.upper().startswith('DP')
        self._title.setText(classroom_label or "—")
        self.reload()

    def _ro(self, text: str = "") -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    @safe_slot("GridPanel.reload")
    def reload(self):
        if self._classroom_id is None:
            self._table.setRowCount(0)
            self._table.setColumnCount(0)
            return
        self._groups = db_enrolment.get_subject_groups(self._classroom_id, self._term_id)
        self._students = db_enrolment.get_active_students(self._classroom_id)
        self._students_by_id = {s['aecuser_ptr_id']: s for s in self._students}
        entries = db_enrolment.get_student_enrolments(self._classroom_id, self._term_id)
        self._enrolments = {}
        for e in entries:
            key = (e['fk_student_id'], e['nr_group_in_pgm'])
            self._enrolments.setdefault(key, []).append(e)
        self._rebuild_table()

    def _status_col(self) -> int | None:
        return 1 + len(self._groups) if self._is_dp else None

    def _rebuild_table(self):
        # Tri/filtre en cours à préserver d'un rechargement à l'autre — sinon
        # la moindre modification (qui recharge la grille) les effacerait.
        header = self._table.horizontalHeader()
        sort_col, sort_order = header.sortIndicatorSection(), header.sortIndicatorOrder()
        prev_filter_col = self._filter_col_combo.currentText() or None
        prev_filter_val = self._filter_val_combo.currentText() or None

        status_col = self._status_col()
        n_cols = 1 + len(self._groups) + (1 if status_col is not None else 0)

        self._table.setSortingEnabled(False)
        self._table.setColumnCount(n_cols)
        labels = ["Élève"] + [g['group_label'] for g in self._groups]
        if status_col is not None:
            labels.append(_STATUS_HEADER)
        self._table.setHorizontalHeaderLabels(labels)
        for col, _g in enumerate(self._groups, start=1):
            self._table.horizontalHeaderItem(col).setTextAlignment(Qt.AlignCenter)
            self._table.horizontalHeaderItem(col).setToolTip(
                "Double-cliquer pour appliquer une matière à toute la classe active")

        # Même largeur pour toutes les colonnes, texte renvoyé à la ligne
        # (les libellés de matière/groupe sont trop longs pour tenir sur une
        # seule ligne à largeur égale).
        header.setStretchLastSection(False)
        for col in range(n_cols):
            header.setSectionResizeMode(col, QHeaderView.Stretch)
        self._table.setWordWrap(True)

        p = theme_manager.palette
        self._table.setRowCount(len(self._students))
        for row, student in enumerate(self._students):
            name_item = self._ro(f"{student['last_name']} {student['first_name']}")
            name_item.setData(Qt.UserRole, student['aecuser_ptr_id'])
            self._table.setItem(row, _NAME_COL, name_item)
            subjects = []
            for col, g in enumerate(self._groups, start=1):
                key = (student['aecuser_ptr_id'], g['nr_group_in_pgm'])
                cell_entries = self._enrolments.get(key, [])
                for e in cell_entries:
                    subjects.append(Subject(group=g['nr_group_in_pgm'], niv_sup=bool(e.get('niv_sup'))))
                # Une matière par ligne (pas de « + »), centré.
                text = "\n".join(self._format_entry(e) for e in cell_entries)
                item = self._ro(text)
                item.setTextAlignment(Qt.AlignCenter)
                if text:
                    item.setToolTip(text)
                if cell_entries:
                    color = _group_color(cell_entries[0]['couleur'], g['nr_group_in_pgm'])
                    item.setForeground(_qcolor(color))
                    item.setBackground(_qcolor(_pastel(color, p.surface)))
                self._table.setItem(row, col, item)
            if status_col is not None:
                status = dp_status(subjects)
                self._table.setItem(row, status_col, self._status_item(status, p))
                if not status.compliant:
                    # Non conforme : la ligne entière ressort, au-delà de la
                    # seule cellule Statut, pour repérer l'élève d'un coup d'œil.
                    for col in range(n_cols):
                        self._table.item(row, col).setBackground(_qcolor(p.error_container))
        self._table.setSortingEnabled(True)
        if sort_col >= 0:
            self._table.sortItems(sort_col, sort_order)

        self._populate_filter_columns(prev_filter_col, prev_filter_val)

    def _status_item(self, status, p) -> QTableWidgetItem:
        if status.compliant:
            item = self._ro("Conforme")
            item.setIcon(md3_icon("check_circle", color=p.success))
            item.setForeground(_qcolor(p.success))
            item.setToolTip("6 matières, groupes 1-5 couverts, 3 NS / 3 NM.")
            return item
        reasons = dp_status_reasons(status)
        item = self._ro("Non conforme")
        item.setIcon(md3_icon("cancel", color=p.error))
        item.setForeground(_qcolor(p.error))
        item.setToolTip("; ".join(reasons))
        return item

    def _format_entry(self, e: dict) -> str:
        return entry_text(e['label'], bool(e.get('niv_sup')), bool(e.get('cross_track')), self._is_dp)

    def _column_labels(self) -> list[str]:
        labels = ["Élève"] + [g['group_label'] for g in self._groups]
        if self._is_dp:
            labels.append(_STATUS_HEADER)
        return labels

    def _populate_filter_columns(self, restore_col: str | None, restore_val: str | None):
        self._filter_col_combo.blockSignals(True)
        self._filter_col_combo.clear()
        self._filter_col_combo.addItem(_FILTER_NONE)
        self._filter_col_combo.addItems(self._column_labels())
        idx = self._filter_col_combo.findText(restore_col) if restore_col else -1
        self._filter_col_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._filter_col_combo.blockSignals(False)
        self._populate_filter_values(restore_val)

    def _populate_filter_values(self, restore_val: str | None = None):
        col = self._filter_col_combo.currentIndex() - 1  # -1 = (Aucun), 0 = Élève, 1.. = groupes
        self._filter_val_combo.blockSignals(True)
        self._filter_val_combo.clear()
        self._filter_val_combo.addItem(_FILTER_ALL)
        if col >= 0:
            values = sorted({
                self._flat(self._table.item(r, col).text())
                for r in range(self._table.rowCount())
                if self._table.item(r, col) and self._table.item(r, col).text()
            })
            self._filter_val_combo.addItems(values)
        idx = self._filter_val_combo.findText(restore_val) if restore_val else -1
        self._filter_val_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._filter_val_combo.blockSignals(False)
        self._apply_filter()

    @safe_slot("GridPanel._on_filter_column_changed")
    def _on_filter_column_changed(self, _index: int):
        self._populate_filter_values()

    @safe_slot("GridPanel._on_filter_value_changed")
    def _on_filter_value_changed(self, _index: int):
        self._apply_filter()

    @staticmethod
    def _flat(text: str) -> str:
        """Cellule multiligne -> une ligne (valeurs du filtre)."""
        return text.replace("\n", " + ")

    def _apply_filter(self):
        col = self._filter_col_combo.currentIndex() - 1
        value = self._filter_val_combo.currentText()
        show_all = col < 0 or value in ("", _FILTER_ALL)
        for row in range(self._table.rowCount()):
            if show_all:
                self._table.setRowHidden(row, False)
                continue
            item = self._table.item(row, col)
            self._table.setRowHidden(row, self._flat(item.text() if item else "") != value)

    @safe_slot("GridPanel._on_cell_double_clicked")
    def _on_cell_double_clicked(self, row: int, col: int):
        group_idx = col - 1
        if not (0 <= group_idx < len(self._groups)):
            return
        name_item = self._table.item(row, _NAME_COL)
        student = self._students_by_id.get(name_item.data(Qt.UserRole)) if name_item else None
        if student is None:
            return
        self._open_student_dialog(student, self._groups[group_idx])

    @safe_slot("GridPanel._on_header_double_clicked")
    def _on_header_double_clicked(self, logical_index: int):
        group_idx = logical_index - 1
        if not (0 <= group_idx < len(self._groups)):
            return
        self._open_class_dialog(self._groups[group_idx])

    def _choices_for_group(self, group: dict, extra_entries: list[dict]) -> list[dict]:
        choices = db_enrolment.get_group_choices(
            self._classroom_id, self._term_id, group['nr_group_in_pgm'])
        known_ids = {c['id'] for c in choices}
        for e in extra_entries:
            if e['cts_id'] not in known_ids:
                choices.append({
                    'id': e['cts_id'], 'label': f"{e['label']} (désactivée)",
                    'niv_sup': e['niv_sup'], 'cross_track': e['cross_track'],
                })
                known_ids.add(e['cts_id'])
        return choices

    def _open_student_dialog(self, student: dict, group: dict):
        phi = theme_manager.phi_theme
        key = (student['aecuser_ptr_id'], group['nr_group_in_pgm'])
        current = self._enrolments.get(key, [])
        current_ids = {e['cts_id'] for e in current}
        choices = self._choices_for_group(group, current)

        dlg = M3Dialog(
            self, f"{student['first_name']} {student['last_name']} — {group['group_label']}",
            f"Maximum {MAX_SUBJECTS_PER_GROUP} matières.", theme=phi)
        dlg.confirm_btn.setText("Valider")
        dlg.cancel_btn.setText("Annuler")
        lst = M3ListWidget(theme=phi, compact=True)
        lst.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        items = []
        for ch in choices:
            it = QListWidgetItem(self._format_entry(ch))
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if ch['id'] in current_ids else Qt.Unchecked)
            it.setData(Qt.UserRole, ch['id'])
            lst.addItem(it)
            items.append(it)
        _size_list_to_items(lst, len(choices), phi)
        dlg.layout().insertWidget(2, lst)

        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        new_selection = {it.data(Qt.UserRole) for it in items if it.checkState() == Qt.Checked}
        if len(new_selection) > MAX_SUBJECTS_PER_GROUP:
            QMessageBox.warning(
                self, "Trop de matières",
                f"Maximum {MAX_SUBJECTS_PER_GROUP} matières par groupe — rien n'a été enregistré.")
            return
        ok = True
        for cts_id in new_selection - current_ids:
            ok = db_enrolment.set_student_subject(
                student['aecuser_ptr_id'], cts_id, self._classroom_id, self._term_id, True) and ok
        for cts_id in current_ids - new_selection:
            ok = db_enrolment.set_student_subject(
                student['aecuser_ptr_id'], cts_id, self._classroom_id, self._term_id, False) and ok
        if not ok:
            QMessageBox.warning(self, "Erreur", "Certaines modifications ont échoué.")
        self.reload()

    def _open_class_dialog(self, group: dict):
        phi = theme_manager.phi_theme
        choices = self._choices_for_group(group, [])
        if not choices:
            QMessageBox.information(self, "Aucune matière", "Aucun slot activé dans ce groupe.")
            return

        dlg = M3Dialog(
            self, f"Toute la classe — {group['group_label']}",
            "Sélectionnez une matière puis Ajouter/Retirer pour tous les élèves actifs.",
            theme=phi)
        # Boutons d'origine du dialogue masqués : tout tient dans une seule
        # rangée ci-dessous (Fermer y compris) pour éviter deux rangées de
        # boutons disproportionnées par rapport à une liste de 1-2 matières.
        dlg.confirm_btn.hide()
        dlg.cancel_btn.hide()
        lst = M3ListWidget(theme=phi, compact=True)
        for ch in choices:
            it = QListWidgetItem(self._format_entry(ch))
            it.setData(Qt.UserRole, ch['id'])
            lst.addItem(it)
        _size_list_to_items(lst, len(choices), phi)
        dlg.layout().insertWidget(2, lst)

        btn_row = QHBoxLayout()
        add_btn = M3Button("Ajouter à tous", theme=phi, variant=ButtonVariant.FILLED)
        remove_btn = M3Button("Retirer de tous", theme=phi, variant=ButtonVariant.OUTLINED)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        close_btn = M3Button("Fermer", theme=phi, variant=ButtonVariant.TEXT)
        close_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(close_btn)
        dlg.layout().insertLayout(3, btn_row)

        def _apply(enabled: bool):
            item = lst.currentItem()
            if item is None:
                QMessageBox.information(self, "Aucune sélection", "Choisissez une matière dans la liste.")
                return
            cts_id = item.data(Qt.UserRole)
            if enabled:
                overflow = db_enrolment.count_group_overflow(
                    self._classroom_id, self._term_id, group['nr_group_in_pgm'], cts_id)
                if overflow > 0:
                    QMessageBox.warning(
                        self, "Trop de matières",
                        f"{overflow} élève(s) ont déjà {MAX_SUBJECTS_PER_GROUP} matières dans ce "
                        "groupe. Rien n'a été appliqué — corrigez leur cas individuellement "
                        "(double-clic sur leur ligne) avant de réessayer.")
                    return
            preview = db_enrolment.count_class_subject_preview(self._classroom_id, cts_id)
            total, already = preview['total_active_students'], preview['already_matching']
            would_change = (total - already) if enabled else already
            verb = "seront inscrits" if enabled else "seront désinscrits"
            resp = QMessageBox.question(
                self, "Confirmer",
                f"{total} élève(s) actif(s) — {already} déjà inscrit(s). "
                f"{would_change} {verb}. Confirmer ?",
                QMessageBox.Yes | QMessageBox.No)
            if resp != QMessageBox.Yes:
                return
            n = db_enrolment.set_class_subject(self._classroom_id, self._term_id, cts_id, enabled)
            QMessageBox.information(self, "Terminé", f"{n} ligne(s) modifiée(s).")
            dlg.accept()

        add_btn.clicked.connect(lambda checked: _apply(True))
        remove_btn.clicked.connect(lambda checked: _apply(False))

        dlg.exec()
        self.reload()


def _qcolor(hex_color: str):
    from PySide6.QtGui import QColor
    return QColor(hex_color)
