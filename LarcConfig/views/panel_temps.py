"""Panel Le temps — année scolaire, trimestres (3) et unités (6), FR/EN.

Structure (skill input-ergonomics) :
- HÉROS pleine largeur, couleur différente (primary_container) et gros
  caractères : année en cours + trimestre en cours + unité en cours
- SectionsFlow responsive (IE7, colonnes égales) : section « Année
  scolaire », section « Trimestres » (3 onglets), section « Unités »
  (6 onglets)
- IE5/IE6 : les composants n'ont pas de taille propre et sont plafonnés
  à ds.field_max_width — la section décide des colonnes
"""
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSpinBox, QVBoxLayout, QWidget,
)

from phibuilder.widgets import (
    M3Button, M3DateEdit, M3Label, M3ScrollArea, M3TabWidget, M3TextField,
)
from phibuilder.phi.scale import SpacingToken
from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from larccommon.widgets import SectionsFlow
from LarcConfig.common.db_access import (
    get_temps, save_annee, save_trimestre, save_unite,
)

_DATE_FMT = 'yyyy-MM-dd'


def _lbl(text, style="body_small"):
    return M3Label(text, theme=theme_manager.phi_theme, style=style)


def _field(layout, label_text, widget):
    """Label au-dessus du champ ; composant sans taille propre (IE5),
    plafonné à ds.field_max_width (IE6)."""
    layout.addWidget(_lbl(label_text))
    widget.setFixedHeight(ds.field_height)
    widget.setMaximumWidth(ds.field_max_width)
    widget.setStyleSheet(ds.flat_input_qss())
    layout.addWidget(widget)


def _date_edit(qdate):
    de = M3DateEdit(theme=theme_manager.phi_theme)
    de.setCalendarPopup(True)  # dates cliquables → calendrier
    de.setDisplayFormat(_DATE_FMT)
    de.setMinimumWidth(ds.field_height * 3)   # C11 : largeur min des dates
    de.setMaximumWidth(ds.field_max_width)    # IE6 : jamais pleine largeur
    if qdate is not None:
        de.setDate(QDate(qdate.year, qdate.month, qdate.day))
    return de


def _save_btn(slot):
    btn = M3Button(_("panel.temps.save"), theme=theme_manager.phi_theme)
    btn.setFixedHeight(ds.field_height + ds.space_xs)  # 40 — aligné champs
    btn.setIcon(md3_icon("save",
                         color=theme_manager.phi_theme.colors.on_primary,
                         size=ds.icon_sm))
    btn.setCursor(Qt.PointingHandCursor)
    btn.clicked.connect(slot)
    return btn


def _lang_col(parent_layout, title, label_field, start_field, end_field):
    """Colonne FR ou EN : label + début + fin (dates cliquables).
    addStretch final : sans lui, l'espace vertical de l'onglet est absorbé
    par les QLabel (politique Preferred) qui se gonflent et décalent tout."""
    col = QVBoxLayout()
    col.setSpacing(ds.space_xs)
    col.addWidget(_lbl(title, "label_medium"))
    _field(col, _("panel.temps.label"), label_field)
    _field(col, _("panel.temps.start"), start_field)
    _field(col, _("panel.temps.end"), end_field)
    col.addStretch(1)
    parent_layout.addLayout(col, 1)


