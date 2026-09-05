from larccommon.design_system import ds
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from larccommon.widgets.themed_widget import ThemedWidget
from phibuilder.widgets import (
    M3Button,
    M3Dialog,
    M3HeaderView,
    M3Label,
    M3Menu,
    M3TableWidget,
    M3TabWidget,
)
from phibuilder.widgets.button import ButtonVariant
from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QPieSeries,
    QValueAxis,
)
from PySide6.QtCore import QDate, QEvent, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from LarcSuperviseur.common.event_helpers import event_color, event_icon
from LarcSuperviseur.common.photos import get_photo_path
from LarcSuperviseur.common.session import session
from LarcSuperviseur.common.theme import QssHelper, theme_manager
from LarcSuperviseur.views.core.data_loader import DataLoader
from LarcSuperviseur.views.core.event_actions import EventActions
from LarcSuperviseur.views.core.event_dialog import EventEditDialog
from LarcSuperviseur.views.dialogs.event_generator import EventGenerator


class StudentDetail(ThemedWidget):
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, object_name="panel")
        self._student_id = 0
        self._external_date_from: str | None = None
        self._external_date_to: str | None = None
        self._actions = EventActions()
        self._loader = DataLoader()
        ds.theme_changed.connect(self._restyle_all)
        self._init_ui()
        self.setStyleSheet(self._STYLE)

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design
        return f"""
            {QssHelper.table(p, d, s)}
            QLabel#sd_photo {{
                background: {p.primary_container};
                border-radius: {ds.radius_sm}px;
            }}
            QFrame#kpi_small {{
                background: {p.surface_variant};
                border-radius: {ds.radius_sm}px;
                padding: {ds.space_xxs}px {ds.space_sm}px;
            }}
            QLabel#sd_kpi_val {{
                font-size: {s(24)}px; font-weight: bold; color: {p.primary};
            }}
            QLabel#sd_kpi_lbl {{
                font-size: {s(11)}px; color: {p.text_strong};
            }}
            QPushButton#sd_add_btn {{
                background: {p.primary}; color: {p.on_primary};
                border: none; border-radius: {ds.radius_md}px;
                font-weight: bold; font-size: {s(28)}px;
            }}
            QPushButton#sd_add_btn:hover {{
                background: {p.active};
            }}
            M3Label#sd_placeholder {{
                color: {p.text_disabled}; font-size: {s(14)}px;
            }}
            QTableWidget#sd_events::item {{
                padding: {ds.space_xxs // 4}px {ds.space_xs - ds.space_xxs // 2}px;  # 1px 6px
            }}
            QWidget#sd_period_f {{
                background: {p.surface_variant};
                border-radius: {ds.radius_sm}px; padding: {ds.space_xxs}px;
            }}
            QLabel#sd_period_val {{
                font-size: {s(24)}px; font-weight: bold; color: {p.text_strong};
            }}
        """

    @safe_slot("StudentDetail._restyle_all")
    def _restyle_all(self):
        try:
            self.setStyleSheet(self._STYLE)
        except RuntimeError:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass

    def _period_dates(self) -> tuple[str, str]:
        today = QDate.currentDate()
        start = today.addMonths(-3)
        return start.toString("yyyy-MM-dd"), today.toString("yyyy-MM-dd")

    def set_period_dates(self, date_from: str, date_to: str):
        """Permet à MainWindow de passer les dates de la période active."""
        self._external_date_from = date_from
        self._external_date_to = date_to

    def _init_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design
        sd_layout = QVBoxLayout(self)
        sd_layout.setContentsMargins(ds.space_xs, ds.space_xs, ds.space_xs, ds.space_xs)
        sd_layout.setSpacing(ds.space_xs)

        # ── Header Q22: photo + nom/classe/ID + KPIs + add event ──
        p = theme_manager.palette
        s = theme_manager.font_size

        hdr = QHBoxLayout()
        hdr.setSpacing(ds.space_md)

        # Photo — Q22a
        self._sd_photo = QLabel()
        self._sd_photo.setObjectName("sd_photo")
        self._sd_photo.setFixedSize(theme_manager.image.logo, theme_manager.image.logo)  # 89×89
        self._sd_photo.setAlignment(Qt.AlignCenter)
        hdr.addWidget(self._sd_photo)

        # Identité — Q22b, Q22f
        identity = QVBoxLayout()
        identity.setSpacing(ds.space_xxs)  # 4px — Q22f

        self._sd_name_lbl = QLabel("—")
        self._sd_name_lbl.setStyleSheet(
            f"font-size: {s(18)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        identity.addWidget(self._sd_name_lbl)  # Q22c

        self._sd_class_lbl = QLabel("—")
        self._sd_class_lbl.setStyleSheet(
            f"font-size: {s(ds.font_label_lg)}px; color: {p.text_strong}; border: none;")
        identity.addWidget(self._sd_class_lbl)  # Q22d

        self._sd_id_lbl = QLabel("—")
        self._sd_id_lbl.setStyleSheet(
            f"font-size: {s(ds.font_label_sm)}px; color: {p.text_strong}; border: none;")
        identity.addWidget(self._sd_id_lbl)  # Q22e

        hdr.addLayout(identity, 1)

        # KPIs inline — period first, then stats
        self._sd_kpis = {}
        period_f = QFrame()
        period_f.setObjectName("sd_period_f")
        period_f.setAttribute(Qt.WA_StyledBackground, True)
        period_fl = QVBoxLayout(period_f)
        period_fl.setContentsMargins(ds.space_xxs, 2, ds.space_xxs, 2)
        self._sd_period_val = QLabel("—")
        self._sd_period_val.setObjectName("sd_period_val")
        self._sd_period_val.setAlignment(Qt.AlignCenter)
        period_fl.addWidget(self._sd_period_val)
        hdr.addWidget(period_f)

        for k, lbl in [
            ("abs", _("chart.absences")),
            ("exit", _("kpi.exit")),
            ("total", _("kpi.total_events")),
        ]:
            f = QFrame()
            f.setObjectName("kpi_small")
            f.setAttribute(Qt.WA_StyledBackground, True)
            f.setMinimumWidth(ds.kpi_card_height)
            fl = QVBoxLayout(f)
            fl.setContentsMargins(ds.space_xxs, 2, ds.space_xxs, 2)
            v = QLabel("—")
            v.setObjectName("sd_kpi_val")
            v.setAlignment(Qt.AlignCenter)
            l = QLabel(lbl)
            l.setObjectName("sd_kpi_lbl")
            l.setAlignment(Qt.AlignCenter)
            fl.addWidget(v)
            fl.addWidget(l)
            self._sd_kpis[k] = v
            hdr.addWidget(f, 1)

        self._sd_add_btn = QPushButton("+")
        self._sd_add_btn.setObjectName("sd_add_btn")
        self._sd_add_btn.setFixedSize(ds.add_btn, ds.add_btn)
        self._sd_add_btn.setCursor(Qt.PointingHandCursor)
        self._sd_add_btn.setToolTip(_("student.add_event"))
        self._sd_add_btn.clicked.connect(self._on_add_event)
        hdr.addWidget(self._sd_add_btn)
        sd_layout.addLayout(hdr)

        # ── Contenu : événements (8) + graphiques (5) ──
        content = QHBoxLayout()
        content.setSpacing(ds.space_xs)

        # Colonne gauche : événements
        left = QVBoxLayout()
        evt_label = M3Label(f"<b>{_('student.tab.events')}</b>")
        left.addWidget(evt_label)
        self._sd_events = M3TableWidget()
        self._sd_events.setAlternatingRowColors(False)
        self._sd_events.setObjectName("sd_events")
        self._sd_events.verticalHeader().setDefaultSectionSize(22)
        self._sd_events.verticalHeader().setMinimumSectionSize(18)
        self._sd_events.horizontalHeader().setStretchLastSection(True)
        self._sd_events.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._sd_events.setSelectionBehavior(M3TableWidget.SelectRows)
        self._sd_events.setContextMenuPolicy(Qt.CustomContextMenu)
        self._sd_events.customContextMenuRequested.connect(
            lambda pos: self._show_context_menu(self._sd_events, pos)
        )
        self._sd_events.viewport().setCursor(Qt.PointingHandCursor)
        self._sd_events.setToolTip(_("history.dblclick_hint"))
        self._sd_events.installEventFilter(self)
        self._sd_events.cellDoubleClicked.connect(self._on_event_table_dblclick)
        self._sd_events.setSortingEnabled(True)
        left.addWidget(self._sd_events, 1)
        content.addLayout(left, 8)

        # Colonne droite : graphiques dans des onglets
        self._sd_chart_tabs = M3TabWidget(parent=self)
        self._sd_chart_tabs.setDocumentMode(True)

        # Onglet 1 : Donut répartition par type
        donut_w = QWidget()
        donut_layout = QVBoxLayout(donut_w)
        donut_layout.setContentsMargins(0, 0, 0, 0)
        self._donut_chart = QChart()
        self._donut_chart.setAnimationOptions(QChart.SeriesAnimations)
        self._donut_chart.legend().setVisible(True)
        self._donut_chart.legend().setAlignment(Qt.AlignBottom)
        self._donut_view = QChartView(self._donut_chart)
        self._donut_view.setRenderHint(QPainter.Antialiasing)
        donut_layout.addWidget(self._donut_view)
        self._sd_chart_tabs.addTab(donut_w, _("chart.by_type"))

        # Onglet 2 : Barres par jour
        bars_w = QWidget()
        bars_layout = QVBoxLayout(bars_w)
        bars_layout.setContentsMargins(0, 0, 0, 0)
        self._bars_chart = QChart()
        self._bars_chart.setAnimationOptions(QChart.SeriesAnimations)
        self._bars_chart.legend().setVisible(False)
        self._bars_view = QChartView(self._bars_chart)
        self._bars_view.setRenderHint(QPainter.Antialiasing)
        bars_layout.addWidget(self._bars_view)
        self._sd_chart_tabs.addTab(bars_w, _("chart.by_day"))

        content.addWidget(self._sd_chart_tabs, 5)
        sd_layout.addLayout(content, 1)

        # Placeholder
        self._sd_placeholder = M3Label(_("student.no_selection"))
        self._sd_placeholder.setObjectName("sd_placeholder")
        self._sd_placeholder.setAlignment(Qt.AlignCenter)
        self._sd_placeholder.setVisible(False)
        sd_layout.addWidget(self._sd_placeholder)

    def load(self, student_id: int):
        self._student_id = student_id
        p = theme_manager.palette
        # Utiliser les dates externes (TimeManager) si disponibles, sinon fallback
        if self._external_date_from and self._external_date_to:
            date_from = self._external_date_from
            date_to = self._external_date_to
        else:
            date_from, date_to = self._period_dates()

        info = self._loader.get_student_info(student_id)
        if not info:
            return

        # Q22c — Nom
        self._sd_name_lbl.setText(f"{info['first_name']} {info['last_name']}")
        # Q22d — Classe
        self._sd_class_lbl.setText(info.get("class_label", "—"))
        # Q22e — ID
        self._sd_id_lbl.setText(f"ID : {student_id}")

        pix = QPixmap(get_photo_path(student_id))
        if not pix.isNull():
            self._sd_photo.setPixmap(
                pix.scaled(theme_manager.image.logo, theme_manager.image.logo, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

        kpi = self._loader.get_student_kpis(student_id, date_from, date_to)
        self._sd_kpis["abs"].setText(str(kpi.get("abs_count", 0)))
        self._sd_kpis["exit"].setText(str(kpi.get("exit_count", 0)))
        self._sd_kpis["total"].setText(str(kpi.get("total", 0)))

        # Événements filtrés par période
        evts = self._loader.get_student_events(student_id, date_from=date_from, date_to=date_to)
        self._sd_events.setRowCount(len(evts))
        self._sd_events.setColumnCount(8)
        self._sd_events.setHorizontalHeaderLabels(
            [
                _("table.id"),
                _("table.type"),
                _("table.location"),
                _("table.subject"),
                _("table.date"),
                _("table.note"),
                _("table.created_by"),
                _("table.validated"),
            ]
        )
        self._sd_events.setColumnHidden(0, True)
        for i, evt in enumerate(evts):
            ei = event_icon(evt["event_type"])
            color = event_color(evt["event_type"])
            items = [
                QTableWidgetItem(str(evt["event_id"])),
                QTableWidgetItem(f"{ei} {evt['event_type']}"),
                QTableWidgetItem(evt.get("lieu_label") or ""),
                QTableWidgetItem(evt.get("subject_label") or ""),
                QTableWidgetItem(
                    evt["event_at"].strftime("%d/%m %H:%M") if evt.get("event_at") else ""
                ),
                QTableWidgetItem(evt.get("note") or ""),
                QTableWidgetItem(evt.get("creator") or ""),
                QTableWidgetItem("\u2713" if evt.get("validated_by") else ""),
            ]
            items[1].setForeground(QBrush(QColor(color)))
            for j, it in enumerate(items):
                if j not in (1, 5):
                    it.setTextAlignment(Qt.AlignCenter)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self._sd_events.setItem(i, j, it)
        hh = self._sd_events.horizontalHeader()
        hh.setSectionResizeMode(0, M3HeaderView.Fixed)
        self._sd_events.setColumnWidth(0, 0)
        hh.setSectionResizeMode(1, M3HeaderView.Interactive)
        self._sd_events.setColumnWidth(1, 280)
        hh.setSectionResizeMode(2, M3HeaderView.Interactive)
        self._sd_events.setColumnWidth(2, 110)
        hh.setSectionResizeMode(3, M3HeaderView.Interactive)
        self._sd_events.setColumnWidth(3, 100)
        hh.setSectionResizeMode(4, M3HeaderView.Interactive)
        self._sd_events.setColumnWidth(4, 100)
        hh.setSectionResizeMode(5, M3HeaderView.Stretch)
        hh.setSectionResizeMode(6, M3HeaderView.Interactive)
        self._sd_events.setColumnWidth(6, 180)
        hh.setSectionResizeMode(7, M3HeaderView.Interactive)
        self._sd_events.setColumnWidth(7, 80)

        # Graphiques
        self._build_donut(evts)
        self._build_bars(evts)

        self._sd_chart_tabs.show()
        self._sd_placeholder.hide()

    def _build_donut(self, evts: list[dict]):
        self._donut_chart.removeAllSeries()
        if not evts:
            self._donut_chart.setTitle(_("chart.no_data"))
            return
        self._donut_chart.setTitle("")
        counts = {}
        for e in evts:
            t = e["event_type"]
            cat = t.split(">")[0].strip()
            counts[cat] = counts.get(cat, 0) + 1
        series = QPieSeries()
        p = theme_manager.palette
        palette_colors = [p.error, p.primary, p.tertiary, p.success, p.text_soft]
        for i, (cat, cnt) in enumerate(counts.items()):
            sl = series.append(f"{cat} ({cnt})", cnt)
            sl.setColor(QColor(palette_colors[i % len(palette_colors)]))
        series.setHoleSize(0.4)
        self._donut_chart.addSeries(series)

    def _build_bars(self, evts: list[dict]):
        self._bars_chart.removeAllSeries()
        for ax in self._bars_chart.axes():
            self._bars_chart.removeAxis(ax)
        if not evts:
            self._bars_chart.setTitle(_("chart.no_data"))
            return
        self._bars_chart.setTitle("")
        by_day = {}
        for e in evts:
            d = e["event_at"].strftime("%d/%m") if e.get("event_at") else "?"
            by_day[d] = by_day.get(d, 0) + 1
        days = sorted(by_day.keys())[-14:]
        bar_set = QBarSet("Événements")
        bar_set.setColor(QColor(theme_manager.palette.primary))
        for d in days:
            bar_set.append(by_day[d])
        series = QBarSeries()
        series.append(bar_set)
        self._bars_chart.addSeries(series)
        ax_x = QBarCategoryAxis()
        ax_x.append(days)
        self._bars_chart.addAxis(ax_x, Qt.AlignBottom)
        series.attachAxis(ax_x)
        ax_y = QValueAxis()
        ax_y.setRange(0, max(by_day.values()) + 2)
        self._bars_chart.addAxis(ax_y, Qt.AlignLeft)
        series.attachAxis(ax_y)

    @safe_slot("StudentDetail.on_add_event")
    def _on_add_event(self):
        sid = self._student_id
        if not sid:
            return
        dlg = EventGenerator(sid, self)
        if dlg.exec():
            data = dlg.get_data()
            data["created_by"] = session.user_id
            if not self._loader.insert_event(data):
                QMessageBox.critical(self, _("common.dialog.error_title"), _("student.save_error"))
                return
            self.load(sid)

    def set_period_label(self, label: str):
        # Traduire la clé de période via le système l10n
        translated = _(f"topbar.period.{label}") if label else label
        self._sd_period_val.setText(translated)
        self._sd_placeholder.setVisible(True)
        self._sd_chart_tabs.hide()
        self.back_requested.emit()

    def _get_event_id_from_table(self, table: M3TableWidget) -> int | None:
        idx = table.currentRow()
        if idx < 0:
            return None
        item = table.item(idx, 0)
        return int(item.text()) if item and item.text().isdigit() else None

    def _show_context_menu(self, table: M3TableWidget, pos):
        eid = self._get_event_id_from_table(table)
        if not eid:
            return
        event = self._actions.get_event_by_id(eid)
        is_validated = event is not None and event.get("validated_by") is not None
        menu = M3Menu(self)
        edit_action = menu.addAction(_("context_menu.edit"))
        validate_action = menu.addAction(
            _("context_menu.invalidate") if is_validated else _("context_menu.validate")
        )
        delete_action = menu.addAction(_("context_menu.delete"))
        chosen = menu.exec(table.viewport().mapToGlobal(pos))
        if chosen == edit_action:
            self._edit_event(eid)
        elif chosen == validate_action:
            self._toggle_validation(eid)
        elif chosen == delete_action:
            self._delete_event(eid)

    @safe_slot("StudentDetail.on_event_table_dblclick")
    def _on_event_table_dblclick(self, row: int, col: int):
        item = self._sd_events.item(row, 0)
        eid = int(item.text()) if item and item.text().isdigit() else None
        if eid:
            self._edit_event(eid)

    def eventFilter(self, obj, event):
        if (
            obj is self._sd_events
            and event.type() == QEvent.KeyPress
            and event.key() in (Qt.Key_Return, Qt.Key_Enter)
        ):
            row = self._sd_events.currentRow()
            if row >= 0:
                self._on_event_table_dblclick(row, 0)
                return True
        return super().eventFilter(obj, event)

    def _edit_event(self, event_id: int):
        dlg = EventEditDialog(event_id, self)
        if dlg.exec() == M3Dialog.Accepted:
            self.load(self._student_id)

    def _toggle_validation(self, event_id: int):
        event = self._actions.get_event_by_id(event_id)
        was_validated = event is not None and event.get("validated_by") is not None
        if self._actions.toggle_validation(event_id, not was_validated):
            self.load(self._student_id)

    def _delete_event(self, event_id: int):
        reply = QMessageBox.question(
            self,
            _("student.confirm_delete_event"),
            _("common.dialog.delete_event").format(id=event_id),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        if self._actions.delete_event(event_id):
            self.load(self._student_id)

    def _clear_layout(self, layout):
        """Vide récursivement un layout (widgets + sous-layouts)."""
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w:
                w.deleteLater()
            else:
                sub = item.layout()
                if sub:
                    self._clear_layout(sub)

    def refresh_theme(self):
        """Re-styler sans reconstruire le layout (template N pattern)."""
        self._restyle_all()
        sid = self._student_id
        if sid:
            # Recharger les données pour mettre à jour les couleurs dynamiques (événements, graphiques)
            self.load(sid)
