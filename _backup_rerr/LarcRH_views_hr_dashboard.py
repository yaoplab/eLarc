"""HRDashboard — Tableau de bord RH 100% responsive avec graphiques.

Pattern canonique : LarcCompta/views/dashboard.py (QScrollArea + KpiCard + chart widgets).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QScrollArea,
    QSizePolicy,
)

from larccommon.design_system import ds
from phibuilder.phi.scale import SpacingToken
from larccommon.icons import icon as md3_icon
from larccommon.theme import theme_manager
from LarcRH.views.sections_flow import SectionsFlow
from larccommon.safe_slot import safe_slot

from LarcRH.common.hr_database import HRDatabase
from LarcRH.views.hr_charts import HBarCell, VBarChart, RingChart, StatChange, AlertRow, _SEGMENT_COLORS


# ════════════════════════════════════════════════════════════════════
# KPI Card — pattern canonique LarcCompta _KpiCard
# ════════════════════════════════════════════════════════════════════

class _KpiCard(QFrame):
    """Carte KPI avec barre d'accent gauche + icône + valeur + label."""

    def __init__(self, label: str, accent_token: str, icon_name: str = "",
                 parent=None):
        super().__init__(parent)
        self._label_text = label
        self._accent_token = accent_token
        self._icon_name = icon_name
        self._value = "—"
        self._icon_label: QLabel | None = None
        self._value_label: QLabel | None = None
        self.setObjectName("kpi_card")
        self.setMinimumSize(ds.sp(130), ds.kpi_card_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(ds.sp(SpacingToken.XXXL) + ds.sp(SpacingToken.XXS) + ds.sp(SpacingToken.MD))
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._setup_ui()
        ds.theme_changed.connect(self._restyle)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_sm, ds.space_md, ds.space_sm)
        layout.setSpacing(ds.space_sm)

        bar = QWidget()
        bar.setObjectName("accent")
        bar.setFixedWidth(ds.space_xxs)
        layout.addWidget(bar)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(ds.sp(SpacingToken.XL) - ds.space_m3, ds.sp(SpacingToken.XL) - ds.space_m3)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setStyleSheet("border: none;")
        layout.addWidget(self._icon_label)

        col = QVBoxLayout()
        col.setSpacing(0)
        self._col = col
        self._value_label = QLabel(self._value)
        col.addWidget(self._value_label)
        lbl = QLabel(self._label_text)
        col.addWidget(lbl)
        layout.addLayout(col, 1)
        self._restyle()

    def set_value(self, value: str):
        self._value = value
        if self._value_label:
            self._value_label.setText(value)

    def set_names(self, names: list[str]):
        """Affiche les noms (petits) sous le libellé — ex. RH connectés."""
        if not hasattr(self, "_names_label"):
            self._names_label = QLabel("")
            self._names_label.setWordWrap(True)
            self._col.addWidget(self._names_label)
        self._names_label.setText(" · ".join(names))

    @safe_slot("_KpiCard._restyle")
    def _restyle(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        accent = getattr(p, self._accent_token, p.primary)
        self.setStyleSheet(f"""
            #kpi_card {{
                background: {p.surface}; border: 1px solid {p.outline_variant};
                border-radius: {ds.radius_sm}px;
            }}
            QWidget#accent {{ background: {accent}; border-radius: {ds.radius_xs // 2}px; }}
        """)
        if self._value_label:
            self._value_label.setStyleSheet(
                f"font-size: {s(22)}px; font-weight: bold; color: {accent}; border: none;")
        for lbl in self.findChildren(QLabel):
            if lbl not in (self._value_label, self._icon_label):
                lbl.setStyleSheet(
                    f"font-size: {s(10)}px; color: {p.text_soft}; border: none;")
        if self._icon_label and self._icon_name:
            self._icon_label.setPixmap(
                md3_icon(self._icon_name, color=accent, size=22).pixmap(22, 22))


# ════════════════════════════════════════════════════════════════════
# SectionCard — conteneur avec titre
# ════════════════════════════════════════════════════════════════════

class _SectionCard(QFrame):
    """Carte conteneur avec titre + contenu."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("section_card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        ds.theme_changed.connect(self._restyle)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(ds.space_md, ds.space_sm, ds.space_md, ds.space_md)
        self._layout.setSpacing(ds.space_sm)

        self._title_label = QLabel(title)
        self._layout.addWidget(self._title_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("sep")
        self._layout.addWidget(sep)

        self._content_layout = QVBoxLayout()
        self._content_layout.setSpacing(ds.space_xxs)
        self._layout.addLayout(self._content_layout, 1)

        self._restyle()

    def content_layout(self):
        return self._content_layout

    @safe_slot("_SectionCard._restyle")
    def _restyle(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        self.setStyleSheet(f"""
            #section_card {{
                background: {p.surface}; border: 1px solid {p.outline_variant};
                border-radius: {ds.radius_sm}px;
            }}
            QFrame#sep {{ color: {p.outline_variant}; border: none; max-height: 1px; }}
        """)
        self._title_label.setStyleSheet(
            f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong}; border: none;")


# ════════════════════════════════════════════════════════════════════
# HRDashboard
# ════════════════════════════════════════════════════════════════════

class HRDashboard(QScrollArea):
    """Tableau de bord RH 100% responsive."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setObjectName("hr_dashboard")

        self._container = QWidget()
        self._container.setObjectName("dashboard_container")
        self._container.installEventFilter(self)
        self.setWidget(self._container)

        self._root_layout = QVBoxLayout(self._container)
        self._root_layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        self._root_layout.setSpacing(ds.space_md)

        ds.theme_changed.connect(self._restyle)
        # J8 : le contenu (barres, anneau) est rebâti par refresh() —
        # connecter refresh au thème (pas depuis _restyle : refresh
        # appelle déjà _restyle -> boucle infinie sinon).
        ds.theme_changed.connect(self.refresh)
        self._setup_ui()

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        return (f"#hr_dashboard {{ background: {p.background}; border: none; }}"
                f"#dashboard_container {{ background: {p.background}; }}")

    @safe_slot("HRDashboard._restyle")
    def _restyle(self):
        try:
            self.setStyleSheet(self._STYLE)
            p = theme_manager.palette
            s = theme_manager.font_size
            if hasattr(self, "_title_label"):
                self._title_label.setStyleSheet(
                    f"font-size: {s(20)}px; font-weight: bold; "
                    f"color: {p.text_strong}; border: none;")
        except RuntimeError:
            pass

    def eventFilter(self, obj, event):
        if obj is self._container and event.type() == QEvent.Resize:
            self._relayout_kpis()
        return super().eventFilter(obj, event)

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size

        # ── Titre ──
        self._title_label = QLabel("Tableau de bord RH")
        self._title_label.setObjectName("dashboard_title")
        self._root_layout.addWidget(self._title_label)

        # ── Section 1 : Indicateurs clés (bande pleine largeur) ──
        kpi_section = _SectionCard("Indicateurs clés")
        self._kpi_grid = QGridLayout()
        self._kpi_grid.setSpacing(ds.space_sm)
        kpi_section.content_layout().addLayout(self._kpi_grid)
        self._root_layout.addWidget(kpi_section)

        self._kpi_cards: dict[str, _KpiCard] = {
            "effectif": _KpiCard("Effectif actif", "primary", "group"),
            "contrats": _KpiCard("Contrats actifs", "success", "contract"),
            "absents": _KpiCard("Absents du jour", "error", "event"),
            "conges": _KpiCard("Congés en attente", "secondary", "schedule"),
            "expirant": _KpiCard("Contrats < 30 j", "tertiary", "warning"),
            "online": _KpiCard("RH connectés", "primary", "person"),
        }
        # Placement initial
        self._relayout_kpis()

        # ── Sections responsive (SectionsFlow IE7) : côte à côte sur écran
        # large, empilées sur écran étroit — largeurs égales par ligne ──
        self._campus_section = _SectionCard("Répartition par campus — effectif présent")
        self._campus_chart = VBarChart()
        self._campus_section.content_layout().addWidget(self._campus_chart)

        self._contract_section = _SectionCard("Contrats par type")
        self._contract_ring = RingChart("contrats")
        self._contract_section.content_layout().addWidget(self._contract_ring)

        abs_card = _SectionCard("Absentéisme 30 j")
        self._absence_stat = StatChange("Taux d'absentéisme 30j", "—", 0.0)
        abs_card.content_layout().addWidget(self._absence_stat)

        tsk_card = _SectionCard("Tâches en retard")
        self._tasks_alert = AlertRow("error", "Tâches en retard", 0)
        tsk_card.content_layout().addWidget(self._tasks_alert)

        self._completeness_section = _SectionCard("Complétude des dossiers")
        self._completeness_pct = _KpiCard("Dossiers complets", "success", "check_circle")
        self._completeness_id = _KpiCard("Pièces ID expirées", "error", "warning")
        self._completeness_trial = _KpiCard("Périodes d'essai", "tertiary", "timeline")
        self._completeness_missing = _KpiCard("Dossiers incomplets", "error", "error")

        cgrid = QGridLayout()
        cgrid.setSpacing(ds.space_sm)
        cgrid.addWidget(self._completeness_pct, 0, 0)
        cgrid.addWidget(self._completeness_missing, 0, 1)
        cgrid.addWidget(self._completeness_id, 1, 0)
        cgrid.addWidget(self._completeness_trial, 1, 1)
        self._completeness_section.content_layout().addLayout(cgrid)

        self._missing_bars_layout = QVBoxLayout()
        self._missing_bars_layout.setSpacing(ds.space_xxs)
        self._completeness_section.content_layout().addLayout(self._missing_bars_layout)

        self._root_layout.addWidget(SectionsFlow(
            [self._campus_section, self._contract_section,
             abs_card, tsk_card, self._completeness_section],
            min_width=ds.sidebar_width + ds.golden_width(ds.sidebar_width)))

        self._root_layout.addStretch(1)
        self._restyle()
        self.refresh()

    def _relayout_kpis(self):
        """Recalcule la grille KPI selon la largeur disponible."""
        # Retirer tous les widgets sans les supprimer
        for i in range(self._kpi_grid.count() - 1, -1, -1):
            item = self._kpi_grid.itemAt(i)
            if item and item.widget():
                self._kpi_grid.removeWidget(item.widget())

        w = self._container.width() - ds.space_md * 2
        if w < 100:
            w = 800  # fallback avant premier affichage
        min_card_w = ds.sp(SpacingToken.XXXL) - ds.sp(SpacingToken.SM) + ds.space_sm
        cols = max(1, min(5, w // min_card_w))

        for i, (key, card) in enumerate(self._kpi_cards.items()):
            row, col = divmod(i, cols)
            self._kpi_grid.addWidget(card, row, col)

    # ── Refresh ──

    def refresh(self):
        """Recharge toutes les données."""
        kpis = HRDatabase.get_dashboard_kpis()

        def _v(key, default="—"):
            val = kpis.get(key, 0) if kpis else 0
            return "—" if val == -1 else str(val)

        self._kpi_cards["effectif"].set_value(_v("total_active"))
        self._kpi_cards["contrats"].set_value(_v("active_contracts"))
        self._kpi_cards["absents"].set_value(_v("absent_today"))
        self._kpi_cards["conges"].set_value(_v("pending_leave"))
        self._kpi_cards["expirant"].set_value(_v("expiring_contracts"))
        online = HRDatabase.get_online_sessions()
        self._kpi_cards["online"].set_value(str(len(online)))
        self._kpi_cards["online"].set_names([s["full_name"] for s in online])

        # Campus
        self._refresh_campus()

        # Contrats
        self._refresh_contracts()

        # Absentéisme
        absence = HRDatabase.get_absence_rate_30d()
        if absence:
            rate = absence.get("rate", 0)
            delta = absence.get("delta", 0)
            events = absence.get("total_events", 0)
            days = absence.get("days_with_absence", 0)
            self._absence_stat.set_data(
                f"{rate}%  ·  {events} événements",
                f"{days} jours/30",
                delta)

        # Tâches en retard
        overdue = HRDatabase.get_overdue_tasks()
        if overdue > 0:
            self._tasks_alert.set_data("error",
                f"{overdue} tâche(s) en retard — échéance dépassée", overdue)
        else:
            self._tasks_alert.set_data("check_circle",
                "Aucune tâche en retard", 0)

        # Complétude
        completeness = HRDatabase.get_completeness_stats()
        self._completeness_pct.set_value(f"{completeness['pct']}%")
        self._completeness_missing.set_value(str(completeness['incomplete']))
        self._completeness_id.set_value(str(HRDatabase.get_expiring_id_docs()))
        self._completeness_trial.set_value(str(HRDatabase.get_trial_periods_ending()))

        # Items de vérification non encore validés — alignés sur les
        # checkboxes de la carte « Vérifié et Validé » (même source)
        for i in range(self._missing_bars_layout.count() - 1, -1, -1):
            w = self._missing_bars_layout.itemAt(i).widget()
            if w:
                self._missing_bars_layout.removeWidget(w)
                w.deleteLater()
        total, missing = HRDatabase.get_dossier_check_stats()
        for m in missing:
            bar = HBarCell(m['label'], m['missing'], total, theme_manager.palette.error)
            self._missing_bars_layout.addWidget(bar)

        # NB : plus de barres « documents manquants » séparées — les
        # documents (CV, Contrat signé, Diplôme) font partie des items de
        # vérification ci-dessus (cohérence : tout cocher + document absent
        # = dossier incomplet, comme dans la fiche).

        self._relayout_kpis()
        self._restyle()

    def _refresh_campus(self):
        """Histogramme vertical de l'effectif présent.

        Par campus quand les campus sont renseignés (fk_campus_id) ;
        sinon fallback par catégorie (plages d'IDs de la sidebar) —
        la donnée campus est vide en base tant que non assignée.
        """
        campuses = HRDatabase.get_headcount_by_campus()
        if campuses:
            self._campus_chart.set_data([
                {"label": c["label"], "value": c["count"], "color": c.get("color", "")}
                for c in campuses
            ])
            return
        cats = HRDatabase.get_headcount_by_category()
        p = theme_manager.palette
        cat_colors = [p.primary, p.secondary, p.tertiary, p.success]
        self._campus_chart.set_data([
            {"label": c["label"], "value": c["count"], "color": cat_colors[i % len(cat_colors)]}
            for i, c in enumerate(cats)
        ])

    def _refresh_contracts(self):
        contracts = HRDatabase.get_contracts_by_type()
        if not contracts:
            self._contract_ring.set_segments([], "")
            return

        total_c = sum(ct["count"] for ct in contracts)
        segments = []
        for i, ct in enumerate(contracts):
            color = _SEGMENT_COLORS[i % len(_SEGMENT_COLORS)]
            segments.append({
                "label": ct.get("type", "?"),
                "value": ct["count"],
                "color": color,
            })
        self._contract_ring.set_segments(segments, f"{total_c} contrats")

    def showEvent(self, event):
        super().showEvent(event)
        self._relayout_kpis()
