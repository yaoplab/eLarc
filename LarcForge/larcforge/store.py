"""Écriture dans larc_issue / larc_run / larc_run_module : upsert + transitions.

Boucle open -> resolved -> regressed :
- un candidat présent sur une ligne 'resolved' => regressed (réapparition).
- une issue vue au run précédent valide (même commande, même scope) et absente
  du run courant => resolved (plus détectée).
"""

from __future__ import annotations

import json

from .models import IssueCandidate, RunScope, RunSummary


def start_run(conn, scope: RunScope, larc_version: str, root: str, python: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO public.larc_run (command, status, scope, python, larc_version, root) "
            "VALUES (%s, 'running', %s::jsonb, %s, %s, %s) RETURNING id",
            (scope.command, json.dumps(scope.__dict__, default=str), python, larc_version, root),
        )
        return cur.fetchone()[0]


def finish_run(conn, run_id: int, summary: RunSummary, status: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE public.larc_run SET finished_at = now(), status = %s, "
            "nb_issues = %s, nb_new = %s, nb_regressed = %s, nb_resolved = %s, nb_errors = %s "
            "WHERE id = %s",
            (status, summary.nb_issues, summary.nb_new, summary.nb_regressed,
             summary.nb_resolved, summary.nb_errors, run_id),
        )


def upsert_candidate(conn, cand: IssueCandidate, run_id: int) -> str:
    """Crée ou met à jour une issue. Retourne 'created' | 'updated' | 'regressed'."""
    sig = cand.signature()
    context = json.dumps(cand.context) if cand.context else None
    with conn.cursor() as cur:
        cur.execute("SELECT id, status FROM public.larc_issue WHERE signature = %s", (sig,))
        row = cur.fetchone()

        if row is None:
            cur.execute(
                "INSERT INTO public.larc_issue (signature, status, occurrences, "
                "first_seen_run, last_seen_run, source, app_name, module, func, line, "
                "level, rule, message, traceback, context, larc_version) "
                "VALUES (%s, 'open', 1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "COALESCE(%s, '{}'::jsonb), %s)",
                (sig, run_id, run_id, cand.source, cand.app_name, cand.module, cand.func,
                 cand.line, cand.level, cand.rule, cand.message, cand.traceback,
                 context, cand.larc_version),
            )
            return "created"

        issue_id, status = row
        if status == "resolved":
            # Réapparition d'un bug corrigé => régression
            cur.execute(
                "UPDATE public.larc_issue SET status = 'regressed', "
                "regressed_count = regressed_count + 1, "
                "first_regressed_at = COALESCE(first_regressed_at, now()), "
                "occurrences = occurrences + 1, last_seen = now(), last_seen_run = %s, "
                "resolved_at = NULL, resolution_note = NULL, line = COALESCE(%s, line), "
                "message = %s, traceback = COALESCE(%s, traceback), "
                "context = COALESCE(%s::jsonb, context), larc_version = COALESCE(%s, larc_version) "
                "WHERE id = %s",
                (run_id, cand.line, cand.message, cand.traceback, context,
                 cand.larc_version, issue_id),
            )
            return "regressed"

        # open ou regressed => occurrence de plus
        cur.execute(
            "UPDATE public.larc_issue SET occurrences = occurrences + 1, "
            "last_seen = now(), last_seen_run = %s, line = COALESCE(%s, line), "
            "message = %s, traceback = COALESCE(%s, traceback), "
            "context = COALESCE(%s::jsonb, context), larc_version = COALESCE(%s, larc_version) "
            "WHERE id = %s",
            (run_id, cand.line, cand.message, cand.traceback, context,
             cand.larc_version, issue_id),
        )
        return "updated"


def resolve_missing(conn, run_id: int, scope: RunScope) -> int:
    """Résout les issues vues au run précédent valide (même commande + même scope) et absentes.

    Retourne le nombre d'issues résolues. Garde-fous : le run précédent doit être
    terminé sans erreur ET avoir un scope identique (sinon un périmètre réduit
    créerait des faux « résolus »).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, scope FROM public.larc_run "
            "WHERE command = %s AND id < %s AND status <> 'error' AND status <> 'running' "
            "ORDER BY id DESC LIMIT 1",
            (scope.command, run_id),
        )
        row = cur.fetchone()
        if row is None:
            return 0
        prev_id, prev_scope = row
        if json.dumps(prev_scope, sort_keys=True, default=str) != scope.canonical():
            return 0
        cur.execute(
            "UPDATE public.larc_issue SET status = 'resolved', resolution_note = %s, "
            "resolved_at = now(), resolved_run = %s "
            "WHERE last_seen_run = %s AND status IN ('open', 'regressed')",
            (f"Plus détectée au run #{run_id}", run_id, prev_id),
        )
        return cur.rowcount


def count_open(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM public.larc_issue WHERE status IN ('open', 'regressed')")
        return cur.fetchone()[0]


def resolve_issue(conn, issue_id: int, note: str) -> int:
    """Marque une issue open/regressed comme résolue (résolution manuelle IHM).

    Retourne le rowcount (0 si l'issue est déjà résolue ou inexistante).
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE public.larc_issue SET status = 'resolved', resolution_note = %s, "
            "resolved_at = now() WHERE id = %s AND status IN ('open', 'regressed')",
            (note, issue_id),
        )
        return cur.rowcount


def resolve_build_issues(conn, app: str, run_id: int) -> int:
    """Résout les issues larcforge:build open/regressed d'une app.

    Appelé quand le build de l'app réussit : le fait de refaire le build
    prouve la correction (pas de garde-fou de scope — build est une action
    ponctuelle, pas une collecte).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM public.larc_issue WHERE source = 'larcforge:build' "
            "AND app_name = %s AND status IN ('open', 'regressed')",
            (app,),
        )
        rows = cur.fetchall()
    n = 0
    for (issue_id,) in rows:
        n += resolve_issue(conn, issue_id, f"Build réussi (run #{run_id})")
    return n


def reopen_issue(conn, issue_id: int) -> int:
    """Réouvre une issue resolved (remet à open, efface note et date de résolution).

    Retourne le rowcount (0 si l'issue n'était pas resolved ou inexistante).
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE public.larc_issue SET status = 'open', resolution_note = NULL, "
            "resolved_at = NULL WHERE id = %s AND status = 'resolved'",
            (issue_id,),
        )
        return cur.rowcount


def abort_run(conn, run_id: int) -> int:
    """Marque un run 'running' comme 'error' — fermeture de l'IHM pendant un
    run. Ciblé par id : ne touche jamais un autre run en cours."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE public.larc_run SET status = 'error' WHERE id = %s "
            "AND status = 'running'",
            (run_id,),
        )
        return cur.rowcount


def snapshot_modules(conn, run_id: int, modules: list[tuple[str, str, int, int]]) -> None:
    """Enregistre l'état (mtime_ns, size) des fichiers .py scannés pour ce run."""
    with conn.cursor() as cur:
        for app, mod, mtime_ns, size in modules:
            cur.execute(
                "INSERT INTO public.larc_run_module (run_id, app_name, module, mtime_ns, size) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (run_id, app_name, module) DO NOTHING",
                (run_id, app, mod, mtime_ns, size),
            )
