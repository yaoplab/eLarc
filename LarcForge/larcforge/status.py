"""Rapport status : comptes, dernières issues, régressions, modules modifiés, alertes conflit."""

from __future__ import annotations

import csv
import io
from typing import Any

# ---------------------------------------------------------------------------
# Requêtes
# ---------------------------------------------------------------------------


def last_runs(conn, n: int = 2) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, command, status, started_at, finished_at, nb_issues, nb_new, "
            "nb_regressed, nb_resolved, nb_errors "
            "FROM public.larc_run WHERE status <> 'running' ORDER BY id DESC LIMIT %s",
            (n,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def counts_by_status(conn) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute("SELECT status, count(*) FROM public.larc_issue GROUP BY status")
        return {s: c for s, c in cur.fetchall()}


def counts_by_category(conn) -> dict[str, int]:
    """Issues open/regressed regroupées par catégorie (dérivée de la source).

    La catégorie est calculée en Python (pas de colonne en base) : GROUP BY
    source en SQL, puis mappage source → catégorie via la taxonomie. Les
    catégories sans issue n'apparaissent pas (l'Accueil les complète à 0).
    """
    from .taxonomy import category_for

    with conn.cursor() as cur:
        cur.execute(
            "SELECT source, count(*) FROM public.v_larc_issues "
            "WHERE status IN ('open', 'regressed') GROUP BY source")
        rows = cur.fetchall()
    counts: dict[str, int] = {}
    for source, c in rows:
        cat = category_for(source)
        counts[cat] = counts.get(cat, 0) + c
    return counts


def counts_by_app(conn) -> list[tuple[str, str, int]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT app_name, status, count(*) FROM public.larc_issue "
            "GROUP BY app_name, status ORDER BY app_name, status")
        return cur.fetchall()


def open_issues(conn, app: str | None = None, limit: int = 15) -> list[dict]:
    q = ("SELECT id, status, app_name, module, rule, message, occurrences, last_seen "
         "FROM public.v_larc_issues WHERE status IN ('open', 'regressed')")
    args: list[Any] = []
    if app:
        q += " AND app_name = %s"
        args.append(app)
    q += " ORDER BY last_seen DESC LIMIT %s"
    args.append(limit)
    with conn.cursor() as cur:
        cur.execute(q, args)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def running_run(conn) -> dict | None:
    """Le run en cours, s'il y en a un (progression IHM — last_runs l'exclut)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, command, started_at FROM public.larc_run "
            "WHERE status = 'running' ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))


def list_issues(conn, status: str | None = None, app: str | None = None,
                source: str | None = None, search: str | None = None,
                limit: int = 500) -> list[dict]:
    """Registre complet (vue v_larc_issues) avec filtres combinables."""
    q = ("SELECT id, status, occurrences, source, app_name, module, func, line, "
         "level, rule, message, last_seen FROM public.v_larc_issues WHERE TRUE")
    args: list[Any] = []
    if status:
        q += " AND status = %s"
        args.append(status)
    if app:
        q += " AND app_name = %s"
        args.append(app)
    if source:
        if source == "linter":
            q += " AND source LIKE %s"  # linter:R, linter:D…
            args.append("linter:%")
        else:
            q += " AND source = %s"
            args.append(source)
    if search:
        q += " AND (message ILIKE %s OR module ILIKE %s)"
        pat = f"%{search}%"
        args.extend((pat, pat))
    q += " ORDER BY last_seen DESC LIMIT %s"
    args.append(limit)
    with conn.cursor() as cur:
        cur.execute(q, args)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def list_apps(conn) -> list[str]:
    """Apps présentes dans le registre (pour le filtre du panneau Issues)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT app_name FROM public.v_larc_issues "
            "ORDER BY app_name")
        return [r[0] for r in cur.fetchall()]


def issue_detail(conn, issue_id: int) -> dict | None:
    """Toutes les colonnes d'une fiche (traceback, context, notes de résolution)."""
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM public.larc_issue WHERE id = %s", (issue_id,))
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))


