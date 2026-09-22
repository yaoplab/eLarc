"""Fenêtre principale LarcConfig — bandeau + navigation + panels à la demande."""
from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from larccommon.widgets.topbar import TopBar
from phibuilder.phi.scale import SpacingToken
from phibuilder.widgets import M3Button, M3Frame, M3Label, M3StackedWidget
from phibuilder.widgets.button import ButtonVariant
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

_SECTIONS = [
    ('accueil', 'Accueil', 'home'),
    ('temps', 'Le temps', 'schedule'),
    ('programmes', 'Programmes et langues', 'school'),
    ('classes', 'Classes', 'view_module'),
    ('affectation', 'Affectation élèves-classes', 'group'),
    ('matieres_classe', 'Matières par classe', 'subject'),
    ('types', "Types d'événements", 'event'),
    ('lieux', 'Lieux', 'location_on'),
    ('themes', 'Thèmes', 'tonality'),
    ('i18n', 'Traductions', 'translate'),
    ('roles', 'Rôles', 'person'),
    ('logs', 'Journal (logs)', 'description'),
]
# Sections dont l'écran n'existe pas encore : affichées grisées « bientôt ».
# « matieres_eleves » (inscription élève × matière) supprimé le 2026-09-22 :
# livré comme onglet « Élèves » de « matieres_classe » (panel_effectifs.py),
# jamais comme section séparée — l'entrée placeholder n'a plus lieu d'être.
_PLANNED = {'programmes', 'classes', 'affectation'}
_ICONS = {k: ic for k, _, ic in _SECTIONS}
_LABELS = {k: lb for k, lb, _ in _SECTIONS}

# Catégories du menu : (clé, titre, [sections]). Une catégorie à une seule
# section est un bouton direct ; sinon un clic déplie/replie ses sections.
_CATEGORIES = [
    ('accueil', 'Accueil', ['accueil']),
    ('temps', 'Le temps', ['temps']),
    ('ecole', 'École et effectifs', ['programmes', 'classes', 'affectation',
                                     'matieres_classe']),
    ('vie', 'Vie scolaire', ['types', 'lieux']),
    ('apparence', 'Apparence et langue', ['themes', 'i18n']),
    ('admin', 'Administration', ['roles', 'logs']),
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

        self._cat_btns = {}
        self._cat_boxes = {}
        for cat, title, keys in _CATEGORIES:
            if len(keys) == 1:
                self._add_nav_button(sl, keys[0], _LABELS[keys[0]], 0)
                continue
            head = self._nav_button(title)
            head.clicked.connect(lambda checked, k=cat: self._toggle_category(k))
            self._cat_btns[cat] = head
            sl.addWidget(head)
            box = QWidget()
            bl = QVBoxLayout(box)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(sp(SpacingToken.XS))
            for key in keys:
                self._add_nav_button(bl, key, _LABELS[key], ds.space_md)
            box.setVisible(False)
            self._cat_boxes[cat] = box
            sl.addWidget(box)

        sl.addStretch()

        # Stack
        self._stack = M3StackedWidget(theme=phi)
        self._stack.setStyleSheet(f"background: {c.background};")

        outer.addWidget(side)
        outer.addWidget(self._stack, 1)
        root.addLayout(outer, 1)

        self._switch('accueil')  # Écran d'entrée : Accueil

    def _nav_button(self, label: str) -> M3Button:
        btn = M3Button(label, theme=theme_manager.phi_theme, variant=ButtonVariant.TEXT)
        btn.setIconSize(QSize(ds.icon_md, ds.icon_md))
        btn.setFixedHeight(ds.field_height + ds.space_xs)
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    def _add_nav_button(self, layout, key: str, label: str, indent: int):
        btn = self._nav_button(label)
        btn.setProperty('indent', indent)
        if key in _PLANNED:
            btn.setEnabled(False)
            btn.setToolTip("Bientôt disponible")
        btn.clicked.connect(lambda checked, k=key: self._switch(k))
        self._btns[key] = btn
        layout.addWidget(btn)

    def _category_of(self, section: str):
        for cat, _t, keys in _CATEGORIES:
            if section in keys and len(keys) > 1:
                return cat
        return None

    @safe_slot("ConfigWindow._toggle_category")
    def _toggle_category(self, cat: str):
        """Déplie la catégorie cliquée et replie les autres."""
        opening = not self._cat_boxes[cat].isVisible()
        for k, box in self._cat_boxes.items():
            box.setVisible(opening and k == cat)
        self._style_buttons(self._current)

    def _style_buttons(self, section: str):
        """Couleurs des boutons de navigation — texte TOUJOURS visible (primary)."""
        c = theme_manager.phi_theme.colors
        active_cat = self._category_of(section)

        def _qss(bg, indent):
            return (f"M3Button {{ background: {bg}; color: {c.primary}; text-align: left; "
                    f"padding-left: {ds.space_xs + indent}px; border-radius: {ds.radius_xs}px; }} "
                    f"M3Button:disabled {{ color: {c.on_surface_variant}; }}")

        for k, btn in self._btns.items():
            bg = c.primary_container if k == section else 'transparent'
            btn.setIcon(md3_icon(_ICONS.get(k, 'home'), color=c.on_surface, size=ds.icon_md))
            if k in _PLANNED:
                btn.setText(f"{_LABELS[k]} (bientôt)")
            btn.setStyleSheet(_qss(bg, btn.property('indent') or 0))
        for cat, btn in self._cat_btns.items():
            opened = self._cat_boxes[cat].isVisible()
            btn.setIcon(md3_icon('expand_less' if opened else 'expand_more',
                                 color=c.on_surface, size=ds.icon_md))
            bg = c.surface_variant if cat == active_cat and not opened else 'transparent'
            btn.setStyleSheet(_qss(bg, 0))

    @safe_slot("ConfigWindow._switch")
    def _switch(self, section: str, force: bool = False):
        if self._current == section and not force:
            return
        self._current = section
        cat = self._category_of(section)
        if cat and not self._cat_boxes[cat].isVisible():
            for k, box in self._cat_boxes.items():
                box.setVisible(k == cat)
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
        from LarcConfig.views.panel_effectifs import EffectifsPanel
        from LarcConfig.views.panel_i18n import I18nPanel
        from LarcConfig.views.panel_lieux import LieuxPanel
        from LarcConfig.views.panel_logs import LogsPanel
        from LarcConfig.views.panel_roles import RolesPanel
        from LarcConfig.views.panel_temps import TempsPanel
        from LarcConfig.views.panel_themes import ThemesPanel
        from LarcConfig.views.panel_types import TypesPanel
        return {
            'accueil': AccueilPanel,
            'temps': TempsPanel,
            'i18n': I18nPanel,
            'themes': ThemesPanel,
            'roles': RolesPanel,
            'logs': LogsPanel,
            'types': TypesPanel,
            'lieux': LieuxPanel,
            'matieres_classe': EffectifsPanel,
        }[section](self._user)
