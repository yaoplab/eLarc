"""MainWindow LarcRH — sidebar 4 catégories + grille photos."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QScrollArea, QStackedWidget, QSizePolicy, QApplication,
)

from larccommon.database import db
from larccommon.session import session
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.icons import icon as md3_icon
from larccommon.safe_slot import safe_slot
from larccommon.widgets.topbar import TopBar


# Catégories comptables (celles qui affichent un effectif entre parenthèses)
_COUNTABLE = {'college', 'primaire', 'maternelle', 'staff'}

CATEGORIES = [
    ('dashboard',  'Vue d\'ensemble',     1001, 5000, 'dashboard'),
    ('college',   'Collège / Lycée',     1001, 2000, 'school'),
    ('primaire',  'Primaire',            2001, 3000, 'school'),
    ('maternelle','Maternelle',          3001, 4000, 'child_care'),
    ('staff',     'Staff non enseignant', 4001, 5000, 'person'),
    ('letters',   'Courriers',           1001, 5000, 'subject'),
    ('tasks',     'Tâches',              1001, 5000, 'check'),
    ('absences',  'Absences/Retards',    1001, 5000, 'calendar_today'),
]


class _CategoryButton(QPushButton):
    """Bouton de catégorie avec icône + compteur."""

    def __init__(self, key: str, label: str, icon_name: str, parent=None):
        super().__init__(parent)
        self._key = key
        self._label = label
        self._icon_name = icon_name
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(theme_manager.image.theme_btn)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # K26 (sidebar-spec) : icône calée à gauche + gap icône↔texte natif Qt
        # (8px = ds.space_xs). Sans text-align:left, Qt centre le groupe
        # icône+texte et l'icône dérive selon la longueur du libellé.
        self.setStyleSheet("QPushButton { text-align: left; }")
        self.setIconSize(QSize(ds.icon_sm,
                               ds.icon_sm))
        font = QFont()
        font.setPointSize(10)
        self.setFont(font)
        self._restyle_icon()
        self._update_text(0)

    def _restyle_icon(self):
        if self._icon_name:
            try:
                self.setIcon(md3_icon(self._icon_name,
                    color=theme_manager.palette.text_strong,
                    size=ds.icon_sm))
            except (ValueError, RuntimeError):
                pass

    def _update_text(self, count: int):
        # Les pages non comptables (Vue d'ensemble, Courriers, Tâches,
        # Absences/Retards) n'affichent PAS de « (0) » inutile.
        if self._key in _COUNTABLE:
            self.setText(f"{self._label} ({count})")
        else:
            self.setText(self._label)

    @property
    def key(self) -> str:
        return self._key


class MainWindow(QWidget):

    SIDEBAR_WIDTH = 233

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LarcRH — Ressources Humaines")
        self._current_key: str | None = None
        self._pages: dict[str, QWidget] = {}

        self._setup_ui()
        self._load_counts()
        ds.theme_changed.connect(self._restyle)

        QTimer.singleShot(100, self._select_first)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar ──
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(self.SIDEBAR_WIDTH)
        sidebar.setStyleSheet(f"""
            #sidebar {{
                background-color: {theme_manager.palette.surface_variant};
                border-right: 1px solid {theme_manager.palette.border};
            }}
        """)

        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(ds.space_xs, theme_manager.image.theme_btn,
                                     ds.space_xs, ds.space_lg)
        sb_layout.setSpacing(ds.space_xs)

        # Logo — D:\projets\logo\logo.png (fallback : ancien logoAEC.png)
        import os
        root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
        logo_path = os.path.join(root, "logo", "logo.png")
        if not os.path.exists(logo_path):
            logo_path = os.path.join(root, "LarcCommon", "logoAEC.png")
        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignCenter)
        # Logo = 80 % de la largeur du sidebar
        logo_w = int(self.SIDEBAR_WIDTH * 0.8)
        logo_lbl.setFixedWidth(logo_w)
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaledToWidth(logo_w, Qt.SmoothTransformation)
            logo_lbl.setPixmap(pix)
        else:
            logo_lbl.setText("Logo")
        logo_lbl.setStyleSheet("border: none; padding: 0;")
        sb_layout.addWidget(logo_lbl)

        sb_layout.addSpacing(ds.space_xs)

        # "Ressources Humaines" above user
        self._role_label = QLabel("Ressources Humaines")
        self._role_label.setAlignment(Qt.AlignCenter)
        self._role_label.setStyleSheet(f"""
            font-size: {theme_manager.font_size(10)}px;
            color: {theme_manager.palette.text_strong};
            padding: 0 5px;
        """)
        sb_layout.addWidget(self._role_label)

        # User name
        self._user_label = QLabel(session.full_name or "Utilisateur")
        self._user_label.setAlignment(Qt.AlignCenter)
        self._user_label.setStyleSheet(f"""
            font-size: {theme_manager.font_size(12)}px; font-weight: bold;
            color: {theme_manager.palette.text_soft};
            padding: 0 5px 8px 5px;
        """)
        sb_layout.addWidget(self._user_label)

        self._sidebar_sep = QLabel()
        self._sidebar_sep.setFixedHeight(1)
        self._sidebar_sep.setStyleSheet(f"background-color: {theme_manager.palette.border};")
        sb_layout.addWidget(self._sidebar_sep)
        sb_layout.addSpacing(8)

        # Category buttons
        self._buttons: dict[str, _CategoryButton] = {}
        for key, label, _lo, _hi, icon_name in CATEGORIES:
            btn = _CategoryButton(key, label, icon_name)
            btn.clicked.connect(lambda checked, k=key: self._switch_to(k))
            self._buttons[key] = btn
            sb_layout.addWidget(btn)

        sb_layout.addStretch()

        layout.addWidget(sidebar)
        self._sidebar = sidebar

        # ── Content ──
        self._content = QWidget()
        self._content.setStyleSheet(f"background-color: {theme_manager.palette.background};")
        cl = QVBoxLayout(self._content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        self._topbar = TopBar()
        self._topbar.logout_requested.connect(self._on_logout)
        self._topbar.theme_changed.connect(self._on_topbar_theme)
        cl.addWidget(self._topbar)

        # Présence RH : heartbeat 60 s + indicateur « N en ligne » (TopBar)
        self._presence_timer = QTimer(self)
        self._presence_timer.setInterval(60_000)
        self._presence_timer.timeout.connect(self._update_presence)
        self._presence_timer.start()
        QTimer.singleShot(0, self._update_presence)

        # Header
        self._header = QWidget()
        self._header.setStyleSheet(f"""
            background-color: {theme_manager.palette.surface};
            border-bottom: 1px solid {theme_manager.palette.border};
        """)
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(ds.space_md, ds.space_sm, ds.space_md, ds.space_sm)

        # Bouton ☰ : cacher / afficher la sidebar générale
        self._toggle_btn = QPushButton()
        self._toggle_btn.setIcon(md3_icon("menu", color=theme_manager.palette.text_strong, size=18))
        self._toggle_btn.setFixedSize(ds.field_height, ds.field_height)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setToolTip("Afficher / masquer le menu")
        self._toggle_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid {theme_manager.palette.outline}; "
            f"border-radius: {ds.radius_xs}px; background: transparent; }} "
            f"QPushButton:hover {{ background: {theme_manager.palette.surface_variant}; }}")
        self._toggle_btn.clicked.connect(self._toggle_sidebar)
        hl.addWidget(self._toggle_btn)

        self._section_title = QLabel()
        self._section_title.setStyleSheet(f"""
            font-size: {theme_manager.font_size(16)}px; font-weight: bold;
            color: {theme_manager.palette.text_strong};
        """)
        hl.addWidget(self._section_title)
        hl.addStretch()

        self._add_btn = QPushButton("+ Ajouter")
        self._add_btn.setCursor(Qt.PointingHandCursor)
        self._add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {theme_manager.palette.primary}; color: {theme_manager.palette.on_primary};
                border: none; border-radius: {ds.radius_sm}px;
                font-size: {theme_manager.font_size(12)}px; font-weight: bold;
                padding: {ds.space_xs}px {ds.space_md}px;
            }}
            QPushButton:hover {{ background: {theme_manager.palette.primary}; }}
        """)
        self._add_btn.clicked.connect(self._on_add)
        hl.addWidget(self._add_btn)

        cl.addWidget(self._header)

        # Stack
        self._stack = QStackedWidget()
        cl.addWidget(self._stack, 1)

        layout.addWidget(self._content, 1)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def _load_counts(self):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            QTimer.singleShot(1000, self._load_counts)
            return
        try:
            cur = conn.cursor()
            for key, _label, lo, hi, _icon in CATEGORIES:
                if key in ('dashboard', 'letters', 'tasks', 'absences'):
                    continue
                if key == 'staff':
                    cur.execute(
                        "SELECT COUNT(*) FROM larcauth_staff "
                        "WHERE aecuser_ptr_id BETWEEN %s AND %s AND enabled = true",
                        (lo, hi)
                    )
                else:
                    cur.execute(
                        "SELECT COUNT(*) FROM larcauth_aecuser a "
                        "JOIN larcauth_teachadm t ON t.aecuser_ptr_id = a.id "
                        "WHERE a.id BETWEEN %s AND %s AND t.enabled = true",
                        (lo, hi)
                    )
                cnt = cur.fetchone()[0]
                btn = self._buttons.get(key)
                if btn:
                    btn._update_text(cnt)
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            from larccommon.logger import log
            log("[MainWindow] Impossible de charger les compteurs")

    @safe_slot("MainWindow._update_presence")
    def _update_presence(self):
        """Heartbeat + rafraîchit l'indicateur « N en ligne » de la TopBar."""
        from LarcRH.common.hr_database import HRDatabase
        HRDatabase.set_session_online(session.user_id or 0, "LarcRH")
        online = HRDatabase.get_online_sessions()
        names = "\n".join(f"• {s['full_name']} ({s['app']})" for s in online)
        self._topbar.set_presence(f"● {len(online)} en ligne", names)

    @safe_slot("MainWindow._on_logout")
    def _on_logout(self):
        from LarcRH.common.hr_database import HRDatabase
        HRDatabase.set_session_offline(session.user_id or 0)
        QApplication.quit()

    @safe_slot("MainWindow._toggle_sidebar")
    def _toggle_sidebar(self):
        """Cache / affiche la sidebar générale (bouton ☰)."""
        self._sidebar.setVisible(not self._sidebar.isVisible())

    def _select_first(self):
        for key, _label, _lo, _hi, _icon in CATEGORIES:
            if key in self._buttons:
                self._switch_to(key)
                break

    @safe_slot("MainWindow._switch_to")
    def _switch_to(self, key: str):
        if key == self._current_key:
            return
        self._current_key = key

        for btn in self._buttons.values():
            btn.setChecked(False)
        btn = self._buttons.get(key)
        if btn:
            btn.setChecked(True)
            self._section_title.setText(btn._label)

        self._add_btn.setVisible(key not in ('dashboard', 'letters', 'tasks', 'absences'))

        if key not in self._pages:
            if key == 'dashboard':
                from LarcRH.views.hr_dashboard import HRDashboard
                page = HRDashboard()
            elif key == 'letters':
                from LarcRH.views.letter_manager import LetterManager
                page = LetterManager()
            elif key == 'tasks':
                page = self._make_todo_page()
            elif key == 'absences':
                from LarcRH.views.absence_planner import AbsencePlanner
                page = AbsencePlanner()
            else:
                from LarcRH.views.staff_grid import StaffGrid
                cat = next((c for c in CATEGORIES if c[0] == key), None)
                page = StaffGrid(key, cat[2], cat[3], is_staff=(key == 'staff'))
                page.staff_selected.connect(self._show_detail)
            self._pages[key] = page
            self._stack.addWidget(page)

        self._stack.setCurrentWidget(self._pages[key])
        page = self._pages[key]
        if hasattr(page, 'refresh'):
            page.refresh()

    @safe_slot("MainWindow._show_detail")
    def _show_detail(self, staff_data: dict):
        from LarcRH.views.staff_detail import StaffDetail
        detail = StaffDetail(staff_data, on_back=self._on_back_from_detail)
        self._stack.addWidget(detail)
        self._stack.setCurrentWidget(detail)

    @safe_slot("MainWindow._on_back_from_detail")
    def _on_back_from_detail(self):
        # Remove all detail widgets (they're pushed on top of the stack)
        from LarcRH.views.staff_detail import StaffDetail
        for i in range(self._stack.count() - 1, -1, -1):
            w = self._stack.widget(i)
            if isinstance(w, StaffDetail):
                self._stack.removeWidget(w)
                w.deleteLater()
        if self._current_key and self._current_key in self._pages:
            self._stack.setCurrentWidget(self._pages[self._current_key])

    def _make_todo_page(self):
        from larccommon.widgets.todo_kanban import TodoKanban
        from LarcRH.common.hr_database import HRDatabase
        from larccommon.session import session
        HRDatabase.ensure_todo_table()
        kanban = TodoKanban(
            load_fn=HRDatabase.get_todos,
            create_fn=HRDatabase.create_todo,
            move_fn=HRDatabase.move_todo,
            delete_fn=HRDatabase.delete_todo,
            reopen_fn=lambda task, uid: HRDatabase.create_todo(
                task.get("desc", ""), task.get("type", "custom"),
                task.get("due_date"), task.get("staff_id"), uid),
            task_types={
                "recrutement": "Recrutement",
                "contrat":    "Contrat",
                "paie":       "Paie",
                "formation":  "Formation",
                "evaluation": "Évaluation",
                "disciplinaire": "Disciplinaire",
                "conge":      "Congé",
                "document":   "Document",
                "custom":     "Manuel",
            },
            user_id=session.user_id,
        )
        return kanban

    @safe_slot("MainWindow._on_add")
    def _on_add(self):
        if self._current_key in ('dashboard', 'letters', 'tasks', 'absences'):
            return
        from LarcRH.views.staff_form import StaffFormDialog
        cat = next((c for c in CATEGORIES if c[0] == self._current_key), None)
        lo = cat[2] if cat else 1001
        hi = cat[3] if cat else 5000
        dlg = StaffFormDialog(lo, hi, parent=self)
        if dlg.exec():
            self._load_counts()
            if self._current_key in self._pages:
                page = self._pages[self._current_key]
                if hasattr(page, 'refresh'):
                    page.refresh()

    @safe_slot("MainWindow._restyle")
    @safe_slot("MainWindow._on_topbar_theme")
    def _on_topbar_theme(self, key: str):
        theme_manager.set_active(key)
        session.theme_pref = key
        self._restyle()

    def _restyle(self):
        # J8 : les pages sont stylées à la construction — les reconstruire
        # à chaque changement de thème (sinon textes figés aux couleurs de
        # l'ancien thème). Exécuté EN PREMIER : une exception dans le chrome
        # ci-dessous ne doit pas empêcher le rebuild.
        try:
            _key = self._current_key
            if _key and _key in self._pages:
                _old = self._pages[_key]
                self._stack.removeWidget(_old)
                _old.deleteLater()
                del self._pages[_key]
                self._current_key = None
                self._switch_to(_key)
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass
        p = theme_manager.palette
        s = theme_manager.font_size
        try:
            self._sidebar.setStyleSheet(f"""
                #sidebar {{
                    background-color: {p.surface_variant};
                    border-right: 1px solid {p.border};
                }}
            """)
            self._content.setStyleSheet(f"background-color: {p.background};")
            self._header.setStyleSheet(f"""
                background-color: {p.surface};
                border-bottom: 1px solid {p.border};
            """)
            self._role_label.setStyleSheet(f"""
                font-size: {s(10)}px; color: {p.text_strong}; padding: 0 5px;
            """)
            self._user_label.setStyleSheet(f"""
                font-size: {s(12)}px; font-weight: bold;
                color: {p.text_soft}; padding: 0 5px 8px 5px;
            """)
            self._sidebar_sep.setStyleSheet(f"background-color: {p.border};")
            self._section_title.setStyleSheet(f"""
                font-size: {s(16)}px; font-weight: bold; color: {p.text_strong};
            """)
            self._add_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {p.primary}; color: {p.on_primary};
                    border: none; border-radius: {ds.radius_sm}px;
                    font-size: {s(12)}px; font-weight: bold;
                    padding: {ds.space_xs}px {ds.space_md}px;
                }}
                QPushButton:hover {{ background: {p.primary}; }}
            """)
            # Icônes des boutons de catégorie
            for btn in self._buttons.values():
                btn._restyle_icon()
            if hasattr(self, "_topbar"):
                self._topbar.restyle()
        except RuntimeError:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass
