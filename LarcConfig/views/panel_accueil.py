"""Panel Accueil — dashboard LarcConfig (skill dashboard-pattern).

Structure : rangée « Aujourd'hui » (date longue localisée), frise année
scolaire, 3 KPIs (Année / Trimestre / Unité), graphiques (donut par
programme, barres horizontales par classe) et tableau détail par classe.

100 % tokens ds.*, couleurs via rôles palette résolus au paint (réactif
aux thèmes), widgets charts partagés larccommon.widgets.
"""
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from phibuilder.widgets import M3Label, M3ScrollArea
from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.l10n import _
from larccommon.logger import log_error
from larccommon.safe_slot import safe_slot
from larccommon.session import session
from larccommon.theme import PROGRAM_STYLES, theme_manager
from larccommon.widgets import HBarCell, KpiCard, RingChart, TimelineWidget
from LarcConfig.common.db_access import get_stats, get_temps

_DATE_FMT = '%d/%m/%Y'

_WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday',
             'saturday', 'sunday']
_MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july',
           'august', 'september', 'october', 'november', 'december']

_MAX_PROGRAMS = 4  # PEI, MYP, DPFr, DPEn — le Primaire (PP/PYP) est exclu


def _fmt_date(value):
    return value.strftime(_DATE_FMT) if value else ''


def _fmt_month_year(value):
    """« 09/2025 » — dates KPI compactes (le détail long débordait)."""
    return value.strftime('%m/%Y') if value else ''


def _fmt_long_date(d):
    """Date longue localisée via clés i18n (pas de setlocale, fragile sous
    Windows) — ex. « Samedi 22 août 2026 » / « Saturday 22 August 2026 »."""
    wd = _(f"date.{_WEEKDAYS[d.weekday()]}")
    mo = _(f"date.{_MONTHS[d.month - 1]}")
    return f"{wd.capitalize()} {d.day} {mo} {d.year}"


def _program_role(sigle):
    """Rôle palette de la série du programme (PROGRAM_STYLES, ordre stable)."""
    roles = PROGRAM_STYLES.get(sigle or '',
                               ("primary", "primary_container", "on_primary"))
    return roles[0]


class _ChartCard(QFrame):
    """Carte conteneur : titre + contenu (pattern _SectionCard LarcRH)."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("chart_card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        ds.theme_changed.connect(self._restyle)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(ds.space_md, ds.space_sm,
                                        ds.space_md, ds.space_md)
        self._layout.setSpacing(ds.space_sm)

        self._title_label = QLabel(title)
        self._layout.addWidget(self._title_label)

        self._content_layout = QVBoxLayout()
        self._content_layout.setSpacing(ds.space_sm)
        self._layout.addLayout(self._content_layout, 1)

        self._restyle()

    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    @safe_slot("_ChartCard.restyle")
    def _restyle(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        self.setStyleSheet(
            f"QFrame#chart_card {{ background: {p.surface}; "
            f"border: 1px solid {p.outline_variant}; "
            f"border-radius: {ds.radius_sm}px; }}")
        self._title_label.setStyleSheet(
            f"font-size: {s(ds.font_body)}px; font-weight: bold; "
            f"color: {p.text_strong}; border: none; background: transparent;")


class _LegendRow(QWidget):
    """Légende des programmes (swatch + nom). Les slots sont créés à la
    construction (C8) — set_programs ne fait que peupler/afficher."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(ds.space_sm)
        self._frames = []
        self._labels = []
        for _i in range(_MAX_PROGRAMS):
            frame = QFrame()
            frame.setFixedSize(ds.space_sm, ds.space_sm)
            lbl = M3Label('', theme=theme_manager.phi_theme, style="body_small")
            frame.hide()
            lbl.hide()
            self._frames.append(frame)
            self._labels.append(lbl)
            self._layout.addWidget(frame)
            self._layout.addWidget(lbl)
        self._layout.addStretch()
        self._roles = [None] * _MAX_PROGRAMS
        ds.theme_changed.connect(self._restyle)
        self._restyle()

    def set_programs(self, programs):
        """programs = [(nom, rôle_palette), ...]"""
        for i, (name, role) in enumerate(programs[:_MAX_PROGRAMS]):
            self._roles[i] = role
            self._labels[i].setText(name)
            self._frames[i].show()
            self._labels[i].show()
        for i in range(len(programs), _MAX_PROGRAMS):
            self._roles[i] = None
            self._frames[i].hide()
            self._labels[i].hide()
        self._restyle()

    @safe_slot("_LegendRow.restyle")
    def _restyle(self):
        p = theme_manager.palette
        for frame, role, lbl in zip(self._frames, self._roles, self._labels):
            frame.setStyleSheet(
                f"background: {getattr(p, role, p.primary) if role else 'transparent'}; "
                f"border: none;")
            if role:
                lbl.set_color(p.text_soft)


