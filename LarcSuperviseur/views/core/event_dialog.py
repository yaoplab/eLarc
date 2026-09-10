from larccommon.design_system import ds
from larccommon.dialogs import EventTypeSelectorWidget
from larccommon.event_type_service import event_type_service, MemberType
from larccommon.l10n import _
from phibuilder.widgets import M3Button, M3Dialog, M3Label, M3TextEdit
from phibuilder.widgets.button import ButtonVariant
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QVBoxLayout,
)

from LarcSuperviseur.common.database import db
from LarcSuperviseur.common.session import session
from LarcSuperviseur.common.theme import theme_manager
from larccommon.safe_slot import safe_slot


class EventEditDialog(M3Dialog):
    def __init__(self, event_id: int, parent=None):
        super().__init__(parent)
        self._event_id = event_id
        self._conn = db.server_conn
        self._selected_node = None
        self.setWindowTitle(_("event_dialog.title").format(id=event_id))
        self.setMinimumSize(ds.window_width * 3 // 5, ds.window_height * 4 // 5)
        p = theme_manager.palette
        self.setStyleSheet(f"EventEditDialog {{ background-color: {p.surface}; border-radius: {ds.radius_lg}px; }}")
        self._setup_ui()
        self._load_event()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        if not db.is_server_connected:
            return

        self._info = M3Label(theme=theme_manager.phi_theme)
        self._info.setWordWrap(True)
        self._info.setTextFormat(Qt.RichText)
        layout.addWidget(self._info)

        hierarchies = event_type_service.filter_applicable(
            MemberType.STUDENT, getattr(session, "fk_language", 2)
        )
        self._selector = EventTypeSelectorWidget(hierarchies)
        self._selector.type_confirmed.connect(self._on_type_confirmed)
        layout.addWidget(self._selector, 1)

        self._note_label = M3Label(_("event_dialog.note"), theme=theme_manager.phi_theme)
        self._note_input = M3TextEdit(theme=theme_manager.phi_theme)
        self._note_input.setMaximumHeight(ds.window_height * 3 // 20)
        self._note_input.setAccessibleName(_("event_dialog.note"))
        self._note_input.setToolTip(_("event.note_tooltip"))
        self._note_input.textChanged.connect(self._on_note_changed)
        layout.addWidget(self._note_label)
        layout.addWidget(self._note_input)
        self._note_label.hide()
        self._note_input.hide()

        p = theme_manager.palette
        btn_row = QHBoxLayout()
        save_btn = M3Button(_("event_dialog.save_button"), theme=theme_manager.phi_theme)
        save_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; "
            f"border: none; border-radius: {ds.radius_sm}px; "
            f"padding: {ds.space_xs}px {ds.space_md}px; font-weight: bold; }}"
        )
        save_btn.clicked.connect(self._save)
        cancel_btn = M3Button(_("event_dialog.cancel_button"), theme=theme_manager.phi_theme, variant=ButtonVariant.OUTLINED)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _load_event(self):
        conn = self._conn
        if not conn:
            QMessageBox.warning(self, _("common.dialog.error"), _("event_dialog.no_connection"))
            self.reject()
            return
        cur = conn.cursor()
        cur.execute(
            """
            SELECT se.event_type, se.event_type_config_id, se.event_at, se.lieu_label,
                   se.subject_label, se.note,
                   aec.last_name || ' ' || aec.first_name AS student_name
            FROM student_event se
            JOIN larcauth_aecuser aec ON aec.id = se.student_id
            WHERE se.event_id = %s
        """,
            (self._event_id,),
        )
        row = cur.fetchone()
        if not row:
            QMessageBox.warning(self, _("common.dialog.error"), _("event_dialog.not_found"))
            self.reject()
            return
        etype, etype_config_id, e_at, lieu, subject, note, student_name = row
        p = theme_manager.palette
        s = theme_manager.font_size
        self._info.setText(
            f"<b style='color:{p.text_strong}'>{student_name}</b> — {etype}<br>"
            f"<span style='color:{p.text_disabled};font-size:{s(10)}px;'>"
            f"{e_at.strftime('%d/%m/%Y %H:%M') if e_at else ''} | {lieu or ''}"
            f"{' | ' + subject if subject else ''}</span>"
        )
        self._note_input.setText(note or "")
        if etype_config_id:
            node = event_type_service.get_by_id(etype_config_id)
            if node:
                self._selected_node = node
                self._selector.preselect(node)
                is_leaf = EventTypeSelectorWidget.is_leaf(node)
                self._note_label.setVisible(is_leaf)
                self._note_input.setVisible(is_leaf)

    @safe_slot("EventEditDialog._on_type_confirmed")
    def _on_type_confirmed(self, node):
        self._selected_node = node
        is_leaf = EventTypeSelectorWidget.is_leaf(node)
        self._note_label.setVisible(is_leaf)
        self._note_input.setVisible(is_leaf)
        if not is_leaf:
            self._note_input.clear()

    @safe_slot("EventEditDialog._on_note_changed")
    def _on_note_changed(self):
        """Tronque la note à 200 caractères (M3TextEdit n'a pas de setMaxLength natif)."""
        text = self._note_input.toPlainText()
        if len(text) > 200:
            cursor = self._note_input.textCursor()
            pos = cursor.position()
            self._note_input.blockSignals(True)
            self._note_input.setPlainText(text[:200])
            cursor.setPosition(min(pos, 200))
            self._note_input.setTextCursor(cursor)
            self._note_input.blockSignals(False)

    @safe_slot("EventEditDialog._save")
    def _save(self):
        conn = self._conn
        if not conn:
            return
        if not self._selected_node:
            QMessageBox.warning(self, _("common.dialog.error"), _("event.error_no_type"))
            return
        is_leaf = EventTypeSelectorWidget.is_leaf(self._selected_node)
        cur = conn.cursor()
        cur.execute(
            "UPDATE student_event SET event_type = %s, event_type_config_id = %s, note = %s WHERE event_id = %s",
            (
                event_type_service.get_path(self._selected_node),
                self._selected_node.id,
                self._note_input.toPlainText().strip() if is_leaf else "",
                self._event_id,
            ),
        )
        conn.commit()
        self.accept()
