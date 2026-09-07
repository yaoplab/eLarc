"""EventGeneratorDialog — Wizard polymorphe pour créer événements (Student/Staff).

Vue scindée : arbre complet des types à gauche (EventTypeSelectorWidget), formulaire
date/heure/lieu/matière/note à droite. Le professeur peut valider à n'importe quel
niveau de l'arbre ; le champ note n'apparaît que si le choix atteint une feuille.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, QDate, QTime, Signal
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QMessageBox,
    QDateEdit,
    QTimeEdit,
    QFrame,
)

from larccommon.database import db
from larccommon.design_system import ds
from larccommon.event_type_service import EventTypeNode, MemberType, event_type_service
from larccommon.dialogs.event_type_selector import EventTypeSelectorWidget, category_color
from larccommon.l10n import _
from larccommon.logger import log
from larccommon.safe_slot import safe_slot
from larccommon.session import ConnMode, session
from larccommon.theme import theme_manager
from larccommon.widgets.themed_widget import ThemedDialog
from phibuilder.widgets import M3Button, M3Card, M3ComboBox, M3Label, M3Splitter, M3TextField
from phibuilder.widgets.button import ButtonVariant
from phibuilder.widgets.card import CardVariant


@dataclass
class EventData:
    """Résultat du wizard : données à insérer en base."""

    member_id: int  # student_id ou staff_id
    member_type: MemberType
    type_code: str  # Code de larcauth_event_type_config
    type_id: int  # id de larcauth_event_type_config — pour event_type_config_id
    type_path: str  # Chemin lisible : "Absence > Absence de l'école > Maladie"
    event_at: str  # Format ISO : "2026-09-05T14:30:00"
    lieu_label: Optional[str] = None
    subject_label: Optional[str] = None
    note: str = ""
    created_location: str = "intranet"  # "intranet" ou "cloud"


class EventGeneratorDialog(ThemedDialog):
    """
    Wizard polymorphe pour créer événements (Student ou Staff).

    Vue scindée : EventTypeSelectorWidget (gauche) + formulaire (droite).
    Émet Signal(EventData) → caller insère en base.
    """

    event_created = Signal(EventData)

    def __init__(self, member_id: int, member_type: MemberType, parent=None):
        super().__init__(parent)
        self._member_id = member_id
        self._member_type = member_type
        self._selected_node: Optional[EventTypeNode] = None
        self._locations: list = []
        self._subjects: list = []

        self._selector: Optional[EventTypeSelectorWidget] = None
        self._detail_panel: Optional[QWidget] = None
        self._accent_bar: Optional[QFrame] = None
        self._path_label: Optional[M3Label] = None
        self._lieu_label_w: Optional[M3Label] = None
        self._lieu_combo: Optional[M3ComboBox] = None
        self._subject_label_w: Optional[M3Label] = None
        self._subject_combo: Optional[M3ComboBox] = None
        self._date_edit: Optional[QDateEdit] = None
        self._time_edit: Optional[QTimeEdit] = None
        self._note_input: Optional[M3TextField] = None
        self._note_label: Optional[M3Label] = None
        self._validate_btn: Optional[M3Button] = None

        self._type_hierarchies = event_type_service.filter_applicable(member_type)
        if not self._type_hierarchies:
            log(f"EventGeneratorDialog: aucun type pour {member_type.value}")

        member_label = _("event.student") if member_type == MemberType.STUDENT else _("event.staff")
        self.setWindowTitle(f"{member_label} {member_id}")
        self.setMinimumWidth(ds.window_width * 9 // 10)
        self.setMinimumHeight(ds.window_height * 3 // 4)

        self._load_locations()
        self._load_subjects()
        self._init_ui()
        ds.theme_changed.connect(self._restyle_all)
        self._restyle_all()

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
        """

    @safe_slot("EventGeneratorDialog._restyle_all")
    def _restyle_all(self):
        try:
            self.setStyleSheet(self._STYLE)
        except RuntimeError:
            pass

    def _load_locations(self):
        try:
            conn = db.server_conn
            if not conn:
                return
            cur = conn.cursor()
            cur.execute('SELECT "IDLieu", "s_IDLieu", "Lieu" FROM larcauth_lieu')
            self._locations = cur.fetchall()
        except Exception as e:
            log(f"EventGeneratorDialog._load_locations: {e}")
            self._locations = []

    def _load_subjects(self):
        """Matières de la classe de l'élève pour le terme courant — sans objet pour le staff."""
        if self._member_type != MemberType.STUDENT:
            return
        try:
            conn = db.server_conn
            if not conn:
                return
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT label FROM larcauth_classroom_termsubject
                WHERE fk_classroom_id = (
                          SELECT s_classroom_id FROM larcauth_student WHERE aecuser_ptr_id = %s
                      )
                  AND fk_term_id = %s AND enabled = TRUE
                ORDER BY label
                """,
                (self._member_id, getattr(session, "term_id", None)),
            )
            self._subjects = [row[0] for row in cur.fetchall()]
            if not self._subjects:
                # Repli : les données de matières du terme courant ne sont pas encore
                # saisies (cf. audit 2026-08-14, créneaux 2026-2027 non générés) — plutôt
                # qu'un champ vide inutilisable, on retombe sur le terme le plus récent
                # pour lequel la classe a des matières.
                cur.execute(
                    """
                    SELECT DISTINCT label FROM larcauth_classroom_termsubject
                    WHERE fk_classroom_id = (
                              SELECT s_classroom_id FROM larcauth_student WHERE aecuser_ptr_id = %s
                          )
                      AND enabled = TRUE
                      AND fk_term_id = (
                              SELECT MAX(fk_term_id) FROM larcauth_classroom_termsubject
                              WHERE fk_classroom_id = (
                                        SELECT s_classroom_id FROM larcauth_student
                                        WHERE aecuser_ptr_id = %s
                                    )
                          )
                    ORDER BY label
                    """,
                    (self._member_id, self._member_id),
                )
                self._subjects = [row[0] for row in cur.fetchall()]
        except Exception as e:
            log(f"EventGeneratorDialog._load_subjects: {e}")
            self._subjects = []

    def _init_ui(self):
        self.setObjectName("evt_root")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(ds.space_lg, ds.space_lg, ds.space_lg, ds.space_lg)

        splitter = M3Splitter(Qt.Horizontal, theme=theme_manager.phi_theme)

        self._selector = EventTypeSelectorWidget(self._type_hierarchies)
        self._selector.type_confirmed.connect(self._on_type_confirmed)
        splitter.addWidget(self._selector)

        self._detail_panel = self._build_detail_panel()
        splitter.addWidget(self._detail_panel)
        splitter.setStretchFactor(0, 45)
        splitter.setStretchFactor(1, 55)

        outer.addWidget(splitter, 1)

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        fl = QVBoxLayout(panel)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(ds.space_md)

        card = M3Card(variant=CardVariant.ELEVATED)
        cl = card.content_layout()
        cl.setSpacing(ds.space_md)

        self._accent_bar = QFrame()
        self._accent_bar.setFixedHeight(ds.space_xxs)
        cl.addWidget(self._accent_bar)

        self._path_label = M3Label("", style="title_medium")
        self._path_label.setWordWrap(True)
        cl.addWidget(self._path_label)

        grid = QVBoxLayout()
        grid.setSpacing(ds.space_sm)

        row1 = QHBoxLayout()
        row1.setSpacing(ds.space_md)
        lieu_col = QVBoxLayout()
        self._lieu_label_w = M3Label(_("event.location"), style="body_medium")
        self._lieu_combo = M3ComboBox(
            [loc[2] for loc in self._locations], theme=theme_manager.phi_theme
        )
        lieu_col.addWidget(self._lieu_label_w)
        lieu_col.addWidget(self._lieu_combo)
        row1.addLayout(lieu_col, 1)

        subject_col = QVBoxLayout()
        self._subject_label_w = M3Label(_("event.subject"), style="body_medium")
        self._subject_combo = M3ComboBox(self._subjects, theme=theme_manager.phi_theme)
        subject_col.addWidget(self._subject_label_w)
        subject_col.addWidget(self._subject_combo)
        row1.addLayout(subject_col, 1)
        grid.addLayout(row1)
        for w in (self._lieu_label_w, self._lieu_combo, self._subject_label_w, self._subject_combo):
            w.hide()

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
        grid.addLayout(dr)

        cl.addLayout(grid)

        self._note_label = M3Label(_("event.note"), style="body_medium")
        self._note_input = M3TextField(placeholder=_("event.note_placeholder"))
        self._note_input.setMaxLength(200)
        cl.addWidget(self._note_label)
        cl.addWidget(self._note_input)
        self._note_label.hide()
        self._note_input.hide()

        fl.addWidget(card, 1)
        fl.addStretch()

        ar = QHBoxLayout()
        ar.addStretch()
        cb = M3Button(_("common.button.cancel"), variant=ButtonVariant.OUTLINED)
        cb.clicked.connect(self.reject)
        ar.addWidget(cb)
        self._validate_btn = M3Button(_("event.validate_button"), variant=ButtonVariant.FILLED)
        self._validate_btn.setEnabled(False)
        self._validate_btn.clicked.connect(self._on_validate)
        ar.addWidget(self._validate_btn)
        fl.addLayout(ar)

        return panel

    @safe_slot("EventGeneratorDialog._on_type_confirmed")
    def _on_type_confirmed(self, node: EventTypeNode):
        """Le professeur a cliqué 'Confirmer ce choix' (feuille ou nœud intermédiaire)."""
        self._selected_node = node
        self._validate_btn.setEnabled(True)

        self._path_label.setText(event_type_service.get_path(node))
        self._accent_bar.setStyleSheet(
            f"background: {category_color(node.category)}; border-radius: {ds.radius_xs}px;"
        )

        show_lieu = node.requires_lieu
        self._lieu_label_w.setVisible(show_lieu)
        self._lieu_combo.setVisible(show_lieu)
        if show_lieu:
            default_idx = self._lieu_combo.findText(_("event.default_lieu"))
            if default_idx >= 0:
                self._lieu_combo.setCurrentIndex(default_idx)

        show_subject = node.requires_subject and self._member_type == MemberType.STUDENT
        self._subject_label_w.setVisible(show_subject)
        self._subject_combo.setVisible(show_subject)

        is_leaf = EventTypeSelectorWidget.is_leaf(node)
        self._note_label.setVisible(is_leaf)
        self._note_input.setVisible(is_leaf)
        if not is_leaf:
            self._note_input.clear()

    def _check_working_day(self) -> bool:
        try:
            conn = db.server_conn
            if not conn:
                return True
            date = self._date_edit.date().toPython()
            cur = conn.cursor()
            cur.execute("SELECT working_day FROM larcauth_agenda WHERE date_all = %s", (date,))
            row = cur.fetchone()
            return bool(row[0]) if row else True
        except Exception as e:
            log(f"EventGeneratorDialog._check_working_day: {e}")
            return True

    def _check_active_term(self) -> bool:
        try:
            conn = db.server_conn
            if not conn:
                return True
            cur = conn.cursor()
            cur.execute("SELECT current_term_number FROM larcauth_academicyear LIMIT 1")
            return bool(cur.fetchone())
        except Exception as e:
            log(f"EventGeneratorDialog._check_active_term: {e}")
            return True

    def _get_datetime_iso(self) -> str:
        date = self._date_edit.date().toPython()
        time = self._time_edit.time().toPython()
        return f"{date}T{time}"

    @safe_slot("EventGeneratorDialog._on_validate")
    def _on_validate(self):
        if not self._check_working_day():
            QMessageBox.warning(self, _("event.error"), _("event.error_not_working_day"))
            return
        if not self._check_active_term():
            QMessageBox.warning(self, _("event.error"), _("event.error_inactive_term"))
            return
        if not self._selected_node:
            QMessageBox.warning(self, _("event.error"), _("event.error_no_type"))
            return

        node = self._selected_node
        is_leaf = EventTypeSelectorWidget.is_leaf(node)
        show_subject = node.requires_subject and self._member_type == MemberType.STUDENT

        event_data = EventData(
            member_id=self._member_id,
            member_type=self._member_type,
            type_code=node.code,
            type_id=node.id,
            type_path=event_type_service.get_path(node),
            event_at=self._get_datetime_iso(),
            lieu_label=self._lieu_combo.currentText() if node.requires_lieu else None,
            subject_label=self._subject_combo.currentText() if show_subject else None,
            note=(self._note_input.text() if is_leaf and self._note_input else ""),
            created_location="cloud" if session.conn_mode == ConnMode.CLOUD else "intranet",
        )

        self.event_created.emit(event_data)
        self.accept()
