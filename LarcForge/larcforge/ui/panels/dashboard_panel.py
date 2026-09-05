"""Panneau Accueil : KPIs, alertes, derniers runs, modules modifiés.

Données via status.render_json (un seul appel, une connexion courte).
DB down → carte « Réessayer » (reload).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from larccommon.widgets.kpi import KpiCard
from phibuilder.widgets import M3Card, M3Label, M3ScrollArea

from ... import database as pg
from ... import status as status_mod
from ...taxonomy import all_categories, category_info
from .common import (
    BodyLabel, DbUnavailableCard, SectionTitle, TypeBadge,
    restyle_card, restyle_label,
)

_MAX_ALERTS = 6
_MAX_MODS = 10


def _fmt_dt(value) -> str:
    if not value:
        return ""
    try:
        return value.strftime("%d/%m %H:%M")
    except AttributeError:
        return str(value)[:16]


class DashboardPanel(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self._ctx = ctx
        self._data: dict | None = None
        self._labels: list = []
        self._build_ui()

    def _build_ui(self):
        phi = theme_manager.phi_theme
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ds.space_lg, ds.space_lg, ds.space_lg, ds.space_lg)
        lay.setSpacing(ds.space_sm)
        self._title = SectionTitle("Accueil")
        lay.addWidget(self._title)

        scroll = M3ScrollArea(theme=phi)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(M3ScrollArea.NoFrame)
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(ds.space_xs, ds.space_xs, ds.space_xs, ds.space_xs)
        cl.setSpacing(ds.space_sm)

        # KPIs
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(ds.space_sm)
        self._kpis = {
            "open": KpiCard("Ouvertes", "error", "error"),
            "regressed": KpiCard("Régressions", "warning", "error"),
            "resolved": KpiCard("Résolues", "check_circle", "success"),
            "total": KpiCard("Total du registre", "dashboard", "primary"),
        }
        for kpi in self._kpis.values():
            kpi_row.addWidget(kpi, 1)
        cl.addLayout(kpi_row)

        # Par type d'erreur (cluster coloré — anticipation des régressions)
        self._types_card = M3Card(theme=phi, variant=ds.CARD_FILLED)
        self._types_card.hide()
        tl = self._types_card.content_layout()
        tl.setSpacing(ds.space_sm)
        tl.addWidget(M3Label("Par type d'erreur", theme=phi, style="title_medium"))
        grid = QGridLayout()
        grid.setSpacing(ds.space_xs)
        self._type_badges: dict[str, TypeBadge] = {}
        for i, cat in enumerate(all_categories()):
            badge = TypeBadge(cat, text=category_info(cat)["label"])
            grid.addWidget(badge, i // 2, i % 2, Qt.AlignLeft)
            self._type_badges[cat] = badge
        tl.addLayout(grid)
        cl.addWidget(self._types_card)

        # Alertes
        self._alerts_card = M3Card(theme=phi, variant=ds.CARD_FILLED)
        self._alerts_card.hide()
        al = self._alerts_card.content_layout()
        al.setSpacing(ds.space_sm)
        self._alerts_title = M3Label("Alertes", theme=phi, style="title_medium")
        al.addWidget(self._alerts_title)
        self._alerts_box = QVBoxLayout()
        self._alerts_box.setSpacing(ds.space_xxs)
        al.addLayout(self._alerts_box)
        cl.addWidget(self._alerts_card)

        # Derniers runs
        self._runs_card = M3Card(theme=phi, variant=ds.CARD_FILLED)
        self._runs_card.hide()
        rl = self._runs_card.content_layout()
        rl.setSpacing(ds.space_sm)
        rl.addWidget(M3Label("Derniers runs", theme=phi, style="title_medium"))
        self._runs_box = QVBoxLayout()
        self._runs_box.setSpacing(ds.space_xxs)
        rl.addLayout(self._runs_box)
        cl.addWidget(self._runs_card)

        # Modules modifiés
        self._mods_card = M3Card(theme=phi, variant=ds.CARD_FILLED)
        self._mods_card.hide()
        ml = self._mods_card.content_layout()
        ml.setSpacing(ds.space_sm)
        ml.addWidget(M3Label("Modules modifiés (dernier run)", theme=phi,
                             style="title_medium"))
        self._mods_box = QVBoxLayout()
        self._mods_box.setSpacing(ds.space_xxs)
        ml.addLayout(self._mods_box)
        cl.addWidget(self._mods_card)

        # DB down
        self._retry = DbUnavailableCard()
        self._retry.retry.connect(self.reload)
        self._retry.hide()
        cl.addWidget(self._retry)

        cl.addStretch()
        scroll.setWidget(content)
        lay.addWidget(scroll, 1)

        self._labels.extend([self._title, self._alerts_title])

    # ── Chargement ────────────────────────────────────────────────────

    @safe_slot("DashboardPanel.reload")
    def reload(self):
        """Rafraîchit tout le tableau (appelé à chaque navigation)."""
        try:
            conn = self._ctx.open_db()
            try:
                self._data = status_mod.render_json(conn)
            finally:
                conn.close()
        except pg.DBUnavailable as exc:
            self._show_db_down(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 — jamais de crash sur données
            self._show_db_down(f"Erreur inattendue : {exc}")
            return
        self._render()

    # ── Rendu ─────────────────────────────────────────────────────────

    def _clear(self, layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _add_line(self, layout: QVBoxLayout, text: str,
                  soft: bool = False) -> BodyLabel:
        lbl = BodyLabel(text)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        self._labels.append(lbl)
        return lbl

    def _render(self):
        data = self._data or {}
        counts = data.get("counts") or {}
        open_n = counts.get("open", 0)
        reg_n = counts.get("regressed", 0)
        res_n = counts.get("resolved", 0)
        self._kpis["open"].set_value(str(open_n))
        self._kpis["open"].set_detail("à traiter")
        self._kpis["regressed"].set_value(str(reg_n))
        self._kpis["regressed"].set_detail("à traiter")
        self._kpis["resolved"].set_value(str(res_n))
        self._kpis["resolved"].set_detail("manuel ou run")
        self._kpis["total"].set_value(str(open_n + reg_n + res_n))
        self._kpis["total"].set_detail("fiches du registre")

        # Par type d'erreur — counts open+regressed par catégorie
        by_cat = data.get("by_category") or {}
        for cat, badge in self._type_badges.items():
            badge.setText(f"{category_info(cat)['label']}  {by_cat.get(cat, 0)}")
        self._types_card.show()

        # Alertes (périmètre + conflits)
        alerts = (data.get("scope_alerts") or []) + \
                 (data.get("conflict_alerts") or [])
        self._clear(self._alerts_box)
        if alerts:
            self._alerts_title.setText(f"Alertes ({len(alerts)})")
            for alert in alerts[:_MAX_ALERTS]:
                self._add_line(self._alerts_box, alert)
            if len(alerts) > _MAX_ALERTS:
                self._add_line(
                    self._alerts_box, f"… et {len(alerts) - _MAX_ALERTS} autres")
        else:
            self._alerts_title.setText("Alertes")
            self._add_line(self._alerts_box, "Aucune alerte. 🎉")
        self._alerts_card.show()

        # Derniers runs
        runs = data.get("runs") or []
        self._clear(self._runs_box)
        if runs:
            for r in runs:
                line = (f"#{r['id']}  {r['command']}  ·  {r['status']}  ·  "
                        f"issues {r['nb_issues']}  (nouvelles {r['nb_new']}, "
                        f"régressions {r['nb_regressed']}, résolues "
                        f"{r['nb_resolved']})  ·  {_fmt_dt(r.get('started_at'))}")
                self._add_line(self._runs_box, line)
        else:
            self._add_line(self._runs_box,
                           "Aucun run enregistré — lancez une vérification.")
        self._runs_card.show()

        # Modules modifiés
        mods = data.get("modules_changed") or []
        self._clear(self._mods_box)
        if mods:
            for m in mods[:_MAX_MODS]:
                self._add_line(self._mods_box, m)
            if len(mods) > _MAX_MODS:
                self._add_line(self._mods_box,
                               f"… et {len(mods) - _MAX_MODS} autres")
        else:
            self._add_line(self._mods_box, "Aucun module modifié.")
        self._mods_card.show()

        self._retry.hide()

    def _show_db_down(self, message: str):
        for card in (self._alerts_card, self._runs_card, self._mods_card,
                     self._types_card):
            card.hide()
        self._retry.set_message(message)
        self._retry.show()

    # ── Réactivité thème ──────────────────────────────────────────────

    def _restyle(self):
        self._title.restyle()
        restyle_label(self._alerts_title, "title_medium",
                      theme_manager.palette.text_strong)
        for lbl in self._labels:
            if lbl is not self._title and lbl is not self._alerts_title:
                lbl.restyle()
        for badge in self._type_badges.values():
            badge.restyle()
        for card in (self._alerts_card, self._runs_card, self._mods_card,
                     self._types_card):
            restyle_card(card)
        self._retry._restyle()
