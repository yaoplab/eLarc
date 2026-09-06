"""EventGeneratorDialog — Wizard polymorphe pour créer événements (Student/Staff).

Types d'événements chargés de larcauth_event_type_config (hiérarchie configurable).
Support N niveaux d'arborescence (vs hardcodé 3).
Marque l'origine : 'intranet' vs 'cloud' pour sync.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from PySide6.QtCore import Qt, QDate, QTime, Signal
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QWidget,
    QMessageBox,
    QDateEdit,
    QTimeEdit,
)

from larccommon.database import db
from larccommon.design_system import ds
from larccommon.event_type_service import (
    EventTypeNode,
    EventTypeConfigService,
    MemberType,
    event_type_service,
)
from larccommon.l10n import _
from larccommon.logger import log
from larccommon.safe_slot import safe_slot
from larccommon.session import session
from larccommon.theme import theme_manager
from larccommon.widgets.themed_widget import ThemedDialog
from phibuilder.widgets import M3Button, M3Card, M3Label, M3TextField
from phibuilder.widgets.button import ButtonVariant
from phibuilder.widgets.card import CardVariant


@dataclass
class EventData:
    """Résultat du wizard : données à insérer en base."""

    member_id: int  # student_id ou staff_id
    member_type: MemberType
    type_code: str  # Code de larcauth_event_type_config
    type_path: str  # Chemin lisible : "Absence > Absence de l'école > Maladie"
    event_at: str  # Format ISO : "2026-09-05T14:30:00"
    lieu_label: Optional[str] = None
    subject_label: Optional[str] = None
    note: str = ""
    created_location: str = "intranet"  # "intranet" ou "cloud"


class EventGeneratorDialog(ThemedDialog):
    """
    Wizard polymorphe pour créer événements (Student ou Staff).

    Charges types depuis event_type_service (config DB).
    Émet Signal(EventData) → caller insère en base.
    """

    event_created = Signal(EventData)

    def __init__(self, member_id: int, member_type: MemberType, parent=None):
        super().__init__(parent)
        self._member_id = member_id
        self._member_type = member_type
        self._path: List[EventTypeNode] = []  # Chemin de navigation
        self._selected_node: Optional[EventTypeNode] = None
        self._selected_lieu_id: int = 0
        self._selected_lieu_label: str = ""
        self._selected_subject: str = ""
        self._locations: List[tuple] = []  # (lieu_id, site_id, lieu_name)
        self._classroom_lieu_ids: set = set()

        # UI
        self._step_card: Optional[M3Card] = None
        self._step_grid: Optional[QGridLayout] = None
        self._bd: Optional[M3Card] = None  # Badge résumé
        self._bd_text: Optional[M3Label] = None
        self._final: Optional[QWidget] = None
        self._date_edit: Optional[QDateEdit] = None
        self._time_edit: Optional[QTimeEdit] = None
        self._note_input: Optional[M3TextField] = None

        # Charger types applicables
        self._type_hierarchies = event_type_service.filter_applicable(member_type)
        if not self._type_hierarchies:
            log(f"EventGeneratorDialog: aucun type pour {member_type.value}")

        # Title
        member_label = _("event.student") if member_type == MemberType.STUDENT else _("event.staff")
        self.setWindowTitle(f"{member_label} {member_id}")
        self.setMinimumWidth(ds.window_width * 17 // 30)  # ~680px

        # Charger ressources (lieux, etc.)
        self._load_locations()

        # UI
        self._init_ui()
        ds.theme_changed.connect(self._restyle_all)
        self._restyle_all()
        self._show_step()

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        s = theme_manager.font_size
        return f"""
            EventGeneratorDialog#evt_root {{
                background: {p.surface};
            }}
            QDateEdit, QTimeEdit {{
                padding: {ds.space_md}px;
                border: 1px solid {p.outline_variant};
                border-radius: {ds.radius_sm}px;
                font-size: {s(13)}px;
                background: {p.surface};
                color: {p.text_strong};
                font-weight: bold;
            }}
            QLabel#evt_sep {{
                color: {p.outline};
            }}
        """

    @safe_slot("EventGeneratorDialog._restyle_all")
    def _restyle_all(self):
        try:
            self.setStyleSheet(self._STYLE)
        except RuntimeError:
            pass

    def _load_locations(self):
        """Charge les lieux depuis la DB."""
        try:
            conn = db.server_conn
            if not conn:
                return

            cur = conn.cursor()
            cur.execute("SELECT lieu_id, site_id, lieu_name FROM larcauth_lieu WHERE is_active = TRUE")
            self._locations = cur.fetchall()
        except Exception as e:
            log(f"EventGeneratorDialog._load_locations: {e}")
            self._locations = []

    def _init_ui(self):
        """Initialise l'interface."""
        p = theme_manager.palette
        self.setObjectName("evt_root")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(ds.space_lg, ds.space_lg, ds.space_lg, ds.space_lg)
        outer.setSpacing(ds.space_md)

        # Card pour les étapes
        self._step_card = M3Card(variant=CardVariant.ELEVATED, parent=self)
        sl = self._step_card.content_layout()
        sl.setContentsMargins(ds.space_lg, ds.space_lg, ds.space_lg, ds.space_lg)
        self._step_grid = QGridLayout()
        self._step_grid.setSpacing(ds.space_sm)
        sl.addLayout(self._step_grid)
        outer.addWidget(self._step_card)

        # Badge (résumé)
        self._bd = M3Card(variant=CardVariant.FILLED, parent=self)
        bdl = self._bd.content_layout()
        bdl.setContentsMargins(ds.space_xl, ds.space_sm, ds.space_xl, ds.space_sm)
        self._bd_text = M3Label("", style="title_medium")
        self._bd_text.setAlignment(Qt.AlignCenter)
        bdl.addWidget(self._bd_text)
        self._bd.hide()
        outer.addWidget(self._bd)

        # Zone finale (date/heure/note/boutons)
        self._final = QWidget()
        fl = QVBoxLayout(self._final)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(ds.space_md)

        # Date + Heure
        dr = QHBoxLayout()
        dr.setSpacing(ds.space_md)
        dr.addWidget(M3Label(_("event.date"), style="body_medium"))
        self._date_edit = QDateEdit(QDate.currentDate())
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("dddd dd MMMM yyyy")
        dr.addWidget(self._date_edit, 2)
        dr.addWidget(M3Label(_("event.time"), style="body_medium"))
        self._time_edit = QTimeEdit(QTime.currentTime())
        self._time_edit.setDisplayFormat("HH:mm")
        dr.addWidget(self._time_edit, 1)
        fl.addLayout(dr)

        # Note
        fl.addWidget(M3Label(_("event.note"), style="body_medium"))
        self._note_input = M3TextField(placeholder=_("event.note_placeholder"))
        self._note_input.setMaxLength(200)
        fl.addWidget(self._note_input)

        # Boutons
        ar = QHBoxLayout()
        ar.addStretch()
        cb = M3Button(_("common.button.cancel"), variant=ButtonVariant.OUTLINED)
        cb.clicked.connect(self.reject)
        ar.addWidget(cb)
        vb = M3Button(_("event.validate_button"), variant=ButtonVariant.FILLED)
        vb.clicked.connect(self._on_validate)
        ar.addWidget(vb)
        fl.addLayout(ar)

        self._final.hide()
        outer.addWidget(self._final)

    @safe_slot("EventGeneratorDialog._show_step")
    def _show_step(self):
        """Affiche l'étape courante."""
        self._step_card.hide()
        self._bd.hide()
        self._final.hide()

        # Effacer le grid
        while self._step_grid.count():
            item = self._step_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._path:
            # Étape 0 : afficher les catégories racines
            self._show_categories()
            self._step_card.show()
            return

        if self._is_final_step():
            # Étape finale : afficher date/heure/note
            self._bd_update()
            self._bd.show()
            self._final.show()
            return

        # Étape N : afficher les enfants
        self._show_children()
        self._step_card.show()
        self.adjustSize()

    def _is_final_step(self) -> bool:
        """Vérifie si le nœud courant n'a pas d'enfants."""
        if not self._path:
            return False

        current_node = self._path[-1]
        return len(current_node.children) == 0

    def _show_categories(self):
        """Affiche les catégories racines (Absence, Retard, Événement)."""
        for idx, (cat, root) in enumerate(self._type_hierarchies.items()):
            btn = M3Button(root.label, variant=ButtonVariant.TONAL)
            btn.setMinimumHeight(ds.space_xl * 2)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, node=root: self._on_node_selected(node))
            self._step_grid.addWidget(btn, 0, idx)

    def _show_children(self):
        """Affiche les enfants du nœud courant."""
        if not self._path:
            return

        current_node = self._path[-1]
        for idx, child in enumerate(current_node.children):
            btn = M3Button(child.label, variant=ButtonVariant.TONAL)
            btn.setMinimumHeight(ds.space_xl - ds.space_xxs)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, node=child: self._on_node_selected(node))
            self._step_grid.addWidget(btn, idx // 3, idx % 3)

    def _bd_update(self):
        """Met à jour le badge résumé."""
        if not self._selected_node:
            self._bd.hide()
            return

        p = theme_manager.palette
        type_path = event_type_service.get_path(self._selected_node)

        if self._selected_node.category == "absence":
            self._bd_text.setText(f"Absence : {type_path}")
            self._bd_text.setStyleSheet(f"color: {p.on_error}; font-weight: bold;")
            self._bd.setStyleSheet(
                f"M3Card {{ background: {p.error}; border-radius: {ds.radius_md}px; }}"
            )
        elif self._selected_node.category == "retard":
            self._bd_text.setText(f"Retard : {type_path}")
            self._bd_text.setStyleSheet(f"color: {p.on_tertiary}; font-weight: bold;")
            self._bd.setStyleSheet(
                f"M3Card {{ background: {p.tertiary}; border-radius: {ds.radius_md}px; }}"
            )
        else:
            txt = f"Événement : {type_path}"
            if self._selected_lieu_label:
                txt += f" — {self._selected_lieu_label}"
            self._bd_text.setText(txt)
            self._bd_text.setStyleSheet(f"color: {p.on_primary}; font-weight: bold;")
            self._bd.setStyleSheet(
                f"M3Card {{ background: {p.primary}; border-radius: {ds.radius_md}px; }}"
            )

    @safe_slot("EventGeneratorDialog._on_node_selected")
    def _on_node_selected(self, node: EventTypeNode):
        """Utilisateur clique sur un nœud."""
        self._path.append(node)
        self._selected_node = node
        self._show_step()

    def _check_working_day(self) -> bool:
        """Vérifie que la date est un jour ouvré."""
        try:
            conn = db.server_conn
            if not conn:
                log("EventGeneratorDialog._check_working_day: DB not connected")
                return True

            date = self._date_edit.date().toPython()
            cur = conn.cursor()
            cur.execute(
                "SELECT working_day FROM larcauth_agenda WHERE agenda_date = %s",
                (date,),
            )
            row = cur.fetchone()
            if row:
                return bool(row[0])
            return True  # Si pas d'entrée, accepter
        except Exception as e:
            log(f"EventGeneratorDialog._check_working_day: {e}")
            return True

    def _check_active_term(self) -> bool:
        """Vérifie que le trimestre est actif."""
        try:
            conn = db.server_conn
            if not conn:
                log("EventGeneratorDialog._check_active_term: DB not connected")
                return True

            cur = conn.cursor()
            cur.execute("SELECT current_term_number FROM larcauth_academicyear LIMIT 1")
            row = cur.fetchone()
            return bool(row)  # True si un trimestre actif
        except Exception as e:
            log(f"EventGeneratorDialog._check_active_term: {e}")
            return True

    def _get_datetime_iso(self) -> str:
        """Retourne datetime en format ISO."""
        date = self._date_edit.date().toPython()
        time = self._time_edit.time().toPython()
        return f"{date}T{time}"

    @safe_slot("EventGeneratorDialog._on_validate")
    def _on_validate(self):
        """Utilisateur valide : créer EventData et émettre signal."""
        # Validation métier
        if not self._check_working_day():
            QMessageBox.warning(self, _("event.error"), _("event.error_not_working_day"))
            return

        if not self._check_active_term():
            QMessageBox.warning(self, _("event.error"), _("event.error_inactive_term"))
            return

        if not self._selected_node:
            QMessageBox.warning(self, _("event.error"), _("event.error_no_type"))
            return

        # Construire EventData
        type_path = event_type_service.get_path(self._selected_node)

        event_data = EventData(
            member_id=self._member_id,
            member_type=self._member_type,
            type_code=self._selected_node.code,
            type_path=type_path,
            event_at=self._get_datetime_iso(),
            lieu_label=self._selected_lieu_label if self._selected_node.requires_lieu else None,
            subject_label=self._selected_subject if self._selected_node.requires_subject else None,
            note=self._note_input.text() if self._note_input else "",
            created_location="intranet",
        )

        self.event_created.emit(event_data)
        self.accept()
