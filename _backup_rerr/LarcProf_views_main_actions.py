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






class SyncActionsMixin:
    """Mixin SyncActionsMixin — voir le module parent."""
    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    @safe_slot("Unknown._on_save_only")
    def _on_save_only(self) -> None:
        """Enregistre les notes en local (SQLite) uniquement — jamais de sync."""
        log('[SAVE] Enregistrement local uniquement')
        n = self._save_grid_edits()
        self.statusBar().showMessage(
            'Enregistré en local' + (f' — {n} cellule(s)' if n else ' — rien à enregistrer'),
            4000)

    @safe_slot("Unknown._on_cancel")
    def _on_cancel(self) -> None:
        """Abandonne les modifications non enregistrees et revient au dashboard."""
        log('[CANCEL] Abandon des modifications non sauvegardees')
        self._dirty_cells.clear()
        self.close()


    # ------------------------------------------------------------------
    # Manager windows
    # ------------------------------------------------------------------
    @safe_slot("Unknown._on_weight")
    def _on_weight(self):
        """Ouvre le dialogue Mode de calcul pour la matiere selectionnee."""
        if self._current_ts_id is None:
            self.statusBar().showMessage('Selectionnez d\'abord une matiere-classe')
            return
        from views.weight_dialog import WeightDialog
        slot_label = ''
        for item in self._items:
            if item['termsubject_id'] == self._current_ts_id:
                slot_label = f"{item['matiere_label']} - {item['class_label']}"
                break
        dlg = WeightDialog(self._current_ts_id, slot_label, self)
        if dlg.exec() == QDialog.Accepted:
            self.statusBar().showMessage('Mode de calcul enregistre', 3000)

    @safe_slot("Unknown._open_manager_f")
    def _open_manager_f(self):
        self._open_manager('F')

    @safe_slot("Unknown._open_manager_s")
    def _open_manager_s(self):
        self._open_manager('S')

    def _open_manager(self, eval_type: str):
        if self._current_ts_id is None:
            self.statusBar().showMessage('Sélectionnez d\'abord une matière-classe')
            return
        existing = self._manager_f if eval_type == 'F' else self._manager_s
        if existing is not None:
            existing.close()
        slot_label = ''
        for item in self._items:
            if item['termsubject_id'] == self._current_ts_id:
                slot_label = f"{item['matiere_label']} - {item['class_label']}"
                break
        try:
            w = EvalManagerWindow(eval_type, self._current_ts_id, slot_label, self)
            w.finished.connect(lambda result: self._on_manager_closed(eval_type))
            w.show()
            if eval_type == 'F':
                self._manager_f = w
            else:
                self._manager_s = w
        except Exception as e:
            log(f'[SAVE-ALL] Erreur: {e}')
            self.statusBar().showMessage(f'Erreur: {e}')

    @safe_slot("MainWindow._on_manager_closed")
    def _on_manager_closed(self, eval_type: str):
        try:
            if self._current_ts_id:
                self._load_evaluations_from_db(self._current_ts_id)
                evals = self._evals_f if eval_type == 'F' else self._evals_s
                visible_set = self._visible_f if eval_type == 'F' else self._visible_s
                still_visible = {idx for idx in visible_set if any(e['index'] == idx and e['is_active'] for e in evals)}
                visible_set.clear()
                visible_set.update(still_visible)
                if not visible_set:
                    for e in evals:
                        if e['is_active']:
                            visible_set.add(e['index'])
                            break
                last_key = '_last_clicked_f' if eval_type == 'F' else '_last_clicked_s'
                lc = getattr(self, last_key)
                if lc is not None and not any(e['index'] == lc and e['is_active'] for e in evals):
                    setattr(self, last_key, next((e['index'] for e in evals if e['is_active']), None))
                self._update_top_bar()
                self._on_selection_changed()
        except RuntimeError:
            pass
        if eval_type == 'F':
            self._manager_f = None
        else:
            self._manager_s = None