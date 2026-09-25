"""Panel Types d'événements — types actifs, et emplacements libres à renommer (gabarit)."""
import datetime
import re
import unicodedata

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QHeaderView, QTableWidgetItem, QMessageBox, QFileDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from phibuilder.widgets import (
    M3Label, M3TableWidget, M3ScrollArea, M3ComboBox, M3Button, M3Dialog, M3TextField,
)
from phibuilder.phi.scale import SpacingToken
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot
from LarcConfig.common import types_excel
from LarcConfig.common.db_access import (
    get_event_type_tree, set_event_type_active, set_event_type_label, activate_event_type,
)

_COL_ID, _COL_LEVEL, _COL_LABEL, _COL_USED, _COL_ACTIVE = range(5)
_FREE_PREFIX = "Categorie_Niv"      # libellé d'un emplacement libre : Categorie_Niv<ID parent>_Level_<rang>


def preview_text(plan, max_changes: int = 12, max_rejected: int = 8) -> str:
    """Texte de l'aperçu d'import : ce qui va changer, et ce qui est refusé (et pourquoi)."""
    labels = {'label': "renommé", 'activate': "activé", 'deactivate': "désactivé"}
    lines = [plan.summary(), ""]
    for ch in plan.changes[:max_changes]:
        lang = types_excel.SHEETS[ch.lang]
        detail = f"« {ch.old} » → « {ch.new} »" if ch.kind == 'label' else f"{ch.old} → {ch.new}"
        lines.append(f"• {ch.id} ({lang}) {labels[ch.kind]} : {detail}")
    if len(plan.changes) > max_changes:
        lines.append(f"… et {len(plan.changes) - max_changes} autre(s) modification(s).")
    if plan.rejected:
        lines += ["", "Refusé :"]
        for lang, tid, reason in plan.rejected[:max_rejected]:
            lines.append(f"• {tid} ({types_excel.SHEETS[lang]}) : {reason}")
        if len(plan.rejected) > max_rejected:
            lines.append(f"… et {len(plan.rejected) - max_rejected} autre(s) refus.")
    return "\n".join(lines)


