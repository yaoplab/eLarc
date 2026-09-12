from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from phibuilder.widgets import M3Button, M3Label, M3Menu, M3ProfileButton
from PySide6.QtCore import QCoreApplication, QSize, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QVBoxLayout,
)

from LarcSuperviseur.common.network import detect_network
from LarcSuperviseur.common.session import session
from LarcSuperviseur.common.theme import theme_manager


class TopBar(QFrame):
    """UI bandeau 2 lignes : date/heure/terme, réseau, thème, boutons période."""

    def __init__(self, on_period_click, on_theme_change, on_refresh):
        super().__init__()
        self.setObjectName("top_bar")
        self._on_period_click = on_period_click
        self._on_theme_change = on_theme_change
        self._on_refresh = on_refresh

        self._unit_periods: list[dict] = []
        self._unit_keys: list[str] = []
        self._unit_buttons: list[M3Button] = []

        self._build_ui()
        self._start_clock()
        ds.theme_changed.connect(self.restyle)

    # ── Construction UI ────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            ds.space_xs + ds.space_xxs // 2,  # 10px
            ds.space_xxs + ds.space_xxs // 2,  # 6px
            ds.space_xs + ds.space_xxs // 2,
            ds.space_xxs + ds.space_xxs // 2,
        )
        outer.setSpacing(ds.space_xxs)
        p = theme_manager.palette
        d = theme_manager.design

        # Ligne 1 -------------------------------------------------------
        row1 = QHBoxLayout()
        row1.setSpacing(d.radius_lg)

        self._date_label = M3Label()
        self._date_label.setStyleSheet(
            f"font-size: {theme_manager.font_size(21)}px; font-weight: bold; color: {p.text_strong};"
        )
        self._time_label = M3Label()
        self._time_label.setStyleSheet(
            f"font-size: {theme_manager.font_size(21)}px; font-weight: bold; color: {p.primary};"
        )
        self._term_label = M3Label()
        self._term_label.setStyleSheet(
            f"font-size: {theme_manager.font_size(13)}px; color: {p.text_strong}; "
            f"padding-left: {theme_manager.font_size(13)}px;"
        )
        self._update_datetime()
        row1.addWidget(self._date_label)
        row1.addWidget(self._time_label)
        row1.addWidget(self._term_label)
        row1.addStretch()

        self._network_label = M3Label()
        self._update_style()
        row1.addWidget(self._network_label)

        self._theme_btn = M3Button()
        self._theme_btn.setObjectName("theme_btn")
        self._theme_btn.setFixedSize(theme_manager.image.theme_btn, theme_manager.image.theme_btn)
        self._theme_btn.setToolTip(_("topbar.theme_tooltip"))
        self._theme_btn.setIcon(self._theme_icon())
        self._theme_btn.setIconSize(
            QSize(ds.icon_sm, ds.icon_sm)
        )
        self._theme_menu = M3Menu(theme=theme_manager.phi_theme)
        _theme_icon_names = {
            "blue": "light_mode",
            "dark": "dark_mode",
            "sobre": "tonality",
            "contrast": "bolt",
        }
        self._theme_menu_actions = []
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
            self._theme_menu_actions.append((a, icon_name, key))
        self._theme_menu.triggered.connect(self._on_theme_triggered)
        self._theme_btn.setMenu(self._theme_menu)
        row1.addWidget(self._theme_btn)

        # Bouton profil (initiales)
        self._profile_btn = M3ProfileButton("?")
        self._profile_btn.setFixedSize(
            ds.icon_md, ds.icon_md
        )
        self._profile_btn.setCursor(Qt.PointingHandCursor)
        self._profile_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; "
            f"font-weight: bold; font-size: {theme_manager.font_size(12)}px; "
            f"border: none; border-radius: 17px; text-align: center; padding: 0px; }}"
            f"QPushButton:hover {{ background: {p.active}; }}"
            f"QPushButton::menu-indicator {{ image: none; width: 0px; }}"
        )
        self.update_profile()
        self._profile_menu = M3Menu(theme=theme_manager.phi_theme, parent=self)
        self._prefs_action = self._profile_menu.addAction(
            md3_icon("settings", color=p.text_strong, size=ds.icon_sm),
            _("topbar.preferences"),
        )
        self._prefs_action.triggered.connect(self._on_preferences)
        self._pwd_action = self._profile_menu.addAction(
            md3_icon("lock", color=p.text_strong, size=ds.icon_sm),
            _("topbar.change_password"),
        )
        self._pwd_action.triggered.connect(self._on_change_password)
        self._profile_menu.addSeparator()
        self._logout_action = self._profile_menu.addAction(
            md3_icon("logout", color=p.text_strong, size=ds.icon_sm),
            _("topbar.logout"),
        )
        self._logout_action.triggered.connect(self._on_logout)
        self._profile_btn.setMenu(self._profile_menu)
        row1.addWidget(self._profile_btn)

        self._loading_label = M3Label()
        self._loading_label.setStyleSheet(
            f"font-size: {theme_manager.font_size(13)}px; color: {p.primary}; font-weight: bold;"
        )
        self._loading_label.setVisible(False)
        row1.addWidget(self._loading_label)

        # Ligne 2 : 5 fixes + slot unités + espacement + refresh ---------
        self._period_row = QHBoxLayout()
        self._period_row.setSpacing(d.spacing)
        self._period_group = QButtonGroup(self)
        self._period_group.setExclusive(True)
        self._period_keys: list[str] = []

        fixed = [
            (_("topbar.period.day"), "day"),
            (_("topbar.period.week"), "week"),
            (_("topbar.period.month"), "month"),
            (_("topbar.period.term"), "term"),
            (_("topbar.year"), "year"),
        ]
        for label, key in fixed:
            btn = self._make_period_btn(label)
            btn.clicked.connect(lambda checked, k=key: self._on_period_click(k))
            self._period_group.addButton(btn)
            self._period_keys.append(key)
            self._period_row.addWidget(btn)
        if self._period_keys:
            self._period_group.buttons()[0].setChecked(True)

        # Slot pour les unités (inséré entre les fixes et le spacer)
        self._unit_slot = QHBoxLayout()
        self._unit_slot.setSpacing(d.spacing)
        self._period_row.addLayout(self._unit_slot)

        self._period_row.addSpacing(13)
        self._refresh_btn = M3Button()
        self._refresh_btn.setFixedSize(
            ds.icon_md, ds.icon_md
        )
        self._refresh_btn.setIcon(
            md3_icon("refresh", color=p.text_strong, size=ds.icon_sm)
        )
        self._refresh_btn.setIconSize(
            QSize(ds.icon_sm, ds.icon_sm)
        )
        self._refresh_btn.clicked.connect(self._on_refresh)
        self._period_row.addWidget(self._refresh_btn)
        self._period_row.addStretch()

        outer.addLayout(row1)
        self._period_container = QFrame()
        self._period_container.setLayout(self._period_row)
        outer.addWidget(self._period_container)

    def _start_clock(self):
        self._clock_timer = QTimer()
        self._clock_timer.timeout.connect(self._update_datetime)
        self._clock_timer.start(10000)

    # ── Boutons période ────────────────────────────────────────────────

    def _make_period_btn(self, label: str) -> M3Button:
        btn = M3Button(label)
        btn.setObjectName("period_btn")
        btn.setCheckable(True)
        btn.setFixedSize(theme_manager.image.logo, theme_manager.image.theme_btn)  # 89×34
        return btn

    def set_unit_periods(self, periods: list[dict]):
        self._unit_periods = periods
        # Vider le slot unités
        for btn in self._unit_buttons:
            self._period_group.removeButton(btn)
            self._unit_slot.removeWidget(btn)
            btn.deleteLater()
        self._unit_buttons.clear()
        self._unit_keys.clear()
        # Re-remplir
        for up in self._unit_periods:
            key = f"unit_{up['id']}"
            btn = self._make_period_btn(up["label"])
            btn.clicked.connect(lambda checked, k=key: self._on_period_click(k))
            self._period_group.addButton(btn)
            self._unit_buttons.append(btn)
            self._unit_keys.append(key)
            self._unit_slot.addWidget(btn)

    def show_period_row(self, visible: bool):
        self._period_container.setVisible(visible)

    # ── Mise à jour des labels ─────────────────────────────────────────

    @safe_slot("TopBar.update_datetime")
    def _update_datetime(self):
        from datetime import datetime

        now = datetime.now()
        self._date_label.setText(now.strftime("%A %d %B %Y") + "  ")
        self._time_label.setText(now.strftime("%H:%M") + "  ")
        t = session.term_label
        self._term_label.setText(f"— {t}" if t else "")

    def update_network(self):
        self._update_style()

    def _update_style(self):
        intranet_ok, internet_ok = detect_network()
        p = theme_manager.palette
        s = theme_manager.font_size
        if intranet_ok:
            self._network_label.setText(_("topbar.network.intranet"))
            self._network_label.setStyleSheet(
                f"color: {p.success}; font-weight: bold; font-size: {s(12)}px;"
            )
        elif internet_ok:
            self._network_label.setText(_("topbar.network.cloud"))
            self._network_label.setStyleSheet(
                f"color: {p.primary}; font-weight: bold; font-size: {s(12)}px;"
            )
        else:
            self._network_label.setText(_("topbar.network.offline"))
            self._network_label.setStyleSheet(f"color: {p.text_disabled}; font-size: {s(12)}px;")

    def set_loading(self, busy: bool, msg: str = _("common.label.loading")):
        self._loading_label.setText("⟳ " + msg if busy else "")
        self._loading_label.setVisible(busy)
        QCoreApplication.processEvents()

    # ── Thème ──────────────────────────────────────────────────────────

    _THEME_ICON_NAMES = {
        "blue": "light_mode",
        "dark": "dark_mode",
        "sobre": "tonality",
        "contrast": "bolt",
    }

    def _theme_icon(self) -> QIcon:
        name = self._THEME_ICON_NAMES.get(theme_manager.active_name, "light_mode")
        p = theme_manager.palette
        return md3_icon(name, color=p.text_strong, size=ds.icon_sm)

    @safe_slot("TopBar.on_theme_triggered")
    def _on_theme_triggered(self, action):
        key = action.data()
        if key:
            self._on_theme_change(key)

    @safe_slot("TopBar.on_logout")
    def _on_logout(self):
        QCoreApplication.quit()

    @safe_slot("TopBar.on_preferences")
    def _on_preferences(self):
        from LarcSuperviseur.common.session import session
        from larccommon.preferences_dialog import PreferencesDialog

        old_theme = theme_manager.active_name
        old_lang = session.fk_language
        dlg = PreferencesDialog(self)
        if dlg.exec():
            lang_changed = session.fk_language != old_lang
            if lang_changed:
                from larccommon.l10n import Translator
                lang = "en" if session.fk_language == 1 else "fr"
                Translator.instance(lang).reload(Translator.l10n_dir())
                QMessageBox.information(
                    self, _("topbar.preferences"),
                    _("topbar.restart_needed"))
            self.update_profile()

    @safe_slot("TopBar.on_change_password")
    def _on_change_password(self):
        from larccommon.password_dialog import ChangePasswordDialog

        dlg = ChangePasswordDialog(self)
        dlg.exec()

    def update_profile(self):
        from LarcSuperviseur.common.session import session

        initials = "".join(w[0].upper() for w in session.full_name.split() if w)[:2] or "?"
        self._profile_btn.setText(initials)

    # ── Réapplication du style après changement de thème ────────────────

    @safe_slot("TopBar.restyle")
    def restyle(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        self._theme_btn.setIcon(self._theme_icon())
        self._profile_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; "
            f"font-weight: bold; font-size: {s(12)}px; border: none; border-radius: 17px; "
            f"text-align: center; padding: 0px; }}"
            f"QPushButton:hover {{ background: {p.active}; }}"
            f"QPushButton::menu-indicator {{ image: none; width: 0px; }}"
        )
        self._date_label.setStyleSheet(
            f"font-size: {s(21)}px; font-weight: bold; color: {p.text_strong};"
        )
        self._time_label.setStyleSheet(
            f"font-size: {s(21)}px; font-weight: bold; color: {p.primary};"
        )
        self._term_label.setStyleSheet(
            f"font-size: {s(13)}px; color: {p.text_strong}; padding-left: 13px;"
        )
        self._loading_label.setStyleSheet(
            f"font-size: {s(13)}px; color: {p.primary}; font-weight: bold;"
        )
        self._update_style()
        for action, icon_name, key in self._theme_menu_actions:
            pal = theme_manager.get_palette(key)
            action.setIcon(
                md3_icon(icon_name, color=pal.primary if pal else "#1565C0", size=ds.icon_sm)
            )
        self._prefs_action.setIcon(md3_icon("settings", color=p.text_strong, size=ds.icon_sm))
        self._pwd_action.setIcon(md3_icon("lock", color=p.text_strong, size=ds.icon_sm))
        self._logout_action.setIcon(md3_icon("logout", color=p.text_strong, size=ds.icon_sm))
