"""LeaveRequestDialog — demande de congé."""
from __future__ import annotations

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDateEdit, QComboBox, QTextEdit,
)

from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot
from larccommon.widgets.themed_widget import ThemedDialog
from phibuilder.phi.scale import SpacingToken

from LarcRH.common.hr_database import HRDatabase

LEAVE_TYPES = ['CA', 'CM', 'MAT', 'PAT', 'CF', 'CS', 'CFOR', 'REC', 'AUT']
LEAVE_LABELS = ['Congé annuel', 'Congé maladie', 'Congé maternité',
                'Congé paternité', 'Congé familial', 'Congé sans solde',
                'Congé formation', 'Récupération', 'Autorisation d\'absence']


class LeaveRequestDialog(ThemedDialog):
    """Dialogue de demande de congé."""

    def __init__(self, staff_id: int, parent=None):
        super().__init__(parent)
        self._staff_id = staff_id

        self.setWindowTitle("Nouvelle demande de congé")
        self.setMinimumSize(
            ds.sp(SpacingToken.XXXL) * 3,
            ds.sp(SpacingToken.XXXL) * 2 + ds.sp(SpacingToken.XXL))
        self.setMaximumWidth(ds.form_max_width)   # IE6 : popup plafonné
        p = theme_manager.palette
        self.setStyleSheet(f"QDialog {{ background: {p.surface}; }}")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_sm)
        p = theme_manager.palette
        s = theme_manager.font_size
        fstyle = ds.flat_input_qss()

        # Type
        layout.addWidget(QLabel("Type de congé :"))
        self._f_type = QComboBox()
        self._f_type.addItems(LEAVE_LABELS)
        self._f_type.setFixedHeight(ds.field_height)
        self._f_type.setMaximumWidth(ds.field_max_width)
        self._f_type.setStyleSheet(fstyle)
        layout.addWidget(self._f_type)

        # Dates
        self._f_start = QDateEdit()
        self._f_start.setCalendarPopup(True)
        self._f_start.setDate(QDate.currentDate())
        self._f_start.setFixedHeight(ds.field_height)
        self._f_start.setMaximumWidth(ds.field_max_width)
        self._f_start.setStyleSheet(fstyle)
        self._f_start.dateChanged.connect(self._recalc_days)
        layout.addWidget(QLabel("Date de début :"))
        layout.addWidget(self._f_start)

        self._f_end = QDateEdit()
        self._f_end.setCalendarPopup(True)
        self._f_end.setDate(QDate.currentDate().addDays(1))
        self._f_end.setFixedHeight(ds.field_height)
        self._f_end.setMaximumWidth(ds.field_max_width)
        self._f_end.setStyleSheet(fstyle)
        self._f_end.dateChanged.connect(self._recalc_days)
        layout.addWidget(QLabel("Date de fin :"))
        layout.addWidget(self._f_end)

        self._f_days_lbl = QLabel("Nombre de jours : 1")
        self._f_days_lbl.setStyleSheet(f"color: {p.text_strong}; font-size: {s(13)}px; border: none;")
        layout.addWidget(self._f_days_lbl)

        # Motif
        layout.addWidget(QLabel("Motif :"))
        self._f_motif = QTextEdit()
        self._f_motif.setFixedHeight(ds.kpi_card_height)
        self._f_motif.setStyleSheet(f"""
            QTextEdit {{ background: transparent; border: 1px solid {p.outline};
            border-radius: {ds.radius_xs}px; padding: {ds.space_xs}px;
            color: {p.text_strong}; font-size: {s(13)}px; }}
            QTextEdit:focus {{ border-color: {p.primary}; }}
        """)
        layout.addWidget(self._f_motif)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Annuler")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setFixedHeight(ds.button_height)
        cancel.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {p.text_strong};
            border: 1px solid {p.outline}; border-radius: {ds.radius_sm}px;
            padding: {ds.space_xs}px {ds.space_md}px; font-size: {s(13)}px; }}
            QPushButton:hover {{ background: {p.surface_variant}; }}
        """)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        save = QPushButton("Soumettre")
        save.setCursor(Qt.PointingHandCursor)
        save.setFixedHeight(ds.button_height)
        save.setStyleSheet(f"""
            QPushButton {{ background: {p.primary}; color: white; border: none;
            border-radius: {ds.radius_sm}px; padding: {ds.space_xs}px {ds.space_md}px;
            font-size: {s(13)}px; font-weight: bold; }}
            QPushButton:hover {{ background: {p.primary}; }}
        """)
        save.clicked.connect(self._on_save)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)

    def _recalc_days(self):
        d1 = self._f_start.date()
        d2 = self._f_end.date()
        days = max(1, d1.daysTo(d2) + 1)
        self._f_days_lbl.setText(f"Nombre de jours : {days}")

    @safe_slot("LeaveRequestDialog._on_save")
    def _on_save(self):
        d1 = self._f_start.date()
        d2 = self._f_end.date()
        days = max(1, d1.daysTo(d2) + 1)
        data = {
            "staff_id": self._staff_id,
            "leave_type": LEAVE_TYPES[self._f_type.currentIndex()],
            "date_debut": d1.toPython(),
            "date_fin": d2.toPython(),
            "nb_days": float(days),
            "motif": self._f_motif.toPlainText().strip() or None,
        }
        if HRDatabase.save_leave_request(data):
            self.accept()