class AccueilPanel(M3ScrollArea):
    """Écran d'entrée LarcConfig — dashboard lisible de loin."""

    def __init__(self, user: dict):
        super().__init__(theme=theme_manager.phi_theme)
        self._user = user

        container = QWidget()
        container.setObjectName("accueil_container")
        l = QVBoxLayout(container)
        l.setContentsMargins(ds.space_lg, ds.space_lg, ds.space_lg, ds.space_lg)
        l.setSpacing(ds.space_md)

        self._setup_ui(l)

        self.setWidget(container)
        self.setWidgetResizable(True)
        ds.theme_changed.connect(self._restyle)
        self._restyle()
        self.reload()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self, l: QVBoxLayout):
        # Titre
        self._title_lbl = M3Label(_("panel.accueil.title"),
                                  theme=theme_manager.phi_theme,
                                  style="headline_small")
        l.addWidget(self._title_lbl)

        # Rangée « Aujourd'hui » : icône + libellé + date longue
        today_row = QHBoxLayout()
        today_row.setSpacing(ds.space_sm)
        self._today_icon = QLabel()
        today_row.addWidget(self._today_icon)
        self._today_lbl = M3Label(_("panel.accueil.today"),
                                  theme=theme_manager.phi_theme,
                                  style="body_medium")
        today_row.addWidget(self._today_lbl)
        self._date_lbl = M3Label('', theme=theme_manager.phi_theme,
                                 style="headline_small")
        today_row.addWidget(self._date_lbl)
        today_row.addStretch()
        l.addLayout(today_row)

        # État vide global (échec chargement année scolaire) — Q2 inline
        empty_data = QHBoxLayout()
        empty_data.setSpacing(ds.space_sm)
        self._empty_data_icon = QLabel()
        empty_data.addWidget(self._empty_data_icon)
        self._empty_data_lbl = M3Label(_("panel.accueil.empty_data"),
                                       theme=theme_manager.phi_theme,
                                       style="body_small")
        empty_data.addWidget(self._empty_data_lbl)
        empty_data.addStretch()
        self._empty_data_w = QWidget()
        self._empty_data_w.setLayout(empty_data)
        self._empty_data_w.hide()
        l.addWidget(self._empty_data_w)

        # Avertissement dérive : aujourd'hui hors de la plage du trimestre/
        # unité configuré manuellement — n'écrase jamais le trimestre actif
        # (règle CLAUDE.md : défini par current_term_number, pas les dates),
        # signale juste l'incohérence pour qu'elle ne passe plus inaperçue.
        drift_row = QHBoxLayout()
        drift_row.setSpacing(ds.space_sm)
        self._drift_icon = QLabel()
        drift_row.addWidget(self._drift_icon)
        self._drift_lbl = M3Label(_("panel.accueil.date_drift"),
                                  theme=theme_manager.phi_theme,
                                  style="body_small")
        drift_row.addWidget(self._drift_lbl)
        drift_row.addStretch()
        self._drift_w = QWidget()
        self._drift_w.setLayout(drift_row)
        self._drift_w.hide()
        l.addWidget(self._drift_w)

        # Frise année scolaire
        self._timeline_card = _ChartCard(_("panel.accueil.timeline"))
        self._timeline = TimelineWidget()
        self._timeline_card.content_layout().addWidget(self._timeline)
        l.addWidget(self._timeline_card)

        # KPIs héros : Année / Trimestre / Unité
        self._kpi_w = QWidget()
        kpi_row = QHBoxLayout(self._kpi_w)
        kpi_row.setContentsMargins(0, 0, 0, 0)
        kpi_row.setSpacing(ds.space_md)
        self._kv_year = KpiCard(_("panel.accueil.year"), "school", "primary")
        self._kv_term = KpiCard(_("panel.accueil.term"), "schedule", "active")
        self._kv_unit = KpiCard(_("panel.accueil.unit"), "timer", "success")
        for card in (self._kv_year, self._kv_term, self._kv_unit):
            kpi_row.addWidget(card, 1)
        l.addWidget(self._kpi_w)

        # Graphiques : donut + barres par classe — colonnes de même largeur
        # que la rangée KPI au-dessus (alignement vertical des sections)
        self._charts_w = QWidget()
        charts_row = QHBoxLayout(self._charts_w)
        charts_row.setContentsMargins(0, 0, 0, 0)
        charts_row.setSpacing(ds.space_md)
        self._donut_card = _ChartCard(_("panel.accueil.stats_donut"))
        self._ring = RingChart()
        self._donut_card.content_layout().addWidget(self._ring)
        charts_row.addWidget(self._donut_card, 1)
        self._eleves_card = _ChartCard(_("panel.accueil.stats_bar_eleves"))
        self._legend_eleves = _LegendRow()
        self._eleves_card.content_layout().addWidget(self._legend_eleves)
        self._bar_eleves = HBarCell()
        self._eleves_card.content_layout().addWidget(self._bar_eleves)
        charts_row.addWidget(self._eleves_card, 1)
        self._matieres_card = _ChartCard(_("panel.accueil.stats_bar_matieres"))
        self._legend_matieres = _LegendRow()
        self._matieres_card.content_layout().addWidget(self._legend_matieres)
        self._bar_matieres = HBarCell()
        self._matieres_card.content_layout().addWidget(self._bar_matieres)
        charts_row.addWidget(self._matieres_card, 1)
        l.addWidget(self._charts_w)

        # État vide des statistiques (Q2 inline)
        empty_stats = QHBoxLayout()
        empty_stats.setSpacing(ds.space_sm)
        self._empty_stats_icon = QLabel()
        empty_stats.addWidget(self._empty_stats_icon)
        self._empty_stats_lbl = M3Label(_("panel.accueil.empty_stats"),
                                        theme=theme_manager.phi_theme,
                                        style="body_small")
        empty_stats.addWidget(self._empty_stats_lbl)
        empty_stats.addStretch()
        self._empty_stats_w = QWidget()
        self._empty_stats_w.setLayout(empty_stats)
        self._empty_stats_w.hide()
        l.addWidget(self._empty_stats_w)

        l.addStretch()

    # -------------------------------------------------------------- données
    @safe_slot("AccueilPanel.reload")
    def reload(self):
        """Populate pur : aucun widget créé ici (C8)."""
        self._lang = 'en' if getattr(session, 'fk_language', 2) == 1 else 'fr'
        # within_year : ignore les gabarits pré-créés de l'année suivante
        # (ex. « T3 2027 ») — la frise doit rester dans l'année affichée
        data = get_temps(within_year=True)
        if not data:
            self._show_empty_data()
            return
        ay = data['annee']
        if ay.get('start') and ay.get('end') and ay['start'] >= ay['end']:
            log_error(
                f"panel_accueil: dates d'année scolaire invalides "
                f"({ay.get('start')} >= {ay.get('end')}) — voir panel Le Temps")
            self._show_empty_data()
            return
        term_nr = ay.get('term') or 0
        unit_nr = ay.get('unit') or 0
        trim = next((t for t in data['trimestres']
                     if t.get('trim') == term_nr), None)
        unit = next((u for u in data['unites']
                     if u.get('unit_nr') == unit_nr), None)

        self._empty_data_w.hide()
        self._timeline_card.show()
        self._kpi_w.show()
        self._charts_w.show()

        today = date.today()
        self._date_lbl.setText(_fmt_long_date(today))

        term_start = trim.get('start_fr') or trim.get('start_en') if trim else None
        term_end = trim.get('end_fr') or trim.get('end_en') if trim else None
        unit_start = unit.get('start_fr') or unit.get('start_en') if unit else None
        unit_end = unit.get('end_fr') or unit.get('end_en') if unit else None
        drift = bool(
            (term_start and term_end and not (term_start <= today <= term_end))
            or (unit_start and unit_end and not (unit_start <= today <= unit_end)))
        self._drift_w.setVisible(drift)

        events = [
            (ay.get('start'), _("panel.accueil.year_start"), 'year_start'),
            (today, _("panel.accueil.today_short"), 'today'),
            (ay.get('end'), _("panel.accueil.year_end"), 'year_end'),
        ]

        def _resolve(row, nr_key):
            sfx = '_en' if self._lang == 'en' else '_fr'
            return {'nr': row[nr_key], 'label': row.get(f'label{sfx}') or '',
                    'start': row.get(f'start{sfx}') or row.get('start_fr')
                             or row.get('start_en'),
                    'end': row.get(f'end{sfx}') or row.get('end_fr')
                           or row.get('end_en')}

        unites_r = [_resolve(u, 'unit_nr') for u in data['unites']]
        trimestres_r = [_resolve(t, 'trim') for t in data['trimestres']]

        self._timeline.set_data(
            ay.get('start'), ay.get('end'),
            [e for e in events if e and e[0]],
            unites=unites_r, trimestres=trimestres_r,
            current_unit_nr=unit_nr, current_trim_nr=term_nr)

        def label_of(row, fr_key, en_key):
            return (row.get(en_key) if self._lang == 'en'
                    else row.get(fr_key)) if row else ''

        self._kv_year.set_value(ay.get('label', ''))
        self._kv_year.set_detail(
            f"{_fmt_month_year(ay.get('start'))} → "
            f"{_fmt_month_year(ay.get('end'))}")
        self._kv_term.set_value(label_of(trim, 'label_fr', 'label_en') or '—')
        self._kv_term.set_detail(
            f"{_fmt_month_year(label_of(trim, 'start_fr', 'start_en'))} → "
            f"{_fmt_month_year(label_of(trim, 'end_fr', 'end_en'))}")
        self._kv_unit.set_value(
            label_of(unit, 'label_fr', 'label_en') or str(unit_nr))
        self._kv_unit.set_detail(
            f"{_fmt_month_year(label_of(unit, 'start_fr', 'start_en'))} → "
            f"{_fmt_month_year(label_of(unit, 'end_fr', 'end_en'))}")

        # Graphiques — Collège & Lycée uniquement (filtre dans get_stats)
        stats = get_stats()
        if stats is None:
            log_error("panel_accueil: get_stats a échoué")
            stats = []
        if not stats:
            self._show_empty_stats()
            return
        self._empty_stats_w.hide()

        programs = [(pr['name'], _program_role(pr['sigle'])) for pr in stats]
        self._legend_eleves.set_programs(programs)
        self._legend_matieres.set_programs(programs)

        self._ring.set_segments(
            [(pr['name'], pr['total_eleves'], _program_role(pr['sigle']))
             for pr in stats])
        self._bar_eleves.set_items(self._class_rows(stats, 'eleves'))
        self._bar_matieres.set_items(self._class_rows(stats, 'matieres'))

    # ---------------------------------------------------------------- états
    def _show_empty_data(self):
        """Échec de chargement de l'année scolaire — état vide inline (Q2)."""
        log_error("panel_accueil: get_temps a échoué")
        self._date_lbl.setText('')
        self._empty_data_w.show()
        for w in (self._timeline_card, self._kpi_w, self._charts_w):
            w.hide()

    def _show_empty_stats(self):
        self._empty_stats_w.show()
        self._ring.set_segments([])
        self._bar_eleves.set_items([])
        self._bar_matieres.set_items([])
        self._legend_eleves.set_programs([])
        self._legend_matieres.set_programs([])

    @staticmethod
    def _class_rows(stats, key):
        """Classes regroupées PAR programme (PEI, MYP, DPFr, DPEn — ordre
        de get_stats), triées par valeur dans chaque groupe, séparées par
        un gap. Couleur = rôle du programme."""
        rows = []
        for pr in stats:
            items = sorted(((c['label'], c[key]) for c in pr['classes']),
                           key=lambda r: r[1], reverse=True)
            if not items:
                continue
            if rows:
                rows.append(None)  # séparateur de groupe
            rows += [(label, value, _program_role(pr['sigle']))
                     for label, value in items]
        return rows

    # ---------------------------------------------------------------- thème
    @safe_slot("AccueilPanel.restyle")
    def _restyle(self):
        p = theme_manager.palette
        # Fond du panneau (viewport + conteneur) — pattern SidebarWidget
        self.viewport().setStyleSheet(f"background: {p.background};")
        self.setStyleSheet(
            f"QWidget#accueil_container {{ background: {p.background}; }}")
        self._title_lbl.set_color(p.text_strong)
        self._today_lbl.set_color(p.text_soft)
        self._date_lbl.set_color(p.text_strong)
        self._empty_data_lbl.set_color(p.text_soft)
        self._empty_stats_lbl.set_color(p.text_soft)
        self._today_icon.setPixmap(
            md3_icon("calendar_month", color=p.primary, size=ds.icon_md)
            .pixmap(ds.icon_md, ds.icon_md))
        self._empty_data_icon.setPixmap(
            md3_icon("info", color=p.text_soft, size=ds.icon_md)
            .pixmap(ds.icon_md, ds.icon_md))
        self._empty_stats_icon.setPixmap(
            md3_icon("info", color=p.text_soft, size=ds.icon_md)
            .pixmap(ds.icon_md, ds.icon_md))
        self._drift_lbl.set_color(p.error)
        self._drift_icon.setPixmap(
            md3_icon("warning", color=p.error, size=ds.icon_md)
            .pixmap(ds.icon_md, ds.icon_md))
        # _ChartCard / KpiCard / _LegendRow s'auto-restylent (ds.theme_changed)
