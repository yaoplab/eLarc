"""ContractFormDialog — création/édition de contrat."""
from __future__ import annotations

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QDateEdit, QComboBox, QTextEdit,
)

from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot
from larccommon.widgets.themed_widget import ThemedDialog
from phibuilder.phi.scale import SpacingToken

from LarcRH.common.hr_database import HRDatabase

CONTRACT_TYPES = ['cdi', 'cdd', 'cdd_renouvelable', 'stage', 'prestataire', 'vacataire', 'temps_partiel']
CONTRACT_LABELS = ['CDI', 'CDD', 'CDD renouvelable', 'Stage', 'Prestataire', 'Vacataire', 'Temps partiel']


class ContractFormDialog(ThemedDialog):
    """Dialogue de création/édition d'un contrat."""

    def __init__(self, staff_id: int, contract_data: dict | None = None, parent=None):
        super().__init__(parent)
        self._staff_id = staff_id
        self._contract = contract_data
        self._is_new = contract_data is None

        self.setWindowTitle("Nouveau contrat" if self._is_new else "Modifier le contrat")
        _w = ds.golden_width(350)
        self.setMinimumSize(_w, ds.sp(SpacingToken.XXXL) * 3 + ds.sp(SpacingToken.XL))
        self.setMaximumWidth(ds.form_max_width)   # IE6 : popup plafonné
        p = theme_manager.palette
        self.setStyleSheet(f"QDialog {{ background: {p.surface}; }}")

        self._setup_ui()
        if not self._is_new and contract_data:
            self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_sm)
        p = theme_manager.palette
        s = theme_manager.font_size

        fstyle = ds.flat_input_qss()

        # Type
        layout.addWidget(QLabel("Type de contrat :"))
        self._f_type = QComboBox()
        self._f_type.addItems(CONTRACT_LABELS)
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
        self._f_start.dateChanged.connect(self._recalc_trial)
        layout.addWidget(QLabel("Date de début :"))
        layout.addWidget(self._f_start)

        self._f_end = QDateEdit()
        self._f_end.setCalendarPopup(True)
        self._f_end.setDate(QDate.currentDate().addYears(1))
        self._f_end.setFixedHeight(ds.field_height)
        self._f_end.setMaximumWidth(ds.field_max_width)
        self._f_end.setStyleSheet(fstyle)
        layout.addWidget(QLabel("Date de fin :"))
        layout.addWidget(self._f_end)

        # Trial period
        self._f_trial = QLineEdit("90")
        self._f_trial.setPlaceholderText("Durée en jours")
        self._f_trial.setFixedHeight(ds.field_height)
        self._f_trial.setMaximumWidth(ds.field_max_width)
        self._f_trial.setStyleSheet(fstyle)
        self._f_trial.textChanged.connect(self._recalc_trial)
        layout.addWidget(QLabel("Période d'essai (jours) :"))
        layout.addWidget(self._f_trial)

        self._f_trial_end = QLabel("Fin période d'essai : —")
        self._f_trial_end.setStyleSheet(f"color: {p.text_soft}; font-size: {s(12)}px; border: none;")
        layout.addWidget(self._f_trial_end)

        # Salary + hours
        row = QHBoxLayout()
        row.setSpacing(ds.space_sm)
        self._f_salary = QLineEdit()
        self._f_salary.setPlaceholderText("Salaire brut mensuel")
        self._f_salary.setFixedHeight(ds.field_height)
        self._f_salary.setMaximumWidth(ds.field_max_width)
        self._f_salary.setStyleSheet(fstyle)
        row.addWidget(QLabel("Salaire :"))
        row.addWidget(self._f_salary)

        self._f_hours = QLineEdit()
        self._f_hours.setPlaceholderText("h/sem")
        self._f_hours.setFixedHeight(ds.field_height)
        self._f_hours.setMaximumWidth(ds.field_max_width)
        self._f_hours.setStyleSheet(fstyle)
        row.addWidget(QLabel("Vol. horaire :"))
        row.addWidget(self._f_hours)
        layout.addLayout(row)

        # Classification
        row2 = QHBoxLayout()
        row2.setSpacing(ds.space_sm)
        self._f_class = QLineEdit()
        self._f_class.setPlaceholderText("Classification")
        self._f_class.setFixedHeight(ds.field_height)
        self._f_class.setMaximumWidth(ds.field_max_width)
        self._f_class.setStyleSheet(fstyle)
        row2.addWidget(QLabel("Classif. :"))
        row2.addWidget(self._f_class)

        self._f_echelon = QLineEdit()
        self._f_echelon.setPlaceholderText("Échelon")
        self._f_echelon.setFixedHeight(ds.field_height)
        self._f_echelon.setMaximumWidth(ds.field_max_width)
        self._f_echelon.setStyleSheet(fstyle)
        row2.addWidget(QLabel("Échelon :"))
        row2.addWidget(self._f_echelon)
        layout.addLayout(row2)

        # Notes
        layout.addWidget(QLabel("Notes :"))
        self._f_notes = QTextEdit()
        self._f_notes.setFixedHeight(ds.kpi_card_height)
        self._f_notes.setStyleSheet(f"""
            QTextEdit {{ background: transparent; border: 1px solid {p.outline};
            border-radius: {ds.radius_xs}px; padding: {ds.space_xs}px;
            color: {p.text_strong}; font-size: {s(13)}px; }}
            QTextEdit:focus {{ border-color: {p.primary}; }}
        """)
        layout.addWidget(self._f_notes)

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

        save = QPushButton("Enregistrer")
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

    def _recalc_trial(self):
        try:
            days = int(self._f_trial.text().strip() or "0")
            end = self._f_start.date().addDays(days)
            self._f_trial_end.setText(f"Fin période d'essai : {end.toString('dd/MM/yyyy')}")
        except ValueError:
            pass

    def _load(self):
        d = self._contract or {}
        if d.get("contract_type") and d["contract_type"] in CONTRACT_TYPES:
            self._f_type.setCurrentIndex(CONTRACT_TYPES.index(d["contract_type"]))
        if d.get("date_debut"):
            self._f_start.setDate(d["date_debut"])
        if d.get("date_fin"):
            self._f_end.setDate(d["date_fin"])
        if d.get("periode_essai"):
            self._f_trial.setText(str(d["periode_essai"]))
        if d.get("salaire_brut"):
            self._f_salary.setText(str(d["salaire_brut"]))
        if d.get("volume_horaire"):
            self._f_hours.setText(str(d["volume_horaire"]))
        if d.get("classification"):
            self._f_class.setText(d["classification"])
        if d.get("echelon"):
            self._f_echelon.setText(str(d["echelon"]))
        if d.get("notes"):
            self._f_notes.setPlainText(d["notes"])
        self._recalc_trial()

    @safe_slot("ContractFormDialog._on_save")
    def _on_save(self):
        data = {
            "id": self._contract.get("id") if self._contract else None,
            "staff_id": self._staff_id,
            "contract_type": CONTRACT_TYPES[self._f_type.currentIndex()],
            "date_debut": self._f_start.date().toPython(),
            "date_fin": self._f_end.date().toPython(),
            "periode_essai": int(self._f_trial.text().strip()) if self._f_trial.text().strip() else None,
            "periode_essai_fin": self._f_start.date().addDays(int(self._f_trial.text().strip() or "0")).toPython(),
            "salaire_brut": float(self._f_salary.text().strip()) if self._f_salary.text().strip() else None,
            "volume_horaire": float(self._f_hours.text().strip()) if self._f_hours.text().strip() else None,
            "classification": self._f_class.text().strip() or None,
            "echelon": int(self._f_echelon.text().strip()) if self._f_echelon.text().strip() else None,
            "statut": self._contract.get("statut", "actif") if self._contract else "actif",
            "notes": self._f_notes.toPlainText().strip() or None,
        }
        if HRDatabase.save_contract(data):
            self.accept()
