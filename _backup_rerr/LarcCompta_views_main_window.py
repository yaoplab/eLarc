"""MainWindow LarcScolarite — SidebarWidget classes + NavButton + dashboard."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QStackedWidget, QSplitter,
    QApplication,
)

from larccommon.database import db
from larccommon.session import session
from larccommon.design_system import ds
from larccommon.theme import theme_manager, PROGRAM_STYLES
from larccommon.widgets.sidebar import SidebarWidget
from larccommon.widgets.nav_button import NavButton
from larccommon.widgets.topbar import TopBar
from larccommon.safe_slot import safe_slot


NAV_ITEMS = [
    ("dashboard", "Tableau de bord", "home"),
    ("impayes",    "Impayés",         "warning"),
    ("parents",    "Parents",         "person"),
    ("rappels",    "Rappels",         "schedule"),
    ("config",     "Configuration",   "settings"),
]


class MainWindow(QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LarcScolarite")
        self._current_key: str = "dashboard"
        self._pages: dict[str, QWidget] = {}
        self._classes: list[tuple] = []
        self._current_class_id: int = 0
        self._current_group_mode: str = "grp_all"

        self._setup_ui()
        self._load_classes()
        ds.theme_changed.connect(self._restyle)
        QTimer.singleShot(100, lambda: self._switch_to("dashboard"))

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._topbar = TopBar()
        self._topbar.logout_requested.connect(QApplication.quit)
        self._topbar.theme_changed.connect(self._on_topbar_theme)
        outer.addWidget(self._topbar)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar dans un QScrollArea ──
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(ds.sidebar_width)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(ds.space_xs, ds.space_xs, ds.space_xs, ds.space_xs)
        sb.setSpacing(ds.space_xs)

        # Logo ecole
        logo_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..",
                         "LarcSuperviseur", "img", "logoAEC.png"))
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaledToHeight(theme_manager.image.logo, Qt.SmoothTransformation)
            logo_lbl = QLabel()
            logo_lbl.setPixmap(pix)
            logo_lbl.setAlignment(Qt.AlignCenter)
            sb.addWidget(logo_lbl)

        # User
        self._user_lbl = QLabel(session.full_name or "Scolarite")
        self._user_lbl.setStyleSheet(
            f"font-size: {s(ds.font_label_lg)}px; font-weight: bold; color: {p.text_strong}; "
            f"padding: 0 {ds.space_xs}px; border: none;")
        sb.addWidget(self._user_lbl)

        self._role_lbl = QLabel("Scolarite")
        self._role_lbl.setStyleSheet(
            f"font-size: {s(ds.font_label_sm)}px; color: {p.text_strong}; "
            f"padding: 0 {ds.space_xs}px {ds.space_xs}px {ds.space_xs}px; border: none;")
        sb.addWidget(self._role_lbl)

        self._sep1 = QLabel()
        self._sep1.setFixedHeight(ds.border_width)
        self._sep1.setStyleSheet(f"background-color: {p.border};")
        sb.addWidget(self._sep1)

        # ── SidebarWidget (programmes → classes) ──
        _sections = [
            ("Primaire", [("PYP", "PYP"), ("PP", "PP")]),
            ("Collège",  [("PEI", "PEI"), ("MYP", "MYP")]),
            ("Lycée",    [("DP", "DPFr"), ("DPEn", "DPEn")]),
        ]
        self._class_sidebar = SidebarWidget(_sections, PROGRAM_STYLES)
        self._class_sidebar.group_selected.connect(self._on_group_selected)
        self._class_sidebar.class_selected.connect(lambda cid, label: self._on_class_clicked(cid, label))
        self._class_sidebar.all_selected.connect(self._on_all_clicked)
        # Retirer le stretch interne du SidebarWidget (evite le grand blanc sous les classes)
        _container = self._class_sidebar.widget()  # le widget conteneur du QScrollArea
        _cl = _container.layout() if _container else None
        if _cl and _cl.count():
            _last = _cl.itemAt(_cl.count() - 1)
            if _last and _last.spacerItem():
                _cl.takeAt(_cl.count() - 1)
        sb.addWidget(self._class_sidebar)

        # Séparateur entre SidebarWidget et NavButtons
        self._sep2 = QLabel()
        self._sep2.setFixedHeight(ds.border_width)
        self._sep2.setStyleSheet(f"background-color: {p.border};")
        sb.addWidget(self._sep2)

        # ── NavButton navigation ──
        self._nav_buttons: dict[str, NavButton] = {}
        for key, label, icon_name in NAV_ITEMS:
            btn = NavButton(
                text=label,
                icon_name=icon_name,
                on_click=lambda checked=False, k=key: self._switch_to(k),
            )
            self._nav_buttons[key] = btn
            sb.addWidget(btn)

        sb.addStretch()
        self._sidebar = sidebar

        # ── Content ──
        self._stack = QStackedWidget()

        # QSplitter horizontal : sidebar ←→ contenu
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._sidebar)
        self._splitter.addWidget(self._stack)
        self._splitter.setSizes([ds.sidebar_width, ds.golden_width(ds.sidebar_width) * 2])
        self._splitter.setHandleWidth(ds.space_xxs)
        layout.addWidget(self._splitter)
        outer.addLayout(layout, 1)
        self._restyle()

    # ------------------------------------------------------------------
    # Load classes
    # ------------------------------------------------------------------
    def _load_classes(self):
        conn = db.server_conn
        if not conn:
            return
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id, c.label, l.fk_program_id, p.sigle
            FROM larcauth_classroom c
            JOIN larcauth_level l ON l.id = c.fk_level_id
            JOIN larcauth_program p ON p.id = l.fk_program_id
            WHERE c.enabled = TRUE AND p.sigle IN ('PYP', 'PP', 'PEI', 'MYP', 'DPEn', 'DPFr')
            ORDER BY p.sigle, c.label
        """)
        self._classes = [(r[0], r[1], r[2], r[3]) for r in cur.fetchall()]
        self._class_sidebar.load_classes(self._classes)

    # ------------------------------------------------------------------
    # SidebarWidget signals
    # ------------------------------------------------------------------
    @safe_slot("MainWindow._on_group_selected")
    def _on_group_selected(self, group: str):
        if group.startswith("grp_"):
            self._current_group_mode = group
            self._current_class_id = 0
        else:
            mode_map = {"Primaire": "grp_primaire", "Collège": "grp_college", "Lycée": "grp_lycee"}
            self._current_group_mode = mode_map.get(group, "grp_all")
            self._current_class_id = 0
        # Mettre a jour le dashboard avec le nouveau filtre
        if "dashboard" in self._pages:
            d = self._pages["dashboard"]
            if hasattr(d, 'set_group_mode'):
                d.set_group_mode(self._current_group_mode)
        self._switch_to("dashboard")

    @safe_slot("MainWindow._on_class_clicked")
    def _on_class_clicked(self, cid: int, label: str):
        self._current_class_id = cid
        self._current_group_mode = "class"
        # Charger le ClassPaymentPanel
        from LarcCompta.views.class_payment_panel import ClassPaymentPanel
        panel = ClassPaymentPanel()
        panel.load(cid, label)
        self._pages["class_payment"] = panel
        self._stack.addWidget(panel)
        self._stack.setCurrentWidget(panel)
        self._current_key = "class_payment"

    @safe_slot("MainWindow._on_all_clicked")
    def _on_all_clicked(self):
        self._current_group_mode = "grp_all"
        self._current_class_id = 0
        if "dashboard" in self._pages:
            d = self._pages["dashboard"]
            if hasattr(d, 'set_group_mode'):
                d.set_group_mode("grp_all")
        self._switch_to("dashboard")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    @safe_slot("MainWindow._switch_to")
    def _switch_to(self, key: str):
        self._current_key = key

        for k, btn in self._nav_buttons.items():
            btn.setChecked(k == key)

        if key not in self._pages:
            if key == "dashboard":
                from LarcCompta.views.dashboard import Dashboard
                self._pages[key] = Dashboard(group_mode=self._current_group_mode)
            elif key == "impayes":
                from LarcCompta.views.impayes import Impayes
                self._pages[key] = Impayes()
            elif key == "parents":
                from LarcCompta.views.parents_list import ParentsList
                self._pages[key] = ParentsList()
            elif key == "rappels":
                from LarcCompta.views.reminders import ReminderPanel
                self._pages[key] = ReminderPanel()
            elif key == "config":
                from LarcCompta.views.fee_config import FeeConfig
                self._pages[key] = FeeConfig()
            else:
                return
            self._stack.addWidget(self._pages[key])

        w = self._pages[key]
        if hasattr(w, 'refresh'):
            w.refresh()
        self._stack.setCurrentWidget(w)

    @safe_slot("MainWindow._on_topbar_theme")
    def _on_topbar_theme(self, key: str):
        theme_manager.set_active(key)
        session.theme_pref = key
        self._restyle()

    @safe_slot("MainWindow._restyle")
    def _restyle(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        try:
            self._sidebar.setStyleSheet(
                f"#sidebar {{ background-color: {p.surface_variant}; }}")
            self._stack.setStyleSheet(f"background: {p.background}; border: none;")
            if hasattr(self, '_splitter'):
                self._splitter.setStyleSheet(
                    f"QSplitter::handle {{ background: {p.border}; }}")
            self._user_lbl.setStyleSheet(
                f"font-size: {s(ds.font_label_lg)}px; font-weight: bold; "
                f"color: {p.text_strong}; padding: 0 {ds.space_xs}px; border: none;")
            self._role_lbl.setStyleSheet(
                f"font-size: {s(ds.font_label_sm)}px; color: {p.text_strong}; "
                f"padding: 0 {ds.space_xs}px {ds.space_xs}px {ds.space_xs}px; border: none;")
            self._sep1.setStyleSheet(f"background-color: {p.border};")
            self._sep2.setStyleSheet(f"background-color: {p.border};")
            # NavButtons
            for btn in self._nav_buttons.values():
                btn.restyle()
            if hasattr(self, '_topbar'):
                self._topbar.restyle()
        except RuntimeError:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass
