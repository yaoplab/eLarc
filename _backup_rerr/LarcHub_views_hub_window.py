from phibuilder.widgets import M3Button, M3Label, M3StackedWidget
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QScrollArea,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QIcon

from larccommon.session import session
from larccommon.database import db, DBMode
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.widgets.nav_button import NavButton
from larccommon.safe_slot import safe_slot


class HubWindow(QWidget):
    SIDEBAR_EXPANDED = 233
    SIDEBAR_COLLAPSED = 0

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"LarcHub — {session.full_name}")
        # 987×610 = paire dorée (610 = sidebar + golden_width(sidebar) ; 987 = golden_width(610))
        _min_h = ds.sidebar_width + ds.golden_width(ds.sidebar_width)  # 610
        self.setMinimumSize(ds.golden_width(_min_h), _min_h)  # 987×610

        self._sidebar_expanded = True
        self._sections: dict[str, dict] = {}
        self._current_section: str | None = None

        self._setup_ui()
        self._build_sections()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._check_connections)
        self._refresh_timer.start(30000)

        ds.theme_changed.connect(self._restyle)

    @safe_slot("HubWindow._restyle")
    def _restyle(self):
        """Ré-applique les styles palette du chrome (sidebar, labels, toggle, titre)."""
        p = theme_manager.palette
        try:
            self._sidebar.setStyleSheet(f"""
                #sidebar {{
                    background-color: {p.surface_variant};
                    border-right: 1px solid {p.border};
                }}
            """)
            self._user_label.setStyleSheet(f"""
                font-size: {theme_manager.font_size(13)}px; font-weight: bold;
                color: {p.text_strong};
                padding: 0 5px;
            """)
            self._role_label.setStyleSheet(f"""
                font-size: {theme_manager.font_size(10)}px; color: {p.text_strong};
                padding: 0 5px 8px 5px;
            """)
            self._sep.setStyleSheet(f"background-color: {p.border};")
            self._toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {p.surface_variant};
                    border: 1px solid {p.border};
                    border-left: none;
                    border-radius: 0 {ds.radius_xs}px {ds.radius_xs}px 0;
                    font-size: {theme_manager.font_size(10)}px;
                    color: {p.text_strong};
                    padding: 0 2px;
                }}
                QPushButton:hover {{
                    background: {p.border};
                }}
            """)
            self._section_title.setStyleSheet(f"""
                font-size: {theme_manager.font_size(16)}px; font-weight: bold;
                color: {p.text_strong};
                background-color: {p.surface};
                padding: {theme_manager.font_size(13)}px {theme_manager.font_size(21)}px;
                border-bottom: 1px solid {p.border};
            """)
            self._content.setStyleSheet(f"background-color: {p.background};")
        except RuntimeError:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        self._sidebar = QWidget()
        self._sidebar.setFixedWidth(self.SIDEBAR_EXPANDED)
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setStyleSheet(f"""
            #sidebar {{
                background-color: {theme_manager.palette.surface_variant};
                border-right: 1px solid {theme_manager.palette.border};
            }}
        """)
        sb_layout = QVBoxLayout(self._sidebar)
        sb_layout.setContentsMargins(ds.space_xs, theme_manager.image.theme_btn, ds.space_xs, theme_manager.font_size(13))
        sb_layout.setSpacing(ds.space_xs)

        # User info in sidebar
        self._user_label = M3Label(session.full_name or "Utilisateur")
        self._user_label.setStyleSheet(f"""
            font-size: {theme_manager.font_size(13)}px; font-weight: bold;
            color: {theme_manager.palette.text_strong};
            padding: 0 5px;
        """)
        sb_layout.addWidget(self._user_label)

        role_names = {
            'ADMIN': 'Administrateur',
            'COORD': 'Coordinateur',
            'SUPERVISEUR': 'Superviseur',
            'SECR': 'Secrétaire',
            'PROF': 'Enseignant',
        }
        # Afficher tous les rôles actifs (multi-rôle)
        tf = getattr(session, 'type_flags', {}) or {}
        active_roles = []
        if tf.get('director'):   active_roles.append('Directeur')
        if tf.get('coordinator'): active_roles.append('Coordinateur')
        if tf.get('supervisor'):  active_roles.append('Superviseur')
        if tf.get('secretary'):   active_roles.append('Secrétaire')
        if tf.get('teacher'):     active_roles.append('Enseignant')
        role_text = ' | '.join(active_roles) if active_roles else role_names.get(session.role.value, session.role.value)
        self._role_label = M3Label(role_text)
        self._role_label.setStyleSheet(f"""
            font-size: {theme_manager.font_size(10)}px; color: {theme_manager.palette.text_strong};
            padding: 0 5px 8px 5px;
        """)
        sb_layout.addWidget(self._role_label)

        self._sep = M3Label()
        self._sep.setFixedHeight(1)
        self._sep.setStyleSheet(f"background-color: {theme_manager.palette.border};")
        sb_layout.addWidget(self._sep)
        sb_layout.addSpacing(8)

        self._btn_layout = QVBoxLayout()
        self._btn_layout.setSpacing(ds.space_xs)
        sb_layout.addLayout(self._btn_layout)
        sb_layout.addStretch()

        # Wrap sidebar in a scroll area for multi-level navigation
        self._sidebar_scroll = QScrollArea()
        self._sidebar_scroll.setWidgetResizable(True)
        self._sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._sidebar_scroll.setFrameShape(QScrollArea.NoFrame)
        self._sidebar_scroll.setWidget(self._sidebar)
        self._sidebar_scroll.setFixedWidth(self.SIDEBAR_EXPANDED)
        layout.addWidget(self._sidebar_scroll)

        # Toggle button — always visible, between sidebar and content
        self._toggle_btn = M3Button("◀")
        self._toggle_btn.setFixedSize(ds.table_row_min, theme_manager.image.logo_small)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: {theme_manager.palette.surface_variant};
                border: 1px solid {theme_manager.palette.border};
                border-left: none;
                border-radius: 0 {ds.radius_xs}px {ds.radius_xs}px 0;
                font-size: {theme_manager.font_size(10)}px;
                color: {theme_manager.palette.text_strong};
                padding: 0 2px;
            }}
            QPushButton:hover {{
                background: {theme_manager.palette.border};
            }}
        """)
        self._toggle_btn.clicked.connect(self._toggle_sidebar)
        layout.addWidget(self._toggle_btn)

        # Content area (right side)
        self._content = QWidget()
        self._content.setStyleSheet(f"background-color: {theme_manager.palette.background};")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Header with section title
        self._section_title = M3Label()
        self._section_title.setStyleSheet(f"""
            font-size: {theme_manager.font_size(16)}px; font-weight: bold;
            color: {theme_manager.palette.text_strong};
            background-color: {theme_manager.palette.surface};
            padding: {theme_manager.font_size(13)}px {theme_manager.font_size(21)}px;
            border-bottom: 1px solid {theme_manager.palette.border};
        """)
        content_layout.addWidget(self._section_title)

        self._stack = M3StackedWidget()
        content_layout.addWidget(self._stack, 1)

        layout.addWidget(self._content, 1)

    @safe_slot("HubWindow._toggle_sidebar")
    def _toggle_sidebar(self):
        self._sidebar_expanded = not self._sidebar_expanded
        w = self.SIDEBAR_EXPANDED if self._sidebar_expanded else 0
        self._sidebar_scroll.setFixedWidth(w)
        self._toggle_btn.setText("▶" if not self._sidebar_expanded else "◀")

    def _build_sections(self):
        sections = []

        conn_ok = db.is_server_connected
        tf = getattr(session, 'type_flags', {}) or {}

        section_icons = {
            'supervision': 'visibility',
            'secretariat': 'description',
            'config': 'settings',
            'bulletin': 'subject',
            'rh': 'person',
            'compta': 'check',
        }

        has_supervision = tf.get('supervisor') or tf.get('coordinator') or tf.get('director')
        sections.append(('supervision', 'Supervision', has_supervision, conn_ok))

        has_bulletin = tf.get('secretary') or tf.get('director') or tf.get('coordinator')
        sections.append(('bulletin', 'Bulletins', has_bulletin, False))

        has_secretariat = tf.get('secretary') or tf.get('director')
        sections.append(('secretariat', 'Secrétariat', has_secretariat, conn_ok))

        has_rh = tf.get('director') or tf.get('secretary')
        sections.append(('rh', 'Ress. Humaines', has_rh, conn_ok))

        has_compta = tf.get('director') or tf.get('secretary')
        sections.append(('compta', 'Scolarite', has_compta, conn_ok))

        has_config = tf.get('director') or tf.get('coordinator')
        sections.append(('config', 'Configuration', has_config, False))

        for key, label, has_role, enabled in sections:
            btn = NavButton(
                text=label,
                icon_name=section_icons.get(key),
                on_click=lambda checked=False, k=key: self._switch_to(k),
            )
            btn.setVisible(has_role)
            btn.setEnabled(enabled and has_role)
            self._btn_layout.addWidget(btn)

            page = self._build_page(key, label)
            self._stack.addWidget(page)

            self._sections[key] = {
                'btn': btn,
                'page': page,
                'loaded': False,
            }

        for key, label, has_role, enabled in sections:
            if has_role and enabled:
                self._switch_to(key)
                break

    def _build_page(self, key: str, label: str):
        w = QWidget()
        return w

    def _switch_to(self, key: str):
        if key == self._current_section:
            return

        for info in self._sections.values():
            info['btn'].setChecked(False)

        info = self._sections.get(key)
        if not info:
            return

        info['btn'].setChecked(True)

        if not info['loaded']:
            self._load_section(key)
            info['loaded'] = True

        self._stack.setCurrentWidget(info['page'])
        self._current_section = key
        self._section_title.setText(info['btn'].text())

    def _load_section(self, key: str):
        info = self._sections.get(key)
        if not info:
            return

        try:
            if key == 'supervision':
                from LarcSuperviseur.views.main_window import MainWindow
                main_win = MainWindow()
            elif key == 'secretariat':
                from LarcSecretaire.views.main_window import MainWindow
                main_win = MainWindow()
            elif key == 'rh':
                from LarcRH.views.main_window import MainWindow as RHMainWindow
                main_win = RHMainWindow()
            elif key == 'compta':
                from LarcCompta.views.main_window import MainWindow as ComptaMainWindow
                main_win = ComptaMainWindow()
            else:
                return

            idx = self._stack.indexOf(info['page'])
            self._stack.removeWidget(info['page'])
            info['page'].deleteLater()
            self._stack.insertWidget(idx, main_win)
            info['page'] = main_win
            self._stack.setCurrentWidget(main_win)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            lbl = M3Label(f"Erreur de chargement : {e}")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: {theme_manager.palette.error}; font-size: {theme_manager.font_size(13)}px;")
            idx = self._stack.indexOf(info['page'])
            self._stack.removeWidget(info['page'])
            info['page'].deleteLater()
            self._stack.insertWidget(idx, lbl)
            info['page'] = lbl

    @safe_slot("Unknown._check_connections")
    def _check_connections(self):
        conn_ok = db.is_server_connected
        for key, info in self._sections.items():
            has_role = info['btn'].isVisible()
            if has_role:
                info['btn'].setEnabled(conn_ok)