class _SectionCard(QFrame):
    """Carte de section : titre (+ widget d'en-tête optionnel, ex. bouton
    Sauvegarder à hauteur du titre) + contenu — thème réactif."""

    def __init__(self, title: str, header_widget=None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(self)
        v.setContentsMargins(ds.space_md, ds.space_sm, ds.space_md, ds.space_md)
        v.setSpacing(ds.space_sm)
        head = QHBoxLayout()
        self._title_lbl = QLabel(title)
        head.addWidget(self._title_lbl)
        head.addStretch(1)
        if header_widget is not None:
            head.addWidget(header_widget)
        v.addLayout(head)
        self._content = QVBoxLayout()
        self._content.setSpacing(ds.space_sm)
        v.addLayout(self._content, 1)
        ds.theme_changed.connect(self._style)
        self._style()

    def content(self) -> QVBoxLayout:
        return self._content

    @safe_slot("_SectionCard.style")
    def _style(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        self.setStyleSheet(
            f"QFrame {{ background: {p.surface}; border: 1px solid "
            f"{p.outline_variant}; border-radius: {ds.radius_sm}px; }}")
        self._title_lbl.setStyleSheet(
            f"font-size: {s(ds.font_title)}px; font-weight: bold; "
            f"color: {p.text_strong}; border: none; background: transparent;")


class _FormTab(QWidget):
    """Onglet formulaire : colonnes FR/EN bornées (le bouton Sauvegarder
    vit dans l'en-tête de la carte de section, à hauteur du titre)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(ds.space_sm)

        cols = QHBoxLayout()
        cols.setSpacing(ds.space_md)
        self.w = {
            'label_fr': M3TextField(theme=theme_manager.phi_theme),
            'start_fr': _date_edit(None),
            'end_fr': _date_edit(None),
            'label_en': M3TextField(theme=theme_manager.phi_theme),
            'start_en': _date_edit(None),
            'end_en': _date_edit(None),
        }
        _lang_col(cols, 'FR', self.w['label_fr'],
                  self.w['start_fr'], self.w['end_fr'])
        _lang_col(cols, 'EN', self.w['label_en'],
                  self.w['start_en'], self.w['end_en'])
        l.addLayout(cols)
        l.addStretch(1)


class TempsPanel(M3ScrollArea):
    """Menu Le temps — héros (année/trimestre/unité en cours) + sections
    responsive : Année scolaire, Trimestres (3 onglets), Unités (6 onglets)."""

    def __init__(self, user: dict):
        super().__init__(theme=theme_manager.phi_theme)
        phi = theme_manager.phi_theme
        sp = phi.spacing.spacing

        self._tabs = {}  # key -> _FormTab

        container = QWidget()
        l = QVBoxLayout(container)
        l.setContentsMargins(sp(SpacingToken.LG), sp(SpacingToken.LG),
                             sp(SpacingToken.LG), sp(SpacingToken.LG))
        l.setSpacing(sp(SpacingToken.MD))
        l.addWidget(M3Label(_("panel.temps.title"), theme=phi,
                            style="headline_small"))

        # HÉROS — couleur différente (primary_container), gros caractères :
        # année en cours + trimestre en cours + unité en cours
        self._hero = QFrame()
        self._hero.setAttribute(Qt.WA_StyledBackground, True)
        hl = QHBoxLayout(self._hero)
        hl.setContentsMargins(ds.space_lg, ds.space_md,
                              ds.space_lg, ds.space_md)
        hl.setSpacing(ds.space_lg)
        self._hero_parts = [
            self._hero_col(hl, "school", _("panel.temps.current_year")),
            self._hero_col(hl, "schedule", _("panel.temps.current_term")),
            self._hero_col(hl, "timer", _("panel.temps.current_unit")),
        ]
        l.addWidget(self._hero)

        # Sections responsive (IE7) : Année | Trimestres (onglets) | Unités.
        # Le bouton Sauvegarder est dans l'en-tête de chaque carte, à la
        # hauteur du titre (il sauvegarde l'onglet actif pour les onglets).
        self._annee_card = _SectionCard(
            _("panel.temps.school_year"), header_widget=_save_btn(self._save_annee))
        self._build_annee_form(self._annee_card.content())

        self._trim_card = _SectionCard(
            _("panel.temps.trimesters"),
            header_widget=_save_btn(self._save_trim_current))
        self._trim_tabs = M3TabWidget(theme=phi)
        self._trim_card.content().addWidget(self._trim_tabs)

        self._unit_card = _SectionCard(
            _("panel.temps.units"),
            header_widget=_save_btn(self._save_unit_current))
        self._unit_tabs = M3TabWidget(theme=phi)
        self._unit_card.content().addWidget(self._unit_tabs)

        self._flow = SectionsFlow(
            [self._annee_card, self._trim_card, self._unit_card],
            min_width=ds.field_max_width - ds.space_md)
        l.addWidget(self._flow)

        # Onglets Trimestres 1..3 et Unités 1..6 (clés alignées sur les index)
        self._trim_keys = []
        for trim in (1, 2, 3):
            key = f"trim{trim}"
            self._trim_keys.append(key)
            self._build_form_tab(
                self._trim_tabs, key, f"{_('panel.temps.trimester')} {trim}")
        self._unit_keys = []
        for nr in range(1, 7):
            key = f"unit{nr}"
            self._unit_keys.append(key)
            self._build_form_tab(
                self._unit_tabs, key, f"{_('panel.temps.unit')} {nr}")

        self.setWidget(container)
        self.setWidgetResizable(True)
        ds.theme_changed.connect(self._style_hero)
        self._style_hero()
        self.reload()
        # Hauteurs égales des 3 cartes (après la première passe de layout)
        QTimer.singleShot(0, self._equalize_heights)

    # -- construction --------------------------------------------------
    @staticmethod
    def _hero_col(parent_layout, icon_name, title):
        """Colonne du héros : icône + titre, valeur en grand, détail."""
        col = QVBoxLayout()
        col.setSpacing(ds.space_xxs)
        head = QHBoxLayout()
        head.setSpacing(ds.space_sm)
        icon_lbl = QLabel()
        head.addWidget(icon_lbl)
        t = _lbl(title, "body_medium")
        head.addWidget(t)
        head.addStretch(1)
        col.addLayout(head)
        value = _lbl('—', "headline_medium")  # 28 px bold — l'essentiel
        col.addWidget(value)
        detail = _lbl('', "body_medium")
        col.addWidget(detail)
        parent_layout.addLayout(col, 1)
        return {'icon_lbl': icon_lbl, 'icon_name': icon_name,
                'title': t, 'value': value, 'detail': detail}

    @safe_slot("TempsPanel.style_hero")
    def _style_hero(self):
        p = theme_manager.palette
        self._hero.setStyleSheet(
            f"QFrame {{ background: {p.primary_container}; "
            f"border: 1px solid {p.outline_variant}; "
            f"border-radius: {ds.radius_md}px; }}")
        for part in self._hero_parts:
            part['icon_lbl'].setPixmap(
                md3_icon(part['icon_name'], color=p.text_strong,
                         size=ds.icon_md).pixmap(ds.icon_md, ds.icon_md))
            part['title'].set_color(p.text_strong)
            part['value'].set_color(p.text_strong)
            part['detail'].set_color(p.text_strong)

    def _build_annee_form(self, content: QVBoxLayout):
        row = QHBoxLayout()
        row.setSpacing(ds.space_md)
        col = QVBoxLayout()
        col.setSpacing(ds.space_xs)
        self._ay_label = M3TextField(theme=theme_manager.phi_theme)
        # largeur confortable pour « 2025-2026 » — la section décide (IE5)
        self._ay_label.setMinimumWidth(ds.field_height * 6)
        self._ay_start = _date_edit(None)
        self._ay_end = _date_edit(None)
        self._ay_term = QSpinBox()
        self._ay_unit = QSpinBox()
        self._ay_term.setRange(1, 3)
        self._ay_unit.setRange(1, 6)
        _field(col, _("panel.temps.label"), self._ay_label)
        _field(col, _("panel.temps.start"), self._ay_start)
        _field(col, _("panel.temps.end"), self._ay_end)
        col.addStretch(1)  # ancrage en haut (voir _lang_col)
        row.addLayout(col, 3)

        col2 = QVBoxLayout()
        col2.setSpacing(ds.space_xs)
        _field(col2, _("panel.temps.current_term_number"), self._ay_term)
        _field(col2, _("panel.temps.current_unit_number"), self._ay_unit)
        # valeurs 1..3 / 1..6 : bornées (IE6) — APRÈS _field (qui pose le
        # plafond générique) ; le reste de la largeur va au libellé année
        self._ay_term.setMaximumWidth(ds.field_height * 3)
        self._ay_unit.setMaximumWidth(ds.field_height * 3)
        col2.addStretch(1)
        row.addLayout(col2, 1)
        content.addLayout(row)

    def _build_form_tab(self, tab_widget, key, title):
        tab = _FormTab()
        self._tabs[key] = tab
        tab_widget.addTab(tab, title)

    def _equalize_heights(self):
        """Les 3 cartes de section à la même hauteur (demande utilisateur)."""
        cards = (self._annee_card, self._trim_card, self._unit_card)
        h = max(c.sizeHint().height() for c in cards)
        for c in cards:
            c.setMinimumHeight(h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._equalize_heights)

    # -- données -------------------------------------------------------
    @safe_slot("TempsPanel.reload")
    def reload(self):
        data = get_temps()
        if not data:
            return
        ay = data['annee']
        term_nr = ay.get('term') or 0
        unit_nr = ay.get('unit') or 0
        trim = next((t for t in data['trimestres']
                     if t.get('trim') == term_nr), None)
        unit = next((u for u in data['unites']
                     if u.get('unit_nr') == unit_nr), None)

        # Héros — l'essentiel en gros caractères
        self._hero_parts[0]['value'].setText(ay.get('label', '') or '—')
        self._hero_parts[0]['detail'].setText(
            f"{self._fmt(ay.get('start'))} → {self._fmt(ay.get('end'))}")
        self._hero_parts[1]['value'].setText(self._lang_label(trim) or '—')
        self._hero_parts[1]['detail'].setText(
            f"{self._fmt(trim.get('start_fr')) if trim else ''} → "
            f"{self._fmt(trim.get('end_fr')) if trim else ''}")
        self._hero_parts[2]['value'].setText(
            f"{unit_nr} — {self._lang_label(unit) or '—'}")
        self._hero_parts[2]['detail'].setText(
            f"{self._fmt(unit.get('start_fr')) if unit else ''} → "
            f"{self._fmt(unit.get('end_fr')) if unit else ''}")

        self._ay_label.setText(ay.get('label', ''))
        self._ay_start.setDate(self._qdate(ay.get('start')))
        self._ay_end.setDate(self._qdate(ay.get('end')))
        self._ay_term.setValue(term_nr)
        self._ay_unit.setValue(unit_nr)

        for t in data['trimestres']:
            self._fill(self._tabs.get(f"trim{t['trim']}"), t)
        for u in data['unites']:
            self._fill(self._tabs.get(f"unit{u['unit_nr']}"), u)

    @staticmethod
    def _fill(tab, row):
        if not tab:
            return
        w = tab.w
        w['label_fr'].setText(row.get('label_fr', '') or '')
        w['start_fr'].setDate(TempsPanel._qdate(row.get('start_fr')))
        w['end_fr'].setDate(TempsPanel._qdate(row.get('end_fr')))
        w['label_en'].setText(row.get('label_en', '') or '')
        w['start_en'].setDate(TempsPanel._qdate(row.get('start_en')))
        w['end_en'].setDate(TempsPanel._qdate(row.get('end_en')))

    @staticmethod
    def _lang_label(row):
        if not row:
            return None
        return row.get('label_fr') or row.get('label_en')

    @staticmethod
    def _qdate(value):
        if value is None:
            return QDate.currentDate()
        return QDate(value.year, value.month, value.day)

    @staticmethod
    def _fmt(value):
        return value.strftime('%d/%m/%Y') if value else ''

    @staticmethod
    def _d(de):
        return de.date().toPython() if de.date().isValid() else None

    # -- sauvegardes ---------------------------------------------------
    @safe_slot("TempsPanel.save_trim_current")
    def _save_trim_current(self):
        """Sauvegarde l'onglet Trimestre actif (bouton de la carte)."""
        idx = self._trim_tabs.currentIndex()
        if 0 <= idx < len(self._trim_keys):
            key = self._trim_keys[idx]
            self._save_trimestre(int(key.replace('trim', '')),
                                 self._tabs[key].w)

    @safe_slot("TempsPanel.save_unit_current")
    def _save_unit_current(self):
        """Sauvegarde l'onglet Unité actif (bouton de la carte)."""
        idx = self._unit_tabs.currentIndex()
        if 0 <= idx < len(self._unit_keys):
            key = self._unit_keys[idx]
            self._save_unite(int(key.replace('unit', '')),
                             self._tabs[key].w)

    @safe_slot("TempsPanel.save_annee")
    def _save_annee(self):
        if save_annee(self._ay_label.text().strip(),
                      self._d(self._ay_start), self._d(self._ay_end),
                      self._ay_term.value(), self._ay_unit.value()):
            self.reload()

    @safe_slot("TempsPanel.save_trimestre")
    def _save_trimestre(self, trim, w):
        if save_trimestre(trim,
                          w['label_fr'].text().strip(),
                          w['label_en'].text().strip(),
                          self._d(w['start_fr']), self._d(w['end_fr']),
                          self._d(w['start_en']), self._d(w['end_en'])):
            self.reload()

    @safe_slot("TempsPanel.save_unite")
    def _save_unite(self, nr, w):
        if save_unite(nr,
                      w['label_fr'].text().strip(),
                      w['label_en'].text().strip(),
                      self._d(w['start_fr']), self._d(w['end_fr']),
                      self._d(w['start_en']), self._d(w['end_en'])):
            self.reload()
