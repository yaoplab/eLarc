"""Mixin GroupStatsMixin — voir views/main_window.py (découpage règle FS, lot 4)."""


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
from LarcSuperviseur.views.dialogs.timetable_editor import TimetableEditor
from LarcSuperviseur.views.panels.student_detail import StudentDetail
from LarcSuperviseur.views.top_bar import TopBar
from larccommon.widgets.sidebar import SidebarWidget
from larccommon.widgets.skeleton import M3Skeleton
from larccommon.widgets.themed_widget import ThemedWidget


class GroupStatsMixin:
    def _show_group_mode(self, mode: str):
        self._content_stack.setCurrentIndex(0)
        self._group_scroll.verticalScrollBar().setValue(0)
        self._top_bar.show_period_row(True)
        trace(f" _show_group_mode({mode}): chargement stats + historique")
        self._load_group_stats(mode)
        self._load_global_history(mode)
        trace(f" _show_group_mode({mode}): terminé")

    def _load_group_stats(self, mode: str):
        if not db.is_server_connected:
            return
        self._top_bar.set_loading(True, _("topbar.loading_stats"))
        conn = db.server_conn
        trace(
            f" _load_group_stats: mode={mode}, server_conn={conn is not None}, term_id={self._time_manager.term_id}"
        )
        if not conn or not self._time_manager.term_id:
            self._top_bar.set_loading(False)
            return

        p = theme_manager.palette
        date_from, date_to = self._time_manager.period_dates()
        trace(f" _load_group_stats: mode={mode}, dates={date_from} → {date_to}")

        try:
            cur = conn.cursor()

            if mode == "grp_all":
                class_filter = "AND p.sigle IN ('PYP', 'PP', 'PEI', 'MYP', 'DPEn', 'DPFr')"
            elif mode == "grp_primaire":
                class_filter = "AND (p.sigle ILIKE 'PYP' OR p.sigle ILIKE 'PP')"
            elif mode == "grp_college":
                class_filter = "AND (p.sigle ILIKE 'PEI' OR p.sigle ILIKE 'MYP')"
            elif mode == "grp_lycee":
                class_filter = "AND (p.sigle ILIKE 'DPEn' OR p.sigle ILIKE 'DPFr')"
            else:
                sigle = mode.split("_")[1]
                class_filter = f"AND p.sigle ILIKE '{sigle}'"

            # --- Stats par classe ---
            cur.execute(
                f"""
                SELECT c.id, c.label,
                       COUNT(DISTINCT se.event_id) AS event_count,
                       COUNT(DISTINCT CASE WHEN se.event_type = %s OR se.event_type ILIKE %s OR se.event_type ILIKE %s THEN se.event_id END) AS abs_count,
                       COUNT(DISTINCT CASE WHEN se.event_type = %s OR se.event_type ILIKE %s OR se.event_type ILIKE %s OR se.event_type ILIKE %s THEN se.event_id END) AS exit_count,
                       COUNT(DISTINCT s.aecuser_ptr_id) AS student_count
                FROM larcauth_classroom c
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program p ON p.id = l.fk_program_id
                LEFT JOIN larcauth_student s ON s.s_classroom_id = c.id AND s.enabled = TRUE
                LEFT JOIN student_event se ON se.student_id = s.aecuser_ptr_id
                    AND DATE(se.event_at) BETWEEN %s AND %s
                WHERE c.enabled = TRUE {class_filter}
                GROUP BY c.id, c.label
                ORDER BY c.label
            """,
                (
                    "absence",
                    "Suivi > Absence%",
                    "Absence%",
                    "exit",
                    "Sortie%",
                    "%Fuite%",
                    "Fugue%",
                    date_from,
                    date_to,
                ),
            )

            rows = cur.fetchall()

            # --- KPIs ---
            total_students = sum(r[5] for r in rows)
            total_abs = sum(r[3] for r in rows)
            total_exits = sum(r[4] for r in rows)
            total_events = sum(r[2] for r in rows)

            self._kpi_cards["total"].setText(str(total_students))
            period_key = self._time_manager.current_period
            self._kpi_period.setText(_(f"topbar.period.{period_key}"))
            present_val = max(0, total_students - total_abs) if total_abs > 0 else total_students
            self._kpi_cards["present"].setText(str(present_val))
            self._kpi_cards["absent"].setText(str(total_abs))
            self._kpi_cards["exit"].setText(str(total_exits))

            # --- Liste des absents ---
            self._absents_group.setVisible(total_abs > 0 and self._absents_table.rowCount() > 0)
            if total_abs > 0:
                cur.execute(
                    f"""
                    SELECT aec.last_name || ' ' || aec.first_name AS name,
                           c.label AS class_label, se.event_type
                    FROM student_event se
                    JOIN larcauth_student s ON s.aecuser_ptr_id = se.student_id
                    JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                    JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                    JOIN larcauth_level l ON l.id = c.fk_level_id
                    JOIN larcauth_program p ON p.id = l.fk_program_id
                    WHERE (se.event_type = %s OR se.event_type ILIKE %s OR se.event_type ILIKE %s)
                      AND DATE(se.event_at) BETWEEN %s AND %s
                      AND se.validated_by IS NULL
                      AND c.enabled = TRUE {class_filter}
                    ORDER BY c.label, aec.last_name
                    LIMIT 50
                """,
                    ("absence", "Suivi > Absence%", "Absence%", date_from, date_to),
                )
                abs_rows = cur.fetchall()
                self._absents_table.setRowCount(len(abs_rows))
                for i, (name, cls, motif) in enumerate(abs_rows):
                    self._absents_table.setItem(i, 0, QTableWidgetItem(name))
                    self._absents_table.setItem(i, 1, QTableWidgetItem(cls))
                    self._absents_table.setItem(i, 2, QTableWidgetItem(motif))
                self._absents_group.setVisible(True)

            # --- Table ---
            self._stats_table.setRowCount(len(rows))
            self._stats_table.setColumnCount(5)
            self._stats_table.setHorizontalHeaderLabels(
                [
                    _("table.header.class"),
                    _("table.header.events"),
                    _("table.header.absences"),
                    _("table.header.exits"),
                    _("table.header.students"),
                ]
            )

            for i, (cid, label, evts, absences, exits, students) in enumerate(rows):
                items = [
                    QTableWidgetItem(label),
                    QTableWidgetItem(str(evts)),
                    QTableWidgetItem(str(absences)),
                    QTableWidgetItem(str(exits)),
                    QTableWidgetItem(str(students)),
                ]
                for item in items:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                for j, item in enumerate(items):
                    item.setTextAlignment(Qt.AlignCenter)
                    self._stats_table.setItem(i, j, item)
            hh = self._stats_table.horizontalHeader()
            total_w = self._stats_table.viewport().width()
            col_w = max(80, total_w // 5)
            for c in range(5):
                hh.setSectionResizeMode(c, M3HeaderView.Fixed)
                self._stats_table.setColumnWidth(c, col_w)

            # --- Barres absences par classe ---
            self._abs_bar.removeAllSeries()
            for ax in self._abs_bar.axes():
                self._abs_bar.removeAxis(ax)
            abs_set = QBarSet(_("chart.serie_absences"))
            abs_set.setColor(QColor(p.error))
            cat_names = []
            for r in rows:
                abs_set << r[3]
                cat_names.append(r[1])
            if rows:
                series = QBarSeries()
                series.append(abs_set)
                self._abs_bar.addSeries(series)
                self._abs_bar.setTitle(_("chart.absences_by_class"))
                self._abs_bar.setAnimationOptions(QChart.SeriesAnimations)
                self._abs_bar.legend().setVisible(False)
                axis_x = QBarCategoryAxis()
                axis_x.append(cat_names)
                axis_x.setLabelsAngle(-45)
                self._abs_bar.addAxis(axis_x, Qt.AlignBottom)
                series.attachAxis(axis_x)
                axis_y = QValueAxis()
                max_abs = max(r[3] for r in rows)
                axis_y.setRange(0, max(max_abs + 2, 10))
                self._abs_bar.addAxis(axis_y, Qt.AlignLeft)
                series.attachAxis(axis_y)
            else:
                self._abs_bar.setTitle(_("chart.absences_by_class_empty"))

            # --- Barres sorties par classe ---
            self._exit_bar.removeAllSeries()
            for ax in self._exit_bar.axes():
                self._exit_bar.removeAxis(ax)
            exit_set = QBarSet(_("chart.serie_exits"))
            exit_set.setColor(QColor(p.tertiary))
            for r in rows:
                exit_set << r[4]
            if rows:
                exit_series = QBarSeries()
                exit_series.append(exit_set)
                self._exit_bar.addSeries(exit_series)
                self._exit_bar.setTitle(_("chart.exits_by_class"))
                self._exit_bar.setAnimationOptions(QChart.SeriesAnimations)
                self._exit_bar.legend().setVisible(False)
                ex_axis_x = QBarCategoryAxis()
                ex_axis_x.append(cat_names)
                ex_axis_x.setLabelsAngle(-45)
                self._exit_bar.addAxis(ex_axis_x, Qt.AlignBottom)
                exit_series.attachAxis(ex_axis_x)
                ex_axis_y = QValueAxis()
                max_exit = max(r[4] for r in rows)
                ex_axis_y.setRange(0, max(max_exit + 2, 5))
                self._exit_bar.addAxis(ex_axis_y, Qt.AlignLeft)
                exit_series.attachAxis(ex_axis_y)
            else:
                self._exit_bar.setTitle(_("chart.exits_by_class_empty"))

            # --- Tendance absences sur la période ---
            self._trend_chart.removeAllSeries()
            for ax in self._trend_chart.axes():
                self._trend_chart.removeAxis(ax)
            cur.execute(
                f"""
                SELECT DATE(se.event_at) AS d, COUNT(*) AS cnt
                FROM student_event se
                JOIN larcauth_student s ON s.aecuser_ptr_id = se.student_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program p ON p.id = l.fk_program_id
                WHERE (se.event_type = %s OR se.event_type ILIKE %s OR se.event_type ILIKE %s)
                  AND c.enabled = TRUE {class_filter}
                  AND DATE(se.event_at) BETWEEN %s AND %s
                GROUP BY d ORDER BY d
            """,
                ("absence", "Suivi > Absence%", "Absence%", date_from, date_to),
            )
            trend_rows = cur.fetchall()
            if trend_rows:
                line = QLineSeries()
                line.setColor(QColor(p.error))
                line.setName(_("chart.serie_absences"))
                for d, cnt in trend_rows:
                    qd = QDate(d.year, d.month, d.day)
                    dt = QDateTime(qd, QTime(0, 0))
                    line.append(dt.toMSecsSinceEpoch(), cnt)
                self._trend_chart.addSeries(line)
                self._trend_chart.setTitle(_("chart.trend_absences"))
                self._trend_chart.setAnimationOptions(QChart.SeriesAnimations)
                self._trend_chart.legend().setVisible(False)
                axis_x_dt = QDateTimeAxis()
                axis_x_dt.setFormat("dd/MM")
                axis_x_dt.setLabelsAngle(-45)
                self._trend_chart.addAxis(axis_x_dt, Qt.AlignBottom)
                line.attachAxis(axis_x_dt)
                axis_y_t = QValueAxis()
                max_t = max(r[1] for r in trend_rows)
                axis_y_t.setRange(0, max_t + 2)
                self._trend_chart.addAxis(axis_y_t, Qt.AlignLeft)
                line.attachAxis(axis_y_t)
            else:
                self._trend_chart.setTitle(_("chart.trend_absences_empty"))

            # --- Donut taux de présence ---
            self._donut_chart.removeAllSeries()
            cur.execute(
                f"""
                SELECT COUNT(DISTINCT s.aecuser_ptr_id) FILTER (
                    WHERE NOT EXISTS (
                        SELECT 1 FROM student_event se2
                        WHERE se2.student_id = s.aecuser_ptr_id
                          AND (se2.event_type = %s OR se2.event_type ILIKE %s OR se2.event_type ILIKE %s)
                          AND DATE(se2.event_at) BETWEEN %s AND %s
                    )
                ) AS present,
                COUNT(DISTINCT s.aecuser_ptr_id) FILTER (
                    WHERE EXISTS (
                        SELECT 1 FROM student_event se3
                        WHERE se3.student_id = s.aecuser_ptr_id
                          AND (se3.event_type = %s OR se3.event_type ILIKE %s OR se3.event_type ILIKE %s)
                          AND DATE(se3.event_at) BETWEEN %s AND %s
                    )
                ) AS absent
                FROM larcauth_student s
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program p ON p.id = l.fk_program_id
                WHERE s.enabled = TRUE AND c.enabled = TRUE {class_filter}
            """,
                (
                    "absence",
                    "Suivi > Absence%",
                    "Absence%",
                    date_from,
                    date_to,
                    "absence",
                    "Suivi > Absence%",
                    "Absence%",
                    date_from,
                    date_to,
                ),
            )
            pres_row = cur.fetchone()
            present_count = pres_row[0] if pres_row else 0
            absent_count = pres_row[1] if pres_row else 0

            if present_count > 0 or absent_count > 0:
                donut = QPieSeries()
                donut.setHoleSize(0.45)
                if present_count > 0:
                    donut.append(_("chart.present"), present_count)
                    donut.slices()[-1].setColor(QColor(p.success))
                    donut.slices()[-1].setLabelVisible(True)
                    donut.slices()[-1].setLabel(f"{_('chart.present')} {present_count}")
                    donut.slices()[-1].setLabelColor(QColor(p.text_strong))
                if absent_count > 0:
                    donut.append(_("chart.absent"), absent_count)
                    donut.slices()[-1].setColor(QColor(p.error))
                    donut.slices()[-1].setLabelVisible(True)
                    donut.slices()[-1].setLabel(f"{_('chart.absent')} {absent_count}")
                    donut.slices()[-1].setLabelColor(QColor(p.text_strong))
                self._donut_chart.addSeries(donut)
                self._donut_chart.setTitle(_("chart.presence_rate"))
                self._donut_chart.legend().setVisible(False)
                self._donut_chart.setAnimationOptions(QChart.SeriesAnimations)
            else:
                self._donut_chart.setTitle(_("chart.presence_rate_empty"))

            self._top_bar.set_loading(False)

        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_load_group_stats: {e}")
            self._top_bar.set_loading(False)

    @safe_slot("MainWindow.on_filter_history")
    def _on_filter_history(self):
        self._load_global_history(self._current_group_mode)

    def _load_global_history(self, mode: str):
        if not db.is_server_connected:
            return
        self._top_bar.set_loading(True, _("topbar.loading_events"))
        conn = db.server_conn
        if not conn or not self._time_manager.term_id:
            self._top_bar.set_loading(False)
            return

        try:
            cur = conn.cursor()

            # Populate filter combos
            if self._history_filter_class.count() <= 1:
                cur.execute("""
                    SELECT c.id, c.label FROM larcauth_classroom c
                    JOIN larcauth_level l ON l.id = c.fk_level_id
                    JOIN larcauth_program p ON p.id = l.fk_program_id
                    WHERE c.enabled = TRUE AND p.sigle IN ('PYP', 'PP', 'PEI', 'MYP', 'DPEn', 'DPFr')
                    ORDER BY c.label
                """)
                for cid, clabel in cur.fetchall():
                    self._history_filter_class.addItem(clabel, cid)
                self._history_filter_class.model().sort(0)
            if self._history_filter_type.count() == 0:
                cur.execute("SELECT DISTINCT event_type FROM student_event ORDER BY event_type")
                for (et,) in cur.fetchall():
                    if et.lower() not in (
                        "absence",
                        "exit",
                        "arrival",
                        "departure",
                        "return",
                        "late",
                        "justified",
                    ):
                        self._history_filter_type.addItem(et)
                self._history_filter_type.setCurrentIndex(-1)
                self._history_filter_type.lineEdit().setText("")

            if mode == "grp_all":
                class_filter = "AND p.sigle IN ('PYP', 'PP', 'PEI', 'MYP', 'DPEn', 'DPFr')"
            elif mode == "grp_primaire":
                class_filter = "AND (p.sigle ILIKE 'PYP' OR p.sigle ILIKE 'PP')"
            elif mode == "grp_college":
                class_filter = "AND (p.sigle ILIKE 'PEI' OR p.sigle ILIKE 'MYP')"
            elif mode == "grp_lycee":
                class_filter = "AND (p.sigle ILIKE 'DPEn' OR p.sigle ILIKE 'DPFr')"
            else:
                sigle = mode.split("_")[1]
                class_filter = f"AND p.sigle ILIKE '{sigle}'"

            # -- Filtres suppl. --
            params = []
            sel_class = self._history_filter_class.currentData()
            sel_type = self._history_filter_type.currentText().strip()
            date_from, date_to = self._time_manager.period_dates()

            if sel_class:
                class_filter += " AND c.id = %s"
                params.append(sel_class)
            if sel_type:
                class_filter += " AND se.event_type ILIKE %s"
                params.append(f"%{sel_type}%")

            cur.execute(
                f"""
                SELECT se.event_id,
                       aec.last_name || ' ' || aec.first_name AS student_name,
                       c.label AS class_name,
                       se.event_type, se.event_at, se.lieu_label, se.subject_label, se.note,
                       u.last_name || ' ' || u.first_name AS created_by_name,
                       se.validated_by
                FROM student_event se
                JOIN larcauth_student s ON s.aecuser_ptr_id = se.student_id
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program p ON p.id = l.fk_program_id
                LEFT JOIN larcauth_aecuser u ON u.id = se.created_by
                WHERE DATE(se.event_at) BETWEEN %s AND %s {class_filter}
                ORDER BY se.event_at DESC
                LIMIT 500
            """,
                (date_from, date_to, *params),
            )

            rows = cur.fetchall()
            self._history_table.setRowCount(len(rows))
            self._history_table.setColumnCount(10)
            self._history_table.setHorizontalHeaderLabels(
                [
                    _("table.header.id"),
                    _("table.header.student"),
                    _("table.header.class"),
                    _("table.header.type"),
                    _("table.header.location"),
                    _("table.header.subject"),
                    _("table.header.time"),
                    _("table.header.note"),
                    _("table.header.created_by"),
                    _("table.header.validated"),
                ]
            )
            self._history_table.setColumnHidden(0, True)  # event_id

            for i, row in enumerate(rows):
                eid, name, cls_name, etype, e_at, lieu, subject, note, creator, validated = row
                ei = event_icon(etype)
                color = event_color(etype)
                display_type = f"{ei} {etype}"

                items = [
                    QTableWidgetItem(str(eid)),
                    QTableWidgetItem(name),
                    QTableWidgetItem(cls_name),
                    QTableWidgetItem(display_type),
                    QTableWidgetItem(lieu or ""),
                    QTableWidgetItem(subject or ""),
                    QTableWidgetItem(e_at.strftime("%H:%M") if e_at else ""),
                    QTableWidgetItem(note or ""),
                    QTableWidgetItem(creator or ""),
                    QTableWidgetItem("✓" if validated else ""),
                ]
                for j in range(len(items)):
                    if j == 3:
                        items[j].setForeground(QBrush(QColor(color)))
                    if j == 9 and validated:
                        items[j].setForeground(QBrush(QColor("#2e7d32")))
                        items[j].setFont(QFont("Segoe UI", 10, QFont.Bold))
                    if j not in (3, 7):
                        items[j].setTextAlignment(Qt.AlignCenter)
                    items[j].setFlags(items[j].flags() & ~Qt.ItemIsEditable)
                    self._history_table.setItem(i, j, items[j])
            hh = self._history_table.horizontalHeader()
            hh.setSectionResizeMode(0, M3HeaderView.Fixed)
            self._history_table.setColumnWidth(0, 0)
            hh.setSectionResizeMode(1, M3HeaderView.Interactive)
            self._history_table.setColumnWidth(1, 140)
            hh.setSectionResizeMode(2, M3HeaderView.Interactive)
            self._history_table.setColumnWidth(2, 100)
            hh.setSectionResizeMode(3, M3HeaderView.Interactive)
            self._history_table.setColumnWidth(3, 300)
            hh.setSectionResizeMode(4, M3HeaderView.Interactive)
            self._history_table.setColumnWidth(4, 120)
            hh.setSectionResizeMode(5, M3HeaderView.Interactive)
            self._history_table.setColumnWidth(5, 110)
            hh.setSectionResizeMode(6, M3HeaderView.Interactive)
            self._history_table.setColumnWidth(6, 100)
            hh.setSectionResizeMode(7, M3HeaderView.Stretch)
            hh.setSectionResizeMode(8, M3HeaderView.Interactive)
            self._history_table.setColumnWidth(8, 200)
            hh.setSectionResizeMode(9, M3HeaderView.Interactive)
            self._history_table.setColumnWidth(9, 130)
            self._top_bar.set_loading(False)

        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_load_global_history: {e}")
            self._top_bar.set_loading(False)

