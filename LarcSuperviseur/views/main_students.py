"""Mixin StudentsMixin — voir views/main_window.py (découpage règle FS, lot 4)."""


from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from larccommon.session import UserRole
from phibuilder.widgets import (
    M3Button,
    M3ComboBox,
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
from LarcSuperviseur.views.core.cardsList.card import StudentCard
from LarcSuperviseur.views.core.cardsList.config import CARD_THEMES
from LarcSuperviseur.views.core.event_actions import EventActions
from LarcSuperviseur.views.core.time_manager import TimeManager
from LarcSuperviseur.views.dialogs.event_generator import EventGenerator
from LarcSuperviseur.views.dialogs.timetable_editor import TimetableEditor
from LarcSuperviseur.views.panels.student_detail import StudentDetail
from LarcSuperviseur.views.top_bar import TopBar
from larccommon.widgets.sidebar import SidebarWidget
from larccommon.widgets.skeleton import M3Skeleton
from larccommon.widgets.themed_widget import ThemedWidget


class StudentsMixin:
    def _show_class_mode(self, class_id: int):
        self._content_stack.setCurrentIndex(1)
        self._class_stack.setCurrentIndex(0)
        self._top_bar.show_period_row(False)

        p = theme_manager.palette
        self._cards_title.setText(f"<b style='color:{p.text_strong}'>{_('main.students_of')} {self._current_class_label}</b>")
        self._load_students(class_id)
        self._selected_student_id = 0

    def _load_students(self, class_id: int):
        if not db.is_server_connected:
            return
        if getattr(self, "_loading_students", False):
            return
        self._loading_students = True
        try:
            self._top_bar.set_loading(True, _("topbar.loading_students"))
            # Afficher le skeleton
            self._class_stack.setCurrentIndex(1)
            self._cards_skeleton.start()
            QApplication.processEvents()
            conn = db.server_conn
            if not conn or not self._time_manager.term_id:
                return

            today = QDate.currentDate().toString("yyyy-MM-dd")

            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.aecuser_ptr_id,
                       aec.last_name, aec.first_name,
                       COALESCE(s.validation, '{}'::jsonb) AS validation
                FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                WHERE s.s_classroom_id = %s AND s.enabled = TRUE
                ORDER BY aec.last_name
            """,
                (class_id,),
            )
            rows = cur.fetchall()

            self._students = [{"id": r[0], "last_name": r[1], "first_name": r[2],
                              "validation": r[3]} for r in rows]

            # Stats d'events pour chaque eleve
            student_ids = [s["id"] for s in self._students]
            period_from, period_to = self._time_manager.period_dates()
            event_stats = {}
            if student_ids:
                ids_sql = ",".join(str(sid) for sid in student_ids)
                # Sorties : sur la periode (trimestre, mois, etc.)
                try:
                    cur.execute(
                        f"""
                        SELECT se.student_id,
                               COUNT(*) AS exit_count
                         FROM student_event se
                         WHERE se.student_id IN ({ids_sql})
                            AND DATE(se.event_at) BETWEEN %s AND %s
                            AND (se.event_type = %s OR se.event_type ILIKE %s OR se.event_type ILIKE %s OR se.event_type ILIKE %s)
                         GROUP BY se.student_id
                     """,
                        (period_from, period_to, "exit", "Sortie%", "%Fuite%", "Fugue%"),
                    )
                    for sid, exit_count in cur.fetchall():
                        event_stats.setdefault(sid, {})["exit"] = exit_count
                except Exception as e:
                    from larccommon.error_reporting import get_reporter
                    get_reporter().report_exception()
                    log(f"_load_students: exit_stats: {e}")
                # Evenements totaux sur la periode (hors sorties)
                try:
                    cur.execute(
                        f"""
                        SELECT se.student_id,
                               COUNT(*) AS total_events
                         FROM student_event se
                         WHERE se.student_id IN ({ids_sql})
                            AND DATE(se.event_at) BETWEEN %s AND %s
                         GROUP BY se.student_id
                     """,
                        (period_from, period_to),
                    )
                    for sid, total_events in cur.fetchall():
                        event_stats.setdefault(sid, {})["total_events"] = total_events
                except Exception as e:
                    from larccommon.error_reporting import get_reporter
                    get_reporter().report_exception()
                    log(f"_load_students: event_stats: {e}")
                # Presence : aujourd'hui uniquement
                try:
                    cur.execute(
                        f"""
                        SELECT se.student_id,
                               CASE WHEN COUNT(*) FILTER (WHERE (se.event_type = %s
                                   OR se.event_type ILIKE %s OR se.event_type ILIKE %s)
                                   AND se.validated_by IS NULL) > 0 THEN 'Absent' ELSE 'Present' END AS presence
                         FROM student_event se
                         WHERE se.student_id IN ({ids_sql})
                            AND DATE(se.event_at) = %s
                         GROUP BY se.student_id
                     """,
                        ("absence", "Suivi > Absence%", "Absence%", today),
                    )
                    for sid, presence in cur.fetchall():
                        event_stats.setdefault(sid, {})["presence"] = presence
                except Exception as e:
                    from larccommon.error_reporting import get_reporter
                    get_reporter().report_exception()
                    log(f"_load_students: presence_stats: {e}")

            # Vider les cartes existantes
            for i in reversed(range(self._cards_layout.count())):
                w = self._cards_layout.itemAt(i).widget()
                if w:
                    w.deleteLater()

            # Grille multi-colonnes avec scroll vertical
            self._card_theme = session.card_theme
            cfg = CARD_THEMES.get(self._card_theme)
            card_w = cfg.card_w + cfg.margin * 2
            avail_w = self._cards_scroll.viewport().width()
            spacing = self._cards_layout.spacing()
            cols = max(1, (avail_w + spacing) // (card_w + spacing)) if avail_w > 100 else 2
            self._student_cards = []  # [(card, search_text)] — pour le filtre de recherche
            for idx, s in enumerate(self._students):
                sid = s["id"]
                card = StudentCard(sid, s["last_name"], s["first_name"], cfg=cfg)
                card.set_role(StudentCard._ROLE_SUPERVISOR)
                stats = event_stats.get(sid, {})
                exit_count = stats.get("exit", 0)
                total_events = stats.get("total_events", 0)
                presence = stats.get("presence", "Present")
                card.set_event_count(total_events)
                card.set_exit_count(exit_count)
                is_absent = presence == "Absent"
                color = theme_manager.palette.error if is_absent else theme_manager.palette.success
                card.set_status(presence, color)
                card.set_absent(is_absent)
                card.clicked.connect(self._on_student_selected)
                search_text = f"{s['last_name']} {s['first_name']}".strip().lower()
                self._student_cards.append((card, search_text))
                self._cards_layout.addWidget(card, idx // cols, idx % cols, Qt.AlignCenter)
            # Réappliquer le filtre en cours (ex: rechargement après changement de classe)
            if getattr(self, "_student_search", None) and self._student_search.text():
                self._on_student_search_changed(self._student_search.text())

            # --- Absents du jour pour cette classe ---
            try:
                cur.execute(
                    """
                    SELECT aec.last_name || ' ' || aec.first_name AS name, se.event_type
                    FROM student_event se
                    JOIN larcauth_student s ON s.aecuser_ptr_id = se.student_id
                    JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                    WHERE s.s_classroom_id = %s
                      AND (se.event_type = %s OR se.event_type ILIKE %s OR se.event_type ILIKE %s)
                      AND DATE(se.event_at) = %s
                      AND se.validated_by IS NULL
                    ORDER BY aec.last_name
                    LIMIT 30
                """,
                    (class_id, "absence", "Suivi > Absence%", "Absence%", today),
                )
                abs_rows = cur.fetchall()
                self._class_absents_table.setRowCount(len(abs_rows))
                for i, (name, motif) in enumerate(abs_rows):
                    self._class_absents_table.setItem(i, 0, QTableWidgetItem(name))
                    self._class_absents_table.setItem(i, 1, QTableWidgetItem(motif))
                self._class_absents_group.setVisible(bool(abs_rows))
            except Exception:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                self._class_absents_group.setVisible(False)

            self._top_bar.set_loading(False)

        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_load_students: {e}")
            self._top_bar.set_loading(False)
        finally:
            self._cards_skeleton.stop()
            self._class_stack.setCurrentIndex(0)
            self._loading_students = False

    @safe_slot("StudentsMixin._on_student_search_changed")
    def _on_student_search_changed(self, text: str):
        """Filtre live des cartes élèves par nom/prénom (recherche insensible à la casse)."""
        needle = (text or "").strip().lower()
        for card, search_text in getattr(self, "_student_cards", []):
            card.setVisible(not needle or needle in search_text)

