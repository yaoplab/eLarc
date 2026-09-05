from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from larccommon.widgets.nav_button import NavButton
from larccommon.widgets.sidebar import SidebarWidget
from LarcSecretaire.common.audit import audit
from LarcSecretaire.common.database import db
from LarcSecretaire.common.logger import log
from LarcSecretaire.common.network import detect_network
from LarcSecretaire.common.session import session
from LarcSecretaire.common.theme import QssHelper, theme_manager
from LarcSecretaire.views.parent_manager import ParentManager
from LarcSecretaire.views.student_form import StudentForm
from LarcSecretaire.views.supervisor_panel import SupervisorPanel
from phibuilder.phi.scale import SpacingToken
from phibuilder.widgets.button import ButtonVariant, M3Button
from phibuilder.widgets.frame import M3Frame
from phibuilder.widgets.headerview import M3HeaderView
from phibuilder.widgets.label import M3Label
from phibuilder.widgets.menu import M3Menu
from phibuilder.widgets.profilebutton import M3ProfileButton
from phibuilder.widgets.scrollarea import M3ScrollArea
from phibuilder.widgets.stackedwidget import M3StackedWidget
from phibuilder.widgets.table import M3TableWidget
from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QValueAxis,
)
from PySide6.QtCore import QEvent, QMargins, QSize, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QWidget):
    def __init__(self):
        if not db.is_server_connected:
            return
        super().__init__()
        self._sp = theme_manager.phi_theme.spacing.spacing
        self._students: list[dict] = []
        self._classes: list[tuple] = []
        self._stats: dict = {}
        self._scope = "school"
        self._scope_label = None

        self.setWindowTitle(_("sec_main.title").format(name=session.full_name))
        # 987×610 = paire dorée (610 = sidebar + golden_width(sidebar) ; 987 = golden_width(610))
        _min_h = ds.sidebar_width + ds.golden_width(ds.sidebar_width)  # 610
        self.setMinimumSize(ds.golden_width(_min_h), _min_h)  # 987×610
        self.setObjectName("root")

        # Charger theme_pref depuis DB
        if session.user_id:
            try:
                cur = db.server_conn.cursor()
                cur.execute("SELECT value FROM larcauth_config WHERE key = %s", (f"user_{session.user_id}_theme_pref",))
                r = cur.fetchone()
                if r and r[0] in ("blue", "dark", "sobre", "contrast"):
                    theme_manager.set_active(r[0])
            except Exception as e:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                log(f"MainWindow.__init__: load theme_pref: {e}")

        ds.theme_changed.connect(self._restyle_all)

        self._setup_ui()
        self._load_initial_data()

        # Timer rafraîchissement
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(60000)
        self._refresh_timer.timeout.connect(self._update_status_bar)
        self._refresh_timer.start()

        # Timer inactivité (10 min → fermeture)
        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(600_000)
        self._idle_timer.timeout.connect(self._on_idle_timeout)
        self._idle_timer.start()
        QApplication.instance().installEventFilter(self)

    def _style(self) -> str:
        p = theme_manager.palette
        d = theme_manager.design
        s = theme_manager.font_size
        return f"""
            QWidget#root {{ background: {p.background}; }}
            {QssHelper.top_bar(p, d)}
            {QssHelper.panel(p, d)}
            {QssHelper.panel_title(p, s, 14)}
            {QssHelper.table(p, d, s)}
            {QssHelper.combobox(p, d)}
            {QssHelper.kpi_common(p, d, s)}
            QFrame#sidebar {{
                background: {p.surface}; border: none;
            }}
            QLabel#kpi_small_value {{
                font-size: {s(18)}px; font-weight: bold; color: {p.primary};
            }}
            QLabel#kpi_small_label {{
                font-size: {s(9)}px; color: {p.text_strong};
            }}
        """

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.MouseButtonPress, QEvent.KeyPress, QEvent.Wheel):
            self._idle_timer.stop()
            self._idle_timer.start()
        return super().eventFilter(obj, event)

    @safe_slot("MainWindow.on_idle_timeout")
    def _on_idle_timeout(self):
        audit.logout(session.user_id, session.full_name)
        QMessageBox.information(
            self,
            _("sec_main.session_expired_title"),
            _("sec_main.session_expired_msg"),
        )
        db.disconnect_all()
        QApplication.quit()

    def closeEvent(self, event):
        if hasattr(self, "_clock_timer") and self._clock_timer:
            self._clock_timer.stop()
        audit.logout(session.user_id, session.full_name)
        db.disconnect_all()
        super().closeEvent(event)

    def _setup_ui(self):
        sp = self._sp
        d = theme_manager.design

        self.setStyleSheet(self._style())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(sp(SpacingToken.SM), sp(SpacingToken.SM), sp(SpacingToken.SM), sp(SpacingToken.SM))
        outer.setSpacing(sp(SpacingToken.SM))

        # Top bar — alignée sur le template N du skill (Sous-système N)
        top = M3Frame()
        top.setObjectName("top_bar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(ds.space_sm, ds.space_xs, ds.space_sm, ds.space_xs)
        top_layout.setSpacing(ds.radius_lg)

        self._title = M3Label(_("sec_main.bar_title").format(name=session.full_name))
        self._title.setStyleSheet(f"font-size: {theme_manager.font_size(21)}px; font-weight: bold; color: {theme_manager.palette.text_strong};")
        top_layout.addWidget(self._title)
        top_layout.addStretch()

        self._date_label = M3Label()
        self._date_label.setStyleSheet(f"font-size: {theme_manager.font_size(21)}px; font-weight: bold; color: {theme_manager.palette.text_strong};")
        top_layout.addWidget(self._date_label)

        self._time_label = M3Label()
        self._time_label.setStyleSheet(f"font-size: {theme_manager.font_size(21)}px; font-weight: bold; color: {theme_manager.palette.primary};")
        top_layout.addWidget(self._time_label)

        self._network_label = M3Label()
        self._network_label.setStyleSheet(f"font-size: {theme_manager.font_size(12)}px; font-weight: bold;")
        top_layout.addWidget(self._network_label)

        # Theme button — avec menu (comme LarcSuperviseur)
        self._theme_btn = M3Button()
        self._theme_btn.setObjectName("theme_btn")
        self._theme_btn.setFixedSize(theme_manager.image.theme_btn, theme_manager.image.theme_btn)
        self._theme_btn.setIcon(self._theme_icon())
        self._theme_btn.setIconSize(QSize(ds.icon_sm, ds.icon_sm))
        self._theme_btn.setCursor(Qt.PointingHandCursor)
        self._theme_menu = M3Menu()
        _theme_icon_names = {
            "blue": "light_mode",
            "dark": "dark_mode",
            "sobre": "tonality",
            "contrast": "bolt",
        }
        for key, label in theme_manager.names():
            icon_name = _theme_icon_names.get(key, "light_mode")
            pal = theme_manager.get_palette(key)
            ic = md3_icon(
                icon_name,
                color=pal.primary if pal else "#1565C0",
                size=ds.icon_sm,
            )
            a = self._theme_menu.addAction(ic, label)
            a.setData(key)
        self._theme_menu.triggered.connect(self._on_theme_triggered)
        self._theme_btn.setMenu(self._theme_menu)
        top_layout.addWidget(self._theme_btn)

        # Profile button — initiales de l'utilisateur
        initials = "".join(w[0].upper() for w in session.full_name.split() if w)[:2] or "?"
        btn_size = ds.space_xxl // 2  # bouton profil rond 42×42
        self._profile_btn = M3ProfileButton(initials)
        self._profile_btn.setFixedSize(btn_size, btn_size)
        self._profile_btn.setCursor(Qt.PointingHandCursor)
        self._profile_btn.setStyleSheet(
            f"QPushButton {{ background: {theme_manager.palette.primary}; "
            f"color: {theme_manager.palette.on_primary}; font-weight: bold; "
            f"font-size: {ds.font_body_md}px; border: none; border-radius: {btn_size//2}px; "
            f"text-align: center; padding: 0px; }}"
            f"QPushButton:hover {{ background: {theme_manager.palette.active}; }}"
            f"QPushButton::menu-indicator {{ image: none; width: 0px; }}"
        )
        self._profile_menu = M3Menu(self)
        prefs_action = self._profile_menu.addAction(
            md3_icon("settings", color=theme_manager.palette.text_strong, size=ds.icon_sm),
            _("sec_main.preferences"),
        )
        prefs_action.triggered.connect(self._on_preferences)
        pwd_action = self._profile_menu.addAction(
            md3_icon("lock", color=theme_manager.palette.text_strong, size=ds.icon_sm),
            _("topbar.change_password"),
        )
        pwd_action.triggered.connect(self._on_change_password)
        self._profile_menu.addSeparator()
        logout_action = self._profile_menu.addAction(
            md3_icon("logout", color=theme_manager.palette.text_strong, size=ds.icon_sm),
            _("sec_main.logout"),
        )
        logout_action.triggered.connect(self._on_logout)
        self._profile_btn.setMenu(self._profile_menu)
        top_layout.addWidget(self._profile_btn)

        outer.addWidget(top)

        # Main layout: sidebar + content
        main_h = QHBoxLayout()
        main_h.setContentsMargins(0, 0, 0, 0)
        main_h.setSpacing(sp(SpacingToken.SM))

        # Sidebar
        self._sidebar = M3Frame()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(ds.sidebar_width)  # K2: 233px pour SidebarWidget
        self._sidebar_layout = QVBoxLayout(self._sidebar)
        self._sidebar_layout.setContentsMargins(sp(SpacingToken.SM), sp(SpacingToken.SM), sp(SpacingToken.SM), sp(SpacingToken.SM))
        self._sidebar_layout.setSpacing(sp(SpacingToken.XXS))

        self._build_sidebar()
        main_h.addWidget(self._sidebar)

        # Content stack
        self._content_stack = M3StackedWidget()

        # Page 0 : Tableau de bord
        self._dashboard_page = self._build_dashboard()
        self._content_stack.addWidget(self._dashboard_page)

        # Page 1 : Mode Supervision (présence, événements)
        self._supervisor_panel = SupervisorPanel()
        self._content_stack.addWidget(self._supervisor_panel)

        # Page 2 : Gestion des parents
        self._parent_manager = ParentManager()
        self._content_stack.addWidget(self._parent_manager)

        # Page 3 : Fiche eleve
        self._student_form = StudentForm()
        self._content_stack.addWidget(self._student_form)

        # Page 4 : A faire (todo list secretariat)
        from LarcSecretaire.views.todo_panel import TodoPanel
        self._todo_panel = TodoPanel()
        self._content_stack.addWidget(self._todo_panel)

        # Rafraichir les photos quand on revient au panneau de supervision
        self._content_stack.currentChanged.connect(self._on_page_changed)

        main_h.addWidget(self._content_stack, 1)
        outer.addLayout(main_h, 1)

        # Status bar
        self._status_bar = M3Label()
        self._status_bar.setFixedHeight(ds.table_row_min)
        self._status_bar.setStyleSheet(
            f"background: {theme_manager.palette.surface_variant}; "
            f"color: {theme_manager.palette.text_strong}; padding: {ds.space_xxs // 2}px {theme_manager.font_size(13)}px; "
            f"font-size: {theme_manager.font_size(10)}px;"
        )
        outer.addWidget(self._status_bar)

        self._update_datetime()
        self._start_clock()
        self._update_status_bar()

    def _build_sidebar(self):
        p = theme_manager.palette
        d = theme_manager.design
        sp = self._sp
        s = theme_manager.font_size

        self._clear_layout(self._sidebar_layout)
        self._selected_btn = None

        dash_btn = M3Button(_("sec_main.dashboard"))
        dash_btn.setMinimumHeight(ds.field_height + ds.space_xs)
        dash_btn.setCursor(Qt.PointingHandCursor)
        dash_btn.setIcon(md3_icon("dashboard", color=p.text_soft, size=ds.icon_sm))
        dash_btn.setIconSize(QSize(ds.icon_sm, ds.icon_sm))
        dash_btn.setStyleSheet(
            f"M3Button {{ background: {p.surface_variant}; color: {p.text_strong}; "
            f"border: none; border-radius: {ds.radius_sm}px; "
            f"font-size: {s(12)}px; padding: {ds.space_xs}px {ds.space_sm}px; "
            f"text-align: left; }}"
            f"M3Button:hover {{ background: {p.primary_container}; }}")
        dash_btn.clicked.connect(lambda checked: self._set_scope("school"))
        self._sidebar_layout.addWidget(dash_btn)

        # ---- SidebarWidget partage pour les sections classes (Sous-systeme K) ----
        _sections = [
            (_("sec_main.college"), [("PEI", "PEI"), ("MYP", "MYP")]),
            (_("sec_main.lycee"), [("DP", "DPFr"), ("DPEn", "DPEn")]),
        ]
        _prog_style = {
            "PEI": ("primary", "primary_container", "on_primary"),
            "MYP": ("secondary", "secondary_container", "on_secondary"),
            "DPFr": ("error", "error_container", "on_error"),
            "DPEn": ("tertiary", "tertiary_container", "on_tertiary"),
        }
        search_btn = M3Button(_("sec_main.search"))
        search_btn.setMinimumHeight(ds.field_height + ds.space_xs)
        search_btn.setCursor(Qt.PointingHandCursor)
        search_btn.setIcon(md3_icon("search", color=p.text_soft, size=ds.icon_sm))
        search_btn.setIconSize(QSize(ds.icon_sm, ds.icon_sm))
        search_btn.setStyleSheet(
            f"M3Button {{ background: {p.surface_variant}; color: {p.text_strong}; "
            f"border: none; border-radius: {ds.radius_sm}px; "
            f"font-size: {s(12)}px; padding: {ds.space_xs}px {ds.space_sm}px; "
            f"text-align: left; }}"
            f"M3Button:hover {{ background: {p.primary_container}; }}")
        search_btn.clicked.connect(lambda checked: self._safe_switch(3, "StudentForm"))
        self._sidebar_layout.addWidget(search_btn)

        parents_btn = M3Button(_("sec_main.parents"))
        parents_btn.setMinimumHeight(ds.field_height + ds.space_xs)
        parents_btn.setCursor(Qt.PointingHandCursor)
        parents_btn.setIcon(md3_icon("person", color=p.text_soft, size=ds.icon_sm))
        parents_btn.setIconSize(QSize(ds.icon_sm, ds.icon_sm))
        parents_btn.setStyleSheet(
            f"M3Button {{ background: {p.surface_variant}; color: {p.text_strong}; "
            f"border: none; border-radius: {ds.radius_sm}px; "
            f"font-size: {s(12)}px; padding: {ds.space_xs}px {ds.space_sm}px; "
            f"text-align: left; }}"
            f"M3Button:hover {{ background: {p.primary_container}; }}")
        parents_btn.clicked.connect(lambda checked: self._content_stack.setCurrentIndex(2))
        self._sidebar_layout.addWidget(parents_btn)

        todo_btn = M3Button(_("todo.title"))
        todo_btn.setMinimumHeight(ds.field_height + ds.space_xs)
        todo_btn.setCursor(Qt.PointingHandCursor)
        todo_btn.setIcon(md3_icon("event", color=p.text_soft, size=ds.icon_sm))
        todo_btn.setIconSize(QSize(ds.icon_sm, ds.icon_sm))
        todo_btn.setStyleSheet(
            f"M3Button {{ background: {p.surface_variant}; color: {p.text_strong}; "
            f"border: none; border-radius: {ds.radius_sm}px; "
            f"font-size: {s(12)}px; padding: {ds.space_xs}px {ds.space_sm}px; "
            f"text-align: left; }}"
            f"M3Button:hover {{ background: {p.primary_container}; }}")
        todo_btn.clicked.connect(lambda checked: self._content_stack.setCurrentIndex(4))
        self._sidebar_layout.addWidget(todo_btn)

        # Créer un nouveau SidebarWidget à chaque rebuild
        self._class_sidebar = SidebarWidget(_sections, _prog_style)
        self._class_sidebar.group_selected.connect(self._on_sidebar_group_selected)
        self._class_sidebar.class_selected.connect(lambda cid, label: self._on_class_clicked(cid))
        self._class_sidebar.load_classes(self._classes)
        self._sidebar_layout.addWidget(self._class_sidebar, 1)  # stretch=1 → prend l'espace restant

        self._sidebar_layout.addStretch()

        # État réseau en bas
        self._sidebar_status = M3Label()
        self._sidebar_status.setAlignment(Qt.AlignCenter)
        self._sidebar_layout.addWidget(self._sidebar_status)
        self._selected_btn = None

    def _build_dashboard(self) -> QWidget:
        page = M3ScrollArea()
        page.setWidgetResizable(True)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(ds.space_sm, ds.space_sm, ds.space_sm, ds.space_sm)
        layout.setSpacing(ds.space_sm)

        # Scope label
        self._scope_label = M3Label(style="headline_small")
        self._scope_label.setAlignment(Qt.AlignCenter)
        self._update_scope_label()
        layout.addWidget(self._scope_label)

        # KPIs — rangée 1 (effectifs)
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(ds.space_xs)
        self._kpi_widgets = {}
        self._kpi_labels = {}
        for key, label in [
            ("total", _("sec_main.kpi.total")),
            ("college", _("sec_main.kpi.college")),
            ("lycee", _("sec_main.kpi.lycee")),
            ("enseignants", _("sec_main.kpi.teachers")),
        ]:
            f = M3Frame()
            f.setObjectName("kpi_card")
            f.setFixedHeight(ds.kpi_card_height)
            fl = QVBoxLayout(f)
            fl.setAlignment(Qt.AlignCenter)
            v = M3Label("—")
            v.setObjectName("kpi_value")
            v.setAlignment(Qt.AlignCenter)
            l = M3Label(label)
            l.setObjectName("kpi_label")
            l.setAlignment(Qt.AlignCenter)
            fl.addWidget(v)
            fl.addWidget(l)
            self._kpi_widgets[key] = v
            self._kpi_labels[key] = l
            kpi_row.addWidget(f, 1)
        layout.addLayout(kpi_row)

        # KPIs — rangée 2 (actions secrétariat, cliquables)
        kpi_row2 = QHBoxLayout()
        kpi_row2.setSpacing(ds.space_xs)
        self._action_kpis = {}
        for key, label, icon_name, color_role in [
            ("no_photo", _("sec_main.kpi.no_photo"), "person", "error"),
            ("no_parent", _("sec_main.kpi.no_parent"), "person", "tertiary"),
            ("no_email", _("sec_main.kpi.no_email"), "mail", "secondary"),
            ("no_doc", _("sec_main.kpi.no_doc"), "description", "primary"),
        ]:
            f = M3Frame()
            f.setObjectName("kpi_small")
            f.setFixedHeight(ds.kpi_card_height)
            f.setCursor(Qt.PointingHandCursor)
            fl = QVBoxLayout(f)
            fl.setAlignment(Qt.AlignCenter)
            fl.setSpacing(ds.space_xxs)
            # Icône + valeur sur la même ligne
            icon_row = QHBoxLayout()
            icon_row.setAlignment(Qt.AlignCenter)
            icon_row.setSpacing(ds.space_xxs)
            ico = QLabel()
            ico.setPixmap(md3_icon(icon_name, color=getattr(ds.p, color_role), size=16).pixmap(16, 16))
            icon_row.addWidget(ico)
            v = M3Label("—")
            v.setObjectName("kpi_small_value")
            v.setAlignment(Qt.AlignCenter)
            icon_row.addWidget(v)
            fl.addLayout(icon_row)
            l = M3Label(label)
            l.setObjectName("kpi_small_label")
            l.setAlignment(Qt.AlignCenter)
            fl.addWidget(l)
            f.mousePressEvent = lambda ev, k=key: self._on_action_kpi(k)
            self._action_kpis[key] = v
            kpi_row2.addWidget(f, 1)
        layout.addLayout(kpi_row2)

        # Corps : tables à gauche, graphiques à droite
        body_row = QHBoxLayout()
        body_row.setSpacing(ds.space_sm)

        left_col = QVBoxLayout()
        left_col.setSpacing(ds.space_xs)

        # Tableau élèves
        self._dashboard_title = M3Label(_("sec_main.stats_class_title"))
        self._dashboard_title.setObjectName("panel_title")
        left_col.addWidget(self._dashboard_title)

        self._dashboard_table = M3TableWidget()
        self._dashboard_table.setColumnCount(6)
        self._dashboard_table.setHorizontalHeaderLabels(
            [
                "Pgm",
                _("sec_main.stats_class_headers_active"),
                _("sec_main.stats_class_headers_rate"),
                _("sec_main.stats_class_headers_male"),
                _("sec_main.stats_class_headers_female"),
                _("sec_main.stats_class_headers_total"),
            ]
        )
        hdr = self._dashboard_table.horizontalHeader()
        for i in range(6):
            hdr.setSectionResizeMode(i, M3HeaderView.Stretch)
            hdr.setMinimumSectionSize(40)
        self._dashboard_table.setMaximumHeight(ds.sp(SpacingToken.HUGE) + ds.sp(SpacingToken.HUGE))
        self._dashboard_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._dashboard_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._dashboard_table.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        self._dashboard_table.verticalHeader().setDefaultSectionSize(ds.table_row_min)
        self._dashboard_table.setStyleSheet(ds.table_qss())
        left_col.addWidget(self._dashboard_table)

        # Tableau enseignants
        self._teacher_title = M3Label(_("sec_main.stats_teacher_title"))
        self._teacher_title.setObjectName("panel_title")
        left_col.addWidget(self._teacher_title)

        self._teacher_table = M3TableWidget()
        self._teacher_table.setColumnCount(2)
        self._teacher_table.setHorizontalHeaderLabels([_("sec_main.stats_teacher_headers"), _("sec_main.stats_teacher_headers_active")])
        thdr = self._teacher_table.horizontalHeader()
        thdr.setSectionResizeMode(0, M3HeaderView.Stretch)
        thdr.setSectionResizeMode(1, M3HeaderView.Stretch)
        self._teacher_table.setMaximumHeight(ds.sp(SpacingToken.COLOSSAL))
        self._teacher_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._teacher_table.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        self._teacher_table.verticalHeader().setDefaultSectionSize(ds.table_row_min)
        self._teacher_table.setStyleSheet(ds.table_qss())
        left_col.addWidget(self._teacher_table)

        body_row.addLayout(left_col, 1)

        # Colonne droite : graphiques
        right_col = QVBoxLayout()
        right_col.setSpacing(ds.space_xs)

        self._niveau_chart_view = QChartView()
        self._niveau_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._niveau_chart_view.setMinimumHeight(ds.golden_height(610))
        right_col.addWidget(self._niveau_chart_view, 1)

        body_row.addLayout(right_col, 2)
        layout.addLayout(body_row)

        # Ratio filles / garçons
        gender_row = QHBoxLayout()
        gender_row.setSpacing(ds.space_xxs)
        gender_row.setAlignment(Qt.AlignCenter)
        self._gender_ratio_label = M3Label()
        self._gender_ratio_label.setStyleSheet(f"font-weight: bold; padding: {ds.space_xxs}px;")
        gender_row.addWidget(self._gender_ratio_label)
        layout.addLayout(gender_row)

        # Alertes
        self._alert_title = M3Label(_("sec_main.alerts_title"))
        self._alert_title.setObjectName("panel_title")
        layout.addWidget(self._alert_title)

        self._alert_label = M3Label()
        self._alert_label.setStyleSheet(f"color: {ds.p.text_strong}; padding: {ds.space_xs}px;")
        self._alert_label.setWordWrap(True)
        self._alert_label.setObjectName("panel")
        layout.addWidget(self._alert_label)

        layout.addStretch()
        page.setWidget(inner)
        return page

    def _populate_niveau_chart(self, rows: list):
        bar_sets = {}
        categories = []
        p = theme_manager.palette
        prog_colors = {
            "PEI": QColor(p.primary),
            "MYP": QColor(p.secondary),
            "DPFr": QColor(p.error),
            "DPEn": QColor(p.success),
        }
        prog_labels = {"PEI": "PEI", "MYP": "MYP", "DPFr": "DP", "DPEn": "DPEn"}
        all_sigles = ("PEI", "MYP", "DPFr", "DPEn")
        by_cat = {}
        for niveau, sigle, cnt in rows:
            if niveau not in by_cat:
                by_cat[niveau] = {}
                categories.append(niveau)
            by_cat[niveau][sigle] = cnt
        for sigle in all_sigles:
            bs = QBarSet(prog_labels[sigle])
            bs.setColor(prog_colors[sigle])
            for cat in categories:
                bs.append(by_cat[cat].get(sigle, 0))
            bar_sets[sigle] = bs

        series = QBarSeries()
        for sigle in all_sigles:
            series.append(bar_sets[sigle])

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(_("sec_main.stats_class_title"))
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsAngle(-45)
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)
        axis_y = QValueAxis()
        mx = max((max(by_cat[c].values()) for c in categories), default=10)
        axis_y.setRange(0, mx + 5)
        axis_y.setLabelFormat("%d")
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        chart.legend().setFont(QFont("Segoe UI", 8))
        chart.setBackgroundBrush(QBrush(QColor(theme_manager.palette.surface)))
        chart.setMargins(QMargins(0, 0, 0, 0))
        self._niveau_chart_view.setChart(chart)

    def _load_initial_data(self):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            db.connect_intranet()
            conn = db.server_conn
        if not conn:
            db.connect_cloud()
            conn = db.server_conn
        if not conn:
            self._status_bar.setText(_("sec_main.no_connection"))
            return

        try:
            cur = conn.cursor()

            _SEC_PROGS = ("PEI", "MYP", "DPEn", "DPFr")

            # Stats globales + enseignants KPI
            cur.execute(
                """
                SELECT COUNT(*) FILTER (WHERE enabled = TRUE) AS total_actifs
                FROM larcauth_student
                WHERE s_classroom_id IN (
                    SELECT c.id FROM larcauth_classroom c
                    JOIN larcauth_level l ON l.id = c.fk_level_id
                    JOIN larcauth_program pr ON pr.id = l.fk_program_id
                    WHERE pr.sigle IN %s
                )
            """,
                (_SEC_PROGS,),
            )
            total_actifs = cur.fetchone()[0]
            self._kpi_widgets["total"].setText(str(total_actifs))
            cur.execute("SELECT COUNT(*) FROM larcauth_teachadm WHERE enabled = TRUE")
            self._kpi_widgets["enseignants"].setText(str(cur.fetchone()[0]))

            # Tableau fusionné programme + genre + ratio F/G élèves
            cur.execute(
                """
                SELECT pr.sigle,
                       COUNT(s.aecuser_ptr_id) FILTER (WHERE s.enabled = TRUE) AS actifs,
                       COUNT(s.aecuser_ptr_id) AS slots,
                       COUNT(s.aecuser_ptr_id) FILTER (WHERE s.enabled = TRUE AND g.sigle IN ('M','Mr')) AS garcons,
                       COUNT(s.aecuser_ptr_id) FILTER (WHERE s.enabled = TRUE AND g.sigle IN ('F','Mme')) AS filles
                FROM larcauth_classroom c
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program pr ON pr.id = l.fk_program_id
                LEFT JOIN larcauth_student s ON s.s_classroom_id = c.id
                LEFT JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                LEFT JOIN larcauth_gender g ON g.id = aec.fk_gender_id
                WHERE pr.sigle IN %s
                GROUP BY pr.id, pr.sigle
                ORDER BY pr.sigle
            """,
                (_SEC_PROGS,),
            )
            prog_rows = cur.fetchall()
            self._dashboard_table.setRowCount(len(prog_rows))
            college = lycee = 0
            total_g = total_f = 0
            for i, (sigle, actifs, slots, garcons, filles) in enumerate(prog_rows):
                taux = f"{actifs / slots * 100:.0f}%" if slots else "—"
                tot_genre = garcons + filles
                for col, val in enumerate(
                    [
                        sigle,
                        str(actifs),
                        taux,
                        str(garcons),
                        str(filles),
                        str(tot_genre),
                    ]
                ):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignCenter)
                    self._dashboard_table.setItem(i, col, item)
                if sigle in ("PEI", "MYP"):
                    college += actifs
                elif sigle in ("DPFr", "DPEn"):
                    lycee += actifs
                total_g += garcons
                total_f += filles
            self._kpi_widgets["college"].setText(str(college))
            self._kpi_widgets["lycee"].setText(str(lycee))

            # Ratio F/G élèves
            gt = total_g + total_f
            if gt:
                self._gender_ratio_label.setText(_("sec_main.ratio_text").format(g=total_g, gp=total_g / gt * 100, f=total_f, fp=total_f / gt * 100))
            else:
                self._gender_ratio_label.setText(_("sec_main.ratio_fallback"))

            # Tableau enseignants
            cur.execute("""
                SELECT 'Enseignants',
                       COUNT(*) FILTER (WHERE type_teacher = TRUE) FROM larcauth_aecuser WHERE is_active = TRUE
                UNION ALL
                SELECT 'Admins',
                       COUNT(*) FILTER (WHERE type_director = TRUE) FROM larcauth_aecuser WHERE is_active = TRUE
                UNION ALL
                SELECT 'Coordinateurs',
                       COUNT(*) FILTER (WHERE type_coordonator = TRUE) FROM larcauth_aecuser WHERE is_active = TRUE
                UNION ALL
                SELECT 'Secrétaires',
                       COUNT(*) FILTER (WHERE type_secretary = TRUE) FROM larcauth_aecuser WHERE is_active = TRUE
            """)
            t_rows = cur.fetchall()
            self._teacher_table.setRowCount(len(t_rows))
            for i, (statut, cnt) in enumerate(t_rows):
                for col, val in enumerate([statut, str(cnt)]):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignCenter)
                    self._teacher_table.setItem(i, col, item)

            # Niveau chart
            cur.execute(
                """
                SELECT l.label, pr.sigle, COUNT(*) AS cnt
                FROM larcauth_student s
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program pr ON pr.id = l.fk_program_id
                WHERE pr.sigle IN %s AND s.enabled = TRUE
                GROUP BY l.id, l.label, pr.sigle
                ORDER BY l.id
            """,
                (_SEC_PROGS,),
            )
            self._populate_niveau_chart(cur.fetchall())

            # ── KPIs actionnables (chaque requête est protégée) ──
            _class_filter = """
                AND s.s_classroom_id IN (
                    SELECT c.id FROM larcauth_classroom c
                    JOIN larcauth_level l ON l.id = c.fk_level_id
                    JOIN larcauth_program pr ON pr.id = l.fk_program_id
                    WHERE pr.sigle IN %s
                )
            """
            alerts = []

            def _safe_count(label, sql, params=None):
                """Exécute une requête COUNT de manière protégée."""
                try:
                    cur.execute(sql, params or ())
                    return cur.fetchone()[0]
                except Exception as e:
                    from larccommon.error_reporting import get_reporter
                    get_reporter().report_exception()
                    log(f"KPI {label}: {e}")
                    return 0

            no_parent = _safe_count("no_parent",
                f"SELECT COUNT(*) FROM larcauth_student s WHERE s.enabled = TRUE {_class_filter}"
                f" AND (s.validation->'parent'->>'ok')::boolean IS NOT TRUE",
                (_SEC_PROGS,))
            self._action_kpis["no_parent"].setText(str(no_parent))

            no_email = _safe_count("no_email",
                f"SELECT COUNT(*) FROM larcauth_student s"
                f" JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id"
                f" WHERE s.enabled = TRUE {_class_filter}"
                f" AND (aec.email IS NULL OR aec.email = '' OR (s.validation->'email'->>'ok')::boolean IS NOT TRUE)",
                (_SEC_PROGS,))
            self._action_kpis["no_email"].setText(str(no_email))

            no_doc = _safe_count("no_doc",
                f"SELECT COUNT(*) FROM larcauth_student s WHERE s.enabled = TRUE {_class_filter}"
                f" AND (s.validation->'dossier'->>'ok')::boolean IS NOT TRUE",
                (_SEC_PROGS,))
            self._action_kpis["no_doc"].setText(str(no_doc))

            no_photo = _safe_count("no_photo",
                f"SELECT COUNT(*) FROM larcauth_student s WHERE s.enabled = TRUE {_class_filter}"
                f" AND (s.validation->'photo'->>'ok')::boolean IS NOT TRUE",
                (_SEC_PROGS,))
            self._action_kpis["no_photo"].setText(str(no_photo))

            if no_parent: alerts.append(_("sec_main.alert_no_parent").format(n=no_parent))
            if no_email: alerts.append(_("sec_main.alert_no_email").format(n=no_email))
            if no_doc: alerts.append(_("sec_main.alert_no_doc").format(n=no_doc))
            self._alert_label.setText(" · ".join(alerts) if alerts else _("sec_main.alert_none"))

            # Classes pour la sidebar
            cur.execute(
                """
                SELECT c.id, c.label, l.fk_program_id, pr.sigle
                FROM larcauth_classroom c
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program pr ON pr.id = l.fk_program_id
                WHERE c.enabled = TRUE AND pr.sigle IN %s
                ORDER BY pr.sigle, c.label
            """,
                (_SEC_PROGS,),
            )
            self._classes = cur.fetchall()
            self._build_sidebar()

            self._status_bar.setText(_("sec_main.loaded"))

        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_load_initial_data: {e}")
            self._status_bar.setText(_("sec_main.loading_error").format(e=e))

    def _on_action_kpi(self, key: str):
        if not db.is_server_connected:
            return
        """Affiche la liste detaillee quand un KPI d action est clique."""
        conn = db.server_conn
        if not conn:
            return
        titles = {
            "no_photo": _("sec_main.kpi.no_photo"),
            "no_parent": _("sec_main.kpi.no_parent"),
            "no_email": _("sec_main.kpi.no_email"),
            "no_doc": _("sec_main.kpi.no_doc"),
        }
        queries = {
            "no_photo": """
                SELECT aec.last_name || ' ' || aec.first_name AS name, c.label AS class
                FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                WHERE s.enabled = TRUE AND (s.validation->'photo'->>'ok')::boolean IS NOT TRUE
                ORDER BY c.label, aec.last_name LIMIT 200
            """,
            "no_parent": """
                SELECT aec.last_name || ' ' || aec.first_name AS name, c.label AS class
                FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                WHERE s.enabled = TRUE AND (s.validation->'parent'->>'ok')::boolean IS NOT TRUE
                ORDER BY c.label, aec.last_name LIMIT 200
            """,
            "no_email": """
                SELECT aec.last_name || ' ' || aec.first_name AS name, c.label AS class
                FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                WHERE s.enabled = TRUE AND (s.validation->'email'->>'ok')::boolean IS NOT TRUE
                ORDER BY c.label, aec.last_name LIMIT 200
            """,
            "no_doc": """
                SELECT aec.last_name || ' ' || aec.first_name AS name, c.label AS class
                FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                WHERE s.enabled = TRUE AND (s.validation->'dossier'->>'ok')::boolean IS NOT TRUE
                ORDER BY c.label, aec.last_name LIMIT 200
            """,
        }
        sql = queries.get(key)
        if not sql:
            return
        try:
            cur = conn.cursor()
            cur.execute(sql)
            rows = cur.fetchall()
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(titles.get(key, key))
        dlg.setMinimumSize(ds.window_height * 5 // 8, ds.window_height // 2)
        dlg.setStyleSheet(f"background: {ds.p.surface};")
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_sm)

        info = M3Label(_("sec_main.kpi_count").format(n=len(rows)))
        info.setStyleSheet(f"color: {ds.p.text_strong}; font-weight: bold;")
        layout.addWidget(info)

        table = M3TableWidget()
        table.set_headers([_("student_form.table_headers"), _("student_form.table_headers_class")])
        table.horizontalHeader().setStretchLastSection(True)
        table.setStyleSheet(ds.table_qss())
        table.setRowCount(len(rows))
        for i, (name, cls) in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(name))
            table.setItem(i, 1, QTableWidgetItem(cls))
        table.resizeColumnsToContents()
        layout.addWidget(table, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(ds.space_sm)
        create_btn = M3Button(_("todo.create_tasks"), variant=ButtonVariant.FILLED)
        create_btn.clicked.connect(lambda checked: (
            self._create_tasks_from_rows(rows, key),
            dlg.accept()
        ))
        btn_row.addWidget(create_btn)
        close_btn = M3Button(_("supervisor.close_button"), variant=ButtonVariant.OUTLINED)
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(close_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        dlg.exec()

    def _create_tasks_from_rows(self, rows: list, task_type: str):
        if not db.is_server_connected:
            return
        """Cree des taches todo a partir d une liste d eleves."""
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            for name, cls in rows:
                cur.execute(
                    "INSERT INTO secretary_todo (task_type, description, created_by) VALUES (%s, %s, %s)",
                    (task_type, f"{name} — {cls}", session.user_id))
            conn.commit()
            self._todo_panel.reload()
            self._content_stack.setCurrentIndex(4)  # Aller au panneau Todo
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            conn.rollback()
            log(f"_create_tasks_from_rows: {e}")

    @safe_slot("MainWindow.on_page_changed")
    def _safe_switch(self, index: int, name: str):
        """Bascule vers la page index avec log de debug."""
        try:
            log(f"MainWindow._safe_switch: switching to {name} (index {index})")
            self._content_stack.setCurrentIndex(index)
            log(f"MainWindow._safe_switch: OK")
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"MainWindow._safe_switch: ERROR {e}")
            import traceback
            log(traceback.format_exc())

    @safe_slot("Unknown._on_page_changed")
    def _on_page_changed(self, index: int):
        if index == 1:  # Page Supervision
            self._supervisor_panel.refresh_photos()
        elif index == 4:  # Page Todo
            self._todo_panel.reload()

    @safe_slot("MainWindow.on_sidebar_group_selected")
    def _on_sidebar_group_selected(self, group: str):
        """Dispatch depuis SidebarWidget — redirige vers _set_scope."""
        if group.startswith("grp_"):
            self._set_scope(group[4:])  # "pei", "myp", etc.
        else:
            self._set_scope(group.lower())  # college, lycee

    @safe_slot("MainWindow.on_class_clicked")
    def _on_class_clicked(self, class_id: int, btn=None):
        label = next((c[1] for c in self._classes if c[0] == class_id), str(class_id))
        self._select_btn(btn)
        self._content_stack.setCurrentIndex(1)
        self._supervisor_panel.load_class(class_id, label)
        self._status_bar.setText(_("sec_main.status_supervise").format(label=label))

    def _select_btn(self, btn):
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

    @safe_slot("MainWindow.set_scope")
    def _set_scope(self, scope: str):
        self._scope = scope
        self._update_scope_label()
        self._content_stack.setCurrentIndex(0)
        self._load_initial_data()

    def _update_scope_label(self):
        if self._scope_label is None:
            return
        labels = {
            "school": "Collège & Lycée",
            "collège": "Collège",
            "lycée": "Lycée",
            "pei": "PEI",
            "myp": "MYP",
            "dp": "DP",
            "dpen": "DPEn",
        }
        self._scope_label.setText(labels.get(self._scope, self._scope))

    def _theme_icon(self):
        name_map = {"blue": "light_mode", "dark": "dark_mode", "sobre": "tonality", "contrast": "bolt"}
        name = name_map.get(theme_manager.active_name, "light_mode")
        return md3_icon(name, color=theme_manager.palette.text_strong, size=ds.icon_sm)

    @safe_slot("MainWindow.on_theme_triggered")
    def _on_theme_triggered(self, action):
        key = action.data()
        if key:
            theme_manager.set_active(key)
            self._restyle_all()
            self._supervisor_panel.reload()
            self._update_status_bar()
            self._update_datetime()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    @safe_slot("MainWindow.on_preferences")
    def _on_preferences(self):
        from larccommon.preferences_dialog import PreferencesDialog

        dlg = PreferencesDialog(self)
        if dlg.exec():
            self._restyle_all()
            QMessageBox.information(self, _("sec_main.title"), _("sec_main.restart_needed"))

    @safe_slot("MainWindow.on_change_password")
    def _on_change_password(self):
        from larccommon.password_dialog import ChangePasswordDialog

        dlg = ChangePasswordDialog(self)
        dlg.exec()

    @safe_slot("MainWindow.on_logout")
    def _on_logout(self):
        from larccommon.database import db as _larc_db

        _larc_db.disconnect_all()
        QApplication.quit()

    def _restyle(self):
        """Alias pour D7 : _restyle_all() met à jour tous les widgets avec les couleurs actuelles."""
        self._restyle_all()

    @safe_slot("Unknown._restyle_all")
    def _restyle_all(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        d = theme_manager.design
        sp = self._sp

        # Main window
        self.setStyleSheet(self._style())

        # Top bar
        self._theme_btn.setIcon(self._theme_icon())
        self._title.setStyleSheet(f"font-size: {s(21)}px; font-weight: bold; color: {p.text_strong};")
        self._date_label.setStyleSheet(f"font-size: {s(21)}px; font-weight: bold; color: {p.text_strong};")
        self._time_label.setStyleSheet(f"font-size: {s(21)}px; font-weight: bold; color: {p.primary};")
        self._network_label.setStyleSheet(f"font-size: {s(12)}px; font-weight: bold;")
        self._profile_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; "
            f"font-weight: bold; font-size: {ds.font_body_md}px; border: none; "
            f"border-radius: {ds.space_xxl // 2}px; text-align: center; "
            f"padding: {ds.radius_none}px; }}"
            f"QPushButton:hover {{ background: {p.active}; }}"
            f"QPushButton::menu-indicator {{ image: none; width: 0px; }}"
        )

        # KPI via QssHelper.kpi_common() dans _style() — pas de QSS inline redondant
        # (les couleurs des valeurs/labels sont dans le QSS global via _style() + QssHelper.kpi_common)
        self._gender_ratio_label.setStyleSheet(f"font-weight: bold; padding: {ds.space_xxs}px; color: {p.text_strong};")
        self._alert_label.setStyleSheet(f"font-size: {s(10)}px; color: {p.text_strong}; padding: {ds.space_xs}px;")

        # Status bar
        self._status_bar.setStyleSheet(
            f"background: {p.surface_variant}; color: {p.text_strong}; padding: {ds.space_xxs // 2}px {theme_manager.font_size(13)}px;"
        )

        # Rebuild sidebar with new palette colors
        self._build_sidebar()

        # Update network status colors
        self._update_status_bar()

        # Propagate theme to supervisor panel
        if hasattr(self, "_supervisor_panel") and self._supervisor_panel:
            self._supervisor_panel.reload()

    def _start_clock(self):
        self._clock_timer = QTimer()
        self._clock_timer.timeout.connect(self._update_datetime)
        self._clock_timer.start(10000)

    @safe_slot("Unknown._update_datetime")
    def _update_datetime(self):
        from datetime import datetime

        now = datetime.now()
        self._date_label.setText(now.strftime("%A %d %B %Y") + "  ")
        self._time_label.setText(now.strftime("%H:%M") + "  ")

    @safe_slot("MainWindow.update_status_bar")
    def _update_status_bar(self):
        intra_ok, internet_ok = detect_network()
        p = theme_manager.palette
        s = theme_manager.font_size
        if intra_ok:
            txt, color = _("sec_main.network_intranet"), p.success
        elif internet_ok:
            txt, color = _("sec_main.network_cloud"), p.primary
        else:
            txt, color = _("sec_main.network_offline"), p.text_disabled
        self._network_label.setText(txt)
        self._network_label.setStyleSheet(f"font-size: {s(12)}px; font-weight: bold; color: {color};")
        self._sidebar_status.setText(txt)
        self._sidebar_status.setStyleSheet(f"font-size: {s(9)}px; color: {color};")
