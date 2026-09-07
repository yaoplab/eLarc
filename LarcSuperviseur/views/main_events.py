"""Mixin EventsMixin — voir views/main_window.py (découpage règle FS, lot 4)."""


from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from larccommon.session import UserRole
from phibuilder.widgets import (
    M3Button,
    M3Frame,
    M3HeaderView,
    M3Label,
    M3Menu,
    M3ScrollArea,
    M3StackedWidget,
    M3TableWidget,
    M3TabWidget,
    M3TextEdit,
)
from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QDateTimeAxis,
    QLineSeries,
    QPieSeries,
    QValueAxis,
)
from PySide6.QtCore import QDate, QDateTime, QEvent, QSize, Qt, QTime, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from LarcSuperviseur.common.database import db
from LarcSuperviseur.views.panels.event_types_panel import EventTypesPanel
from LarcSuperviseur.common.event_helpers import event_color, event_icon
from LarcSuperviseur.common.logger import log
from LarcSuperviseur.common.session import session
from LarcSuperviseur.common.theme import QssHelper, theme_manager
from larccommon.theme import PROGRAM_STYLES
from LarcSuperviseur.common.trace import trace
from larccommon.dialogs import EventGeneratorDialog, EventData, MemberType, EventTypeSelectorWidget
from larccommon.event_type_service import event_type_service
from LarcSuperviseur.common.database import db
from LarcSuperviseur.views.core.cardsList.card import StudentCard
from LarcSuperviseur.views.core.cardsList.config import CARD_THEMES
from LarcSuperviseur.views.core.event_actions import EventActions
from LarcSuperviseur.views.core.time_manager import TimeManager
from LarcSuperviseur.views.dialogs.timetable_editor import TimetableEditor
from LarcSuperviseur.views.panels.student_detail import StudentDetail
from LarcSuperviseur.views.top_bar import TopBar
from larccommon.widgets.sidebar import SidebarWidget
from larccommon.widgets.skeleton import M3Skeleton
from larccommon.widgets.themed_widget import ThemedWidget


