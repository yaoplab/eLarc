"""Panneau Registre des issues : filtres, tableau, détail, résolution.

Actions de fiche : « Résoudre avec note » (open/regressed → resolved) et
« Réouvrir » (resolved → open). Une connexion courte par opération.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout, QTableWidgetItem, QVBoxLayout, QWidget,
)

from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from phibuilder.widgets import (
    M3Button, M3Card, M3ComboBox, M3Label, M3TableWidget, M3TextField,
)
from phibuilder.widgets.button import ButtonVariant

from ... import database as pg
from ... import status as status_mod
from ... import store
from ...taxonomy import (
    all_categories, category_for, category_info, discover_skills, type_colors,
)
from .common import (
    BodyLabel, DbUnavailableCard, NoteDialog, SectionTitle, restyle_card,
    restyle_label,
)

_STATUSES = [("", "Tous les statuts"),
             ("open", "Ouvertes"),
             ("resolved", "Résolues"),
             ("regressed", "Régressées")]
_SOURCES = [("", "Toutes les sources"),
            ("linter", "Linters"),
            ("pytest", "Tests pytest"),
            ("errorlog", "Erreurs d'application")]
# Filtre catégorie — labels lus dans la taxonomie (une catégorie ajoutée à
# taxonomy.py apparaît ici sans autre modification).
_CATEGORIES = [(cat, category_info(cat)["label"]) for cat in all_categories()]
_COLS = ["ID", "Statut", "Type", "App", "Module", "Règle", "Message", "Vu le"]


def _fmt_dt(value) -> str:
    if not value:
        return ""
    try:
        return value.strftime("%d/%m %H:%M")
    except AttributeError:
        return str(value)[:16]


class IssuesPanel(QWidget):
    """Registre filtrable + détail + gestion des fiches."""

    def __init__(self, ctx):
        super().__init__()
        self._ctx = ctx
        self._detail: dict | None = None
        self._apps: list[str] = []
        self._labels: list = []
        self._skills = discover_skills(self._ctx.root)
        self._build_ui()

    # ── Construction ──────────────────────────────────────────────────

    def _build_ui(self):
        phi = theme_manager.phi_theme
        p = theme_manager.palette
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ds.space_lg, ds.space_lg, ds.space_lg, ds.space_lg)
        lay.setSpacing(ds.space_sm)
        self._title = SectionTitle("Registre des issues")
        lay.addWidget(self._title)

        # Filtres
        filt = QHBoxLayout()
        filt.setSpacing(ds.space_sm)
        self._status_combo = M3ComboBox(items=[l for _, l in _STATUSES],
                                        theme=phi)
        self._status_combo.setFixedHeight(ds.field_height + ds.space_xs)
        filt.addWidget(self._status_combo, 2)
        self._app_combo = M3ComboBox(items=["Toutes les apps"], theme=phi)
        self._app_combo.setFixedHeight(ds.field_height + ds.space_xs)
        filt.addWidget(self._app_combo, 2)
        self._source_combo = M3ComboBox(items=[l for _, l in _SOURCES],
                                        theme=phi)
        self._source_combo.setFixedHeight(ds.field_height + ds.space_xs)
        filt.addWidget(self._source_combo, 2)
        self._cat_combo = M3ComboBox(
            items=["Toutes les catégories"] + [l for _, l in _CATEGORIES],
            theme=phi)
        self._cat_combo.setFixedHeight(ds.field_height + ds.space_xs)
        filt.addWidget(self._cat_combo, 2)
        self._search = M3TextField(theme=phi, placeholder="Rechercher (message, module)…")
        self._search.setStyleSheet(ds.flat_input_qss())
        self._search.returnPressed.connect(self.reload)
        filt.addWidget(self._search, 3)
        btn = M3Button("Filtrer", theme=phi, variant=ButtonVariant.TONAL)
        btn.setIcon(md3_icon("filter_list", color=p.primary, size=ds.icon_md))
        btn.clicked.connect(self.reload)
        filt.addWidget(btn)
        lay.addLayout(filt)

        # Compteur
        self._count_lbl = M3Label("", theme=phi, style="body_medium")
        lay.addWidget(self._count_lbl)

        # Tableau
        self._table = M3TableWidget(0, len(_COLS), theme=phi)
        self._table.setHorizontalHeaderLabels(_COLS)
        self._table.setStyleSheet(ds.table_qss())
        self._table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._table.setSelectionMode(M3TableWidget.SingleSelection)
        self._table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._table.setWordWrap(False)
        self._table.itemSelectionChanged.connect(self._on_selection)
        self._table.setMinimumHeight(ds.space_xxxl * 2)
        lay.addWidget(self._table, 3)

        # Détail
        self._detail_card = M3Card(theme=phi, variant=ds.CARD_ELEVATED)
        dl = self._detail_card.content_layout()
        dl.setSpacing(ds.space_sm)
        self._detail_title = M3Label("Sélectionnez une fiche pour voir le détail",
                                     theme=phi, style="title_medium")
        dl.addWidget(self._detail_title)
        self._detail_body = BodyLabel("")
        self._detail_body.setWordWrap(True)
        dl.addWidget(self._detail_body)
        actions = QHBoxLayout()
        actions.setSpacing(ds.space_sm)
        self._btn_resolve = M3Button("Résoudre avec une note", theme=phi,
                                     variant=ButtonVariant.FILLED)
        self._btn_resolve.setIcon(md3_icon("check_circle", color=p.on_primary,
                                           size=ds.icon_md))
        self._btn_resolve.clicked.connect(self._on_resolve)
        actions.addWidget(self._btn_resolve)
        self._btn_reopen = M3Button("Réouvrir", theme=phi,
                                    variant=ButtonVariant.TONAL)
        self._btn_reopen.setIcon(md3_icon("refresh", color=p.primary,
                                          size=ds.icon_md))
        self._btn_reopen.clicked.connect(self._on_reopen)
        actions.addWidget(self._btn_reopen)
        actions.addStretch()
        dl.addLayout(actions)
        self._btn_resolve.hide()
        self._btn_reopen.hide()
        lay.addWidget(self._detail_card)

        # DB down
        self._retry = DbUnavailableCard()
        self._retry.retry.connect(self.reload)
        self._retry.hide()
        lay.addWidget(self._retry)

    # ── Chargement ────────────────────────────────────────────────────

    @safe_slot("IssuesPanel.reload")
    def reload(self):
        """Recharge le tableau avec les filtres courants (appels DB courts)."""
        status_key = _STATUSES[self._status_combo.currentIndex()][0]
        app_key = self._current_app()
        source_key = _SOURCES[self._source_combo.currentIndex()][0]
        search = self._search.text().strip() or None
        try:
            conn = self._ctx.open_db()
            try:
                issues = status_mod.list_issues(
                    conn, status=status_key, app=app_key, source=source_key,
                    search=search, limit=500)
                cat_idx = self._cat_combo.currentIndex()
                if cat_idx > 0:
                    cat_key = _CATEGORIES[cat_idx - 1][0]
                    issues = [i for i in issues
                              if category_for(i.get("source")) == cat_key]
                if not self._apps:
                    self._apps = status_mod.list_apps(conn)
                    self._refresh_apps()
                self._data = issues
            finally:
                conn.close()
        except pg.DBUnavailable as exc:
            self._show_db_down(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 — jamais de crash sur données
            self._show_db_down(f"Erreur inattendue : {exc}")
            return
        self._render_table()
        self._retry.hide()
        self._detail = None
        self._render_detail()

    def _current_app(self) -> str | None:
        idx = self._app_combo.currentIndex()
        if idx <= 0:
            return None
        return self._apps[idx - 1]

    def _refresh_apps(self):
        self._app_combo.clear()
        self._app_combo.addItems(["Toutes les apps"] + self._apps)

    def _render_table(self):
        self._table.setRowCount(len(self._data))
        for row, issue in enumerate(self._data):
            cat = category_for(issue.get("source"))
            vals = [
                str(issue.get("id", "")),
                issue.get("status", ""),
                category_info(cat)["label"],
                issue.get("app_name") or "",
                issue.get("module") or "",
                issue.get("rule") or "",
                (issue.get("message") or "")[:80],
                _fmt_dt(issue.get("last_seen")),
            ]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setData(Qt.UserRole, issue.get("id"))
                if col == 2:  # colonne Type : badge coloré de la catégorie
                    badge, _container, texte = type_colors(cat)
                    item.setBackground(QColor(badge))
                    item.setForeground(QColor(texte))
                self._table.setItem(row, col, item)
        n = len(self._data)
        self._count_lbl.setText(
            f"{n} fiche{'s' if n > 1 else ''} affichée{'s' if n > 1 else ''}"
            + (" (500 max — précisez les filtres)" if n == 500 else ""))

    # ── Détail ────────────────────────────────────────────────────────

    @safe_slot("IssuesPanel.on_selection")
    def _on_selection(self):
        items = self._table.selectedItems()
        if not items:
            return
        issue_id = items[0].data(Qt.UserRole)
        try:
            conn = self._ctx.open_db()
            try:
                self._detail = status_mod.issue_detail(conn, issue_id)
            finally:
                conn.close()
        except pg.DBUnavailable as exc:
            self._show_db_down(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            self._detail = {"message": f"Erreur de lecture : {exc}"}
        self._render_detail()

    def _render_detail(self):
        d = self._detail
        if not d:
            self._detail_title.setText(
                "Sélectionnez une fiche pour voir le détail")
            self._detail_body.setText("")
            self._btn_resolve.hide()
            self._btn_reopen.hide()
            return
        self._detail_title.setText(
            f"Fiche #{d.get('id')} — {d.get('app_name') or ''} "
            f"{d.get('module') or ''} {d.get('rule') or ''}"
            + (f"  ({d.get('status')})" if d.get("status") else ""))
        source = d.get("source") or ""
        info = category_info(category_for(source))
        lines = [
            f"Source : {source}   ·   Niveau : {d.get('level') or ''}"
            f"   ·   Occurrences : {d.get('occurrences') or 0}"
            + (f"   ·   Régressions : {d.get('regressed_count') or 0}"
               if d.get("regressed_count") else ""),
            f"Type : {info['label']} — {info['description']}",
        ]
        skill = info.get("skill")
        if skill:
            sd = self._skills.get(skill)
            lines.append(f"Skill : {skill}" + (f" — {sd}" if sd else ""))
        lines.append(f"Message : {d.get('message') or ''}")
        if d.get("func"):
            lines.append(f"Fonction : {d['func']}"
                         + (f"  ·  Ligne : {d.get('line')}" if d.get("line") else ""))
        if d.get("traceback"):
            lines.append(f"Traceback :\n{d['traceback'][:600]}")
        if d.get("resolution_note"):
            lines.append(
                f"Note de résolution ({_fmt_dt(d.get('resolved_at'))}) : "
                f"{d['resolution_note']}")
        lines.append(
            f"Première détection : {_fmt_dt(d.get('first_seen'))}   ·   "
            f"Dernière : {_fmt_dt(d.get('last_seen'))}")
        self._detail_body.setText("\n".join(lines))
        status = d.get("status")
        self._btn_resolve.setVisible(status in ("open", "regressed"))
        self._btn_reopen.setVisible(status == "resolved")

    # ── Actions de fiche ──────────────────────────────────────────────

    @safe_slot("IssuesPanel.on_resolve")
    def _on_resolve(self):
        d = self._detail
        if not d or d.get("status") not in ("open", "regressed"):
            return
        dialog = NoteDialog(
            f"Résoudre la fiche #{d.get('id')}",
            "Expliquez ce qui a été corrigé (visible dans le registre) :")
        note = dialog.exec_note()
        if note is None:
            return
        try:
            conn = self._ctx.open_db()
            try:
                store.resolve_issue(conn, d["id"], note)
            finally:
                conn.close()
        except pg.DBUnavailable as exc:
            self._show_db_down(str(exc))
            return
        self.reload()

    @safe_slot("IssuesPanel.on_reopen")
    def _on_reopen(self):
        d = self._detail
        if not d or d.get("status") != "resolved":
            return
        try:
            conn = self._ctx.open_db()
            try:
                store.reopen_issue(conn, d["id"])
            finally:
                conn.close()
        except pg.DBUnavailable as exc:
            self._show_db_down(str(exc))
            return
        self.reload()

    # ── Divers ────────────────────────────────────────────────────────

    def _show_db_down(self, message: str):
        self._table.setRowCount(0)
        self._count_lbl.setText("")
        self._detail = None
        self._render_detail()
        self._retry.set_message(message)
        self._retry.show()

    def _restyle(self):
        p = theme_manager.palette
        self._title.restyle()
        restyle_label(self._count_lbl, "body_medium", p.text_soft)
        restyle_label(self._detail_title, "title_medium", p.text_strong)
        for lbl in self._labels:
            lbl.restyle()
        restyle_card(self._detail_card)
        self._table.refresh()
        self._table.setStyleSheet(ds.table_qss())
        self._search.setStyleSheet(ds.flat_input_qss())
        self._btn_resolve.setIcon(md3_icon("check_circle", color=p.on_primary,
                                           size=ds.icon_md))
        self._btn_reopen.setIcon(md3_icon("refresh", color=p.primary,
                                          size=ds.icon_md))
        self._retry._restyle()
