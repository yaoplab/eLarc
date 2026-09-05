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
from common.theme import theme_manager
from common.grid_config import pei_config
from views.eval_manager import EvalManagerWindow
from larccommon.safe_slot import safe_slot






class DataMixin:
    """Mixin DataMixin — voir le module parent."""

    def _restyle_all(self) -> None:
        """Hook de restyle piloté par le parent (règle D6).

        La classe composante (MainWindow) connecte theme_changed → son
        _restyle() ré-applique les styles palette posés ici (ex. _roles_lbl).
        """

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------
    def _update_roles_label(self):
        """Met a jour le label des roles dans le header."""
        roles = session.role_display
        self._roles_lbl.setText(roles)
        self._roles_lbl.setStyleSheet(
            f"color: {theme_manager.theme.palette.on_primary}; border: none;"
        )

    def _read_annee_scolaire(self) -> str:
        conn = db.local_conn
        if conn is None:
            return '—'
        row = conn.execute(
            'SELECT annee_scolaire FROM module_config WHERE id = 1'
        ).fetchone()
        return row[0] if row else '—'

    # ------------------------------------------------------------------
    # Combined data loader
    # ------------------------------------------------------------------
    def _load_combined_data(self) -> None:
        """Charge les items Matière-Classe et les élèves depuis SQLite."""
        conn = db.local_conn
        if conn is None:
            self.statusBar().showMessage('Aucune base locale disponible')
            return

        try:
            user_id = session.user_id
            term_id = session.term_id
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self.statusBar().showMessage('Session non disponible')
            return

        if not user_id or not term_id:
            self.statusBar().showMessage('Session incomplète')
            return

        try:
            cur = conn.cursor()

            # 1. Items Matière-Classe (une seule requête)
            cur.execute("""
                SELECT cts.id AS termsubject_id,
                       ls.label AS matiere,
                       c.id AS class_id,
                       c.label AS classe,
                       c.fk_level_id
                FROM larcauth_classroom_termsubject cts
                JOIN larcauth_levelsubject ls ON ls.id = cts.fk_levelsubject_id
                JOIN larcauth_classroom c ON c.id = cts.fk_classroom_id
                WHERE cts.fk_teacher_id = ?
                  AND cts.fk_term_id = ?
                  AND cts.enabled = 1
                  AND c.enabled = 1
                ORDER BY ls.label, c.label
            """, (user_id, term_id))
            rows = cur.fetchall()

            self._items = []
            self._cycle_par_classe.clear()
            for r in rows:
                termsubject_id = r[0]
                matiere = r[1]
                class_id = r[2]
                classe = r[3]
                level_id = r[4]
                if class_id not in self._cycle_par_classe:
                    self._cycle_par_classe[class_id] = self._determine_cycle(conn, level_id)
                cycle = self._cycle_par_classe[class_id]
                self._items.append({
                    'termsubject_id': termsubject_id,
                    'matiere_label': matiere,
                    'class_id': class_id,
                    'class_label': classe,
                    'cycle': cycle,
                })

            # 1b. Items Autre Matière-Classe (termothersubject)
            cur.execute("""
                SELECT cto.id AS termothersubject_id,
                       cto.label AS matiere,
                       c.id AS class_id,
                       c.label AS classe
                FROM larcauth_classroom_termothersubject cto
                JOIN larcauth_classroom c ON c.id = cto.fk_classroom_id
                WHERE cto.fk_supervisor_id = ?
                  AND cto.fk_term_id = ?
                  AND cto.enabled = 1
                  AND c.enabled = 1
                ORDER BY cto.label, c.label
            """, (user_id, term_id))
            other_rows = cur.fetchall()

            self._items_other = []
            for r in other_rows:
                self._items_other.append({
                    'termothersubject_id': r[0],
                    'matiere_label': r[1],
                    'class_id': r[2],
                    'class_label': r[3],
                })

            # 2. Élèves par classe
            self._eleves_par_classe.clear()
            all_class_ids = {item['class_id'] for item in self._items}
            for class_id in all_class_ids:
                cur.execute("""
                    SELECT s.aecuser_ptr_id, u.last_name, u.first_name
                    FROM larcauth_student s
                    JOIN larcauth_aecuser u ON u.id = s.aecuser_ptr_id
                    WHERE s.s_classroom_id = ?
                      AND s.enabled = 1
                    ORDER BY u.last_name, u.first_name
                """, (class_id,))
                self._eleves_par_classe[class_id] = [
                    {'id': r[0], 'nom': r[1], 'prenom': r[2]} for r in cur.fetchall()
                ]

            # 3. Peupler le combo
            self._items_combo.blockSignals(True)
            self._items_combo.clear()
            self._items_combo.addItem('— Sélectionnez —', None)
            for item in self._items:
                label = f"{item['matiere_label']} - {item['class_label']}"
                self._items_combo.addItem(label, item['class_id'])
            self._items_combo.blockSignals(False)

            # 3b. Peupler le combo Autre Matière-Classe
            self._items_other_combo.blockSignals(True)
            self._items_other_combo.clear()
            self._items_other_combo.addItem('— Sélectionnez —', None)
            for item in self._items_other:
                label = f"{item['matiere_label']} - {item['class_label']}"
                self._items_other_combo.addItem(label, item['termothersubject_id'])
            self._items_other_combo.blockSignals(False)

            if len(self._items) == 1:
                self._items_combo.setCurrentIndex(1)

            n_elv = sum(len(v) for v in self._eleves_par_classe.values())
            self.statusBar().showMessage(
                f'{len(self._items)} matière(s)-classe(s) · {n_elv} élève(s)'
            )

        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self.statusBar().showMessage(f'Erreur chargement données : {e}')

    def _determine_cycle(self, conn, level_id: int) -> str:
        """Retourne 'PEI' ou 'DP' selon le programme du niveau."""
        try:
            row = conn.execute("""
                SELECT p.sigle
                FROM larcauth_program p
                JOIN larcauth_level l ON l.fk_program_id = p.id
                WHERE l.id = ?
            """, (level_id,)).fetchone()
            if row:
                sigle = row[0].upper()
                if sigle in ('DP', 'IBDP', 'DIPLOMA', 'DPFR', 'DPEN'):
                    return 'DP'
            return 'PEI'  # PEI, MYP, et tout le reste
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return 'PEI'

    @safe_slot("Unknown._on_item_selected")
    def _on_item_selected(self, idx: int) -> None:
        """Item Matière-Classe sélectionné → charge évaluations + grille."""
        # Garde : interdit de changer de matiere avec des modifs non sauvegardees
        if not self._confirm_leave():
            self._items_combo.blockSignals(True)
            self._items_combo.setCurrentIndex(self._last_item_idx)
            self._items_combo.blockSignals(False)
            return
        self._last_item_idx = idx
        class_id = self._items_combo.itemData(idx) if idx >= 0 else None
        if class_id is None:
            self._clear_top_bar()
            self._clear_grille()
            self.statusBar().showMessage(
                f'{len(self._items)} matière(s)-classe(s) · sélectionnez un item'
            )
            return

        item = None
        for i in self._items:
            if i['class_id'] == class_id:
                item = i
                break
        if item is None:
            self._clear_grille()
            return

        ts_id = item['termsubject_id']
        cycle = item['cycle']
        eleves = self._eleves_par_classe.get(class_id, [])
        label = f"{item['matiere_label']} - {item['class_label']}"

        self._current_ts_id = ts_id
        self._current_cycle = cycle
        self._current_item = item

        self._load_evaluations_from_db(ts_id)
        # Auto-sélectionner le premier slot actif de chaque type
        self._visible_f.clear()
        for e in self._evals_f:
            if e['is_active']:
                self._visible_f.add(e['index'])
                self._last_clicked_f = e['index']
                break
        self._visible_s.clear()
        for e in self._evals_s:
            if e['is_active']:
                self._visible_s.add(e['index'])
                self._last_clicked_s = e['index']
                break
        self._update_top_bar()

        self._fill_grille(item, cycle, eleves)
        # Calcul auto des jugements + note/7 (nécessite _row_ids/_current_student_ids
        # peuplés par _fill_grille) puis re-fill pour afficher les valeurs calculées.
        self._auto_compute_judgments_and_note()
        self._fill_grille(item, cycle, eleves)
        self.statusBar().showMessage(
            f'{label} · {cycle} · {len(eleves)} élève(s)'
        )

    def _load_evaluations_from_db(self, ts_id: int):
        """Charge les évaluations F et S depuis SQLite."""
        conn = db.local_conn
        if conn is None:
            return
        try:
            self._evals_f = []
            self._evals_s = []
            for eval_type in ('F', 'S'):
                rows = conn.execute("""
                    SELECT id, index_eval, label, nature, source,
                           crit_a, crit_b, crit_c, crit_d
                    FROM larcauth_evaluation
                    WHERE fk_classroom_termsubject_id = ?
                      AND type_evaluation = ?
                      AND CAST(index_eval AS INTEGER) BETWEEN 1 AND 12
                    ORDER BY CAST(index_eval AS INTEGER)
                """, (str(ts_id), eval_type)).fetchall()
                evals_list = []
                for r in rows:
                    crits_active = any((r[i] or '0') == '1' for i in (5, 6, 7, 8))
                    evals_list.append({
                        'id': r[0],
                        'index': int(r[1]),
                        'label': r[2] or '',
                        'nature': r[3] or '',
                        'source': r[4] or '',
                        'crit_a': r[5] or '0',
                        'crit_b': r[6] or '0',
                        'crit_c': r[7] or '0',
                        'crit_d': r[8] or '0',
                        'is_active': crits_active,
                    })
                if eval_type == 'F':
                    self._evals_f = evals_list
                else:
                    self._evals_s = evals_list
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"Erreur chargement évaluations: {e}")

    def _clear_top_bar(self):
        """Vide les détails du top bar quand aucune matière-classe sélectionnée."""
        self._last_clicked_f = None
        self._last_clicked_s = None
        for widgets in (self._fwidgets, self._swidgets):
            layout = widgets['scroll_content'].layout()
            if layout:
                while layout.count():
                    item = layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()

    def _update_top_bar(self):
        """Met à jour les icônes et détails du top bar avec les données chargées."""
        self._update_icons('F', self._evals_f, self._fwidgets)
        self._update_icons('S', self._evals_s, self._swidgets)
