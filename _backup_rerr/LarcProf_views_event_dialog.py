"""Dialogue rapide de creation d'evenement eleve.

Accessible depuis le clic droit sur un eleve dans la grille.
Prend le type d'evenement et une note optionnelle, sauvegarde en SQLite local.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)

from common.event_service import EventService
from common.session import session
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot
from larccommon.widgets.themed_widget import ThemedDialog


class EventDialog(ThemedDialog):
    """Dialogue de creation rapide d'evenement."""

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        return f"""
            QDialog {{ background: {p.background}; }}
            QPushButton#ok_btn {{
                background: {p.success}; color: white; font-weight: bold;
                padding: {ds.space_xs}px {ds.font_label_lg}px;
                border-radius: {ds.radius_xs}px; }}
            QPushButton#ok_btn:hover {{ background: {p.success}; }}
        """

    def __init__(self, student_name: str, student_id: int, parent=None):
        super().__init__(parent)
        self._student_id = student_id
        self._student_name = student_name

        self.setWindowTitle(f"Evenement — {student_name}")
        self.setMinimumWidth(ds.sidebar_width)
        self.setModal(True)

        self._setup_ui()
        self.setStyleSheet(self._STYLE)
        ds.theme_changed.connect(self._restyle)
        self._type_combo.setFocus()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(ds.space_xs)

        info = QLabel(f"Eleve : {self._student_name}")
        info.setStyleSheet(
            f"font-weight: bold; font-size: {theme_manager.font_size(12)}px; "
            f"color: {theme_manager.palette.text_strong};"
        )
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(ds.space_xxs)

        self._type_combo = QComboBox()
        self._type_combo.addItem("— Selectionner —", "")
        for key, label in EventService.EVENT_TYPES.items():
            self._type_combo.addItem(label, key)
        self._type_combo.setStyleSheet(
            f"padding: {ds.space_xxs}px; font-size: {theme_manager.font_size(12)}px;"
        )
        form.addRow("Type :", self._type_combo)

        self._note_edit = QTextEdit()
        self._note_edit.setPlaceholderText("Note optionnelle (200 caracteres max)")
        self._note_edit.setMaximumHeight(ds.kpi_card_height)
        self._note_edit.setStyleSheet(
            f"padding: {ds.space_xxs}px; font-size: {theme_manager.font_size(11)}px;"
        )
        form.addRow("Note :", self._note_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        # Renommer le bouton OK
        ok_btn = buttons.button(QDialogButtonBox.Ok)
        if ok_btn:
            ok_btn.setText("Enregistrer")
            ok_btn.setObjectName("ok_btn")
        layout.addWidget(buttons)

    @safe_slot("EventDialog._restyle")
    def _restyle(self):
        self.setStyleSheet(self._STYLE)

    @safe_slot("EventDialog._on_save")
    def _on_save(self):
        event_type = self._type_combo.currentData()
        if not event_type:
            self._show_error("Sélectionnez un type d'événement.")
            return

        note = self._note_edit.toPlainText().strip()[:200]

        try:
            EventService.insert_event(
                student_id=self._student_id,
                event_type=event_type,
                created_by=session.user_id,
                note=note,
            )
            self.accept()
        except Exception as e:
            self._show_error(f"Erreur : {e}")

    def _show_error(self, msg: str):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Erreur", msg)