class EventsMixin:
    def _on_add_event(self):
        if not db.is_server_connected:
            return
        sid = self._selected_student_id
        if not sid:
            return
        dlg = EventGeneratorDialog(sid, MemberType.STUDENT, self)
        dlg.event_created.connect(self._insert_student_event)
        dlg.exec()

    def _insert_student_event(self, evt: EventData):
        """Insère l'événement créé dans la table student_event."""
        conn = db.server_conn
        if not conn:
            QMessageBox.warning(self, _("common.error"), _("main.error_no_db_connection"))
            return
        self._top_bar.set_loading(True, _("main.saving"))
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO student_event
                (student_id, event_type, event_type_config_id, event_at, lieu_label,
                 subject_label, note, source, created_by, created_location)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    evt.member_id,
                    evt.type_path,
                    evt.type_id,
                    evt.event_at,
                    evt.lieu_label,
                    evt.subject_label,
                    evt.note,
                    "EventGeneratorDialog",
                    session.user_id,
                    evt.created_location,
                ),
            )
            conn.commit()
            self._top_bar.set_loading(False)
            self._load_student_detail(evt.member_id)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_on_add_event insert: {e}")
            self._top_bar.set_loading(False)
            conn.rollback()
            QMessageBox.critical(
                self, _("common.error"), f"{_('main.error_save_failed')} : {e}"
            )

    def _get_event_id_from_table(self, table: M3TableWidget) -> int | None:
        idx = table.currentRow()
        if idx < 0:
            return None
        item = table.item(idx, 0)
        return int(item.text()) if item and item.text().isdigit() else None

    @safe_slot("MainWindow.edit_event")
    def _edit_event(self, event_id: int):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            QMessageBox.warning(self, _("common.error"), _("main.error_no_db_connection"))
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
            (event_id,),
        )
        row = cur.fetchone()
        if not row:
            QMessageBox.warning(self, _("common.error"), _("main.error_event_not_found"))
            return
        etype, etype_config_id, e_at, lieu, subject, note, student_name = row

        dlg = QDialog(self)
        dlg.setWindowTitle(f"{_('event.edit_title')} #{event_id}")
        dlg.setMinimumSize(ds.window_width * 3 // 5, ds.window_height * 4 // 5)
        layout = QVBoxLayout(dlg)
        p = theme_manager.palette

        info = M3Label(
            f"<b>{student_name}</b> — {etype}<br>"
            f"<span style='color:{p.text_disabled};font-size:{theme_manager.font_size(10)}px;'>"
            f"{e_at.strftime('%d/%m/%Y %H:%M') if e_at else ''} | {lieu or ''}"
            f"{' | ' + subject if subject else ''}</span>"
        )
        info.setWordWrap(True)
        info.setTextFormat(Qt.RichText)
        layout.addWidget(info)

        hierarchies = event_type_service.filter_applicable(MemberType.STUDENT)
        selector = EventTypeSelectorWidget(hierarchies)
        existing_node = event_type_service.get_by_id(etype_config_id) if etype_config_id else None
        if existing_node:
            selector.preselect(existing_node)
        layout.addWidget(selector, 1)

        note_label = M3Label(_("event.edit_note"))
        note_input = M3TextEdit()
        note_input.setText(note or "")
        note_input.setMaximumHeight(ds.space_xxl + ds.space_lg)
        note_label.setVisible(existing_node is not None and EventTypeSelectorWidget.is_leaf(existing_node))
        note_input.setVisible(note_label.isVisible())
        layout.addWidget(note_label)
        layout.addWidget(note_input)

        state = {"node": existing_node}

        @safe_slot("MainWindow.edit_event.on_type_confirmed")
        def on_type_confirmed(node):
            state["node"] = node
            is_leaf = EventTypeSelectorWidget.is_leaf(node)
            note_label.setVisible(is_leaf)
            note_input.setVisible(is_leaf)
            if not is_leaf:
                note_input.clear()

        selector.type_confirmed.connect(on_type_confirmed)

        btn_row = QHBoxLayout()
        save_btn = M3Button(_("event.save"))
        save_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; "
            f"border: none; border-radius: {theme_manager.design.radius}px; "
            f"padding: {ds.space_xs}px {ds.space_md}px; font-weight: bold; }}"
        )

        @safe_slot("MainWindow.edit_event.save")
        def on_save():
            node = state["node"]
            if not node:
                QMessageBox.warning(dlg, _("common.error"), _("event.error_no_type"))
                return
            is_leaf = EventTypeSelectorWidget.is_leaf(node)
            cur.execute(
                "UPDATE student_event SET event_type = %s, event_type_config_id = %s, note = %s WHERE event_id = %s",
                (
                    event_type_service.get_path(node),
                    node.id,
                    note_input.toPlainText().strip() if is_leaf else "",
                    event_id,
                ),
            )
            conn.commit()
            dlg.accept()

        save_btn.clicked.connect(on_save)
        cancel_btn = M3Button(_("event.cancel"))
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        if dlg.exec() == QDialog.Accepted:
            self.refresh_all()

    @safe_slot("MainWindow.on_history_dblclick")
    def _on_history_dblclick(self, row: int, col: int):
        table = self._history_table
        item = table.item(row, 0)
        eid = int(item.text()) if item and item.text().isdigit() else None
        if eid:
            self._edit_event(eid)

    def eventFilter(self, obj, event):
        if (
            obj is self._history_table
            and event.type() == QEvent.KeyPress
            and event.key() in (Qt.Key_Return, Qt.Key_Enter)
        ):
            row = self._history_table.currentRow()
            if row >= 0:
                self._on_history_dblclick(row, 0)
                return True
        return super().eventFilter(obj, event)

    def _show_event_context_menu(self, table: M3TableWidget, pos):
        eid = self._get_event_id_from_table(table)
        if not eid:
            return
        event = self._actions.get_event_by_id(eid)
        is_validated = event is not None and event.get("validated_by") is not None
        menu = M3Menu(self)
        edit_action = menu.addAction(
            md3_icon(
                "edit", color=theme_manager.palette.text_strong, size=ds.icon_sm
            ),
            _("context_menu.edit"),
        )
        validate_action = menu.addAction(
            md3_icon(
                "lock" if is_validated else "check_circle",
                color=theme_manager.palette.text_strong,
                size=ds.icon_sm,
            ),
            _("context_menu.invalidate") if is_validated else _("context_menu.validate"),
        )
        delete_action = menu.addAction(
            md3_icon(
                "delete",
                color=theme_manager.palette.text_strong,
                size=ds.icon_sm,
            ),
            _("context_menu.delete"),
        )
        chosen = menu.exec(table.viewport().mapToGlobal(pos))
        if chosen == edit_action:
            self._edit_event(eid)
        elif chosen == validate_action:
            self._toggle_validation(eid)
        elif chosen == delete_action:
            self._delete_event(eid)

    def _toggle_validation(self, event_id: int):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("SELECT validated_by FROM student_event WHERE event_id = %s", (event_id,))
            row = cur.fetchone()
            if row and row[0] is not None:
                cur.execute(
                    "UPDATE student_event SET validated_by = NULL WHERE event_id = %s", (event_id,)
                )
            else:
                cur.execute(
                    "UPDATE student_event SET validated_by = %s WHERE event_id = %s",
                    (session.user_id, event_id),
                )
            conn.commit()
            self.refresh_all()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_toggle_validation: {e}")
            conn.rollback()

    def _delete_event(self, event_id: int):
        if not db.is_server_connected:
            return
        reply = QMessageBox.question(
            self,
            _("main.confirm_delete_title"),
            f"{_('main.confirm_delete_message')} #{event_id} ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM student_event WHERE event_id = %s", (event_id,))
            conn.commit()
            self.refresh_all()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_delete_event: {e}")
            conn.rollback()
            QMessageBox.critical(self, _("common.error"), f"{_('main.error_delete_failed')} : {e}")

