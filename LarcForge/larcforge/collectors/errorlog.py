"""Collecteur : erreurs enregistrées par les apps (error_log R1).

Source principale : table public.error_log (PostgreSQL).
Fallback si PG est down : spool SQLite local (.error_spool/*.db) en lecture seule.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..config import PROJETS
from ..models import IssueCandidate

DEFAULT_LEVELS = ("ERROR", "WARNING")


def collect_pg(conn, since_h: int = 24, levels: tuple[str, ...] = DEFAULT_LEVELS,
               limit: int = 500) -> list[IssueCandidate]:
    cands: list[IssueCandidate] = []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT app_name, app_version, level, module, func, line, message, traceback, context "
            "FROM public.error_log "
            "WHERE ts > now() - make_interval(hours => %s) AND level = ANY(%s) "
            "ORDER BY ts DESC LIMIT %s",
            (since_h, list(levels), limit),
        )
        for app, ver, lvl, mod, func, line, msg, tb, ctx in cur.fetchall():
            cands.append(IssueCandidate(
                source="errorlog",
                app_name=app,
                module=mod,
                func=func,
                line=line,
                level=lvl or "ERROR",
                message=msg,
                traceback=tb,
                context=ctx,
                larc_version=ver,
            ))
    return cands


def collect_spool(root: Path, limit: int = 500) -> list[IssueCandidate]:
    """Relecture des spools SQLite locaux (messages en attente d'envoi)."""
    cands: list[IssueCandidate] = []
    app_dirs = [root / p for p in [*PROJETS, "LarcCommon"]]
    for app_dir in app_dirs:
        spool_dir = app_dir / ".error_spool"
        if not spool_dir.is_dir():
            continue
        for db_path in spool_dir.glob("*.db"):
            try:
                con = sqlite3.connect(str(db_path))
                rows = con.execute(
                    "SELECT payload FROM pending ORDER BY id ASC LIMIT ?", (limit,)).fetchall()
                con.close()
            except Exception:
                continue
            for (payload,) in rows:
                try:
                    rec = json.loads(payload)
                except Exception:
                    rec = {}
                cands.append(IssueCandidate(
                    source="errorlog",
                    app_name=rec.get("app_name") or app_dir.name,
                    module=rec.get("module"),
                    func=rec.get("func"),
                    line=rec.get("line"),
                    level=rec.get("level") or "ERROR",
                    message=rec.get("message") or payload[:500],
                    traceback=rec.get("traceback"),
                    larc_version=rec.get("app_version"),
                ))
    return cands
