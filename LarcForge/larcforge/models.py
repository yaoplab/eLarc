"""Structures de données de LarcForge."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from .signature import signature as _signature


@dataclass
class IssueCandidate:
    """Une occurrence de problème détectée par un collecteur (avant écriture DB)."""

    source: str                 # 'linter:R' | 'pytest' | 'errorlog'
    app_name: str               # repo (linters/tests) ou app_name (error_log)
    module: str | None = None   # chemin relatif à la racine, séparateur '/'
    func: str | None = None
    line: int | None = None
    level: str = "ERROR"
    rule: str | None = None
    message: str = ""
    traceback: str | None = None
    context: dict | None = None
    larc_version: str | None = None

    def signature(self) -> str:
        return _signature(self.source, self.app_name, self.module, self.func, self.message)


@dataclass
class RunScope:
    """Périmètre d'un run — comparé (canonical) pour valider les résolutions."""

    command: str
    linters: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    include_integration: bool = False
    since_h: int | None = None
    level: str | None = None

    def canonical(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, default=str)


@dataclass
class RunSummary:
    """Bilan d'un run."""

    nb_issues: int = 0        # vues ce run (créées + mises à jour + régressées)
    nb_new: int = 0
    nb_regressed: int = 0
    nb_resolved: int = 0
    nb_errors: int = 0        # erreurs techniques de collecte
    errors: list[str] = field(default_factory=list)
    run_id: int | None = None                     # rempli par le runner (mode DB)
    candidates: list[dict] = field(default_factory=list)  # détails (mode --no-db)

    def as_dict(self) -> dict:
        return asdict(self)
