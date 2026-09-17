"""Fenêtre principale LarcConfig — bandeau + navigation + panels à la demande."""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QApplication,
)
from PySide6.QtCore import Qt, QSize
from phibuilder.widgets import M3Button, M3Label, M3Frame
from phibuilder.widgets.button import ButtonVariant
from phibuilder.phi.scale import SpacingToken
from larccommon.design_system import ds
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from larccommon.widgets.topbar import TopBar
from larccommon.icons import icon as md3_icon

_SECTIONS = [
    ('accueil', 'Accueil', 'home'),
    ('temps', 'Le temps', 'schedule'),
    ('i18n', 'Langues', 'translate'),
    ('themes', 'Themes', 'tonality'),
    ('roles', 'Roles', 'person'),
    ('logs', 'Logs', 'description'),
    ('types', "Types d'evenements", 'event'),
    ('lieux', 'Lieux', 'location_on'),
]


class ConfigWindow(QWidget):
    def __init__(self, user: dict):
        super().__init__()
        self._user = user
        self._panels = {}
        self._current = None
        self._btns = {}

        phi = theme_manager.phi_theme
        c = phi.colors
        sp = phi.spacing.spacing

        self.setWindowTitle(f"LarcConfig — {user.get('first_name','')} {user.get('last_name','')}")
        self.setObjectName("root")
        # Minimum 1024×720 (Fibonacci : 1024 = 7·136+52+20 ; 720 = 5·136+32+8)
        self.setMinimumSize(ds.space_xxxl * 7 + ds.button_height + ds.space_md,
                            ds.space_xxxl * 5 + ds.space_lg + ds.space_xs)
        self.setStyleSheet(f"QWidget#root {{ background: {c.background}; }}")

        # Bandeau commun (profil, préférences, thèmes, date, réseau)
        self._topbar = TopBar()
        self._topbar.logout_requested.connect(QApplication.quit)
        self._topbar.theme_changed.connect(self._on_topbar_theme)
        self._topbar.update_profile()
        ds.theme_changed.connect(self._restyle_all)  # réactivité thème

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._topbar)

        outer = QHBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Sidebar
        side = M3Frame(theme=phi)
        self._side = side
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(ds.sidebar_width)
        side.setStyleSheet(f"background: {c.surface}; border-right: 1px solid {c.outline_variant};")
        sl = QVBoxLayout(side)
        sl.setContentsMargins(sp(SpacingToken.SM), sp(SpacingToken.MD),
                              sp(SpacingToken.SM), sp(SpacingToken.MD))
        sl.setSpacing(sp(SpacingToken.XS))

        self._title_lbl = M3Label("LarcConfig", theme=phi, style="headline_small")
        sl.addWidget(self._title_lbl)
        self._user_lbl = M3Label(f"{user.get('first_name','')} {user.get('last_name','')}",
                                 theme=phi, style="body_small")
        sl.addWidget(self._user_lbl)
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

        # Stack
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {c.background};")

        outer.addWidget(side)
        outer.addWidget(self._stack, 1)
        root.addLayout(outer, 1)

        self._switch('accueil')  # Écran d'entrée : Accueil

    def _style_buttons(self, section: str):
        """Couleurs des boutons de navigation — texte TOUJOURS visible (primary)."""
        c = theme_manager.phi_theme.colors
        icons = dict((k, ic) for k, _, ic in _SECTIONS)
        for k, btn in self._btns.items():
            bg = c.primary_container if k == section else 'transparent'
            btn.setIcon(md3_icon(icons.get(k, 'home'), color=c.on_surface,
                                 size=ds.icon_md))
            btn.setStyleSheet(
                f"M3Button {{ background: {bg}; color: {c.primary}; text-align: left; "
                f"padding-left: {ds.space_xs}px; border-radius: {ds.radius_xs}px; }}")

    @safe_slot("ConfigWindow._switch")
    def _switch(self, section: str, force: bool = False):
        if self._current == section and not force:
            return
        self._current = section
        self._style_buttons(section)
        is_new = section not in self._panels
        if is_new:
            panel = self._create(section)
            if panel:
                self._panels[section] = panel
                self._stack.addWidget(panel)
        if section in self._panels:
            panel = self._panels[section]
            self._stack.setCurrentWidget(panel)
            # Panneaux mis en cache (jamais reconstruits) : on rafraîchit
            # leurs données à chaque navigation vers eux, sinon un panneau
            # ouvert AVANT une modification ailleurs (ex. dates dans « Le
            # Temps ») reste figé sur les anciennes valeurs.
            if not is_new and hasattr(panel, 'reload'):
                panel.reload()

    @safe_slot("ConfigWindow.on_topbar_theme")
    def _on_topbar_theme(self, key: str):
        theme_manager.set_active(key)

    @safe_slot("ConfigWindow.restyle_all")
    def _restyle_all(self):
        """Réactivité thème (pattern LarcRH) : chrome inline + reconstruction
        du panneau courant (les pages sont stylées à la construction)."""
        c = theme_manager.phi_theme.colors
        self.setStyleSheet(f"QWidget#root {{ background: {c.background}; }}")
        self._stack.setStyleSheet(f"background: {c.background};")
        self._side.setStyleSheet(
            f"background: {c.surface}; border-right: 1px solid {c.outline_variant};")

        # Textes sidebar — visibles dans tous les thèmes (M3Label gèle la
        # couleur à la construction → on la re-pose avec la typographie)
        def _label_qss(lbl, style_name, color):
            s = getattr(theme_manager.phi_theme.typo, style_name)
            lbl.setStyleSheet(
                f"M3Label {{ font-family: '{s.family}'; font-size: {s.size}px; "
                f"font-weight: {s.weight}; letter-spacing: {s.letter_spacing}px; "
                f"color: {color}; }}")
        _label_qss(self._title_lbl, 'headline_small',
                   theme_manager.palette.text_strong)
        _label_qss(self._user_lbl, 'body_small',
                   theme_manager.palette.text_soft)
        self._style_buttons(self._current)

        key = self._current
        panel = self._panels.get(key)
        if panel is not None and hasattr(panel, '_restyle'):
            panel._restyle()  # panneau réactif : pas de reconstruction
        elif panel is not None:
            # chemin historique : destroy + recreate (panels sans _restyle)
            self._panels.pop(key)
            self._stack.removeWidget(panel)
            panel.deleteLater()
            self._switch(key, force=True)
        self._topbar.restyle()

    def _create(self, section: str):
        from LarcConfig.views.panel_accueil import AccueilPanel
        from LarcConfig.views.panel_temps import TempsPanel
        from LarcConfig.views.panel_i18n import I18nPanel
        from LarcConfig.views.panel_themes import ThemesPanel
        from LarcConfig.views.panel_roles import RolesPanel
        from LarcConfig.views.panel_logs import LogsPanel
        from LarcConfig.views.panel_types import TypesPanel
        from LarcConfig.views.panel_lieux import LieuxPanel
        return {
            'accueil': AccueilPanel,
            'temps': TempsPanel,
            'i18n': I18nPanel,
            'themes': ThemesPanel,
            'roles': RolesPanel,
            'logs': LogsPanel,
            'types': TypesPanel,
            'lieux': LieuxPanel,
        }[section](self._user)
