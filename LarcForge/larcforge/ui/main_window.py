"""Fenêtre principale LarcForge — bandeau + navigation + panels à la demande.

Patron : LarcConfig/views/config_window.py (QWidget#root, sidebar M3Frame,
QStackedWidget lazy, _restyle_all). Pas de login : l'IHM est un poste de
contrôle local, sans session utilisateur.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QMessageBox, QStackedWidget, QVBoxLayout, QWidget,
)
from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from larccommon.widgets.topbar import TopBar
from phibuilder.phi.scale import SpacingToken
from phibuilder.widgets import M3Button, M3Frame, M3Label
from phibuilder.widgets.button import ButtonVariant

from . import db as db_mod
from .panels.common import restyle_label
from .profiles import DbProfile, ProfilesStore, UiConfig

_SECTIONS = [
    ("accueil", "Accueil", "home"),
    ("verifs", "Vérifications", "bolt"),
    ("issues", "Registre des issues", "error"),
    ("config", "Configuration", "settings"),
    ("aide", "Aide", "info"),
]


@dataclass
class AppContext:
    """Contexte partagé par les panels : racine, timeout, persistance, DB."""

    root: str
    timeout: int
    store: ProfilesStore
    config: UiConfig

    def open_db(self, profile: DbProfile | None = None):
        """Connexion à la base — profil explicite, profil actif, ou config.ini."""
        if profile is None and self.config.active_db_profile:
            for p in self.config.db_profiles:
                if p.name == self.config.active_db_profile:
                    profile = p
                    break
        return db_mod.open_db(self.root, profile)


class MainWindow(QWidget):
    def __init__(self, root, timeout: int = 300,
                 store: ProfilesStore | None = None,
                 config: UiConfig | None = None):
        super().__init__()
        store = store or ProfilesStore()
        config = config or store.load()
        self._ctx = AppContext(root=root, timeout=timeout, store=store,
                               config=config)
        self._panels: dict[str, QWidget] = {}
        self._current: str | None = None
        self._btns: dict[str, M3Button] = {}

        phi = theme_manager.phi_theme
        c = phi.colors
        sp = phi.spacing.spacing

        self.setWindowTitle(f"LarcForge — {config.branding.school_name}")
        self.setObjectName("root")
        # Minimum 1024×720 (Fibonacci : 1024 = 7·136+52+20 ; 720 = 5·136+32+8)
        self.setMinimumSize(ds.space_xxxl * 7 + ds.button_height + ds.space_md,
                            ds.space_xxxl * 5 + ds.space_lg + ds.space_xs)
        self.setStyleSheet(f"QWidget#root {{ background: {c.background}; }}")

        # Bandeau commun : date + sélecteur de thème (pas de réseau/profil)
        self._topbar = TopBar(show_network=False, show_profile=False)
        self._topbar.theme_changed.connect(self._on_topbar_theme)
        ds.theme_changed.connect(self._restyle_all)  # réactivité thème

        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)
        root_lay.addWidget(self._topbar)

        outer = QHBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Sidebar
        side = M3Frame(theme=phi)
        self._side = side
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(ds.sidebar_width)
        side.setStyleSheet(
            f"background: {c.surface}; border-right: 1px solid {c.outline_variant};")
        sl = QVBoxLayout(side)
        sl.setContentsMargins(sp(SpacingToken.SM), sp(SpacingToken.MD),
                              sp(SpacingToken.SM), sp(SpacingToken.MD))
        sl.setSpacing(sp(SpacingToken.XS))

        self._title_lbl = M3Label("LarcForge", theme=phi, style="headline_small")
        sl.addWidget(self._title_lbl)
        self._school_lbl = M3Label(config.branding.school_name, theme=phi,
                                   style="body_small")
        sl.addWidget(self._school_lbl)
        sl.addSpacing(sp(SpacingToken.MD))

        for key, label, icon_name in _SECTIONS:
            btn = M3Button(label, theme=phi, variant=ButtonVariant.TEXT)
            btn.setIcon(md3_icon(icon_name, color=c.on_surface, size=ds.icon_md))
            btn.setIconSize(QSize(ds.icon_md, ds.icon_md))
            btn.setFixedHeight(ds.field_height + ds.space_xs)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self._switch(k))
            self._btns[key] = btn
            sl.addWidget(btn)

        sl.addStretch()

        # Stack des panels (chargés à la demande)
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {c.background};")

        outer.addWidget(side)
        outer.addWidget(self._stack, 1)
        root_lay.addLayout(outer, 1)

        self._switch("accueil")  # Écran d'entrée : Accueil

    # ── Navigation ─────────────────────────────────────────────────────

    def _style_buttons(self, section: str):
        """Couleurs des boutons de navigation — texte TOUJOURS visible (primary)."""
        c = theme_manager.phi_theme.colors
        icons = dict((k, ic) for k, _, ic in _SECTIONS)
        for k, btn in self._btns.items():
            bg = c.primary_container if k == section else "transparent"
            btn.setIcon(md3_icon(icons.get(k, "home"), color=c.on_surface,
                                 size=ds.icon_md))
            btn.setStyleSheet(
                f"M3Button {{ background: {bg}; color: {c.primary}; "
                f"text-align: left; padding-left: {ds.space_xs}px; "
                f"border-radius: {ds.radius_xs}px; }}")

    def _switch(self, section: str, force: bool = False):
        if self._current == section and not force:
            return
        self._current = section
        self._style_buttons(section)
        if section not in self._panels:
            panel = self._create(section)
            if panel:
                self._panels[section] = panel
                self._stack.addWidget(panel)
        if section in self._panels:
            self._stack.setCurrentWidget(self._panels[section])
            reload = getattr(self._panels[section], "reload", None)
            if callable(reload):
                reload()  # fraîcheur : chaque panel se recharge à la visite

    @safe_slot("MainWindow.on_topbar_theme")
    def _on_topbar_theme(self, key: str):
        theme_manager.set_active(key)

    @safe_slot("MainWindow.restyle_all")
    def _restyle_all(self):
        """Réactivité thème (pattern LarcConfig) : chrome inline + panels."""
        c = theme_manager.phi_theme.colors
        self.setStyleSheet(f"QWidget#root {{ background: {c.background}; }}")
        self._stack.setStyleSheet(f"background: {c.background};")
        self._side.setStyleSheet(
            f"background: {c.surface}; border-right: 1px solid {c.outline_variant};")

        # Textes sidebar — visibles dans tous les thèmes (M3Label gèle la
        # couleur à la construction → on la re-pose avec la typographie)
        restyle_label(self._title_lbl, "headline_small",
                      theme_manager.palette.text_strong)
        restyle_label(self._school_lbl, "body_small",
                      theme_manager.palette.text_soft)
        self._style_buttons(self._current)

        for panel in self._panels.values():
            restyle = getattr(panel, "_restyle", None)
            if callable(restyle):
                restyle()  # panneau réactif : pas de reconstruction
        self._topbar.restyle()

    def _create(self, section: str):
        from .panels.config_panel import ConfigPanel
        from .panels.dashboard_panel import DashboardPanel
        from .panels.help_panel import HelpPanel
        from .panels.issues_panel import IssuesPanel
        from .panels.run_panel import RunPanel
        panel = {
            "accueil": DashboardPanel,
            "verifs": RunPanel,
            "issues": IssuesPanel,
            "config": ConfigPanel,
            "aide": HelpPanel,
        }[section](self._ctx)
        sig = getattr(panel, "switch_requested", None)
        if sig is not None:
            sig.connect(self._switch)  # ex. « Voir le registre » depuis le run
        branded = getattr(panel, "branding_changed", None)
        if branded is not None:
            branded.connect(self._on_branding_changed)  # marque école
        return panel

    @safe_slot("MainWindow.on_branding_changed")
    def _on_branding_changed(self):
        """Marque école mise à jour dans Configuration → chrome rafraîchi."""
        cfg_ui = self._ctx.config
        self.setWindowTitle(f"LarcForge — {cfg_ui.branding.school_name}")
        self._school_lbl.setText(cfg_ui.branding.school_name)

    def closeEvent(self, event):
        """Fermeture pendant un run → confirmation (le run serait interrompu)."""
        panel = self._panels.get("verifs")
        if panel is not None and panel.run_in_progress():
            ret = QMessageBox.question(
                self, "Vérification en cours",
                "Une vérification est en cours.\n"
                "Quitter l'application ? Le run sera interrompu et marqué "
                "comme erroné dans le registre.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ret != QMessageBox.Yes:
                event.ignore()
                return
            panel.close_run()
        super().closeEvent(event)