def _slug(text: str, max_len: int) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")[:max_len].strip("_")


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

        # Ligne 1 : titre (avec la langue) et choix de la langue
        title_row = QHBoxLayout()
        self._title = M3Label("Types d'événements", theme=phi, style="headline_small")
        title_row.addWidget(self._title)
        title_row.addStretch()
        title_row.addWidget(M3Label("Langue :", theme=phi, style="body_medium"))
        self._lang_combo = M3ComboBox(["Français", "English"], theme=phi)
        self._lang_combo.currentIndexChanged.connect(self._on_view_changed)
        title_row.addWidget(self._lang_combo)
        l.addLayout(title_row)

        # Ligne 2 : affichage et filtres
        filter_row = QHBoxLayout()
        filter_row.addWidget(M3Label("Affichage :", theme=phi, style="body_medium"))
        self._view_combo = M3ComboBox(["Types", "Types + emplacements libres"], theme=phi)
        self._view_combo.currentIndexChanged.connect(self._on_view_changed)
        filter_row.addWidget(self._view_combo)
        self._filter_text = M3TextField(placeholder="Filtrer par libellé ou ID…", theme=phi)
        self._filter_text.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self._filter_text, 1)
        filter_row.addWidget(M3Label("Niveau :", theme=phi, style="body_medium"))
        self._filter_level = M3ComboBox(["Tous", "N1", "N2", "N3", "N4"], theme=phi)
        self._filter_level.currentIndexChanged.connect(self._apply_filter)
        filter_row.addWidget(self._filter_level)
        l.addLayout(filter_row)

        # Ligne 3 : actions
        action_row = QHBoxLayout()
        self._add_btn = add_btn = M3Button("Ajouter un type", theme=phi)
        add_btn.setToolTip("Active le prochain emplacement libre sous le type sélectionné "
                           "(aucune sélection : nouvelle racine)")
        add_btn.clicked.connect(self._on_add_type)
        action_row.addWidget(add_btn)
        action_row.addStretch()
        self._export_btn = export_btn = M3Button("Exporter Excel", theme=phi)
        export_btn.setToolTip("Enregistre tous les types (français et anglais) dans un fichier Excel")
        export_btn.clicked.connect(self._on_export)
        action_row.addWidget(export_btn)
        self._import_btn = import_btn = M3Button("Importer Excel", theme=phi)
        import_btn.setToolTip("Relit un fichier exporté : renommages et activations, après aperçu")
        import_btn.clicked.connect(self._on_import)
        action_row.addWidget(import_btn)
        l.addLayout(action_row)

        self._hint = M3Label("", theme=phi, style="body_small")
        l.addWidget(self._hint)
        self._where = M3Label("", theme=phi, style="body_medium")   # position du type sélectionné
        self._where.setVisible(False)
        l.addWidget(self._where)

        self._table = M3TableWidget(theme=phi)
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["ID", "Niveau", "Libellé", "Utilisé", "Actif"])
        h = self._table.horizontalHeader()
        # Colonnes réglables à la souris ; « Libellé » prend la place restante
        for col in (_COL_ID, _COL_LEVEL, _COL_USED, _COL_ACTIVE):
            h.setSectionResizeMode(col, QHeaderView.Interactive)
        h.setSectionResizeMode(_COL_LABEL, QHeaderView.Stretch)
        h.setMinimumSectionSize(ds.space_xl)
        self._table.setColumnWidth(_COL_ID, ds.space_xxl + ds.space_md)
        self._table.setColumnWidth(_COL_LEVEL, ds.space_xxl + ds.space_sm)
        self._table.setColumnWidth(_COL_USED, ds.space_xxl + ds.space_sm)
        self._table.setColumnWidth(_COL_ACTIVE, ds.space_xxl)
        self._table.setAlternatingRowColors(False)
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.currentCellChanged.connect(self._on_selection_changed)
        l.addWidget(self._table)

        self.setWidget(container)
        self.setWidgetResizable(True)

        self._user = user
        self._rows: list[dict] = []
        self._loading = False
        self.reload()

    def _fk_language(self) -> int:
        return 2 if self._lang_combo.currentIndex() == 0 else 1

    def _show_free(self) -> bool:
        return self._view_combo.currentIndex() == 1

    def reload(self):
        self._loading = True
        show_free = self._show_free()
        self._rows = get_event_type_tree(self._fk_language(), include_free=show_free)
        dim = QBrush(QColor(theme_manager.phi_theme.colors.on_surface_variant))
        self._table.setRowCount(len(self._rows))
        for i, r in enumerate(self._rows):
            indent = "    " * r['depth']
            self._table.setItem(i, _COL_ID, self._readonly_item(str(r['id'])))
            self._table.setItem(i, _COL_LEVEL, self._readonly_item(f"N{r['depth'] + 1}"))
            label_item = QTableWidgetItem(f"{indent}{r['label'] or ''}")
            label_item.setData(Qt.UserRole, r['label'] or '')
            usage = r.get('usage', 0)
            if usage:
                # type déjà utilisé : ni renommé ni désactivé (le passé changerait de sens)
                label_item.setFlags(label_item.flags() & ~Qt.ItemIsEditable)
                label_item.setToolTip(self._locked_message(usage))
            self._table.setItem(i, _COL_LABEL, label_item)
            self._table.setItem(i, _COL_USED, self._readonly_item(str(usage) if usage else ""))
            active_item = QTableWidgetItem()
            active_item.setFlags(active_item.flags() | Qt.ItemIsUserCheckable)
            active_item.setCheckState(Qt.Checked if r['enabled'] else Qt.Unchecked)
            self._table.setItem(i, _COL_ACTIVE, active_item)
            if not r['enabled']:
                for col in (_COL_ID, _COL_LEVEL, _COL_LABEL):
                    self._table.item(i, col).setForeground(dim)
        self._apply_filter()
        n_active = sum(1 for r in self._rows if r['enabled'])
        n_free = sum(1 for r in self._rows if r['is_free'])
        n_off = len(self._rows) - n_active - n_free            # types désactivés (restent visibles)
        lang = "Français" if self._fk_language() == 2 else "English"
        self._title.setText(f"Types d'événements — {lang}")
        self._show_where("")
        if self._fk_language() == 1:
            self._hint.setStyleSheet("")
        text = f"{n_active} types actifs"
        if n_off:
            text += f", {n_off} désactivés (grisés : cochez « Actif » pour les réactiver)"
        if show_free:
            text += (f", {n_free} emplacements libres (renommez-en un puis cochez « Actif », "
                     "ou utilisez « Ajouter un type »)")
        self._hint.setText(text + ".")
        if self._fk_language() == 1:
            self._hint.setText(self._hint.text() + " Arbre anglais : les libellés y sont "
                               "encore ceux du français tant qu'ils ne sont pas traduits.")
        self._loading = False

    @staticmethod
    def _readonly_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    @safe_slot("TypesPanel._apply_filter")
    def _apply_filter(self, *_args):
        """Masque les lignes qui ne correspondent ni au texte (libellé ou ID) ni au niveau."""
        text = self._filter_text.text().strip().lower()
        level = self._filter_level.currentIndex()          # 0 = tous, 1..4 = N1..N4

        for i, r in enumerate(self._rows):
            ok = (not text or text in str(r['label'] or '').lower() or text in str(r['id']))
            ok = ok and (level == 0 or r['depth'] + 1 == level)
            self._table.setRowHidden(i, not ok)
        self._show_where("")

    def _show_where(self, text: str):
        self._where.setText(text)
        self._where.setVisible(bool(text))

    def _position_of(self, rec: dict) -> str:
        """Chemin du type et plage d'IDs de sa branche (tout ce qui est en dessous)."""
        by_id = {r['id']: r for r in self._rows}
        parts, cur = [], rec
        while cur is not None:
            parts.append(cur['label'] or '')
            cur = by_id.get(cur['parent_id'])
        width = {0: 1000, 1: 100, 2: 10}.get(rec['depth'], 1)
        return (f"{' > '.join(reversed(parts))} — ID {rec['id']} "
                f"(sa branche : de {rec['id']} à {rec['id'] + width - 1})")

    @safe_slot("TypesPanel._on_selection_changed")
    def _on_selection_changed(self, row: int, _col: int, _prev_row: int, _prev_col: int):
        if self._loading or not (0 <= row < len(self._rows)):
            return
        self._show_where(self._position_of(self._rows[row]))

    @safe_slot("TypesPanel._on_view_changed")
    def _on_view_changed(self, _index: int):
        self.reload()

    @safe_slot("TypesPanel._on_item_changed")
    def _on_item_changed(self, item: QTableWidgetItem):
        if self._loading:
            return
        row = item.row()
        rec = self._rows[row]
        if item.column() == _COL_ACTIVE:
            self._on_active_toggled(rec, item.checkState() == Qt.Checked)
        elif item.column() == _COL_LABEL:
            self._on_label_edited(rec, item)

    @staticmethod
    def _locked_message(usage: int) -> str:
        return (f"Utilisé par {usage} événement(s), dans l'une ou l'autre langue, branche "
                "comprise : ce type ne peut être ni renommé ni désactivé.")

    def _on_active_toggled(self, rec: dict, enabled: bool):
        if not enabled and rec.get('usage', 0):
            QMessageBox.warning(self, "Type utilisé", self._locked_message(rec['usage']))
            self.reload()
            return
        if enabled and rec['is_free'] and str(rec['label']).startswith(_FREE_PREFIX):
            QMessageBox.warning(
                self, "Emplacement libre",
                "Renommez d'abord cet emplacement avant de l'activer.")
        elif set_event_type_active(rec['id'], enabled):
            rec['enabled'] = enabled
            if not enabled or rec['is_free']:
                rec['is_free'] = False
        self.reload()

    def _on_label_edited(self, rec: dict, item: QTableWidgetItem):
        if rec.get('usage', 0):                     # garde-fou : la cellule n'est déjà pas éditable
            self.reload()
            return
        indent = "    " * rec['depth']
        text = item.text()
        # Le texte affiché contient une indentation visuelle qui ne fait pas partie du
        # libellé : on ne la retire que si elle est encore présente (une édition
        # normale remplace tout le texte de la cellule, préfixe compris).
        new_label = (text[len(indent):] if text.startswith(indent) else text).strip()
        if not new_label:
            new_label = rec['label'] or ''
        if new_label != rec['label'] and set_event_type_label(rec['id'], new_label):
            rec['label'] = new_label
        self._loading = True
        item.setText(f"{indent}{rec['label'] or ''}")
        item.setData(Qt.UserRole, rec['label'] or '')
        self._loading = False

    @safe_slot("TypesPanel._on_add_type")
    def _on_add_type(self):
        """Active le prochain emplacement libre sous le type sélectionné, dans les 2 langues."""
        phi = theme_manager.phi_theme
        row = self._table.currentRow()
        parent = self._rows[row] if 0 <= row < len(self._rows) else None
        if parent is not None and not parent['enabled']:
            QMessageBox.warning(self, "Type inactif", "Sélectionnez un type actif comme parent.")
            return
        where = f"sous « {parent['label']} »" if parent else "à la racine"
        dlg = M3Dialog(self, "Ajouter un type", f"Nouveau type {where}.", theme=phi)
        dlg.confirm_btn.setText("Ajouter")
        dlg.cancel_btn.setText("Annuler")
        label_fr = M3TextField(placeholder="Libellé (français)", theme=phi)
        label_en = M3TextField(placeholder="Libellé (anglais, facultatif)", theme=phi)
        dlg.layout().insertWidget(2, label_fr)
        dlg.layout().insertWidget(3, label_en)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        fr = label_fr.text().strip()
        en = label_en.text().strip() or fr
        if not fr:
            QMessageBox.warning(self, "Champ requis", "Le libellé français est obligatoire.")
            return
        parent_code = parent['code'] if parent else None
        room = 64 - (len(parent_code) + 1 if parent_code else 0)
        suffix = _slug(fr, room)
        if not suffix or not activate_event_type(parent_code, suffix, fr, en):
            QMessageBox.warning(
                self, "Ajout impossible",
                "Aucun emplacement libre sous ce type (ou ce code existe déjà).")
        self.reload()

    # ------------------------------------------------------------------ Excel
    @safe_slot("TypesPanel._on_export")
    def _on_export(self):
        name = f"Types_evenements_{datetime.date.today():%Y%m%d}.xlsx"
        path, _filter = QFileDialog.getSaveFileName(self, "Exporter vers Excel", name, "Excel (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        author = f"{self._user.get('first_name', '')} {self._user.get('last_name', '')}".strip()
        try:
            types_excel.export_types_xlsx(path, author=author)
        except OSError as exc:                       # fichier ouvert dans Excel, dossier protégé…
            QMessageBox.warning(self, "Export impossible", f"Le fichier n'a pas pu être écrit :\n{exc}")
            return
        QMessageBox.information(self, "Export terminé", f"Fichier créé :\n{path}")

    def _confirm_import(self, plan) -> bool:
        phi = theme_manager.phi_theme
        dlg = M3Dialog(self, "Importer depuis Excel", preview_text(plan), theme=phi)
        dlg.cancel_btn.setText("Annuler")
        dlg.confirm_btn.setText("Appliquer")
        dlg.confirm_btn.setEnabled(bool(plan.changes))
        return dlg.exec() == dlg.DialogCode.Accepted

    @safe_slot("TypesPanel._on_import")
    def _on_import(self):
        path, _filter = QFileDialog.getOpenFileName(self, "Importer depuis Excel", "", "Excel (*.xlsx)")
        if not path:
            return
        try:
            sheets = types_excel.read_types_xlsx(path)
        except Exception as exc:                     # fichier illisible ou mauvais classeur
            QMessageBox.warning(self, "Import impossible", f"Ce fichier n'a pas pu être lu :\n{exc}")
            return
        current = {lang: get_event_type_tree(lang, include_free=True) for lang in types_excel.SHEETS}
        plan = types_excel.plan_import(sheets, current)
        if not plan.changes and not plan.rejected:
            QMessageBox.information(self, "Import", "Aucune différence avec l'état actuel.")
            return
        if not self._confirm_import(plan):
            return
        done, failed = types_excel.apply_plan(plan)
        self.reload()
        text = f"{done} modification(s) appliquée(s)."
        if failed:
            text += "\n\nNon appliquées :\n" + "\n".join(failed[:8])
        QMessageBox.information(self, "Import terminé", text)
