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
    M3TextField,
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
from LarcSuperviseur.views.main_events import EventsMixin
from LarcSuperviseur.views.main_group import GroupStatsMixin
from LarcSuperviseur.views.main_students import StudentsMixin
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


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Fenêtre principale
# ---------------------------------------------------------------------------
class MainWindow(GroupStatsMixin, StudentsMixin, EventsMixin, QWidget):
    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        d = theme_manager.design
        s = theme_manager.font_size
        return f"""
            {QssHelper.top_bar(p, d)}
            {QssHelper.panel(p, d)}
            {QssHelper.panel_title(p, s, 14)}
            {QssHelper.table(p, d, s)}
            {QssHelper.combobox(p, d)}
            {QssHelper.push_button(p, d, s)}
            {QssHelper.section_btn(p, d, s)}
            {QssHelper.class_btn(p, d, s)}
            {QssHelper.period_btn(p, d)}
            {QssHelper.kpi_common(p, d, s)}
            {QssHelper.phi_btn(p, d)}
            QPushButton#theme_btn {{
                background: transparent; border: none; font-size: {s(18)}px;
            }}
            QPushButton#tt_btn {{
                background: {p.surface_variant}; color: {p.text_strong};
                border: none; border-radius: {d.radius}px; padding: {d.field_pad_v}px {d.field_pad_h}px;
                font-size: {s(10)}px;
            }}
            QPushButton#tt_btn:hover {{
                background: {p.primary}; color: {p.on_primary};
            }}
            QLabel#kpi_small_value {{
                font-size: {s(18)}px; font-weight: bold; color: {p.primary};
            }}
            QLabel#kpi_small_label {{
                font-size: {s(9)}px; color: {p.text_strong};
            }}
            QLabel#sd_photo {{
                background: {p.surface_variant}; border-radius: {d.radius_lg}px;
            }}
            QLabel#sd_contact_value {{
                font-size: {s(13)}px; color: {p.text_strong}; padding-left: {d.radius_lg}px;
            }}
            QLabel#sd_contact_label {{
                font-size: {s(13)}px; color: {p.text_strong};
            }}
            QPushButton#sd_back {{
                background: transparent; color: {p.primary};
                border: none; font-weight: bold;
                font-size: {s(11)}px; padding: {d.btn_sm_pad_v}px {d.spacing}px;
            }}
            QPushButton#sd_back:hover {{
                color: {p.active};
            }}
            QPushButton#sd_add_event {{
                background: {p.primary}; color: {p.on_primary};
                border: none; border-radius: {d.radius_xl}px; font-weight: bold;
                font-size: {s(28)}px;
            }}
            QPushButton#sd_add_event:hover {{
                background: {p.active};
            }}
            QLabel#sd_placeholder {{
                color: {p.text_disabled}; font-size: {s(14)}px;
            }}
            QLabel#sd_class {{
                color: {p.text_strong}; font-size: {s(11)}px;
            }}
            QWidget#group_page {{
                background: {p.background};
            }}
        """

    def __init__(self):
        super().__init__()
        trace(" MainWindow.__init__: démarre")
        self.setWindowTitle(_("main.title").format(name=session.full_name, role=session.role.value))
        self._current_class_id: int = 0
        self._current_class_label: str = ""
        self._selected_btn: M3Button | None = None
        self._current_group_mode: str = ""  # 'pei', 'dp', 'etab', 'class'
        self._current_weekday: int = 0
        self._selected_student_id: int = 0
        self._students: list[dict] = []
        self._classes: list = []
        self._programs: dict = {}
        self._time_manager = TimeManager()
        self._actions = EventActions()
        self._load_user_prefs()  # avant _init_ui pour éviter thème mixte
        self._init_ui()
        ds.theme_changed.connect(self._restyle_all)
        trace(" MainWindow.__init__: _init_ui OK, appel _load_initial_data")
        self._load_initial_data()
        trace(" MainWindow.__init__: _load_initial_data terminé")
        QTimer.singleShot(30000, self._refresh_timer)

    def _init_ui(self):
        self.setStyleSheet(self._STYLE)
        d = theme_manager.design
        outer = QVBoxLayout()
        outer.setContentsMargins(d.spacing, d.spacing, d.spacing, d.spacing)
        outer.setSpacing(d.spacing)

        # -- Top bar ------------------------------------------------------------
        self._top_bar = TopBar(
            on_period_click=self._on_period_clicked,
            on_theme_change=self._on_theme_selected,
            on_refresh=self.refresh_all,
        )
        outer.addWidget(self._top_bar)

        # -- Main area (sidebar + content) ------------------------------------
        main_h = QHBoxLayout()
        main_h.setContentsMargins(0, 0, 0, 0)
        main_h.setSpacing(d.spacing)

        # Sidebar gauche — SidebarWidget partagé (Sous-système K)
        _sections = [
            (_("sidebar.section_primaire"), [("PYP", "PYP"), ("PP", "PP")]),
            (_("sidebar.section_college"), [("PEI", "PEI"), ("MYP", "MYP")]),
            (_("sidebar.section_lycee"), [("DP", "DPFr"), ("DPEn", "DPEn")]),
        ]
        # Couleurs des programmes centralisées dans larccommon.theme.PROGRAM_STYLES
        self._sidebar = SidebarWidget(_sections, PROGRAM_STYLES)
        if session.role in (UserRole.ADMIN, UserRole.COORD):
            self._sidebar.set_header_widgets([self._build_event_types_btn()])
        self._sidebar.group_selected.connect(self._on_sidebar_group_selected)
        self._sidebar.class_selected.connect(lambda cid, label: self._on_class_clicked(cid, label))
        self._sidebar.all_selected.connect(self._on_all_clicked)

        # Content area
        self._content_stack = M3StackedWidget()

        # Page 0: Mode groupe (KPIs + charts + tables)
        self._group_page = ThemedWidget(object_name="group_page")
        self._group_scroll = M3ScrollArea()
        self._group_scroll.setWidgetResizable(True)
        self._group_scroll.setWidget(self._group_page)
        self._group_scroll.setFrameShape(M3Frame.NoFrame)
        # Fond du viewport = couleur réelle (PAS « transparent » : un viewport
        # transparent casse l'héritage des palettes Qt et noircit tous les
        # widgets en dessous — noms illisibles en thème contrasté, 2026-08-16)
        self._group_scroll.viewport().setStyleSheet(
            f"background: {theme_manager.palette.background};")
        group_layout = QVBoxLayout(self._group_page)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(ds.space_xs)

        # -- Ligne KPIs --
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(ds.space_xs)
        self._kpi_cards = {}
        # Period label
        self._kpi_period = M3Label("—")
        self._kpi_period.setObjectName("kpi_value")
        self._kpi_period.setAlignment(Qt.AlignCenter)
        period_card = M3Frame()
        period_card.setObjectName("kpi_card")
        period_card.setFixedHeight(ds.kpi_card_height)
        period_card.setAttribute(Qt.WA_StyledBackground, True)
        period_card.setAccessibleName(_("kpi.period"))
        period_card.setToolTip(_("kpi.period"))
        pcl = QVBoxLayout(period_card)
        pcl.setContentsMargins(ds.space_xs, ds.space_xxs, ds.space_xs, ds.space_xxs)
        pcl.addWidget(self._kpi_period)
        period_label = M3Label(_("kpi.period"))
        period_label.setObjectName("kpi_label")
        period_label.setAlignment(Qt.AlignCenter)
        pcl.addWidget(period_label)
        kpi_row.addWidget(period_card)

        for k, label in [
            ("total", _("kpi.total")),
            ("present", _("kpi.present")),
            ("absent", _("kpi.absent")),
            ("exit", _("kpi.exit")),
        ]:
            card = M3Frame()
            card.setObjectName("kpi_card")
            card.setFixedHeight(ds.kpi_card_height)
            card.setAttribute(Qt.WA_StyledBackground, True)
            card.setAccessibleName(label)
            card.setToolTip(label)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(ds.space_xs, ds.space_xxs, ds.space_xs, ds.space_xxs)
            val = M3Label("—")
            val.setObjectName("kpi_value")
            val.setAlignment(Qt.AlignCenter)
            val.setAccessibleName(label)
            lbl = M3Label(label)
            lbl.setObjectName("kpi_label")
            lbl.setAlignment(Qt.AlignCenter)
            cl.addWidget(val)
            cl.addWidget(lbl)
            self._kpi_cards[k] = val
            kpi_row.addWidget(card)
        group_layout.addLayout(kpi_row)

        # -- Liste des absents (apres KPIs, avant historique) --
        self._absents_group = M3Frame()
        self._absents_group.setObjectName("panel")
        self._absents_group.setAttribute(Qt.WA_StyledBackground, True)
        absents_layout = QVBoxLayout(self._absents_group)
        absents_title = M3Label(f"<b>{_('kpi.absent')}</b>")
        absents_title.setObjectName("panel_title")
        absents_layout.addWidget(absents_title)
        self._absents_table = M3TableWidget()
        self._absents_table.setColumnCount(3)
        self._absents_table.setHorizontalHeaderLabels(
            [_("table.header.name"), _("table.header.class"), _("table.header.reason")]
        )
        self._absents_table.horizontalHeader().setStretchLastSection(True)
        self._absents_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._absents_table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._absents_table.setMaximumHeight(ds.kpi_card_height * 2 + ds.space_md)
        absents_layout.addWidget(self._absents_table)
        self._absents_group.setVisible(False)
        self._history_group = M3Frame()
        self._history_group.setObjectName("panel")
        self._history_group.setAttribute(Qt.WA_StyledBackground, True)
        self._history_layout = QVBoxLayout(self._history_group)
        history_title = M3Label(f"<b>{_('history.title')}</b>")
        history_title.setObjectName("panel_title")
        self._history_table = M3TableWidget()
        self._history_table.setAlternatingRowColors(False)
        self._history_table.horizontalHeader().setStretchLastSection(True)
        self._history_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._history_table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._history_table.setSortingEnabled(True)
        self._history_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._history_table.customContextMenuRequested.connect(
            lambda pos: self._show_event_context_menu(self._history_table, pos)
        )
        self._history_table.viewport().setCursor(Qt.PointingHandCursor)
        self._history_table.setToolTip(_("history.dblclick_hint"))
        self._history_table.installEventFilter(self)
        self._history_table.cellDoubleClicked.connect(self._on_history_dblclick)
        self._history_layout.addWidget(history_title)
        # -- Filtres --
        filter_row = QHBoxLayout()
        filter_row.setSpacing(d.spacing)
        self._history_filter_class = M3ComboBox()
        self._history_filter_class.setMinimumWidth(ds.avatar)  # 150px
        self._history_filter_class.addItem(_("history.filter_all_classes"), "")
        filter_row.addWidget(M3Label(_("history.filter_class") + ":"))
        filter_row.addWidget(self._history_filter_class)
        self._history_filter_type = M3ComboBox()
        self._history_filter_type.setMinimumWidth(ds.window_width * 3 // 20)  # 180px
        self._history_filter_type.setEditable(True)
        self._history_filter_type.lineEdit().setPlaceholderText(
            _("history.filter_type_placeholder")
        )
        filter_row.addWidget(M3Label(_("history.filter_type") + ":"))
        filter_row.addWidget(self._history_filter_type)
        filter_row.addSpacing(ds.space_xs)
        filter_btn = M3Button(_("history.filter_button"))
        filter_btn.setCursor(Qt.PointingHandCursor)
        filter_btn.clicked.connect(self._on_filter_history)
        filter_row.addWidget(filter_btn)
        filter_row.addStretch()
        self._history_layout.addLayout(filter_row)
        self._history_layout.addWidget(self._history_table)
        self._history_group.setMinimumHeight(ds.window_height * 2 // 5)  # 320px
        hist_row = QHBoxLayout()
        hist_row.setAlignment(Qt.AlignTop)
        hist_row.addWidget(self._history_group, 3)
        hist_row.addWidget(self._absents_group, 1, Qt.AlignTop)
        group_layout.addLayout(hist_row, 1)

        # -- Bottom row: charts (tabbed) + stats table --
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(ds.space_xs)

        self._charts_tabs = M3TabWidget()
        self._charts_tabs.setMinimumSize(
            ds.window_width * 7 // 20, ds.window_height * 3 // 8  # 420×300
        )

        tab_abs = QWidget()
        tab_abs_layout = QVBoxLayout(tab_abs)
        tab_abs_layout.setContentsMargins(0, 0, 0, 0)
        self._abs_bar_view = QChartView()
        self._abs_bar_view.setRenderHint(QPainter.Antialiasing)
        self._abs_bar_view.setObjectName("panel")
        self._abs_bar = QChart()
        self._abs_bar_view.setChart(self._abs_bar)
        tab_abs_layout.addWidget(self._abs_bar_view)
        self._charts_tabs.addTab(tab_abs, _("chart.absences"))

        tab_exit = QWidget()
        tab_exit_layout = QVBoxLayout(tab_exit)
        tab_exit_layout.setContentsMargins(0, 0, 0, 0)
        self._exit_bar_view = QChartView()
        self._exit_bar_view.setRenderHint(QPainter.Antialiasing)
        self._exit_bar_view.setObjectName("panel")
        self._exit_bar = QChart()
        self._exit_bar_view.setChart(self._exit_bar)
        tab_exit_layout.addWidget(self._exit_bar_view)
        self._charts_tabs.addTab(tab_exit, _("chart.exits"))

        tab_trend = QWidget()
        tab_trend_layout = QVBoxLayout(tab_trend)
        tab_trend_layout.setContentsMargins(0, 0, 0, 0)
        self._trend_view = QChartView()
        self._trend_view.setRenderHint(QPainter.Antialiasing)
        self._trend_view.setObjectName("panel")
        self._trend_chart = QChart()
        self._trend_chart.setAnimationOptions(QChart.SeriesAnimations)
        self._trend_view.setChart(self._trend_chart)
        tab_trend_layout.addWidget(self._trend_view)
        self._charts_tabs.addTab(tab_trend, _("chart.trend"))

        tab_donut = QWidget()
        tab_donut_layout = QVBoxLayout(tab_donut)
        tab_donut_layout.setContentsMargins(0, 0, 0, 0)
        self._donut_view = QChartView()
        self._donut_view.setRenderHint(QPainter.Antialiasing)
        self._donut_view.setObjectName("panel")
        self._donut_chart = QChart()
        self._donut_view.setChart(self._donut_chart)
        tab_donut_layout.addWidget(self._donut_view)
        self._charts_tabs.addTab(tab_donut, _("chart.presence_rate"))

        bottom_row.addWidget(self._charts_tabs, 3)

        self._stats_group = M3Frame()
        self._stats_group.setObjectName("panel")
        self._stats_group.setAttribute(Qt.WA_StyledBackground, True)
        self._stats_layout = QVBoxLayout(self._stats_group)
        stats_title = M3Label(f"<b>{_('table.stats_title')}</b>")
        stats_title.setObjectName("panel_title")
        self._stats_table = M3TableWidget()
        self._stats_table.setAlternatingRowColors(False)
        self._stats_table.horizontalHeader().setStretchLastSection(True)
        self._stats_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._stats_table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._stats_layout.addWidget(stats_title)
        self._stats_layout.addWidget(self._stats_table)
        bottom_row.addWidget(self._stats_group, 2)

        group_layout.addLayout(bottom_row)

        # Page 1: Mode classe (cards empilées avec détail élève)
        self._class_page = QWidget()
        class_layout = QVBoxLayout(self._class_page)
        class_layout.setContentsMargins(0, 0, 0, 0)

        self._class_stack = M3StackedWidget()

        # -- Page 0 : Cartes élèves --
        self._cards_widget = QWidget()
        self._cards_layout = QGridLayout(self._cards_widget)
        self._cards_layout.setSpacing(ds.space_xs)
        self._cards_scroll = M3ScrollArea()
        self._cards_scroll.setWidget(self._cards_widget)
        self._cards_scroll.setWidgetResizable(True)
        cards_frame = M3Frame()
        cards_frame.setObjectName("panel")
        cards_frame.setAttribute(Qt.WA_StyledBackground, True)
        cards_frame_layout = QVBoxLayout(cards_frame)
        cards_frame_layout.setContentsMargins(0, 0, 0, 0)
        # Header row: titre à gauche, bouton EDT à droite
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        self._cards_title = M3Label(f"<b>{_('student.cards_title')}</b>")
        self._cards_title.setObjectName("panel_title")
        header_row.addWidget(self._cards_title)
        header_row.addStretch()

        # Recherche élève (filtre live sur nom/prénom des cartes affichées)
        self._student_search = M3TextField(placeholder=_("student.search_placeholder"))
        self._student_search.setObjectName("student_search")
        self._student_search.setFixedWidth(ds.space_xxxl + ds.space_xl)  # 188px
        self._student_search.setFixedHeight(ds.field_height - ds.space_md)  # 32px
        self._student_search.setAccessibleName(_("student.search_placeholder"))
        self._student_search.setToolTip(_("student.search_tooltip"))
        self._student_search.textChanged.connect(self._on_student_search_changed)
        header_row.addWidget(self._student_search)
        # (préférences chargées avant _init_ui via _load_user_prefs)

        # Boutons thèmes Phi
        self._phi_group = QButtonGroup(self)
        self._phi_group.setExclusive(True)
        self._card_theme: str = session.card_theme
        for key, icon_name in [
            ("compact", "view_comfy"),
            ("medium", "view_module"),
            ("large", "dashboard"),
        ]:
            btn = M3Button("")
            btn.setObjectName("phi_btn")
            btn.setCheckable(True)
            btn.setFixedSize(theme_manager.image.theme_btn, theme_manager.image.theme_btn)
            btn.setToolTip(f"{_('student.phi_theme')} {key.capitalize()}")
            btn.setIcon(
                md3_icon(
                    icon_name,
                    color=theme_manager.palette.text_strong,
                    size=ds.icon_sm,
                )
            )
            btn.setIconSize(QSize(ds.icon_sm, ds.icon_sm))
            self._phi_group.addButton(btn)
            btn.clicked.connect(lambda checked, k=key: self._on_card_theme(k))
            if key == session.card_theme:
                btn.setChecked(True)
            header_row.addWidget(btn)
        self._tt_edit_btn = M3Button(f" {_('student.timetable')}")
        self._tt_edit_btn.setObjectName("tt_btn")
        self._tt_edit_btn.setCursor(Qt.PointingHandCursor)
        self._tt_edit_btn.setIcon(
            md3_icon(
                "calendar_today",
                color=theme_manager.palette.text_strong,
                size=ds.icon_sm,
            )
        )
        self._tt_edit_btn.setIconSize(
            QSize(ds.icon_sm, ds.icon_sm)
        )
        self._tt_edit_btn.clicked.connect(self._on_edit_timetable)
        header_row.addWidget(self._tt_edit_btn)
        cards_frame_layout.addLayout(header_row)

        # Fond réel (PAS transparent — voir le commentaire du group_scroll)
        self._cards_scroll.viewport().setStyleSheet(
            f"background: {theme_manager.palette.surface};")
        self._cards_widget.setAttribute(Qt.WA_StyledBackground, True)
        self._cards_widget.setStyleSheet(
            f"background: {theme_manager.palette.surface};")

        self._class_absents_group = M3Frame()
        self._class_absents_group.setObjectName("panel")
        self._class_absents_group.setAttribute(Qt.WA_StyledBackground, True)
        cal = QVBoxLayout(self._class_absents_group)
        cal.setContentsMargins(ds.space_xs, ds.space_xxs, ds.space_xs, ds.space_xxs)
        cal_title = M3Label(f"<b>{_('student.absents_today')}</b>")
        cal_title.setStyleSheet(f"font-size: {theme_manager.font_size(13)}px; font-weight: bold;")
        cal.addWidget(cal_title)
        self._class_absents_table = M3TableWidget()
        self._class_absents_table.setColumnCount(2)
        self._class_absents_table.setHorizontalHeaderLabels(
            [_("table.header.name"), _("table.header.reason")]
        )
        self._class_absents_table.horizontalHeader().setStretchLastSection(True)
        self._class_absents_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._class_absents_table.setMaximumHeight(ds.kpi_card_height + ds.space_xl + ds.space_xs)
        cal.addWidget(self._class_absents_table)
        # Row cartes (3/4) + absents (1/4)
        self._class_absents_group.setVisible(False)
        cards_absents_row = QHBoxLayout()
        cards_absents_row.setAlignment(Qt.AlignTop)
        cards_absents_row.addWidget(self._cards_scroll, 3)
        cards_absents_row.addWidget(self._class_absents_group, 1, Qt.AlignTop)
        cards_frame_layout.addLayout(cards_absents_row)
        self._class_stack.addWidget(cards_frame)  # index 0

        # -- Page 1 : Skeleton loading --
        self._cards_skeleton_page = QWidget()
        sk_layout = QVBoxLayout(self._cards_skeleton_page)
        sk_layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        sk_layout.setAlignment(Qt.AlignCenter)
        self._cards_skeleton = M3Skeleton.table(self._cards_skeleton_page, rows=6, cols=4)
        self._cards_skeleton.set_label(_("topbar.loading_students"))
        sk_layout.addWidget(self._cards_skeleton)
        self._class_stack.addWidget(self._cards_skeleton_page)  # index 1

        # -- Page 2 : Detail eleve --
        self._build_student_detail()

        class_layout.addWidget(self._class_stack)
        self._class_stack.addWidget(self._student_detail)  # index 2

        self._content_stack.addWidget(self._group_scroll)  # 0
        self._content_stack.addWidget(self._class_page)  # 1
        self._event_types_panel = EventTypesPanel()
        self._content_stack.addWidget(self._event_types_panel)  # 2
        self._content_stack.setCurrentIndex(0)

        main_h.addWidget(self._sidebar)
        main_h.addWidget(self._content_stack, 1)

        outer.addLayout(main_h)
        self.setLayout(outer)
        self._compact_tables()

    def _compact_tables(self):
        for table in self.findChildren(QTableWidget):
            table.verticalHeader().setDefaultSectionSize(ds.table_row_min)
            table.verticalHeader().setMinimumSectionSize(ds.table_min_section)

    def _build_student_detail(self):
        self._student_detail = StudentDetail()
        self._student_detail.back_requested.connect(self._on_back_to_cards)
        self._student_detail.hide()

    def _rebuild_student_detail_theme(self):
        if hasattr(self, "_student_detail") and self._student_detail:
            self._student_detail.refresh_theme()


    @safe_slot("MainWindow.on_class_clicked")
    @safe_slot("MainWindow.on_sidebar_group_selected")
    def _on_sidebar_group_selected(self, group: str):
        """Dispatch depuis SidebarWidget — sections (l10n) et programmes (grp_*) ."""
        if group.startswith("grp_"):
            # Clic sur en-tête programme : group = "grp_pei"
            prog = group[4:]  # "pei"
            self._current_group_mode = f"grp_{prog.lower()}"
            self._current_class_id = 0
            self._current_class_label = prog
            self._select_btn(None)
            self._show_group_mode(f"grp_{prog.lower()}")
        else:
            # Clic sur section (Primaire/Collège/Lycée)
            mode_map = {
                _("sidebar.section_primaire"): "grp_primaire",
                _("sidebar.section_college"): "grp_college",
                _("sidebar.section_lycee"): "grp_lycee",
            }
            self._current_group_mode = mode_map[group]
            self._current_class_id = 0
            self._current_class_label = group
            self._select_btn(None)
            self._show_group_mode(mode_map[group])

    def _on_class_clicked(self, class_id: int, label: str, btn: M3Button | None = None):
        self._current_class_id = class_id
        self._current_class_label = label
        self._current_group_mode = "class"
        self._select_btn(btn)
        self._show_class_mode(class_id)

    @safe_slot("MainWindow.on_all_clicked")
    def _on_all_clicked(self):
        self._current_group_mode = "grp_all"
        self._current_class_id = 0
        self._current_class_label = ""
        self._select_btn(None)
        trace(" _on_all_clicked: lance _show_group_mode(grp_all)")
        self._show_group_mode("grp_all")
        trace(" _on_all_clicked: terminé")

    def _select_btn(self, btn: M3Button | None):
        if self._selected_btn is not None:
            try:
                self._selected_btn.setChecked(False)
            except RuntimeError:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                pass
        self._selected_btn = btn
        if btn is not None:
            try:
                btn.setChecked(True)
            except RuntimeError:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                pass

    def _load_initial_data(self):
        if not db.is_server_connected:
            return
        self._top_bar.set_loading(True, _("topbar.loading_initial"))
        trace(" _load_initial_data: démarre")
        conn = db.server_conn
        trace(f" _load_initial_data: server_conn={conn is not None}")
        if not conn:
            QMessageBox.warning(self, _("common.error"), _("main.error_no_connection"))
            self._top_bar.set_loading(False)
            return

        try:
            cur = conn.cursor()

            # Terme actif + annee academique (via academicyear)
            cur.execute("""
                SELECT t.id, t.label, ay.label
                FROM larcauth_term t, larcauth_academicyear ay
                WHERE ay.s_id = (SELECT MAX(s_id) FROM larcauth_academicyear)
                  AND t.trim = ay.current_term_number
                  AND t.fk_language_id = %s
                ORDER BY t.id DESC
                LIMIT 1
            """, (getattr(session, "fk_language", 2),))
            r = cur.fetchone()
            if r:
                self._time_manager.term_id = int(r[0])
                self._time_manager.term_label = r[1]
                session.term_id = int(r[0])
                session.term_label = f"{r[2]} — {r[1]}"
            else:
                self._time_manager.term_id = 0
                self._time_manager.term_label = ""
                session.term_id = 0
                session.term_label = ""

            # Programmes (PEI, DP, ...)
            cur.execute("SELECT id, sigle, label FROM larcauth_program ORDER BY sigle")
            self._programs = {r[0]: {"sigle": r[1], "label": r[2]} for r in cur.fetchall()}
            trace(f" _load_initial_data: {len(self._programs)} programmes chargés")

            # Classes avec leur programme via level (Collège + Lycée uniquement)
            cur.execute("""
                SELECT c.id, c.label, l.fk_program_id, p.sigle
                FROM larcauth_classroom c
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program p ON p.id = l.fk_program_id
                WHERE c.enabled = TRUE AND p.sigle IN ('PYP', 'PP', 'PEI', 'MYP', 'DPEn', 'DPFr')
                ORDER BY p.sigle, c.label
            """)
            self._classes = cur.fetchall()
            trace(f" _load_initial_data: {len(self._classes)} classes chargées")

            # Unités de période
            from LarcSuperviseur.views.core.data_loader import DataLoader

            self._time_manager.unit_periods = DataLoader().get_unit_periods()
            self._top_bar.set_unit_periods(self._time_manager.unit_periods)

            # Charger les classes dans le SidebarWidget
            trace(" _load_initial_data: chargement classes dans SidebarWidget")
            self._sidebar.load_classes(self._classes)
            trace(" _load_initial_data: classes chargées")

            # Activer le mode groupe par défaut
            self._on_all_clicked()
            self._top_bar.set_loading(False)

        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_load_initial_data: {e}")
            QMessageBox.critical(self, _("common.error"), str(e))
            self._top_bar.set_loading(False)

    @safe_slot("MainWindow.on_period_clicked")
    def _on_period_clicked(self, key: str):
        self._time_manager.select_period(key)
        self.refresh_all()

    def _load_user_prefs(self):
        if not db.is_server_connected:
            return
        """Charge les préférences utilisateur avant la construction UI."""
        if not session.user_id:
            return
        try:
            cur = db.server_conn.cursor()
            cur.execute(
                "SELECT key, value FROM larcauth_config WHERE key LIKE %s",
                (f"user_{session.user_id}_%",),
            )
            for k, v in cur.fetchall():
                pref = k.rsplit("_", 1)[-1]
                if pref == "theme_pref":
                    session.theme_pref = v
                    theme_manager.set_active(v)
                elif pref == "card_theme":
                    session.card_theme = v
                elif pref == "fk_language":
                    session.fk_language = int(v)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"MainWindow._load_user_prefs: {e}")

    @safe_slot("MainWindow._restyle_all")
    def _restyle_all(self):
        """Réapplique le style courant à tous les fonds réels (PAS transparents —
        palette noire sinon) après un changement de thème, interne ou externe
        (PreferencesDialog, sélecteur top bar)."""
        p = theme_manager.palette
        self.setStyleSheet(self._STYLE)
        self._top_bar.restyle()
        self._rebuild_student_detail_theme()
        self._top_bar.update_network()
        if hasattr(self, "_cards_scroll"):
            self._cards_scroll.viewport().setStyleSheet(f"background: {p.surface};")
        if hasattr(self, "_cards_widget"):
            self._cards_widget.setStyleSheet(f"background: {p.surface};")
        if hasattr(self, "_group_scroll"):
            self._group_scroll.viewport().setStyleSheet(f"background: {p.background};")
        if self._current_group_mode:
            self.refresh_all()

    @safe_slot("MainWindow.on_theme_selected")
    def _on_theme_selected(self, key: str):
        theme_manager.set_active(key)
        session.theme_pref = key
        self._restyle_all()

    # ---- Mode groupe -------------------------------------------------------





    # ---- Mode classe -------------------------------------------------------



    @safe_slot("MainWindow.on_student_selected")
    def _on_student_selected(self, student_id: int):
        self._selected_student_id = student_id
        self._top_bar.show_period_row(True)
        self._load_student_detail(student_id)

    @safe_slot("MainWindow.on_edit_timetable")
    def _on_edit_timetable(self):
        if not self._current_class_id:
            return
        # Trouver le label de la classe
        label = ""
        for cid, l, pid, sigle in self._classes:
            if cid == self._current_class_id:
                label = l
                break
        dlg = TimetableEditor(self._current_class_id, label, self._time_manager.term_id, self)
        dlg.exec()

    @safe_slot("MainWindow.on_back_to_cards")
    def _on_back_to_cards(self):
        self._student_detail.hide()
        self._class_stack.setCurrentIndex(0)

    @safe_slot("MainWindow.on_card_theme")
    def _on_card_theme(self, key: str):
        if not db.is_server_connected:
            return
        self._card_theme = key
        session.card_theme = key
        if session.user_id:
            try:
                cur = db.server_conn.cursor()
                cur.execute(
                    "INSERT INTO larcauth_config (key, value) VALUES (%s, %s) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                    (f"user_{session.user_id}_card_theme", key),
                )
                db.server_conn.commit()
            except Exception as e:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                log(f"MainWindow._on_card_theme: save prefs: {e}")
        if self._current_class_id:
            self._load_students(self._current_class_id)

    def _build_event_types_btn(self):
        """Bouton sidebar 'Types d'événements' (ADMIN/COORD) → page 2 du stack."""
        p = theme_manager.palette
        btn = M3Button(_("event_types.title"))
        btn.setIcon(md3_icon("event", color=p.text_strong, size=ds.icon_sm))
        btn.setIconSize(QSize(ds.icon_sm, ds.icon_sm))
        btn.setMinimumHeight(ds.button_height)
        btn.clicked.connect(self._on_event_types_btn)
        return btn

    @safe_slot("MainWindow.on_event_types_btn")
    def _on_event_types_btn(self):
        self._content_stack.setCurrentIndex(2)


    def _load_student_detail(self, student_id: int):
        date_from, date_to = self._time_manager.period_dates()
        trace(f" _load_student_detail: id={student_id}, période={self._time_manager.current_period}, dates={date_from} → {date_to}")
        self._student_detail.set_period_dates(date_from, date_to)
        self._student_detail.set_period_label(self._time_manager.current_period)
        self._student_detail.load(student_id)
        self._student_detail.show()
        self._class_stack.setCurrentWidget(self._student_detail)








    @safe_slot("MainWindow.refresh_all")
    def refresh_all(self):
        self._event_types_panel.refresh()
        self._top_bar.update_network()
        if self._current_group_mode == "class":
            if self._selected_student_id:
                trace(f"refresh_all: reload student detail {self._selected_student_id}")
                self._load_student_detail(self._selected_student_id)
            else:
                trace(f"refresh_all: show class mode {self._current_class_id}")
                self._show_class_mode(self._current_class_id)
        elif self._current_group_mode:
            trace(f"refresh_all: show group mode {self._current_group_mode}")
            self._show_group_mode(self._current_group_mode)

    def _refresh_timer(self):
        self._top_bar.update_network()
        QTimer.singleShot(30000, self._refresh_timer)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow_students_grid()
