"""StaffEventDialog — dialogue d'ajout d'événement (absence, retard, sortie).

Pattern: Q7 section card + Q8 labels AU-DESSUS des champs + Q19b boutons.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QDateTime, Signal
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QDateTimeEdit, QWidget, QFrame,
)

from larccommon.database import db
from larccommon.session import session
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot
from larccommon.widgets.themed_widget import ThemedDialog
from phibuilder.phi.scale import SpacingToken


class StaffEventDialog(ThemedDialog):

    event_saved = Signal()

    MODES = [
        ("Absence", "Ab"),
        ("Retard", "Re"),
    ]

    def __init__(self, staff_data: dict, parent=None):
        super().__init__(parent)
        self._staff = staff_data
        self._selected_type: str | None = None
        self._mode_buttons: dict[str, QPushButton] = {}

        name = staff_data.get("full_name", "—")
        self.setWindowTitle(f"Événement — {name}")
        _w = ds.sidebar_width + ds.golden_width(ds.sidebar_width)
        self.setMinimumSize(_w, 560)
        self.setMaximumWidth(ds.form_max_width)   # IE6 : popup plafonné
        self._setup_ui()

    # ── QSS ──

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        s = theme_manager.font_size
        return f"""
            StaffEventDialog {{
                background: {p.surface};
            }}
            QComboBox {{
                background: {p.background};
                border: 1px solid {p.outline};
                border-radius: {ds.radius_xs}px;
                padding: {ds.space_xs}px {ds.space_sm}px;
                color: {p.text_strong};
                font-size: {s(13)}px;
            }}
            QDateTimeEdit {{
                background: {p.background};
                border: 1px solid {p.outline};
                border-radius: {ds.radius_xs}px;
                padding: {ds.space_xs}px {ds.space_sm}px;
                color: {p.text_strong};
                font-size: {s(13)}px;
            }}
            QComboBox:focus, QDateTimeEdit:focus {{
                border-color: {p.primary};
            }}
            QDateTimeEdit QLineEdit {{
                color: {p.text_strong};
                background: {p.background};
            }}
            QTextEdit {{
                background: {p.background};
                border: 1px solid {p.outline};
                border-radius: {ds.radius_xs}px;
                padding: {ds.space_sm}px;
                color: {p.text_strong};
                font-size: {s(13)}px;
            }}
            QTextEdit:focus {{
                border-color: {p.primary};
            }}
        """

    @safe_slot("StaffEventDialog._restyle")
    def _restyle(self):
        try:
            self.setStyleSheet(self._STYLE)
        except RuntimeError:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass

    # ── UI ──

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size

        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_md)

        # ── Header ──
        header = QLabel(f"Événement — {self._staff.get('full_name', '—')}")
        header.setStyleSheet(
            f"font-size: {s(16)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {p.outline_variant};")
        layout.addWidget(sep)

        # ── Mode: Absence / Retard ──
        lbl_mode = QLabel("Type")
        lbl_mode.setStyleSheet(
            f"font-size: {s(ds.font_label_sm)}px; color: {p.text_soft}; "
            f"font-weight: bold; border: none;")
        layout.addWidget(lbl_mode)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(ds.space_xs)

        for label, prefix in self.MODES:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(ds.field_height + ds.space_xs)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {p.surface_variant};
                    color: {p.text_strong};
                    border: 1px solid {p.outline};
                    border-radius: {ds.radius_sm}px;
                    padding: {ds.space_xs}px {ds.space_md}px;
                    font-size: {s(13)}px;
                }}
                QPushButton:checked {{
                    background: {p.primary};
                    color: white;
                    border-color: {p.primary};
                }}
                QPushButton:hover:!checked {{ border-color: {p.primary}; }}
            """)
            btn.clicked.connect(lambda checked, p=prefix: self._select_mode(p))
            mode_row.addWidget(btn)
            self._mode_buttons[prefix] = btn
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # ── Motif ──
        lbl_motif = QLabel("Motif")
        lbl_motif.setStyleSheet(
            f"font-size: {s(ds.font_label_sm)}px; color: {p.text_soft}; "
            f"font-weight: bold; border: none;")
        layout.addWidget(lbl_motif)

        self._motif_field = QComboBox()
        # Combo STANDARD (non editable) : un clic n'importe où ouvre le menu.
        # En mode editable, seule la petite flèche ouvre le popup — le clic sur
        # le texte focusse la saisie et donne l'impression que la combo « ne
        # s'ouvre pas » (bug signalé 2026-08-16).
        self._motif_field.setEditable(False)
        self._motif_field.setPlaceholderText("Sélectionner un motif")
        self._motif_field.setFixedHeight(ds.field_height)
        self._motif_field.setMaximumWidth(ds.field_max_width)
        self._motif_field.setStyleSheet(ds.flat_input_qss())
        self._motif_field.setVisible(False)
        layout.addWidget(self._motif_field)

        # ── Date / Heure ──
        lbl_dt = QLabel("Date / Heure")
        lbl_dt.setStyleSheet(
            f"font-size: {s(ds.font_label_sm)}px; color: {p.text_soft}; "
            f"font-weight: bold; border: none;")
        layout.addWidget(lbl_dt)

        self._date_edit = QDateTimeEdit()
        self._date_edit.setDateTime(QDateTime.currentDateTime())
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setFixedHeight(ds.field_height)
        self._date_edit.setMinimumWidth(ds.sp(SpacingToken.XXXL))
        self._date_edit.setMaximumWidth(ds.field_max_width)
        layout.addWidget(self._date_edit)

        # ── Note ──
        lbl_note = QLabel("Note")
        lbl_note.setStyleSheet(
            f"font-size: {s(ds.font_label_sm)}px; color: {p.text_soft}; "
            f"font-weight: bold; border: none;")
        layout.addWidget(lbl_note)

        self._note = QTextEdit()
        self._note.setMinimumHeight(ds.field_height * 2)
        self._note.setMaximumHeight(ds.kpi_card_height)
        layout.addWidget(self._note)

        # ── Actions — Q19b: secondaire gauche, primaire droite ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel = QPushButton("Annuler")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setFixedHeight(ds.field_height + ds.space_xs)
        cancel.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {p.text_strong};
                border: 1px solid {p.outline};
                border-radius: {ds.radius_sm}px;
                padding: {ds.space_xs}px {ds.space_md}px;
                font-size: {s(13)}px;
            }}
            QPushButton:hover {{ background: {p.surface_variant}; }}
        """)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        save = QPushButton("Enregistrer")
        save.setCursor(Qt.PointingHandCursor)
        save.setFixedHeight(ds.field_height + ds.space_xs)
        save.setStyleSheet(f"""
            QPushButton {{
                background: {p.primary}; color: white;
                border: none; border-radius: {ds.radius_sm}px;
                padding: {ds.space_xs}px {ds.space_md}px;
                font-size: {s(13)}px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {p.primary}; }}
        """)
        save.clicked.connect(self._on_save)
        btn_row.addWidget(save)

        layout.addLayout(btn_row)
        self.setStyleSheet(self._STYLE)

    # ── Logic ──

    def _select_mode(self, prefix: str):
        self._selected_type = prefix
        for pfx, btn in self._mode_buttons.items():
            btn.setChecked(pfx == prefix)

        self._motif_field.clear()
        self._motif_field.setVisible(True)

        motifs_absence = [
            "Maladie (certificat fourni)",
            "Maladie (sans certificat)",
            "Absence injustifiée",
            "Congé non autorisé",
            "Abandon de poste",
            "Retard de plus de 30 min",
            "Absence autorisée non rémunérée",
            "Force majeure",
        ]
        motifs_retard = [
            "Retard simple (< 15 min)",
            "Retard moyen (15-30 min)",
            "Embouteillage / Transport",
            "Motif familial",
            "Problème de santé",
            "Retard non justifié",
        ]
        motifs = motifs_absence if prefix == "Ab" else motifs_retard
        for m in motifs:
            self._motif_field.addItem(m)
        self._motif_field.setCurrentIndex(-1)

    @safe_slot("StaffEventDialog._on_save")
    def _on_save(self):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Base de données",
                              "Impossible de se connecter à la base de données.")
            return

        if not self._selected_type:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Champ obligatoire",
                              "Veuillez sélectionner le type (Absence ou Retard).")
            return

        motif = self._motif_field.currentText().strip() or self._motif_field.currentText()
        event_label = f"{'Absence' if self._selected_type == 'Ab' else 'Retard'} — {motif}"

        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO staff_event (staff_id, event_type, event_at,
                    note, source, created_by, modified_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                self._staff["id"],
                event_label,
                self._date_edit.dateTime().toPython(),
                self._note.toPlainText().strip() or None,
                "RH",
                session.user_id,
                session.user_id,
            ))
            self.event_saved.emit()
            self.accept()

        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Erreur",
                              "Une erreur est survenue lors de l'enregistrement.")


def open_staff_event_generator(staff_data: dict, parent=None):
    from PySide6.QtWidgets import QMessageBox
    from LarcRH.common.hr_database import HRDatabase
    # La génération d'événements n'est possible que les JOURS OUVRÉS
    # (larcauth_agenda.working_day) — hors jour ouvré : interdiction.
    if not HRDatabase.is_working_day():
        QMessageBox.information(
            parent, "LarcRH",
            "Aujourd'hui n'est pas un jour ouvré — "
            "impossible de générer des événements.")
        return
    dlg = StaffEventDialog(staff_data, parent)
    if dlg.exec():
        QMessageBox.information(parent, "LarcRH", "Événement enregistré.")
        # NB : rafraîchir la grille SEULEMENT après la boîte de confirmation —
        # refresh() détruit la carte (parent du dialogue) ; si le rafraîchis-
        # sement avait lieu pendant la boîte modale, sa boucle d'événements
        # exécuterait le deleteLater → segfault C++ (plante de l'app).
        _refresh_parent_grid(parent)


def _refresh_parent_grid(widget):
    while widget:
        from LarcRH.views.staff_grid import StaffGrid
        if isinstance(widget, StaffGrid):
            widget.refresh()
            return
        widget = widget.parent()