def regressed_issues(conn, limit: int = 10) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, app_name, module, rule, message, regressed_count, "
            "first_regressed_at, occurrences FROM public.v_larc_issues "
            "WHERE status = 'regressed' ORDER BY first_regressed_at DESC LIMIT %s",
            (limit,),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _snapshot(conn, run_id: int) -> dict[tuple[str, str], tuple[int, int]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT app_name, module, mtime_ns, size FROM public.larc_run_module "
            "WHERE run_id = %s", (run_id,))
        return {(a, m): (mt, s) for a, m, mt, s in cur.fetchall()}


def _module_changes(conn) -> list[tuple[str, str, str]]:
    """(app_name, module, nature) modifiés entre les deux derniers runs."""
    runs = last_runs(conn, 2)
    if len(runs) < 2:
        return []
    older, newer = runs[1]["id"], runs[0]["id"]
    prev = _snapshot(conn, older)
    cur_ = _snapshot(conn, newer)
    changes = []
    for key in sorted(cur_):
        if key in prev and prev[key] != cur_[key]:
            changes.append((key[0], key[1], "modifié"))
        elif key not in prev:
            changes.append((key[0], key[1], "nouveau"))
    for key in sorted(prev):
        if key not in cur_:
            changes.append((key[0], key[1], "supprimé"))
    return changes


def module_diffs(conn) -> list[str]:
    """Modules modifiés/supprimés entre les deux derniers runs (substitut git)."""
    return [f"{module} ({nature})" for _, module, nature in _module_changes(conn)]


def scope_alerts(conn) -> list[str]:
    """Modules modifiés depuis le dernier run SANS issue résolue associée ce run.

    C'est le signal d'un changement hors périmètre : un module a bougé alors
    qu'aucune issue de ce module n'est passée 'resolved' au dernier run —
    la modification ne corrige donc rien de répertorié.
    """
    changes = _module_changes(conn)
    if not changes:
        return []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT app_name, module FROM public.larc_issue "
            "WHERE resolved_run = (SELECT max(id) FROM public.larc_run "
            "                       WHERE status <> 'running') "
            "AND module IS NOT NULL")
        fixed = set(cur.fetchall())
    return [
        f"{module} ({nature}) — aucune issue de ce module résolue au dernier "
        f"run : changement hors périmètre ?"
        for app, module, nature in changes if (app, module) not in fixed
    ]


