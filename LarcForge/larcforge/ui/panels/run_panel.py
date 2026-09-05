"""Panneau Vérifications : cases à cocher, combos, lancement, progression.

« Tout vérifier » pose le scope canonique du CLI (full_scope) → la
résolution automatique des fiches est active. « Lancer la sélection » pose
un scope personnalisé → bandeau « pas de résolution automatique ».
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QCheckBox, QVBoxLayout, QWidget

from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.logger import log
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from phibuilder.widgets import (
    M3Button, M3Card, M3ComboBox, M3Frame, M3Label, M3ProgressBar, M3ScrollArea,
)
from phibuilder.widgets.button import ButtonVariant

from ... import config as cfg
from ... import database as pg
from ... import status as status_mod
from ... import store
from ..workers import RunWorker, custom_scope, full_scope
from .common import BodyLabel, DbUnavailableCard, SectionTitle, restyle_label

_COMMANDS = [
    ("run", "Tout vérifier (linters + tests + erreurs)"),
    ("lints", "Linters seulement"),
    ("tests", "Tests pytest seulement"),
    ("errorlog", "Erreurs d'application (24 h) seulement"),
]
_SINCE = [("24", "24 dernières heures (comme la ligne de commande)"),
          ("12", "12 dernières heures"),
          ("48", "48 dernières heures"),
          ("72", "72 dernières heures"),
          ("168", "7 derniers jours")]
_LEVELS = [("ERROR,WARNING", "Erreurs et avertissements (recommandé)"),
           ("ERROR", "Erreurs seulement"),
           ("WARNING", "Avertissements seulement")]


class RunPanel(QWidget):
    """Formulaire de lancement des vérifications + progression + résultat."""

    switch_requested = Signal(str)

    def __init__(self, ctx):
        super().__init__()
        self._ctx = ctx
        self._worker: RunWorker | None = None
        self._active_run_id: int | None = None
        self._poll = QTimer(self)
        self._poll.setInterval(1000)
        self._poll.timeout.connect(self._poll_running)
        self._started_at: float | None = None
        self._elapsed = M3Label("", theme=theme_manager.phi_theme)
        self._last_scope: object | None = None

        self._build_ui()
        self._apply_profile_defaults()

    # ── Construction ──────────────────────────────────────────────────

    def _build_ui(self):
        phi = theme_manager.phi_theme
        c = phi.colors
        p = theme_manager.palette
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ds.space_lg, ds.space_lg, ds.space_lg, ds.space_lg)
        lay.setSpacing(ds.space_sm)
        lay.addWidget(SectionTitle("Vérifications"))

        scroll = M3ScrollArea(theme=phi)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(M3ScrollArea.NoFrame)
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(ds.space_xs, ds.space_xs, ds.space_xs, ds.space_xs)
        cl.setSpacing(ds.space_sm)

        # Commande
        card = M3Card(theme=phi, variant=ds.CARD_FILLED)
        v = card.content_layout()
        v.setSpacing(ds.space_sm)
        v.addWidget(M3Label("Type de vérification", theme=phi,
                            style="title_medium"))
        self._cmd_combo = M3ComboBox(
            items=[label for _, label in _COMMANDS], theme=phi)
        self._cmd_combo.setFixedHeight(ds.field_height + ds.space_xs)
        v.addWidget(self._cmd_combo)
        cl.addWidget(card)

        # Projets
        card = M3Card(theme=phi, variant=ds.CARD_FILLED)
        v = card.content_layout()
        v.setSpacing(ds.space_sm)
        v.addWidget(M3Label("Projets vérifiés (8)", theme=phi,
                            style="title_medium"))
        self._proj_checks: dict[str, QCheckBox] = {}
        for name in cfg.PROJETS:
            self._proj_checks[name] = self._make_check(v, name)
        self._add_tout(v, list(self._proj_checks.values()))
        cl.addWidget(card)

        # Linters
        card = M3Card(theme=phi, variant=ds.CARD_FILLED)
        v = card.content_layout()
        v.setSpacing(ds.space_sm)
        v.addWidget(M3Label("Linters (10)", theme=phi, style="title_medium"))
        self._lint_checks: dict[str, QCheckBox] = {}
        for key, script in cfg.LINTERS:
            self._lint_checks[key] = self._make_check(v, f"{key} — {script}")
        self._add_tout(v, list(self._lint_checks.values()))
        cl.addWidget(card)

        # Tests
        card = M3Card(theme=phi, variant=ds.CARD_FILLED)
        v = card.content_layout()
        v.setSpacing(ds.space_sm)
        v.addWidget(M3Label("Tests pytest (4 projets)", theme=phi,
                            style="title_medium"))
        self._test_checks: dict[str, QCheckBox] = {}
        for name in cfg.TEST_PROJECTS:
            self._test_checks[name] = self._make_check(v, name)
        self._include_int = self._make_check(
            v, "Inclure les tests d'intégration (lents)", checked=False)
        self._add_tout(v, list(self._test_checks.values()))
        cl.addWidget(card)

        # Options
        card = M3Card(theme=phi, variant=ds.CARD_FILLED)
        v = card.content_layout()
        v.setSpacing(ds.space_sm)
        v.addWidget(M3Label("Options", theme=phi, style="title_medium"))
        v.addWidget(M3Label("Depuis quand ?", theme=phi, style="body_medium"))
        self._since_combo = M3ComboBox(
            items=[label for _, label in _SINCE], theme=phi)
        self._since_combo.setFixedHeight(ds.field_height + ds.space_xs)
        v.addWidget(self._since_combo)
        v.addWidget(M3Label("Niveaux de gravité", theme=phi,
                            style="body_medium"))
        self._level_combo = M3ComboBox(
            items=[label for _, label in _LEVELS], theme=phi)
        self._level_combo.setFixedHeight(ds.field_height + ds.space_xs)
        v.addWidget(self._level_combo)
        cl.addWidget(card)

        # Bandeau scope (résolution automatique active ou non)
        self._scope_banner = M3Frame(theme=phi)
        self._scope_banner.setAttribute(Qt.WA_StyledBackground, True)
        bl = QVBoxLayout(self._scope_banner)
        bl.setContentsMargins(ds.space_md, ds.space_sm, ds.space_md, ds.space_sm)
        self._scope_lbl = M3Label("", theme=phi, style="body_medium")
        bl.addWidget(self._scope_lbl)
        cl.addWidget(self._scope_banner)

        # Boutons
        btn_lay = QVBoxLayout()
        btn_lay.setSpacing(ds.space_sm)
        self._btn_full = M3Button("Tout vérifier", theme=phi,
                                  variant=ButtonVariant.FILLED)
        self._btn_full.setIcon(md3_icon("bolt", color=p.on_primary,
                                        size=ds.icon_md))
        self._btn_full.clicked.connect(self._on_start_full)
        btn_lay.addWidget(self._btn_full)
        self._btn_sel = M3Button("Lancer la sélection", theme=phi,
                                 variant=ButtonVariant.TONAL)
        self._btn_sel.clicked.connect(self._on_start_selection)
        btn_lay.addWidget(self._btn_sel)
        cl.addLayout(btn_lay)

        # Progression
        self._prog = M3ProgressBar(theme=phi)
        self._prog.setRange(0, 0)  # indéterminée pendant un run
        self._prog.hide()
        cl.addWidget(self._prog)
        self._status_lbl = M3Label("", theme=phi, style="body_medium")
        cl.addWidget(self._status_lbl)
        cl.addWidget(self._elapsed)

        # Résultat
        self._result_card = M3Card(theme=phi, variant=ds.CARD_ELEVATED)
        self._result_card.hide()
        self._result_lay = self._result_card.content_layout()
        self._result_lay.setSpacing(ds.space_sm)
        self._result_title = M3Label("", theme=phi, style="title_medium")
        self._result_lay.addWidget(self._result_title)
        self._result_msg = BodyLabel("")
        self._result_lay.addWidget(self._result_msg)
        self._btn_issues = M3Button("Voir le registre des issues", theme=phi,
                                    variant=ButtonVariant.TONAL)
        self._btn_issues.clicked.connect(self._on_show_issues)
        self._btn_issues.hide()
        self._result_lay.addWidget(self._btn_issues)
        self._retry_card = DbUnavailableCard()
        self._retry_card.retry.connect(self._on_retry)
        self._result_lay.addWidget(self._retry_card)
        cl.addWidget(self._result_card)

        cl.addStretch()
        scroll.setWidget(content)
        lay.addWidget(scroll, 1)

        self._update_scope_banner()

    def _make_check(self, parent_layout, text: str, checked: bool = True) -> QCheckBox:
        p = theme_manager.palette
        cb = QCheckBox(text)
        cb.setChecked(checked)
        cb.setCursor(Qt.PointingHandCursor)
        cb.setStyleSheet(
            f"QCheckBox {{ color: {p.text_strong}; background: transparent; }}")
        parent_layout.addWidget(cb)
        return cb

    def _add_tout(self, parent_layout, checks: list[QCheckBox]):
        btn = M3Button("Tout cocher / décocher", theme=theme_manager.phi_theme,
                       variant=ButtonVariant.TEXT)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(
            lambda checked, cs=checks: self._toggle_group(cs))
        parent_layout.addWidget(btn)

    @safe_slot("RunPanel.toggle_group")
    def _toggle_group(self, checks: list[QCheckBox]):
        any_checked = any(c.isChecked() for c in checks)
        for c in checks:
            c.setChecked(not any_checked)

    # ── Profil actif (pré-sélection école) ────────────────────────────

    def _apply_profile_defaults(self):
        """Pré-coche selon le profil de vérification actif, sinon tout."""
        cfg_ui = self._ctx.config
        profile = None
        if cfg_ui.active_run_profile:
            for rp in cfg_ui.run_profiles:
                if rp.name == cfg_ui.active_run_profile:
                    profile = rp
                    break
        if profile is None:
            self._cmd_combo.setCurrentIndex(0)
            self._since_combo.setCurrentIndex(0)
            self._level_combo.setCurrentIndex(0)
            return
        for key in self._lint_checks:
            self._lint_checks[key].setChecked(key in profile.linters)
        for name in self._proj_checks:
            self._proj_checks[name].setChecked(name in profile.projects)
        for name in self._test_checks:
            self._test_checks[name].setChecked(name in profile.test_projects)
        self._include_int.setChecked(profile.include_integration)
        # la commande reste « run » — le profil fixe projets/linters/fenêtre
        for i, (key, _) in enumerate(_SINCE):
            if int(key) == (profile.since_h or 24):
                self._since_combo.setCurrentIndex(i)
                break
        for i, (key, _) in enumerate(_LEVELS):
            if key == (profile.level or "ERROR,WARNING"):
                self._level_combo.setCurrentIndex(i)
                break

    # ── Scope ─────────────────────────────────────────────────────────

    def _scope_from_ui(self) -> tuple[object, bool]:
        """Retourne (scope, is_full) depuis les cases et combos."""
        projects = [p for p in cfg.PROJETS if self._proj_checks[p].isChecked()]
        linters = [k for k in cfg.LINTER_KEYS if self._lint_checks[k].isChecked()]
        tests = [t for t in cfg.TEST_PROJECTS if self._test_checks[t].isChecked()]
        include = self._include_int.isChecked()
        cmd = _COMMANDS[self._cmd_combo.currentIndex()][0]
        since_h = int(_SINCE[self._since_combo.currentIndex()][0])
        level = _LEVELS[self._level_combo.currentIndex()][0]
        # la fenêtre par défaut (24 h) est celle de la CLI : le scope pose
        # None (execute convertit en 24) pour matcher la résolution auto
        scope = custom_scope(cmd, projects, linters, include,
                             None if since_h == 24 else since_h, level)
        is_full = scope.canonical() == full_scope().canonical()
        if is_full:
            # GARDE-FOU : poser le scope canonique EXACT (since_h=None) pour
            # que la résolution automatique matche le run CLI en base.
            scope = full_scope()
        return scope, is_full

    def _update_scope_banner(self):
        """Bandeau « résolution automatique » — reflet exact du scope."""
        scope, is_full = self._scope_from_ui()
        p = theme_manager.palette
        c = theme_manager.phi_theme.colors
        color = c.primary if is_full else p.error
        self._scope_lbl.setText(
            ("✓ Résolution automatique des fiches ACTIVE — même périmètre "
             "que la ligne de commande (larcforge run).") if is_full
            else ("Vérifications personnalisées — la résolution "
                  "automatique des fiches n'est PAS active."))
        self._scope_lbl.setStyleSheet(
            f"M3Label {{ color: {color}; font-size: {ds.font_body}px; }}")
        self._scope_banner.setStyleSheet(
            f"background: {c.surface_variant}; border-radius: {ds.radius_sm}px;")
        self._last_scope = scope
        self._is_full = is_full

    # ── Lancement ─────────────────────────────────────────────────────

    def _launch(self, scope):
        self._set_running(True)
        self._started_at = None
        self._active_run_id = None
        self._elapsed.setText("")
        self._result_card.hide()
        worker = RunWorker(self._ctx.root, scope, timeout=self._ctx.timeout)
        worker.run_finished.connect(self._on_finished)
        worker.run_failed.connect(self._on_failed)
        self._worker = worker
        worker.start()
        self._poll.start()

    @safe_slot("RunPanel.on_start_full")
    def _on_start_full(self):
        self._launch(full_scope())

    @safe_slot("RunPanel.on_start_selection")
    def _on_start_selection(self):
        scope, _ = self._scope_from_ui()
        self._launch(scope)

    @safe_slot("RunPanel.on_retry")
    def _on_retry(self):
        self._retry_card.hide()
        self._launch(self._last_scope or full_scope())

    def _set_running(self, running: bool):
        for widget in (self._btn_full, self._btn_sel):
            widget.setEnabled(not running)
        self._prog.setVisible(running)
        self._status_lbl.setText(
            "Vérifications en cours…" if running else "")

    # ── Progression (polling du run actif) ────────────────────────────

    @safe_slot("RunPanel.poll_running")
    def _poll_running(self):
        if self._worker is None or not self._worker.isRunning():
            self._poll.stop()
            return
        if self._started_at is None:
            self._started_at = time.time()
        else:
            elapsed = time.time() - self._started_at
            self._elapsed.setText(f"Temps écoulé : {elapsed:.0f} s")
        # le run actif en base (dernier id 'running') — requête courte
        try:
            conn = self._ctx.open_db()
            try:
                row = status_mod.running_run(conn)
            finally:
                conn.close()
        except Exception:
            return  # DB down en cours de run : on repollera au prochain tick
        if row:
            self._active_run_id = row["id"]
            self._status_lbl.setText(
                f"Run #{row['id']} en cours — {row.get('command', '')}")

    # ── Fin de run ────────────────────────────────────────────────────

    @safe_slot("RunPanel.on_finished")
    def _on_finished(self, summary, code: int, message: str):
        self._poll.stop()
        self._set_running(False)
        p = theme_manager.palette
        if code == 4:
            self._result_card.show()
            self._result_title.setText("Base de données indisponible")
            self._result_msg.setText(message)
            self._retry_card.show()
            self._btn_issues.hide()
            return
        self._retry_card.hide()
        self._result_card.show()
        title = ("Aucune issue ouverte" if code == 0
                 else "Issues trouvées" if code == 1
                 else "Erreurs techniques de collecte")
        self._result_title.setText(
            f"{title} — run #{summary.run_id or '—'}  ({message})")
        self._result_msg.setText(
            f"Issues vues : {summary.nb_issues}   ·   Nouvelles : {summary.nb_new}   ·   "
            f"Régressions : {summary.nb_regressed}   ·   Résolues : {summary.nb_resolved}"
            + (f"   ·   Erreurs de collecte : {summary.nb_errors}"
               if summary.nb_errors else ""))
        if summary.errors:
            self._result_msg.setText(
                self._result_msg.text() + "\n" + "\n".join(summary.errors[:3]))
        self._btn_issues.setVisible(code == 1)
        self._elapsed.setText("")

    @safe_slot("RunPanel.on_failed")
    def _on_failed(self, message: str):
        self._poll.stop()
        self._set_running(False)
        self._result_card.show()
        self._result_title.setText("Erreur inattendue")
        self._result_msg.setText(message)
        self._retry_card.hide()
        self._btn_issues.hide()
        self._elapsed.setText("")

    @safe_slot("RunPanel.on_show_issues")
    def _on_show_issues(self):
        self.switch_requested.emit("issues")

    # ── Fermeture pendant un run (appelé par MainWindow.closeEvent) ──

    def run_in_progress(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def close_run(self):
        """Interrompt le run en cours et marque le run en base comme 'error'."""
        if not self.run_in_progress():
            return
        run_id = self._active_run_id
        if run_id is not None:
            try:
                conn = self._ctx.open_db()
                try:
                    store.abort_run(conn, run_id)
                finally:
                    conn.close()
            except Exception as exc:  # noqa: BLE001
                log(f"LarcForge : impossible de marquer le run {run_id} "
                    f"comme interrompu : {exc}", level="ERROR")
        self._poll.stop()
        self._worker.terminate()
        self._worker.wait(3000)
        self._set_running(False)

    # ── Divers ────────────────────────────────────────────────────────

    def reload(self):
        self._update_scope_banner()

    def _restyle(self):
        p = theme_manager.palette
        c = theme_manager.phi_theme.colors
        for cb in list(self._proj_checks.values()) + \
                list(self._lint_checks.values()) + \
                list(self._test_checks.values()) + [self._include_int]:
            cb.setStyleSheet(
                f"QCheckBox {{ color: {p.text_strong}; background: transparent; }}")
        self._btn_full.setIcon(md3_icon("bolt", color=p.on_primary,
                                        size=ds.icon_md))
        self._scope_banner.setStyleSheet(
            f"background: {c.surface_variant}; border-radius: {ds.radius_sm}px;")
        color = c.primary if self._is_full else p.error
        self._scope_lbl.setStyleSheet(
            f"M3Label {{ color: {color}; font-size: {ds.font_body}px; }}")
        restyle_label(self._result_title, "title_medium", p.text_strong)
        self._result_msg.restyle()
