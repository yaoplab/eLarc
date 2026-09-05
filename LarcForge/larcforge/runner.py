"""Orchestration : un run = un larc_run, collecteurs séquentiels, écriture DB.

Retourne (summary, exit_code) — exit : 0 propre · 1 issues · 3 technique · 4 DB.
"""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

from . import config as cfg
from . import database as pg
from . import store
from .collectors import build as build_coll
from .collectors import errorlog as errorlog_coll
from .collectors import linters as linters_coll
from .collectors import larcommon_clients as lc_validator
from .collectors import pytest_collector
from .models import RunScope, RunSummary


def scan_modules(root: Path, projects: list[str]) -> list[tuple[str, str, int, int]]:
    """Snapshot des fichiers .py scannables (substitut git — aucun repo n'a de .git)."""
    modules: list[tuple[str, str, int, int]] = []
    for project in projects:
        base = root / project
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            parts = p.relative_to(base).parts
            if any(seg in cfg.EXCLUDE_DIRS for seg in parts[:-1]):
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            rel = p.relative_to(root).as_posix()
            modules.append((project, rel, st.st_mtime_ns, st.st_size))
    return modules


def execute(root: Path, scope: RunScope, python: str | None = None,
            timeout: int = 300, use_db: bool = True,
            keys: list[str] | None = None,
            include_integration: bool = False,
            since_h: int = 24, levels: tuple[str, ...] = ("ERROR", "WARNING"),
            limit: int = 500,
            spool_fallback: bool = True,
            dry_run: bool = False) -> tuple[RunSummary, int, str]:
    """Exécute les collecteurs du scope. Retourne (summary, exit_code, message).

    Si dry_run=True : audit des vérifications (lints + tests) sans écrire en DB
    et sans compilation lourde. Utile pour auditer avant la phase de build.
    """
    python = python or sys.executable
    summary = RunSummary()
    conn = None
    run_id = None

    # ÉTAPE 1 (Durcissement) : Blocage strict dès les erreurs techniques
    if use_db and not dry_run:
        try:
            conn = pg.connect(root=root)
        except Exception as exc:
            return summary, 4, f"ARRÊT : Connexion DB impossible : {exc}"

    if conn is not None and not dry_run:
        run_id = store.start_run(conn, scope, cfg.larc_version(root), str(root), python)
        summary.run_id = run_id

    all_cands = []

    # ═══ ÉTAPE 0 : Cross-Client Validation (Larcommon) ═══
    if "LarcCommon" in (scope.projects or cfg.PROJETS):
        cands, errors = lc_validator.collect(
            root, python, scope.projects or cfg.PROJETS, timeout
        )
        all_cands.extend(cands)
        summary.nb_errors += len(errors)
        summary.errors.extend(errors)

        # Blocage STRICT : si un client ne peut pas importer Larcommon → ARRÊT
        if cands and not dry_run:
            return summary, 1, f"ARRÊT : {len(cands)} client(s) cannot import Larcommon"
        if summary.nb_errors > 0 and not dry_run:
            return summary, 3, f"ARRÊT : Erreur technique cross-client"

    # ÉTAPE 1 : Linting (1ère barrière)
    if scope.command in ("run", "lints"):
        cands, errors = linters_coll.collect(
            root, python, root / "scripts",
            scope.projects or cfg.PROJETS, keys or scope.linters, timeout)
        all_cands.extend(cands)
        summary.nb_errors += len(errors)
        summary.errors.extend(errors)
        # Blocage strict : si des erreurs technique ou des issues, arrêt immédiat en mode strict
        if summary.nb_errors > 0 and not dry_run:
            return summary, 3, f"ARRÊT : {summary.nb_errors} erreur(s) technique au linting"
        if all_cands and not dry_run:
            return summary, 1, f"ARRÊT : {len(all_cands)} problème(s) détecté(s) au linting"

    # ÉTAPE 2 : Tests (2ème barrière, seulement si linting propre)
    if scope.command in ("run", "tests"):
        cands, errors = pytest_collector.collect(
            root, python, scope.projects or None, include_integration,
            timeout=max(timeout, 900))
        all_cands.extend(cands)
        summary.nb_errors += len(errors)
        summary.errors.extend(errors)
        # Blocage strict : arrêt en mode strict
        if summary.nb_errors > 0 and not dry_run:
            return summary, 3, f"ARRÊT : {summary.nb_errors} erreur(s) technique aux tests"
        if cands and not dry_run:
            return summary, 1, f"ARRÊT : Tests échoués — {len(cands)} problème(s) détecté(s)"
    # ÉTAPE 3 (Errorlog, uniquement en mode non-dry-run)
    if scope.command in ("run", "errorlog") and not dry_run:
        if conn is not None:
            try:
                all_cands.extend(errorlog_coll.collect_pg(conn, since_h, levels, limit))
            except Exception as exc:  # noqa: BLE001
                summary.nb_errors += 1
                summary.errors.append(f"[errorlog] requête PG : {exc}")
        elif spool_fallback:
            all_cands.extend(errorlog_coll.collect_spool(root))

    # Mode DRY-RUN : rapport d'audit sans écriture DB
    if dry_run:
        if all_cands:
            summary.candidates = [asdict(c) for c in all_cands]
            msg = f"DRY-RUN AUDIT : {len(all_cands)} problème(s) détecté(s) (DB non modifiée)"
            return summary, 1, msg
        if summary.nb_errors:
            msg = f"DRY-RUN AUDIT : {summary.nb_errors} erreur(s) technique(s) (DB non modifiée)"
            return summary, 3, msg
        return summary, 0, "DRY-RUN AUDIT : audit propre (prêt pour la compilation)"

    if conn is not None and run_id is not None:
        seen = set()
        for cand in all_cands:
            action = store.upsert_candidate(conn, cand, run_id)
            if action == "created":
                summary.nb_new += 1
            elif action == "regressed":
                summary.nb_regressed += 1
            summary.nb_issues += 1
            seen.add(cand.signature())
        summary.nb_resolved = store.resolve_missing(conn, run_id, scope)
        store.snapshot_modules(conn, run_id, scan_modules(root, scope.projects or cfg.PROJETS))

        open_count = store.count_open(conn)
        run_status = ("error" if summary.nb_errors
                      else "issues" if open_count > 0 else "ok")
        store.finish_run(conn, run_id, summary, run_status)
        if conn is not None:
            try:
                conn.close()
            except Exception as exc:  # noqa: BLE001 — fermeture best-effort
                print(f"LarcForge : fermeture de connexion : {exc}",
                      file=sys.stderr)

        if open_count > 0:
            return summary, 1, f"{open_count} issue(s) ouverte(s) ou régressée(s)"
        if summary.nb_errors:
            return summary, 3, f"{summary.nb_errors} erreur(s) technique(s) de collecte"
        return summary, 0, "Aucune issue ouverte"

    # Mode --no-db : console pure (candidats exposés pour affichage/JSON)
    if all_cands:
        summary.candidates = [asdict(c) for c in all_cands]
        return summary, 1, f"{len(all_cands)} problème(s) détecté(s) (mode --no-db)"
    if summary.nb_errors:
        return summary, 3, f"{summary.nb_errors} erreur(s) technique(s) de collecte"
    return summary, 0, "Rien à signaler (mode --no-db)"