def conflict_alerts(conn) -> list[str]:
    """Issues open/regressed dont le module a changé depuis leur dernière détection."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT max(id) FROM public.larc_run WHERE status <> 'running'")
        latest = cur.fetchone()[0]
        if latest is None:
            return []
        cur.execute(
            "SELECT id, app_name, module, last_seen_run FROM public.larc_issue "
            "WHERE status IN ('open', 'regressed') AND last_seen_run IS NOT NULL "
            "AND module IS NOT NULL")
        issues = cur.fetchall()

        alerts = []
        for issue_id, app, module, seen_run in issues:
            if seen_run >= latest:
                continue
            cur.execute(
                "SELECT mtime_ns, size FROM public.larc_run_module "
                "WHERE run_id = %s AND app_name = %s AND module = %s",
                (seen_run, app, module))
            old = cur.fetchone()
            cur.execute(
                "SELECT mtime_ns, size FROM public.larc_run_module "
                "WHERE run_id = %s AND app_name = %s AND module = %s",
                (latest, app, module))
            new = cur.fetchone()
            if old is not None and new is None:
                alerts.append(
                    f"issue #{issue_id} : {module} a été supprimé depuis la "
                    f"dernière détection (run #{seen_run}) — vérifier la validité")
            elif old is not None and new is not None and old != new:
                alerts.append(
                    f"issue #{issue_id} : {module} modifié depuis la dernière "
                    f"détection (run #{seen_run}) — vérifier si elle est toujours valide")
    return alerts


# ---------------------------------------------------------------------------
# Rendu
# ---------------------------------------------------------------------------


def render(conn, app: str | None = None, open_only: bool = False) -> str:
    lines: list[str] = []
    lines.append("=" * 62)
    lines.append("  LARCFORGE — ÉTAT DU REGISTRE")
    lines.append("=" * 62)

    counts = counts_by_status(conn)
    lines.append(f"\nIssues par statut : open={counts.get('open', 0)}  "
                 f"regressed={counts.get('regressed', 0)}  "
                 f"resolved={counts.get('resolved', 0)}")

    by_app = counts_by_app(conn)
    if by_app:
        lines.append("\nPar application (app | open | regressed | resolved) :")
        for app_name, status, c in by_app:
            if app and app_name != app:
                continue
            lines.append(f"  {app_name:<16} {status:<10} {c}")

    runs = last_runs(conn, 2)
    if runs:
        r = runs[0]
        lines.append(f"\nDernier run #{r['id']} : commande={r['command']} statut={r['status']} "
                     f"(issues={r['nb_issues']} new={r['nb_new']} "
                     f"regressed={r['nb_regressed']} resolved={r['nb_resolved']} "
                     f"errors={r['nb_errors']})")

    if not open_only:
        diffs = module_diffs(conn)
        if diffs:
            lines.append(f"\nModules modifiés depuis le dernier run ({len(diffs)}) :")
            for d in diffs[:20]:
                lines.append(f"  • {d}")
            if len(diffs) > 20:
                lines.append(f"  … et {len(diffs) - 20} autres")

        scopes = scope_alerts(conn)
        if scopes:
            lines.append(f"\nPérimètre de correction ({len(scopes)}) — "
                         f"modules modifiés sans issue résolue associée :")
            lines.extend(f"  {s}" for s in scopes)

    reg = regressed_issues(conn)
    if reg:
        lines.append(f"\nRégressions ({len(reg)}) :")
        for r in reg:
            lines.append(f"  #{r['id']} [{r['app_name']}] {r['rule'] or ''} — {r['message'][:60]} "
                         f"(x{r['regressed_count']})")

    alerts = conflict_alerts(conn)
    if alerts:
        lines.append(f"\nAlertes de conflit ({len(alerts)}) :")
        lines.extend(f"  {a}" for a in alerts)

    issues = open_issues(conn, app)
    if issues:
        lines.append(f"\nDernières issues ouvertes/régressées ({len(issues)}) :")
        for i in issues:
            lines.append(f"  #{i['id']} [{i['status']:<9}] [{i['app_name']}] "
                         f"{i['module'] or ''} {i['rule'] or ''} — {i['message'][:50]}")
    elif not open_only:
        lines.append("\nAucune issue ouverte. 🎉")

    lines.append("\n" + "=" * 62)
    return "\n".join(lines)


def render_json(conn, app: str | None = None, open_only: bool = False) -> dict:
    return {
        "counts": counts_by_status(conn),
        "by_category": counts_by_category(conn),
        "by_app": [{"app": a, "status": s, "count": c} for a, s, c in counts_by_app(conn)
                   if not app or a == app],
        "runs": last_runs(conn, 2),
        "regressed": regressed_issues(conn),
        "modules_changed": module_diffs(conn),
        "scope_alerts": scope_alerts(conn),
        "conflict_alerts": conflict_alerts(conn),
        "open_issues": open_issues(conn, app),
    }


def render_csv(conn, app: str | None = None, open_only: bool = False) -> str:
    with conn.cursor() as cur:
        q = ("SELECT id, status, occurrences, source, app_name, module, func, line, "
             "level, rule, message, larc_version, first_seen, last_seen "
             "FROM public.v_larc_issues WHERE TRUE")
        args: list[Any] = []
        if open_only:
            q += " AND status IN ('open', 'regressed')"
        if app:
            q += " AND app_name = %s"
            args.append(app)
        q += " ORDER BY last_seen DESC"
        cur.execute(q, args)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(cols)
    writer.writerows(rows)
    return out.getvalue()
