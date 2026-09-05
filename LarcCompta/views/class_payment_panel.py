"""ClassPaymentPanel — grille vignettes avec statut hérité du parent payeur."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from larccommon.database import db
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.widgets.card import StudentCard
from larccommon.widgets.card_config import DEFAULT_CONFIG
from larccommon.safe_slot import safe_slot


class ClassPaymentPanel(QWidget):

    student_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._students: list[dict] = []
        self._class_id = 0
        self._class_label = ""
        self._setup_ui()
        ds.theme_changed.connect(self._restyle)

    def _restyle(self):
        p = theme_manager.palette
        self.setStyleSheet(f"background: {p.background}; border: none;")

    def _setup_ui(self):
        self._grid_layout = QGridLayout(self)
        self._grid_layout.setContentsMargins(
            ds.font_label_lg, ds.font_label_lg, ds.font_label_lg, ds.font_label_lg)
        self._grid_layout.setSpacing(DEFAULT_CONFIG.spacing)

    def load(self, class_id: int, class_label: str = ""):
        self._class_id = class_id
        self._class_label = class_label
        self._load_data()

    def _load_data(self):
        if not db.is_server_connected:
            return
        self._clear_grid()
        conn = db.server_conn
        if not conn:
            return
        cur = conn.cursor()

        # Le statut est herite du parent et stocke dans larcauth_student.statut_scolarite
        # Il est mis a jour automatiquement a chaque paiement (sync_parent_to_children)
        cur.execute("""
            SELECT s.aecuser_ptr_id, aec.last_name, aec.first_name,
                   COALESCE(s.statut_scolarite, 'en_retard') as status
            FROM larcauth_student s
            JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
            WHERE s.s_classroom_id = %s AND s.enabled = TRUE
            ORDER BY aec.last_name, aec.first_name
        """, (self._class_id,))

        # Mapping : statut_scolarite -> set_payment_status
        _MAP = {"solde": "solde", "exonere": "solde",
                "en_cours": "normal", "en_retard": "retard"}

        students = []
        for row in cur.fetchall():
            sid, ln, fn, db_status = row
            status = _MAP.get(db_status, "retard")
            students.append({
                "id": sid, "last_name": ln, "first_name": fn,
                "status": status,
            })

        if not students:
            empty = QLabel("Aucun eleve dans cette classe")
            empty.setAlignment(Qt.AlignCenter)
            p = theme_manager.palette
            empty.setStyleSheet(f"color: {p.text_soft}; font-size: {theme_manager.font_size(13)}px;")
            self._grid_layout.addWidget(empty, 0, 0)
            return

        self._students = students
        avail_w = self.width()
        cfg = DEFAULT_CONFIG
        cols = max(1, (avail_w + cfg.spacing) // (cfg.card_w + cfg.spacing)) if avail_w > 100 else 3

        for i, s in enumerate(students):
            card = StudentCard(s["id"], s["last_name"], s["first_name"], cfg)
            card.clicked.connect(lambda sid=s["id"]: self.student_selected.emit(sid))
            card.set_payment_status(s["status"])
            for j in range(card._badges_row.count()):
                w = card._badges_row.itemAt(j).widget()
                if w:
                    w.hide()
            self._grid_layout.addWidget(card, i // cols, i % cols, Qt.AlignCenter)

        # Spacers pour la derniere ligne incomplete (evite l'etirement)
        remaining = len(students) % cols
        if remaining:
            for i in range(cols - remaining):
                spacer = QWidget()
                spacer.setFixedSize(cfg.card_w, cfg.card_h)
                self._grid_layout.addWidget(spacer, len(students) // cols, cols - remaining + i, Qt.AlignCenter)

    def _clear_grid(self):
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def refresh(self):
        if self._class_id:
            self._load_data()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._students:
            self._reflow()

    def _reflow(self):
        avail_w = self.width()
        cfg = DEFAULT_CONFIG
        cols = max(1, (avail_w + cfg.spacing) // (cfg.card_w + cfg.spacing)) if avail_w > 100 else 3
        cards = []
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item and item.widget():
                w = item.widget()
                if isinstance(w, StudentCard):
                    cards.append(w)
                else:
                    w.deleteLater()
        # Re-inserer
        for idx, card in enumerate(cards):
            self._grid_layout.addWidget(card, idx // cols, idx % cols, Qt.AlignCenter)
        # Spacers derniere ligne
        remaining = len(cards) % cols
        if remaining:
            for i in range(cols - remaining):
                spacer = QWidget()
                spacer.setFixedSize(cfg.card_w, cfg.card_h)
                self._grid_layout.addWidget(spacer, len(cards) // cols, cols - remaining + i, Qt.AlignCenter)
