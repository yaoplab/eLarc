"""Fenêtre principale — Espace de travail du professeur.

Top bar (toujours visible) : matière-classe, formatives, sommatives, jugements.
Workspace (après sélection) : grille élèves × notes + barre actions.
"""
from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QAction, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStatusBar,
    QStyle,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from larccommon.design_system import ds



from common.database import db
from common.logger import log
from common.session import session
from common.theme import theme_manager, ZONE_F_COLOR, ZONE_S_COLOR, ZONE_NEUTRAL, ZONE_TEXT_LIGHT
from common.grid_config import pei_config
from views.eval_manager import EvalManagerWindow
from views.grid_table import ColorItem, _note_gradient, ZoneHeaderView
from larccommon.safe_slot import safe_slot






class NotesGridMixin:
    """Mixin NotesGridMixin — voir le module parent."""

    def _restyle_all(self) -> None:
        """Hook de restyle piloté par le parent (règle D6).

        La classe composante (MainWindow) connecte theme_changed → son
        _restyle() reconstruit la grille (styles palette posés ici).
        """

    def _update_icons(self, eval_type: str, evals: list[dict], widgets: dict):
        """Construit la liste scrollable des slots actifs."""
        # Nettoyer les anciennes rangées
        layout = widgets['scroll_content'].layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        visible_set = self._visible_f if eval_type == 'F' else self._visible_s
        active_count = sum(1 for e in evals if e['is_active'])
        new_rows = {}

        for e in evals:
            if not e['is_active']:
                continue
            idx = e['index']
            is_visible = idx in visible_set

            # Rangée cliquable
            row = QFrame()
            row.setFrameShape(QFrame.StyledPanel)
            row.setAttribute(Qt.WA_StyledBackground, True)
            if is_visible:
                row.setStyleSheet(
                    f"QFrame {{ background: {theme_manager.theme.palette.primary_container}; "
                    f"border: 1px solid {theme_manager.theme.palette.active}; "
                    f"border-left: 3px solid {theme_manager.theme.palette.primary}; "
                    f"border-radius: {ds.radius_xs}px; }}"
                )
            else:
                row.setStyleSheet(
                    f"QFrame {{ background: {theme_manager.theme.palette.background}; "
                    f"border: 1px solid {theme_manager.theme.palette.border}; "
                    f"border-radius: {ds.radius_xs}px; }}"
                )
            row.setCursor(Qt.PointingHandCursor)

            rh = QHBoxLayout(row)
            rh.setContentsMargins(ds.space_xxs, 1, ds.space_xxs, 1)
            rh.setSpacing(ds.space_xxs)

            # Index
            idx_lbl = QLabel(f'{eval_type}{idx:02d}')
            idx_lbl.setFixedWidth(ds.idx_label_width)
            idx_lbl.setFont(theme_manager.font(theme_manager.theme.fonts.small, QFont.Bold))
            idx_lbl.setStyleSheet(f"color: {theme_manager.theme.palette.text_strong}; border: none;")
            rh.addWidget(idx_lbl)

            # Nature (le label DB est redondant avec idx_lbl, on remplace par nature)
            nature_txt = (e.get('nature') or '')
            if len(nature_txt) > 22:
                nature_txt = nature_txt[:20] + '…'
            lbl_nature = QLabel(nature_txt)
            lbl_nature.setFixedWidth(ds.nature_label_width)
            lbl_nature.setFont(theme_manager.font(theme_manager.theme.fonts.small))
            lbl_nature.setStyleSheet(f"color: {theme_manager.theme.palette.text_strong}; border: none;")
            rh.addWidget(lbl_nature)

            if e.get('nature', ''):
                rh.addSpacing(ds.space_xs)

            # Critères — lettres à positions fixes (A, B, C, D alignés entre tous les slots)
            crits_box = QHBoxLayout()
            crits_box.setSpacing(0)
            for l in ('a', 'b', 'c', 'd'):
                ltr_lbl = QLabel(l.upper() if e.get(f'crit_{l}', '0') == '1' else '')
                ltr_lbl.setFixedWidth(ds.crit_letter_width)
                ltr_lbl.setFont(theme_manager.font(theme_manager.theme.fonts.small, QFont.Bold))
                ltr_lbl.setStyleSheet(
                    f"font-weight: bold; color: {theme_manager.theme.palette.active}; border: none;"
                )
                crits_box.addWidget(ltr_lbl)
            rh.addLayout(crits_box)

            rh.addStretch()

            # Rendre cliquable
            row.mousePressEvent = lambda event, ev=eval_type, si=idx: self._on_slot_icon_clicked(ev, si)

            layout.addWidget(row)
            new_rows[idx] = row

        # Message si aucun slot actif
        if active_count == 0:
            empty_lbl = QLabel('Aucune évaluation active')
            empty_lbl.setProperty('class', 'placeholder')
            empty_lbl.setFont(theme_manager.font(theme_manager.theme.fonts.small))
            empty_lbl.setStyleSheet(f"color: {theme_manager.theme.palette.inactive}; padding: {ds.space_xxs}px;")
            layout.addWidget(empty_lbl)

        layout.addStretch()
        widgets['slot_rows'] = new_rows

        # Boutons Toute/Aucune/Commentaire : variante claire pour les deux
        # panneaux (fonds neutres clairs — plus de panneau sombre pour S)
        dark = False
        all_visible = len(visible_set) == active_count and active_count > 0
        none_visible = len(visible_set) == 0
        widgets['tout_btn'].setChecked(all_visible)
        widgets['tout_btn'].setStyleSheet(self._btn_toggle_style(all_visible, dark=dark))
        widgets['aucune_btn'].setChecked(none_visible)
        widgets['aucune_btn'].setStyleSheet(self._btn_toggle_style(none_visible, dark=dark))
        comment_key = '_show_f_comment' if eval_type == 'F' else '_show_s_comment'
        show_comm = getattr(self, comment_key, False)
        widgets['comm_btn'].setChecked(show_comm)
        widgets['comm_btn'].setStyleSheet(self._btn_toggle_style(show_comm, dark=dark))

    # ------------------------------------------------------------------
    # Gestionnaires des interactions Top bar
    # ------------------------------------------------------------------

    def _on_slot_icon_clicked(self, eval_type: str, slot_index: int):
        """Clic sur une icône de slot : bascule l'affichage dans la grille."""
        evals = self._evals_f if eval_type == 'F' else self._evals_s
        visible_set = self._visible_f if eval_type == 'F' else self._visible_s

        is_active = False
        for e in evals:
            if e['index'] == slot_index and e['is_active']:
                is_active = True
                break
        if not is_active:
            return

        # Mémoriser le dernier clic pour le détail
        if eval_type == 'F':
            self._last_clicked_f = slot_index
        else:
            self._last_clicked_s = slot_index

        if slot_index in visible_set:
            visible_set.discard(slot_index)
        else:
            visible_set.add(slot_index)

        self._on_selection_changed()

    def _on_toggle_all(self, eval_type: str):
        """Bascule : affiche tous les slots actifs ou les masque."""
        evals = self._evals_f if eval_type == 'F' else self._evals_s
        visible_set = self._visible_f if eval_type == 'F' else self._visible_s

        active_indices = {e['index'] for e in evals if e['is_active']}
        if visible_set == active_indices:
            visible_set.clear()
            if eval_type == 'F':
                self._last_clicked_f = None
            else:
                self._last_clicked_s = None
        else:
            visible_set.clear()
            visible_set.update(active_indices)
            # Premier actif comme dernier clic
            for e in evals:
                if e['is_active']:
                    if eval_type == 'F':
                        self._last_clicked_f = e['index']
                    else:
                        self._last_clicked_s = e['index']
                    break
        self._on_selection_changed()

    def _on_toggle_none(self, eval_type: str):
        """Masque tous les slots de ce type."""
        visible_set = self._visible_f if eval_type == 'F' else self._visible_s
        visible_set.clear()
        if eval_type == 'F':
            self._last_clicked_f = None
        else:
            self._last_clicked_s = None
        self._on_selection_changed()

    def _on_toggle_comment(self, eval_type: str):
        """Affiche/masque la colonne commentaire pour ce type."""
        key = '_show_f_comment' if eval_type == 'F' else '_show_s_comment'
        setattr(self, key, not getattr(self, key))
        self._on_selection_changed()

    def _on_toggle_crit(self, letter: str):
        """Affiche/masque une colonne critère dans la grille."""
        self._visible_crits[letter] = not self._visible_crits[letter]
        self._crit_btns[letter].setStyleSheet(self._btn_crit_style(self._visible_crits[letter]))
        self._on_selection_changed()

    @safe_slot("Unknown._on_jgt_toggle")
    def _on_jgt_toggle(self):
        """Bascule l'affichage des 4 colonnes jugement."""
        checked = self._jwidgets['jgt_btn'].isChecked()
        self._jwidgets['jgt_btn'].setStyleSheet(self._btn_toggle_style(checked))
        self._on_selection_changed()

    @safe_slot("Unknown._on_jgt_note_toggle")
    def _on_jgt_note_toggle(self):
        """Bascule visibilité colonne note sur 7."""
        checked = self._jwidgets['note_btn'].isChecked()
        self._jwidgets['note_btn'].setStyleSheet(self._btn_toggle_style(checked))
        self._on_selection_changed()

    @safe_slot("Unknown._on_jgt_comment_toggle")
    def _on_jgt_comment_toggle(self):
        """Bascule visibilité commentaire jugements."""
        self._show_jgt_comment = not self._show_jgt_comment
        self._jwidgets['comm_btn'].setStyleSheet(
            self._btn_toggle_style(self._show_jgt_comment))
        self._on_selection_changed()

    def _on_selection_changed(self):
        """Recharge la grille apres un changement de selection."""
        self._save_grid_edits()
        self._auto_compute_judgments_and_note()
        if self._current_item is None:
            return
        item = self._current_item
        class_id = item['class_id']
        cycle = item['cycle']
        eleves = self._eleves_par_classe.get(class_id, [])
        self._update_top_bar()
        self._fill_grille(item, cycle, eleves)

    def _clear_grille(self):
        """Vide la grille tout en gardant le layout."""
        if self._grille is not None:
            self._grille.setRowCount(0)
            self._grille.setColumnCount(0)
            self._grille.setRowCount(0)
            self._grille.setColumnCount(0)
        self._visible_f.clear()
        self._visible_s.clear()
        self._current_item = None

    def _fill_grille(self, item: dict, cycle: str, eleves: list[dict]) -> None:
        """Remplit la grille élèves × notes avec les colonnes sélectionnées."""
        if self._grille is None:
            return

        conn = db.local_conn
        if conn is None:
            return

        # Bloquer les signaux pendant le remplissage
        self._grille.blockSignals(True)
        self._dirty_cells.clear()

        # Le tri actif réordonne les lignes à CHAQUE insertion d'item pendant
        # le remplissage → les items se mélangent entre élèves (une case à
        # cocher « Validé » pouvait se retrouver dans la colonne d'une note).
        # On coupe le tri pendant le remplissage, puis on réapplique l'ordre
        # de tri courant (indicateur du header) une fois la grille remplie.
        _hdr = self._grille.horizontalHeader()
        _sort_col = _hdr.sortIndicatorSection()
        _sort_asc = _hdr.sortIndicatorOrder() == Qt.AscendingOrder
        self._grille.setSortingEnabled(False)

        # --- 1. Déterminer les colonnes à afficher selon les sélections ---
        synth_display = 'note_on_7' if cycle == 'PEI' else 'moy_on_20'
        table = ('larcauth_learnerpei_has_termsubjectpei' if cycle == 'PEI'
                 else 'larcauth_learnerdp_has_termsubjectdp')

        visible_db_cols: list[str] = []

        # Lookup rapide critères par évaluation
        _eval_crits: dict[str, dict[int, dict[str, bool]]] = {'F': {}, 'S': {}}
        for et, evals in (('F', self._evals_f), ('S', self._evals_s)):
            for e in evals:
                _eval_crits[et][e['index']] = {
                    'a': e.get('crit_a', '0') == '1',
                    'b': e.get('crit_b', '0') == '1',
                    'c': e.get('crit_c', '0') == '1',
                    'd': e.get('crit_d', '0') == '1',
                }

        def _crit_visible(eval_type: str, idx: int, crit: str) -> bool:
            if not self._visible_crits.get(crit, False):
                return False
            ec = _eval_crits.get(eval_type, {}).get(idx, {})
            return ec.get(crit, False)

        # Colonnes des slots formatives visibles
        for slot_idx in sorted(self._visible_f):
            for crit in ('a', 'b', 'c', 'd'):
                if _crit_visible('F', slot_idx, crit):
                    db_name = f'f{slot_idx:02d}_note_{crit}'
                    visible_db_cols.append(db_name)
            if self._show_f_comment:
                visible_db_cols.append(f'f{slot_idx:02d}_observation')

        # Colonnes des slots sommatives visibles
        for slot_idx in sorted(self._visible_s):
            for crit in ('a', 'b', 'c', 'd'):
                if _crit_visible('S', slot_idx, crit):
                    db_name = f's{slot_idx:02d}_note_{crit}'
                    visible_db_cols.append(db_name)
            if self._show_s_comment:
                visible_db_cols.append(f's{slot_idx:02d}_observation')

        # Jugements — uniquement les critères sélectionnés (cohérence avec
        # les colonnes de notes : un critère désélectionné disparaît partout)
        if self._jwidgets['jgt_btn'].isChecked():
            for letter in ('a', 'b', 'c', 'd'):
                if self._visible_crits.get(letter, False):
                    visible_db_cols.append(f'jgt_{letter}')
        if self._jwidgets['note_btn'].isChecked():
            visible_db_cols.append(synth_display)
            visible_db_cols.append('_note_validated')  # colonne virtuelle pour checkbox
        if self._show_jgt_comment:
            visible_db_cols.append('term_observation')

        # --- 2. Vérifier quelles colonnes existent dans la table ---
        existing_db_cols: set[str] = set()
        try:
            cur = conn.execute(f'PRAGMA table_info("{table}")')
            for row in cur.fetchall():
                existing_db_cols.add(row[1])
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"Lecture du schéma de la table {table} impossible : {e}")

        def _nature_for_prefix(col_name: str, idx: int) -> str:
            evals = self._evals_f if col_name.startswith('f') else self._evals_s
            for e in evals:
                if e['index_eval'] == idx:
                    return e.get('nature', '') or ''
            return ''

        existing_visible = [c for c in visible_db_cols if c in existing_db_cols or c == '_note_validated']

        # --- 3. Noms d'affichage ---
        display_names = []
        for c in existing_visible:
            if c.startswith('f') and '_note_' in c:
                parts = c.split('_')
                if c.endswith('_nature') or 'nature' in c:
                    idx = int(parts[0][1:]) if parts[0][1:].isdigit() else 0
                    nat = _nature_for_prefix(c, idx)
                    display_names.append(nat if nat else 'Nature')
                else:
                    display_names.append(f'F{parts[0][1:]}_{parts[-1].upper()}')
            elif c.startswith('s') and '_note_' in c:
                parts = c.split('_')
                if c.endswith('_nature') or 'nature' in c:
                    idx = int(parts[0][1:]) if parts[0][1:].isdigit() else 0
                    nat = _nature_for_prefix(c, idx)
                    display_names.append(nat if nat else 'Nature')
                else:
                    display_names.append(f'S{parts[0][1:]}_{parts[-1].upper()}')
            elif c.startswith('jgt_'):
                display_names.append(f'Jgt {c[-1].upper()}')
            elif c == synth_display:
                display_names.append('Note' if cycle == 'PEI' else 'Moy.')
            elif c.endswith('_observation'):
                display_names.append(f'{c[0].upper()} Obs.')
            elif c == 'term_observation':
                display_names.append('Obs. Terme')
            elif c == '_note_validated':
                display_names.append('Valide')
            else:
                display_names.append(c)

        # Configurer la grille unique
        self._grille.setColumnCount(1 + len(display_names))
        self._grille.setHorizontalHeaderLabels(['Élève'] + display_names)

        # Entêtes : fond par zone via ZoneHeaderView (paintEvent). Les items
        # ne portent que le texte (setHorizontalHeaderLabels ci-dessus) — le
        # BackgroundRole et un delegate sont ignorés par QHeaderView.
        p = theme_manager.theme.palette
        zone_bgs: list = [QColor(ZONE_NEUTRAL)]   # colonne 0 = Élève
        zone_fgs: dict = {0: QColor(p.text_strong)}
        for col, db_name in enumerate(existing_visible, start=1):
            if db_name.startswith('f'):
                zone_bgs.append(QColor(ZONE_F_COLOR))      # formatives = bleu ciel
                zone_fgs[col] = QColor(ZONE_TEXT_LIGHT)
            elif db_name.startswith('s'):
                zone_bgs.append(QColor(ZONE_S_COLOR))      # sommatives = bleu marine
                zone_fgs[col] = QColor(ZONE_TEXT_LIGHT)
            else:
                zone_bgs.append(QColor(ZONE_NEUTRAL))      # élève/validé/obs.
                zone_fgs[col] = QColor(p.text_strong)
        hdr = self._grille.horizontalHeader()
        if isinstance(hdr, ZoneHeaderView):
            hdr.set_zone_colors(zone_bgs, zone_fgs)
        row_count = len(eleves)
        self._grille.setRowCount(row_count)

        # --- 4. Charger les notes — scoped par CTS, matchées par fk_student_id ---
        ts_id = item['termsubject_id']
        notes: dict[int, dict[str, str]] = {}
        self._row_ids: dict[int, int] = {}
        if existing_visible:
            has_fk = False
            fk_col = 'fk_student_id'
            try:
                cur = conn.execute(f'PRAGMA table_info("{table}")')
                for col in cur.fetchall():
                    if col[1] == 'fk_student_id':
                        has_fk = True
                        fk_col = 'fk_student_id'
                        break
                    if col[1] == 'learner_has_termsubject_ptr_id':
                        has_fk = True
                        fk_col = 'learner_has_termsubject_ptr_id'
                        # continue checking — fk_student_id preferred
            except Exception as e:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                log(f"Vérification de la colonne fk_student_id impossible : {e}")

            if has_fk:
                # Remplacer _note_validated (virtuel) par note_on_7_checked (reel)
                select_list = ['id', fk_col]
                for c in existing_visible:
                    if c == '_note_validated':
                        if 'note_on_7_checked' not in select_list:
                            select_list.append('note_on_7_checked')
                    else:
                        select_list.append(c)
                try:
                    cols_sql = ', '.join(f'"{c}"' for c in select_list)
                    rows = conn.execute(
                        f'SELECT {cols_sql} FROM "{table}"'
                    ).fetchall()
                    for r in rows:
                        pei_id = int(r[0] or 0)
                        student_id = int(r[1] or 0)
                        if not student_id or not pei_id:
                            continue
                        row_dict: dict[str, str] = {}
                        for ci, cn in enumerate(select_list):
                            row_dict[cn] = r[ci] if r[ci] is not None else ''
                        notes[student_id] = row_dict
                        self._row_ids[student_id] = pei_id
                except Exception as e:
                    from larccommon.error_reporting import get_reporter
                    get_reporter().report_exception()
                    log(f"Erreur chargement notes: {e}")
            else:
                self.statusBar().showMessage(
                    'Données ancienne génération — relancez --mode4 pour les notes'
                )

        # --- 5. Remplir la grille ---
        self._valid_states: dict[int, bool] = {}  # student_id -> case « Validé » cochée
        for row_idx, eleve in enumerate(eleves):
            # Colonne 0 : nom élève
            name_txt = (f"{eleve['prenom']} {eleve['nom']}" if self._name_format_prenom_first
                        else f"{eleve['nom']} {eleve['prenom']}")
            item_eleve = QTableWidgetItem(name_txt)
            item_eleve.setFlags(item_eleve.flags() & ~Qt.ItemIsEditable)
            item_eleve.setData(Qt.UserRole, eleve['id'])
            item_eleve.setData(Qt.UserRole + 1, eleve['nom'])
            item_eleve.setData(Qt.UserRole + 2, eleve['prenom'])
            item_eleve.setTextAlignment(Qt.AlignCenter)
            # Fond gris clair neutre — parallèle visuel avec la zone 1 du sidebar
            item_eleve.setData(Qt.UserRole + 3, QColor(ZONE_NEUTRAL))
            self._grille.setItem(row_idx, 0, item_eleve)

            # Colonnes 1..N : notes
            eleve_notes = notes.get(eleve['id'], {})
            for ci, db_name in enumerate(existing_visible):
                if db_name == '_note_validated':
                    # Colonne virtuelle « Validé » : vrai QCheckBox posé dans
                    # la cellule (setCellWidget). Un item QTableWidgetItem
                    # checkable se re-basculait deux fois (bascule native Qt
                    # + mouseReleaseEvent de ClipboardTable) : un clic sur la
                    # case ne laissait rien coche. Le QCheckBox est un vrai
                    # composant : clic fiable, retour visuel net. Apres un
                    # tri, _resync_validated_widgets recale les cases.
                    checked = eleve_notes.get('note_on_7_checked', '') in ('1', 'True', 'true', True)
                    self._valid_states[eleve['id']] = checked
                    cb = QCheckBox()
                    cb.setChecked(checked)  # avant connexion : pas d'écriture au chargement
                    cb.setToolTip('Valider la note /7')
                    cb.stateChanged.connect(
                        partial(self._on_validated_toggled, eleve['id']))
                    # Centrage de la case dans la cellule
                    wrap = QWidget()
                    lay = QHBoxLayout(wrap)
                    lay.setContentsMargins(0, 0, 0, 0)
                    lay.setAlignment(Qt.AlignCenter)
                    lay.addWidget(cb)
                    self._grille.setCellWidget(row_idx, ci + 1, wrap)
                    continue

                val = eleve_notes.get(db_name, '')

                item_bg: QColor | None = None

                is_synth = (db_name == synth_display)
                is_note_col = '_note_' in db_name or is_synth
                if is_note_col:
                    # Format conditionnel rouge→vert selon la valeur (conservé)
                    item_bg = _note_gradient(val, cycle)

                item = ColorItem(str(val), item_bg)
                item.setTextAlignment(Qt.AlignCenter)
                self._grille.setItem(row_idx, ci + 1, item)

        self._current_table = table
        self._current_col_names = existing_visible
        self._current_student_ids = [e['id'] for e in eleves]
        # Largeur colonnes notes (décalage de 1 pour la colonne élève)
        if pei_config:
            self._grille.setColumnWidth(0, pei_config.student_width)
            for ci, db_name in enumerate(existing_visible):
                is_obs = '_observation' in db_name or db_name == 'term_observation'
                if is_obs:
                    self._grille.setColumnWidth(ci + 1, pei_config.remark_width)
                else:
                    self._grille.setColumnWidth(ci + 1, pei_config.note_width)

        # Réappliquer l'ordre de tri courant (les lignes bougent en bloc avec
        # leurs items — plus de mélange), puis réactiver le tri.
        if _sort_col >= 0:
            self._grille.sortItems(
                _sort_col,
                Qt.AscendingOrder if _sort_asc else Qt.DescendingOrder)
        self._grille.setSortingEnabled(True)

        self._grille.blockSignals(False)
        # Le tri (restauré ci-dessus) déplace les items mais laisse les
        # QCheckBox « Validé » en place — recaler les cases sur les lignes.
        self._resync_validated_widgets()

    @safe_slot("Unknown._on_cell_changed")
    def _on_cell_changed(self, row: int, col: int) -> None:
        if row < 0 or row >= self._grille.rowCount():
            return
        if col <= 0 or col - 1 >= len(self._current_col_names):
            return  # colonne 0 = nom élève (non-éditable)
        item_name = self._grille.item(row, 0)
        student_id = item_name.data(Qt.UserRole) if item_name else None
        if student_id is None:
            return
        db_name = self._current_col_names[col - 1]
        item = self._grille.item(row, col)
        # Colonne « Valide » : aucun item checkable — c'est un vrai QCheckBox
        # posé via setCellWidget (voir _fill_grille) ; sa bascule passe par
        # _on_validated_toggled, jamais par cellChanged.
        val = item.text().strip() if item else ''

        # Recalculer le gradient pour cette cellule
        if isinstance(item, ColorItem) and ('_note_' in db_name or db_name in ('note_on_7', 'moy_on_20')):
            item.set_bg(_note_gradient(val, self._current_cycle))

        self._dirty_cells[(student_id, db_name)] = val
        self.statusBar().showMessage('Modifications non sauvegardées')

        # Recalcul immediat (PEI) apres saisie d'une note : les jugements
        # d'abord (jgt_a..d), puis la note/7 — depuis les cellules en cours
        # d'edition pour ne pas lire des valeurs non encore enregistrees.
        if self._current_cycle == 'PEI' and '_note_' in db_name:
            self._live_recompute(student_id)

        # Toute modification de note, jugement ou note/7 invalide la
        # validation : le calcul a ete redeclenche (notes) ou l'enseignant
        # a corrige lui-meme un calcul (jugements / note/7 saisis a la main).
        if ('_note_' in db_name or db_name.startswith('jgt_')
                or db_name in ('note_on_7', 'moy_on_20')):
            self._invalidate_note(student_id)

    @safe_slot("Unknown._on_cell_double_clicked")
    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        """Double-clic sur la colonne eleve → ouvre la fiche detaillee.
        Double-clic sur une cellule de notes → laisse l'edition inline."""
        if col != 0:
            return
        item_name = self._grille.item(row, 0)
        student_id = item_name.data(Qt.UserRole) if item_name else None
        if student_id is not None:
            self._open_student_card(student_id)

    def _open_student_card(self, student_id: int) -> None:
        """Ouvre la fiche detaillee d'un eleve (attributs du MainWindow)."""
        if self._current_item is None or self._current_ts_id is None:
            return
        from views.student_card_view import StudentCardView
        item = self._current_item
        label = f"{item['matiere_label']} - {item['class_label']}"
        dlg = StudentCardView(self._current_ts_id, label, item['class_id'],
                              self._current_cycle, self)
        dlg.exec()

    @safe_slot("Unknown._on_header_section_clicked")
    def _on_header_section_clicked(self, col: int) -> None:
        if col != 0:
            return
        self._name_format_prenom_first = not self._name_format_prenom_first
        for row in range(self._grille.rowCount()):
            item = self._grille.item(row, 0)
            if item:
                nom = item.data(Qt.UserRole + 1)
                prenom = item.data(Qt.UserRole + 2)
                if nom and prenom:
                    item.setText(f"{prenom} {nom}" if self._name_format_prenom_first
                                 else f"{nom} {prenom}")

    def _save_grid_edits(self) -> int:
        """Sauvegarde les cellules modifiées dans SQLite. Retourne le nombre de cellules sauvegardées."""
        conn = db.local_conn
        if conn is None or not self._dirty_cells:
            return 0
        table = getattr(self, '_current_table', None)
        if table is None:
            return 0
        log(f'[SAVE] {len(self._dirty_cells)} cellules à sauvegarder dans {table}')
        saved = 0
        try:
            for (student_id, db_name), val in list(self._dirty_cells.items()):
                pei_id = self._row_ids.get(student_id)
                if pei_id is None:
                    continue
                conn.execute(
                    f'UPDATE "{table}" SET "{db_name}" = ? WHERE id = ?',
                    (val, pei_id)
                )
                saved += 1
            conn.commit()
            self._dirty_cells.clear()
            log(f'[SAVE] {saved} cellule(s) sauvegardée(s)')
            if saved:
                self.statusBar().showMessage(f'{saved} cellule(s) sauvegardée(s)')
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f'[SAVE] Erreur: {e}')
            self.statusBar().showMessage(f'Erreur sauvegarde: {e}')
        return saved

    def _auto_compute_judgments_and_note(self) -> None:
        """Calcule automatiquement les jugements (jgt_a..d) et la note/7
        pour tous les eleves de la matiere-classe courante.
        Ne fait rien si pas de termsubject selectionne ou si cycle DP."""
        if self._current_ts_id is None or not self._current_student_ids:
            return
        if self._current_cycle == 'DP':
            return  # DP: calcul different (a implementer plus tard)

        conn = db.local_conn
        if conn is None:
            return

        self._build_evals_by_crit()
        for student_id in self._current_student_ids:
            if self._row_ids.get(student_id) is not None:
                self._recompute_one_student(student_id)
        conn.commit()

    def _build_evals_by_crit(self) -> None:
        """Construit le cache des evaluations actives par critere
        (type, index) pour le termsubject courant."""
        conn = db.local_conn
        evals_by_crit: dict[str, list[tuple[str, int]]] = {'A': [], 'B': [], 'C': [], 'D': []}
        evals_rows = conn.execute("""
            SELECT type_evaluation, index_eval, crit_a, crit_b, crit_c, crit_d
            FROM larcauth_evaluation
            WHERE fk_classroom_termsubject_id = ? AND CAST(index_eval AS INTEGER) BETWEEN 1 AND 12
        """, (str(self._current_ts_id),)).fetchall()
        for r in evals_rows:
            etype = str(r[0]).strip().upper()
            idx = int(r[1])
            for i, crit in enumerate(('A', 'B', 'C', 'D')):
                if str(r[2 + i]).strip() in ('1', 'TRUE', 'ON'):
                    evals_by_crit[crit].append((etype, idx))
        self._evals_by_crit = evals_by_crit

    def _recompute_one_student(self, student_id: int,
                               override: dict[str, str] | None = None
                               ) -> tuple[Optional[float], dict[str, int]]:
        """Recalcule jugements (jgt_a..d) puis note/7 d'un eleve, ecrit en base.
        Retourne (note, jgt_values) — note None si pas de donnees.

        override : cellules de notes en cours de saisie (non enregistrees),
        {nom_colonne: valeur str} — elles remplacent la base pour le calcul.
        Memes regles que la boucle historique de _auto_compute_judgments_and_note."""
        conn = db.local_conn
        if conn is None or self._current_ts_id is None:
            return None, {}
        table = 'larcauth_learnerpei_has_termsubjectpei'
        learner_id = self._row_ids.get(student_id)
        if learner_id is None:
            return None, {}
        if not getattr(self, '_evals_by_crit', None):
            self._build_evals_by_crit()

        # Ponderation F/S (meme logique que CalcEngine._compute_pei) :
        # jugement = moy(F) x wf + moy(S) x ws, arrondi a l'entier (jamais de virgule)
        from common.calc_engine import CalcEngine
        formula = CalcEngine.get_formula(self._current_ts_id)
        wf = formula.get("formative_weight", 0.4)
        ws = formula.get("summative_weight", 0.6)

        # Jugements par critere : moyenne ponderée F/S puis arrondi entier.
        # Un critère désélectionné dans le top bar est exclu du calcul
        # (cohérence avec l'affichage : il disparaît de la grille).
        jgt_values = {}
        for crit in ('A', 'B', 'C', 'D'):
            if not self._visible_crits.get(crit.lower(), True):
                continue
            f_vals, s_vals = [], []
            for etype, idx in self._evals_by_crit[crit]:
                col = f"{etype[0].lower()}{idx:02d}_note_{crit.lower()}"
                row = conn.execute(
                    f'SELECT "{col}" FROM "{table}" WHERE id = ?',
                    (learner_id,)
                ).fetchone()
                if override is not None and col in override:
                    # Saisie en cours (non encore enregistree) : la valeur
                    # live remplace celle de la base.
                    raw = override[col]
                    if raw not in (None, ''):
                        (f_vals if etype in ("F", "FORMATIVES") else s_vals).append(float(raw))
                elif row and row[0] is not None:
                    (f_vals if etype in ("F", "FORMATIVES") else s_vals).append(float(row[0]))
            f_mean = sum(f_vals) / len(f_vals) if f_vals else None
            s_mean = sum(s_vals) / len(s_vals) if s_vals else None
            if f_mean is not None and s_mean is not None:
                jgt_values[crit.lower()] = round(f_mean * wf + s_mean * ws)
            elif s_mean is not None:
                jgt_values[crit.lower()] = round(s_mean)
            elif f_mean is not None:
                jgt_values[crit.lower()] = round(f_mean)

        # Mettre a jour les jugements en base
        if jgt_values:
            cols = ', '.join(f'"{f"jgt_{k}"}" = ?' for k in jgt_values)
            params = list(jgt_values.values()) + [learner_id]
            conn.execute(f'UPDATE "{table}" SET {cols} WHERE id = ?', params)

        # Calculer la note/7 via CalcEngine, avec les critères
        # effectifs (désélectionnés dans le top bar) : le mode de
        # calcul s'adapte au nombre de critères restants.
        active_crits = [c for c in ('A', 'B', 'C', 'D')
                        if self._visible_crits.get(c.lower(), True)]
        note = CalcEngine.compute_note(student_id, self._current_ts_id,
                                       active_crits=active_crits,
                                       override=override)
        if note is not None:
            conn.execute(
                f'UPDATE "{table}" SET note_on_7 = ? WHERE id = ?',
                (note, learner_id)
            )
        return note, jgt_values

    def _save_note_validation(self, student_id: int, checked: bool) -> None:
        """Sauvegarde la validation note_on_7_checked pour un eleve.
        Le calcul (jugements puis note/7) se fait a la saisie, pas ici."""
        conn = db.local_conn
        if conn is None or self._current_ts_id is None:
            return
        table = ('larcauth_learnerpei_has_termsubjectpei' if self._current_cycle == 'PEI'
                 else 'larcauth_learnerdp_has_termsubjectdp')
        learner_id = self._row_ids.get(student_id)
        if learner_id is None:
            return
        conn.execute(
            f'UPDATE "{table}" SET note_on_7_checked = ? WHERE id = ?',
            (1 if checked else 0, learner_id)
        )
        conn.commit()

    @safe_slot("Unknown._on_validated_toggled")
    def _on_validated_toggled(self, student_id: int, state: int) -> None:
        """Clic sur la case « Valide » (QCheckBox de la grille) :
        sauvegarde directe de note_on_7_checked, sans recalcul."""
        checked = state == Qt.Checked.value if isinstance(state, int) else bool(state)
        self._valid_states[student_id] = checked
        self._save_note_validation(student_id, checked)

    def _resync_validated_widgets(self) -> None:
        """Recale les QCheckBox « Valide » sur les lignes apres un tri :
        Qt deplace les items mais laisse les cellWidgets en place."""
        try:
            vcol = self._current_col_names.index('_note_validated') + 1
        except ValueError:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return
        for r in range(self._grille.rowCount()):
            it = self._grille.item(r, 0)
            if it is None:
                continue
            sid = it.data(Qt.UserRole)
            if sid is None:
                continue
            cw = self._grille.cellWidget(r, vcol)
            if cw is None:
                continue
            cb = cw.findChild(QCheckBox)
            if cb is None:
                continue
            cb.blockSignals(True)
            cb.setChecked(self._valid_states.get(sid, False))
            cb.blockSignals(False)

    def _invalidate_note(self, student_id: int) -> None:
        """Toute modification de note, jugement ou note/7 d'un eleve invalide
        la validation : le calcul a ete redeclenche (notes) ou l'enseignant
        a corrige lui-meme un calcul (jugements / note/7 saisis a la main).
        La validation redevient donc false et la case « Valide » se decoche."""
        conn = db.local_conn
        if conn is None or self._current_ts_id is None:
            return
        table = ('larcauth_learnerpei_has_termsubjectpei' if self._current_cycle == 'PEI'
                 else 'larcauth_learnerdp_has_termsubjectdp')
        learner_id = self._row_ids.get(student_id)
        if learner_id is None:
            return
        conn.execute(
            f'UPDATE "{table}" SET note_on_7_checked = 0 WHERE id = ?',
            (learner_id,)
        )
        conn.commit()
        # Decocher la case « Valide » dans la grille (le QCheckBox de la
        # cellule — sans re-declencher sa sauvegarde, deja faite en base)
        for i, name in enumerate(self._current_col_names):
            if name != '_note_validated':
                continue
            col = i + 1
            for r in range(self._grille.rowCount()):
                it = self._grille.item(r, 0)
                if it is not None and it.data(Qt.UserRole) == student_id:
                    cw = self._grille.cellWidget(r, col)
                    if cw is not None:
                        cb = cw.findChild(QCheckBox)
                        if cb is not None:
                            cb.blockSignals(True)
                            cb.setChecked(False)
                            cb.blockSignals(False)
                    self._valid_states[student_id] = False
                    return

    def _live_recompute(self, student_id: int) -> None:
        """Recalcul immediat apres saisie d'une note (PEI) : jugements
        d'abord (jgt_a..d), puis note/7. Utilise les cellules en cours
        d'edition (_dirty_cells) pour ne pas lire des valeurs non encore
        enregistrees, puis rafraichit les cellules calculees de la grille."""
        override = {dbn: v for (sid, dbn), v in self._dirty_cells.items()
                    if sid == student_id and '_note_' in dbn}
        note, jgt_values = self._recompute_one_student(student_id, override)
        self._update_grille_student_cells(student_id, jgt_values, note)

    def _update_grille_student_cells(self, student_id: int,
                                     jgt_values: dict[str, int],
                                     note: Optional[float]) -> None:
        """Rafraichit les cellules calculees (jgt_a..d puis note/7 ou /20)
        de la grille pour un eleve, sans declencher de nouveau itemChanged."""
        row = None
        for r in range(self._grille.rowCount()):
            it = self._grille.item(r, 0)
            if it is not None and it.data(Qt.UserRole) == student_id:
                row = r
                break
        if row is None:
            return
        self._grille.blockSignals(True)
        try:
            for i, name in enumerate(self._current_col_names):
                col = i + 1
                if name in ('jgt_a', 'jgt_b', 'jgt_c', 'jgt_d'):
                    txt = str(jgt_values.get(name[-1], ''))
                elif name in ('note_on_7', 'moy_on_20'):
                    txt = str(int(note)) if note is not None else ''
                else:
                    continue
                item = self._grille.item(row, col)
                if item is not None:
                    item.setText(txt)
                    if isinstance(item, ColorItem):
                        item.set_bg(_note_gradient(txt, self._current_cycle))
        finally:
            self._grille.blockSignals(False)

    @safe_slot("Unknown._on_other_item_selected")
    def _on_other_item_selected(self, idx: int) -> None:
        """Item Autre Matière-Classe sélectionné."""
        termother_id = self._items_other_combo.itemData(idx) if idx >= 0 else None
        if termother_id is None:
            self._clear_grille()
            self.statusBar().showMessage(
                f'{len(self._items)} matière(s)-classe(s)'
            )
            return

        self._clear_grille()
        item = None
        for i in self._items_other:
            if i['termothersubject_id'] == termother_id:
                item = i
                break
        label = f"{item['matiere_label']} - {item['class_label']}" if item else 'Autre matière'
        self.statusBar().showMessage(f'{label} (autre matière)')
