"""TopBar partagée — date/heure, réseau, thème, profil.

Utilisée par LarcSuperviseur, LarcRH, LarcCompta.
Importe exclusivement depuis larccommon (pas de dépendance applicative).
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QSize, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QMessageBox, QApplication,
)

from phibuilder.widgets import M3Button, M3Label, M3Menu, M3ProfileButton

from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.l10n import _
from larccommon.network import detect_network
from larccommon.preferences_dialog import PreferencesDialog
from larccommon.safe_slot import safe_slot
from larccommon.session import session
from larccommon.theme import theme_manager


class TopBar(QFrame):
    """Barre supérieure : date/heure, réseau, sélecteur de thème, profil.

    Émet theme_changed(theme_key) et logout_requested().
    """

    theme_changed = Signal(str)
    logout_requested = Signal()

    _THEME_ICONS = {
        "blue": "light_mode",
        "dark": "dark_mode",
        "sobre": "tonality",
        "contrast": "bolt",
    }

    def __init__(self, show_network: bool = True, show_theme: bool = True,
                 show_profile: bool = True, show_datetime: bool = True,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("top_bar")
        self._show_network = show_network
        self._show_theme = show_theme
        self._show_profile = show_profile
        self._show_datetime = show_datetime
        self._build_ui()
        if show_datetime:
            self._start_clock()

    # ── UI ────────────────────────────────────────────────────────────

    def _build_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QHBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_xs, ds.space_md, ds.space_xs)
        layout.setSpacing(ds.space_sm)

        # Date + Heure
        if self._show_datetime:
            self._date_label = M3Label()
            self._date_label.setStyleSheet(
                f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong}; border: none;")
            self._time_label = M3Label()
            self._time_label.setStyleSheet(
                f"font-size: {s(13)}px; font-weight: bold; color: {p.primary}; border: none;")
            self._update_datetime()
            layout.addWidget(self._date_label)
            layout.addWidget(self._time_label)

        layout.addStretch()

        # Réseau
        if self._show_network:
            self._network_label = M3Label()
            self._update_network()
            layout.addWidget(self._network_label)

        # Thème
        if self._show_theme:
            self._theme_btn = M3Button()
            self._theme_btn.setObjectName("theme_btn")
            self._theme_btn.setFixedSize(theme_manager.image.theme_btn,
                                         theme_manager.image.theme_btn)
            self._theme_btn.setToolTip(_("topbar.theme_tooltip"))
            self._theme_btn.setIcon(self._make_theme_icon())
            self._theme_btn.setIconSize(QSize(18, 18))
            self._theme_menu = M3Menu()
            for key, label in theme_manager.names():
                icon_name = self._THEME_ICONS.get(key, "light_mode")
                pal = theme_manager.get_palette(key)
                ic = md3_icon(icon_name, color=pal.primary if pal else "#1F4494", size=18)
                a = self._theme_menu.addAction(ic, label)
                a.setData(key)
            self._theme_menu.triggered.connect(self._on_theme_triggered)
            self._theme_btn.setMenu(self._theme_menu)
            layout.addWidget(self._theme_btn)

        # Profil
        if self._show_profile:
            initials = self._compute_initials()
            self._profile_btn = M3ProfileButton(initials)
            self._profile_btn.setFixedSize(theme_manager.image.profile_btn,
                                           theme_manager.image.profile_btn)
            self._profile_btn.setCursor(Qt.PointingHandCursor)
            self._profile_btn.setStyleSheet(
                f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; "
                f"font-weight: bold; font-size: {s(12)}px; "
                f"border: none; border-radius: 17px; text-align: center; padding: 0px; }}"
                f"QPushButton:hover {{ background: {p.active}; }}"
                f"QPushButton::menu-indicator {{ image: none; width: 0px; }}")
            self._profile_menu = M3Menu(self)
            prefs_action = self._profile_menu.addAction(
                md3_icon("settings", color=p.text_strong, size=18),
                _("topbar.preferences"))
            prefs_action.triggered.connect(self._on_preferences)
            pwd_action = self._profile_menu.addAction(
                md3_icon("lock", color=p.text_strong, size=18),
                _("topbar.change_password"))
            pwd_action.triggered.connect(self._on_change_password)
            self._profile_menu.addSeparator()
            logout_action = self._profile_menu.addAction(
                md3_icon("logout", color=p.text_strong, size=18),
                _("topbar.logout"))
            logout_action.triggered.connect(self._on_logout)
            self._profile_btn.setMenu(self._profile_menu)
            layout.addWidget(self._profile_btn)

        self.setStyleSheet(self._style)

    @property
    def _style(self) -> str:
        p = theme_manager.palette
        return (f"#top_bar {{ background: {p.surface}; "
                f"border-bottom: 1px solid {p.outline_variant}; "
                f"border-radius: 0px; }}"
                # Boutons icône-only : pas de padding global (icône centrée)
                f"QPushButton#theme_btn, QPushButton#profile_btn "
                f"{{ padding: 0; }}")

    # ── Horloge ───────────────────────────────────────────────────────

    def _start_clock(self):
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_datetime)
        self._clock_timer.start(60_000)

    @safe_slot("TopBar._update_datetime")
    def _update_datetime(self):
        now = datetime.now()
        # Format français
        jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        mois = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        date_str = f"{jours[now.weekday()]} {now.day} {mois[now.month - 1]} {now.year}"
        time_str = now.strftime("%H:%M")
        if hasattr(self, "_date_label"):
            self._date_label.setText(date_str + "  ")
        if hasattr(self, "_time_label"):
            self._time_label.setText(time_str + "  ")

    # ── Réseau ────────────────────────────────────────────────────────

    def _update_network(self):
        if not hasattr(self, "_network_label"):
            return
        intranet_ok, internet_ok = detect_network()
        p = theme_manager.palette
        s = theme_manager.font_size
        if intranet_ok:
            self._network_label.setText(_("topbar.network.intranet"))
            self._network_label.setStyleSheet(
                f"color: {p.success}; font-weight: bold; font-size: {s(11)}px; border: none;")
        elif internet_ok:
            self._network_label.setText(_("topbar.network.cloud"))
            self._network_label.setStyleSheet(
                f"color: {p.primary}; font-weight: bold; font-size: {s(11)}px; border: none;")
        else:
            self._network_label.setText(_("topbar.network.offline"))
            self._network_label.setStyleSheet(
                f"color: {p.text_disabled}; font-size: {s(11)}px; border: none;")

    # ── Thème ─────────────────────────────────────────────────────────

    def _make_theme_icon(self) -> QIcon:
        name = self._THEME_ICONS.get(theme_manager.active_name, "light_mode")
        return md3_icon(name, color=theme_manager.palette.text_strong, size=18)

    @safe_slot("TopBar._on_theme_triggered")
    def _on_theme_triggered(self, action):
        key = action.data()
        if key:
            self.theme_changed.emit(key)

    # ── Profil ────────────────────────────────────────────────────────

    def _compute_initials(self) -> str:
        name = session.full_name or ""
        return "".join(w[0].upper() for w in name.split() if w)[:2] or "?"

    @safe_slot("TopBar._on_preferences")
    def _on_preferences(self):
        old_theme = theme_manager.active_name
        old_lang = session.fk_language
        dlg = PreferencesDialog(self)
        if dlg.exec():
            lang_changed = session.fk_language != old_lang
            if lang_changed:
                QMessageBox.information(
                    self, _("topbar.preferences"),
                    _("topbar.restart_needed"))
            self.update_profile()

    @safe_slot("TopBar._on_change_password")
    def _on_change_password(self):
        from larccommon.password_dialog import ChangePasswordDialog
        dlg = ChangePasswordDialog(self)
        dlg.exec()

    @safe_slot("TopBar._on_logout")
    def _on_logout(self):
        self.logout_requested.emit()

    def update_profile(self):
        if hasattr(self, "_profile_btn"):
            self._profile_btn.setText(self._compute_initials())

    def set_presence(self, text: str, tooltip: str = ""):
        """Indicateur de présence (ex. « ● 3 en ligne ») à côté du réseau.

        Le tooltip liste les noms des utilisateurs connectés.
        """
        if not hasattr(self, "_presence_label"):
            self._presence_label = M3Label("")
            self._presence_label.setStyleSheet(
                f"font-size: {theme_manager.font_size(11)}px; font-weight: bold; "
                f"color: {theme_manager.palette.primary}; border: none;")
            idx = self.layout().indexOf(getattr(self, "_network_label", None))
            self.layout().insertWidget(idx + 1 if idx >= 0 else 2,
                                       self._presence_label)
        self._presence_label.setText(text)
        if tooltip:
            self._presence_label.setToolTip(tooltip)

    # ── Restyle (appelé après changement de thème) ────────────────────

    def restyle(self):
        """Réapplique les styles après un changement de thème."""
        p = theme_manager.palette
        s = theme_manager.font_size
        self.setStyleSheet(self._style)
        if hasattr(self, "_theme_btn"):
            self._theme_btn.setIcon(self._make_theme_icon())
        if hasattr(self, "_profile_btn"):
            self._profile_btn.setStyleSheet(
                f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; "
                f"font-weight: bold; font-size: {s(12)}px; "
                f"border: none; border-radius: 17px; text-align: center; padding: 0px; }}"
                f"QPushButton:hover {{ background: {p.active}; }}"
                f"QPushButton::menu-indicator {{ image: none; width: 0px; }}")
        if hasattr(self, "_date_label"):
            self._date_label.setStyleSheet(
                f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        if hasattr(self, "_time_label"):
            self._time_label.setStyleSheet(
                f"font-size: {s(13)}px; font-weight: bold; color: {p.primary}; border: none;")
        self._update_network()