def execute_build(root: Path, app: str = "LarcForge", python: str | None = None,
                  timeout: int = 900, onefile: bool = False,
                  use_db: bool = True) -> tuple[RunSummary, int, str]:
    """Build PyInstaller d'une app : un larc_run, échec → issue larcforge:build.

    Succès → les issues build open de l'app passent résolues (le build refait
    prouve la correction) — la résolution automatique par scope ne s'applique
    pas (build est une action ponctuelle, pas une collecte de défauts).
    """
    python = python or sys.executable
    summary = RunSummary()
    conn = None
    run_id = None

    if use_db:
        try:
            conn = pg.connect(root=root)
        except Exception as exc:  # noqa: BLE001
            return summary, 4, f"Connexion DB impossible : {exc}"

    scope = RunScope(command="build", projects=[app])
    if conn is not None:
        run_id = store.start_run(conn, scope, cfg.larc_version(root), str(root), python)
        summary.run_id = run_id

    cands, errors, info = build_coll.collect(root, python, app, onefile, timeout)
    summary.nb_errors += len(errors)
    summary.errors.extend(errors)

    if conn is not None and run_id is not None:
        for cand in cands:
            action = store.upsert_candidate(conn, cand, run_id)
            if action == "created":
                summary.nb_new += 1
            elif action == "regressed":
                summary.nb_regressed += 1
            summary.nb_issues += 1
        if not cands and not errors:
            summary.nb_resolved = store.resolve_build_issues(conn, app, run_id)

        open_count = store.count_open(conn)
        run_status = ("error" if summary.nb_errors
                      else "issues" if open_count > 0 else "ok")
        store.finish_run(conn, run_id, summary, run_status)
        try:
            conn.close()
        except Exception as exc:  # noqa: BLE001 — fermeture best-effort
            print(f"LarcForge : fermeture de connexion : {exc}",
                  file=sys.stderr)

        ok_detail = ""
        if info.get("out"):
            ok_detail = f" — {info['out']} ({info['size'] or 0} octets)"
        if open_count > 0:
            return summary, 1, f"{open_count} issue(s) ouverte(s) ou régressée(s)"
        if summary.nb_errors:
            return summary, 3, f"{summary.nb_errors} erreur(s) technique(s) de collecte"
        return summary, 0, f"Build OK{ok_detail}"

    # Mode --no-db : console pure
    summary.candidates = [asdict(c) for c in cands]
    if cands:
        return summary, 1, f"Échec du build {app} (mode --no-db)"
    if errors:
        return summary, 3, "; ".join(errors)
    if info.get("out"):
        return summary, 0, f"Build OK — {info['out']} ({info['size'] or 0} octets)"
    return summary, 3, f"Build {app} : sortie introuvable"
