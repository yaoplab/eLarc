"""Collecteur : exécute les linters (scripts/) et convertit leur JSON en candidates.

Interfaces homogènes : `python scripts/<linter>.py --dir <root> --json`,
exit 0 (propre) ou 1 (violations), JSON `ensure_ascii=False` fiable.
Exception : les linters « globaux » (_GLOBAL_KEYS) s'exécutent SANS --dir —
ils auditent le code central (audit_theme_reactive, lint_palette_contrast).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import LINTERS
from ..models import IssueCandidate
from .base import CollectorError, module_of, run_subprocess


# Linters « globaux » : auditent le code central (palette, thème) — pas de --dir.
_GLOBAL_KEYS = {"REACT", "CTR"}


def _iter_entries(key: str, payload) -> list[dict]:
    """Extrait les entrées de violation quel que soit le format JSON du linter."""
    if not isinstance(payload, (dict, list)):
        return []
    if key in ("R", "D"):
        # {"results": {groupe: [{file,line,rule,...}], ...}, "total": N}
        results = payload.get("results")
        if isinstance(results, dict):
            return [e for group in results.values() if isinstance(group, list) for e in group]
        return results if isinstance(results, list) else []
    if key == "CTR":
        # lint_palette_contrast.py — liste plate de {rule, severity, message, file}
        return [e for e in payload if isinstance(e, dict)]
    if key == "REACT":
        # {module: {"files": N, "total_vulnerable": N, "results": [{file, ...}]}}
        entries = []
        for mod in payload.values():
            if isinstance(mod, dict) and isinstance(mod.get("results"), list):
                for r in mod["results"]:
                    if isinstance(r, dict) and (r.get("total_vulnerable") or 0) > 0:
                        entries.append({**r, "module_group": mod.get("module") or ""})
        return entries
    if key == "FS":
        # {"violations": [...], "stats": {...}}
        vs = payload.get("violations") if isinstance(payload, dict) else None
        return vs if isinstance(vs, list) else []
    if isinstance(payload, list):
        return [e for e in payload if isinstance(e, dict)]
    return []


def _level_for(key: str, severity: str) -> str:
    sev = (severity or "").upper()
    if key == "C":
        return "ERROR"            # checklist pré-soumission : toute violation est bloquante
    if sev in ("P0", "ERROR", "HIGH"):
        return "ERROR"
    return "WARNING"


def _candidates(key: str, payload, app_fallback: str, root: Path) -> list[IssueCandidate]:
    cands = []
    for entry in _iter_entries(key, payload):
        file = str(entry.get("file") or "")
        rule = str(entry.get("rule") or "")
        if key == "REACT":
            message = f"{entry.get('total_vulnerable')} appel(s) palette non protégé(s) (audit thème)"
            module = None
        else:
            message = str(entry.get("message") or entry.get("context")
                          or entry.get("detail") or "")
            module = module_of(file, app_fallback, root)
        app = str(entry.get("project") or app_fallback)
        severity = str(entry.get("severity") or "")
        cands.append(IssueCandidate(
            source=f"linter:{key}",
            app_name=app,
            module=module,
            line=entry.get("line"),
            level=_level_for(key, severity),
            rule=rule,
            func=rule,
            message=message or f"Violation {rule} dans {file}",
        ))
    return cands


def collect(root: Path, python: str, scripts_dir: Path,
            projects: list[str], keys: list[str] | None = None,
            timeout: int = 300) -> tuple[list[IssueCandidate], list[str]]:
    """Lance les linters demandés. Retourne (candidates, erreurs techniques)."""
    cands: list[IssueCandidate] = []
    errors: list[str] = []
    wanted = set(keys) if keys else {k for k, _ in LINTERS}

    for key, script in LINTERS:
        if key not in wanted:
            continue
        script_path = scripts_dir / script
        if not script_path.is_file():
            errors.append(f"[{key}] script introuvable : {script}")
            continue
        if key in _GLOBAL_KEYS:
            # Auditent le code central (pas de --dir utile) — une seule passe.
            # REACT couvre plusieurs projets, CTR est rattaché à LarcCommon.
            app = "Larc" if key == "REACT" else "LarcCommon"
            try:
                result = run_subprocess([python, str(script_path), "--json"],
                                        cwd=root, timeout=timeout)
            except CollectorError as exc:
                errors.append(f"[{key}] {exc}")
                continue
            if result.returncode not in (0, 1):
                errors.append(f"[{key}] code retour {result.returncode} (crash?)")
                continue
            try:
                payload = json.loads(result.stdout or "null")
            except json.JSONDecodeError:
                errors.append(f"[{key}] sortie JSON illisible")
                continue
            if payload:
                cands.extend(_candidates(key, payload, app, root))
            continue

        for project in projects:
            proot = root / project
            if not proot.is_dir():
                continue
            try:
                result = run_subprocess(
                    [python, str(script_path), "--dir", str(proot), "--json"],
                    cwd=root, timeout=timeout,
                )
            except CollectorError as exc:
                errors.append(f"[{key}/{project}] {exc}")
                continue
            if result.returncode not in (0, 1):
                errors.append(f"[{key}/{project}] code retour {result.returncode} (crash?)")
                continue
            try:
                payload = json.loads(result.stdout or "null")
            except json.JSONDecodeError:
                errors.append(f"[{key}/{project}] sortie JSON illisible")
                continue
            if payload:
                cands.extend(_candidates(key, payload, project, root))
    return cands, errors
