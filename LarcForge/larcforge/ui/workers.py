"""Worker d'exécution : appelle runner.execute() hors du fil UI.

GARDE-FOU SCOPE (critique) : full_scope() doit être EXACTEMENT l'égal du
scope posé par la CLI par défaut (`larcforge run`) — comparez
scope.canonical(). since_h=None est crucial : le run CLI pose None
(execute convertit en 24) ; si l'UI posait 24, la résolution automatique
des fiches ne se déclencherait jamais.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from .. import config as cfg
from ..models import RunScope
from ..runner import execute as _execute


def full_scope() -> RunScope:
    """Scope canonique du CLI : « Tout vérifier » (résolution auto active)."""
    return RunScope(
        command="run",
        linters=list(cfg.LINTER_KEYS),
        projects=list(cfg.PROJETS),
        include_integration=False,
        since_h=None,
        level="ERROR,WARNING",
    )


def custom_scope(command: str, projects: list[str], linters: list[str],
                 include_integration: bool = False, since_h: int = 24,
                 level: str = "ERROR,WARNING") -> RunScope:
    """Scope personnalisé (cases à cocher) — pas de résolution automatique."""
    return RunScope(
        command=command,
        linters=linters,
        projects=projects,
        include_integration=include_integration,
        since_h=since_h,
        level=level,
    )


class RunWorker(QThread):
    """Exécute un run hors du fil UI.

    PAS de @safe_slot sur run() : safe_slot avale les exceptions et l'UI
    resterait bloquée. try/except complet — run_failed est TOUJOURS émis
    en cas d'erreur inattendue, run_finished sinon.
    """

    run_finished = Signal(object, int, str)  # (RunSummary, exit_code, message)
    run_failed = Signal(str)

    def __init__(self, root, scope: RunScope, timeout: int = 300,
                 use_db: bool = True, parent=None):
        super().__init__(parent)
        self._root = root
        self._scope = scope
        self._timeout = timeout
        self._use_db = use_db

    def run(self):
        try:
            summary, code, message = _execute(
                self._root, self._scope,
                timeout=self._timeout,
                use_db=self._use_db,
                keys=self._scope.linters,
                include_integration=self._scope.include_integration,
                since_h=self._scope.since_h or 24,
                levels=tuple(l.strip() for l in
                             (self._scope.level or "ERROR,WARNING").split(",")
                             if l.strip()),
                limit=500,
            )
        except Exception as exc:  # noqa: BLE001 — l'UI doit toujours se débloquer
            self.run_failed.emit(str(exc))
            return
        self.run_finished.emit(summary, code, message)
