"""CLI LarcForge — `python -m larcforge <commande>`.

Codes de sortie : 0 propre · 1 issues open/regressed · 2 usage · 3 technique · 4 DB.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from . import config as cfg
from . import database as pg
from . import status as status_mod
from .ddl import apply_sql
from .models import RunScope
from .runner import execute

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError, ValueError):
    # Environnements sans reconfigure (StringIO des tests, flux fermés) :
    # l'encodage par défaut de la plateforme est utilisé tel quel.
    pass

_SQL_DDL = Path(__file__).resolve().parents[1] / "sql" / "01_larc_issue.sql"


# ---------------------------------------------------------------------------
# Parsing des arguments métier
# ---------------------------------------------------------------------------


def _parse_list(text: str | None) -> list[str] | None:
    return [p.strip() for p in text.split(",") if p.strip()] if text else None


def _parse_linters(text: str) -> list[str]:
    keys = [k.strip().upper() for k in text.split(",") if k.strip()]
    if not keys or "ALL" in keys:
        return cfg.LINTER_KEYS
    bad = [k for k in keys if k not in cfg.LINTER_KEYS]
    if bad:
        raise SystemExit(
            f"ERREUR : linters inconnus : {', '.join(bad)} "
            f"(disponibles : {', '.join(cfg.LINTER_KEYS)}, all)"
        )
    return keys


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------


def cmd_init_db(args) -> int:
    section = "SupabaseDatabase" if args.cloud else "IntranetDatabase"
    print(f"→ Application du DDL sur {section}…")
    try:
        conn = pg.connect(section=section, root=args.root)
    except Exception as exc:  # noqa: BLE001
        print(f"ERREUR DB : {exc}", file=sys.stderr)
        return 4
    ok, skips = apply_sql(conn, _SQL_DDL.read_text(encoding="utf-8"))
    try:
        conn.close()
    except Exception as exc:  # noqa: BLE001 — fermeture best-effort
        print(f"Note : fermeture de connexion : {exc}", file=sys.stderr)
    for s in ok:
        print(f"  ✓ {s}")
    if skips:
        print(f"\nIgnorées ({len(skips)}) — déjà en place ou erreur :")
        for s in skips[:10]:
            print(f"  • {s}")
        if len(skips) > 10:
            print(f"  … et {len(skips) - 10} autres")
    print(f"\n{len(ok)} instruction(s) appliquée(s), {len(skips)} ignorée(s).")
    if not ok:
        return 3
    return 0


def _scope_for(args, command: str) -> RunScope:
    return RunScope(
        command=command,
        linters=_parse_linters(getattr(args, "linters", "all")),
        projects=_parse_list(getattr(args, "projects", None)) or cfg.PROJETS,
        include_integration=getattr(args, "include_integration", False),
        since_h=getattr(args, "since", None),
        level=getattr(args, "level", None) or "ERROR,WARNING",
    )


def _levels(scope: RunScope) -> tuple[str, ...]:
    return tuple(l.strip() for l in (scope.level or "ERROR,WARNING").split(",") if l.strip())


def _run_and_report(args, scope: RunScope, verb: str) -> int:
    dry_run = getattr(args, "dry_run", False)
    summary, code, message = execute(
        args.root, scope,
        timeout=args.timeout,
        use_db=not args.no_db,
        keys=scope.linters,
        include_integration=scope.include_integration,
        since_h=scope.since_h or 24,
        levels=_levels(scope),
        limit=getattr(args, "limit", 500),
        dry_run=dry_run,
    )
    if dry_run:
        verb = f"{verb} (DRY-RUN)"
    return _report(args, summary, code, message, verb)


def _report(args, summary, code: int, message: str, verb: str) -> int:
    if args.json:
        out = {"command": verb, "exit_code": code, "message": message}
        out.update(summary.as_dict())
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return code
    print(f"\n=== {verb.upper()} — run #{summary.run_id or '—'} ===")
    print(f"  problèmes vus : {summary.nb_issues}  "
          f"nouveaux : {summary.nb_new}  "
          f"régressions : {summary.nb_regressed}  "
          f"résolus : {summary.nb_resolved}")
    if summary.nb_errors:
        print(f"  erreurs techniques : {summary.nb_errors}")
        for e in summary.errors[:5]:
            print(f"    • {e}")
    if args.no_db and summary.candidates:
        print(f"\n  Détail ({len(summary.candidates)}) :")
        for c in summary.candidates[:15]:
            loc = c.get("module") or ""
            rule = c.get("rule") or ""
            msg = (c.get("message") or "")[:70]
            print(f"    [{c.get('app_name')}] {loc} {rule} — {msg}")
        if len(summary.candidates) > 15:
            print(f"    … et {len(summary.candidates) - 15} autres")
    print(f"  → {message}  [exit {code}]")
    return code


def cmd_ui(args) -> int:
    """Lance l'interface graphique — import paresseux (PySide6 optionnel)."""
    try:
        from .ui.app import main
    except ImportError:
        print(
            "ERREUR : PySide6 manquant pour l'interface graphique.\n"
            'Installez : pip install "larcforge[gui]"',
            file=sys.stderr,
        )
        return 2
    return main(args.root, timeout=args.timeout)


def cmd_status(args) -> int:
    if args.no_db:
        print("ERREUR : status nécessite la base PostgreSQL (pas de --no-db).",
              file=sys.stderr)
        return 2
    try:
        conn = pg.connect(root=args.root)
    except Exception as exc:  # noqa: BLE001
        print(f"ERREUR DB : {exc}", file=sys.stderr)
        return 4
    try:
        if args.csv:
            print(status_mod.render_csv(conn, app=args.app, open_only=args.open), end="")
            return 0
        if args.json:
            print(json.dumps(status_mod.render_json(conn, app=args.app,
                                                    open_only=args.open),
                             ensure_ascii=False, indent=2, default=str))
            return 0
        print(status_mod.render(conn, app=args.app, open_only=args.open))
        return 0
    finally:
        try:
            conn.close()
        except Exception as exc:  # noqa: BLE001 — fermeture best-effort
            print(f"Note : fermeture de connexion : {exc}", file=sys.stderr)


def cmd_build(args) -> int:
    """Compile une app en exécutable Windows (PyInstaller)."""
    from .collectors import build as build_coll
    from .runner import execute_build

    if args.app not in build_coll.supported_apps():
        print(
            f"ERREUR : app « {args.app} » non supportée pour le build en v1 "
            f"(disponibles : {', '.join(build_coll.supported_apps())}).",
            file=sys.stderr,
        )
        return 2
    summary, code, message = execute_build(
        args.root, app=args.app, timeout=max(args.timeout, 900),
        onefile=args.onefile, use_db=not args.no_db)
    return _report(args, summary, code, message, f"build {args.app}")


def cmd_types(args) -> int:
    """Liste les types d'erreur auto-découverts : linters, catégories, couleurs, skills.

    C'est la preuve de l'auto-découverte : un linter déposé dans scripts/ avec un
    header LINTER_META apparaît ici sans modifier le moindre code.
    """
    from .taxonomy import (CATEGORIES, discover_linters, discover_skills,
                           all_categories)

    linters = discover_linters(args.root / "scripts")
    skills = discover_skills(args.root)

    if args.json:
        # hex lues directement dans la palette (source de vérité), sans
        # dépendre du thème actif — light ET dark sont listées.
        from larccommon.theme import ERROR_CATEGORY_COLORS
        cats = []
        for cat in all_categories():
            info = CATEGORIES[cat]
            colors = ERROR_CATEGORY_COLORS.get(cat)
            cats.append({
                "key": cat,
                "label": info["label"],
                "icon": info["icon"],
                "description": info["description"],
                "skill": info.get("skill"),
                "skill_label": skills.get(info["skill"]) if info.get("skill") else None,
                "colors": colors,
            })
        print(json.dumps(
            {"linters": linters, "categories": cats, "skills": skills},
            ensure_ascii=False, indent=2))
        return 0

    print("=" * 62)
    print("  TYPES D'ERREUR — AUTO-DÉCOUVERTE")
    print("=" * 62)
    print(f"\nLinters découverts ({len(linters)}) via LINTER_META :")
    for m in linters:
        print(f"  {m['key']:<5} {m['script']:<28} {m['label']:<22} [{m['category']}]")
    if not linters:
        print("  (aucun — vérifiez scripts/*.py)")

    print(f"\nCatégories ({len(all_categories())}) :")
    for cat in all_categories():
        info = CATEGORIES[cat]
        skill = info.get("skill")
        skill_txt = f" — skill: {skill}" + (f" ({skills[skill][:60]}…)" if skill in skills else "") if skill else ""
        print(f"  {cat:<11} {info['label']:<22} icône={info['icon']}{skill_txt}")

    print(f"\nSkills disponibles ({len(skills)}) : {', '.join(sorted(skills))}")
    print("\n" + "=" * 62)
    return 0


def cmd_help(args) -> int:
    """Référence des contrôles : les vérifications EXACTES de chaque linter/reviewer.

    Auto-découverte (taxonomy.discover_checks) : docstring des linters +
    corps des .claude/skills/*-review.md. Filtrable par --linter / --reviewer.
    """
    from .taxonomy import discover_checks

    checks = discover_checks(args.root)
    linters = checks["linters"]
    reviewers = checks["reviewers"]

    # --linter / --reviewer restreignent chacun l'autre liste : le filtre
    # affiche UNE catégorie de contrôles, pas le dossier entier.
    if args.linter:
        key = args.linter.upper()
        linters = [m for m in linters if m["key"].upper() == key]
        reviewers = []
        if not linters:
            print(f"ERREUR : linter inconnu : {args.linter}", file=sys.stderr)
            return 2
    if args.reviewer:
        reviewers = [r for r in reviewers if r["name"] == args.reviewer]
        linters = []
        if not reviewers:
            print(f"ERREUR : reviewer inconnu : {args.reviewer}", file=sys.stderr)
            return 2

    if args.json:
        print(json.dumps({"linters": linters, "reviewers": reviewers},
                         ensure_ascii=False, indent=2))
        return 0

    print("=" * 62)
    print("  RÉFÉRENCE DES CONTRÔLES")
    print("=" * 62)

    for m in linters:
        print(f"\n┌─ [{m['key']}] {m['label']}")
        print(f"│  script    : {m['script']}")
        print(f"│  catégorie : {m['category']}"
              + (f" · skill : {m['skill']}" if m.get("skill") else ""))
        print(f"│  résumé    : {m.get('description', '')}")
        doc = (m.get("doc") or "").strip()
        if doc:
            print("│")
            for line in doc.splitlines():
                print(f"│  {line}")

    for r in reviewers:
        print(f"\n┌─ {r['name']}")
        print(f"│  catégorie  : {r.get('category') or '—'}"
              + (f" · déclencheur : {r['trigger']}" if r.get("trigger") else ""))
        print(f"│  résumé     : {r.get('description') or '—'}")
        body = (r.get("body") or "").strip()
        if body:
            print("│")
            for line in body.splitlines():
                print(f"│  {line}")

    print("\n" + "=" * 62)
    return 0


def cmd_docs(args) -> int:
    """Génère la doc Markdown de référence (docs/reference-controles.md).

    Consommée comme documentation humaine ; régénérée à chaque ajout/édition
    d'un linter ou d'un reviewer.
    """
    from .reference import render_markdown
    from .taxonomy import discover_checks

    checks = discover_checks(args.root)
    out = Path(args.out) if args.out else \
        Path(__file__).resolve().parents[1] / "docs" / "reference-controles.md"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_markdown(checks), encoding="utf-8")
    except OSError as exc:  # noqa: BLE001 — rendu fichier best-effort
        print(f"ERREUR : écriture impossible ({out}) : {exc}", file=sys.stderr)
        return 3
    print(f"→ {out}")
    print(f"  {len(checks['linters'])} linter(s), "
          f"{len(checks['reviewers'])} reviewer(s) documentés.")
    return 0


# ---------------------------------------------------------------------------
# ArgumentParser
# ---------------------------------------------------------------------------


def _add_globals(p: argparse.ArgumentParser) -> None:
    """Flags globaux — acceptés avant ET après la sous-commande."""
    p.add_argument("--root", default=None,
                   help="racine du monorepo (défaut : détection depuis le package)")
    p.add_argument("--no-db", action="store_true",
                   help="collecte sans écrire dans PostgreSQL (console pure)")
    p.add_argument("--timeout", type=int, default=300,
                   help="timeout par collecteur en secondes (défaut 300)")
    p.add_argument("--json", action="store_true",
                   help="sortie JSON")
    p.add_argument("--dry-run", action="store_true",
                   help="mode audit : vérifications seulement, sans écriture DB ni compilation")


def _add_globals_sub(p: argparse.ArgumentParser) -> None:
    """Flags globaux pour les sous-commandes — default=SUPPRESS.

    Sans cela, les defaults des sous-parsers (store_true → False) écrasent la
    valeur déjà posée par le parser principal : `--no-db run` perdrait le flag.
    Le parser principal garantit les defaults ; le sous-parser ne pose
    l'attribut que si le flag est effectivement fourni après la sous-commande.
    """
    p.add_argument("--root", default=argparse.SUPPRESS,
                   help=argparse.SUPPRESS)
    p.add_argument("--no-db", action="store_true", default=argparse.SUPPRESS,
                   help=argparse.SUPPRESS)
    p.add_argument("--timeout", type=int, default=argparse.SUPPRESS,
                   help=argparse.SUPPRESS)
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help=argparse.SUPPRESS)
    p.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS,
                   help=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="larcforge",
        description="Poste de contrôle unique : linters + pytest + error_log, "
                    "registre larc_issue avec détection de régression.",
        epilog="Codes de sortie : 0 propre · 1 issues open/regressed · "
               "2 usage · 3 technique · 4 DB.",
    )
    parser.add_argument("--version", action="store_true",
                        help="affiche la version et quitte")
    _add_globals(parser)
    sub = parser.add_subparsers(dest="command", metavar="commande")
    globals_only = argparse.ArgumentParser(add_help=False)
    _add_globals_sub(globals_only)

    p = sub.add_parser("init-db", parents=[globals_only],
                       help="crée les tables larc_issue/larc_run/larc_run_module")
    p.add_argument("--cloud", action="store_true",
                   help="utilise la section SupabaseDatabase au lieu d'IntranetDatabase")
    p.set_defaults(func=cmd_init_db)

    p = sub.add_parser("lints", parents=[globals_only],
                       help="lance les linters (défaut : tous, 8 projets)")
    p.add_argument("--projects", default=None, help="liste séparée par des virgules")
    p.add_argument("--linters", default="all",
                   help="clés séparées par des virgules, ex. R,D,V,C,S (défaut all)")
    p.set_defaults(func=lambda a: _run_and_report(a, _scope_for(a, "lints"), "lints"))

    p = sub.add_parser("tests", parents=[globals_only],
                       help="lance pytest des repos avec tests/")
    p.add_argument("--projects", default=None, help="liste séparée par des virgules")
    p.add_argument("--include-integration", action="store_true",
                   help="inclut les tests marqués integration")
    p.set_defaults(func=lambda a: _run_and_report(a, _scope_for(a, "tests"), "tests"))

    p = sub.add_parser("errorlog", parents=[globals_only],
                       help="lit error_log (24 h) — fallback spool si PG down")
    p.add_argument("--since", type=int, default=24, help="fenêtre en heures (défaut 24)")
    p.add_argument("--level", default=None, help="niveaux, ex. ERROR ou ERROR,WARNING")
    p.add_argument("--limit", type=int, default=500, help="max d'entrées (défaut 500)")
    p.set_defaults(func=lambda a: _run_and_report(a, _scope_for(a, "errorlog"), "errorlog"))

    p = sub.add_parser("run", parents=[globals_only],
                       help="run complet : lints → tests → errorlog")
    p.set_defaults(func=lambda a: _run_and_report(a, _scope_for(a, "run"), "run"))

    p = sub.add_parser("status", parents=[globals_only],
                       help="rapport : comptes, régressions, modules modifiés")
    p.add_argument("--app", default=None, help="filtre par application")
    p.add_argument("--open", action="store_true", help="issues ouvertes/régressées uniquement")
    p.add_argument("--csv", action="store_true", help="export CSV de toutes les issues")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("build", parents=[globals_only],
                       help="compile une app en exécutable Windows (PyInstaller)")
    p.add_argument("--app", default="LarcForge",
                   help="app cible (défaut LarcForge)")
    p.add_argument("--onefile", action="store_true",
                   help="exécutable mono-fichier (compilation plus lente)")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("ui", parents=[globals_only],
                       help="lance l'interface graphique (dashboard de contrôle)")
    p.set_defaults(func=cmd_ui)

    p = sub.add_parser("types", parents=[globals_only],
                       help="liste les types d'erreur auto-découverts (linters, catégories, couleurs, skills)")
    p.set_defaults(func=cmd_types)

    p = sub.add_parser("help", parents=[globals_only],
                       help="référence des contrôles : vérifications exactes de chaque linter/reviewer")
    p.add_argument("--linter", default=None,
                   help="affiche un seul linter (ex. D, CTR)")
    p.add_argument("--reviewer", default=None,
                   help="affiche un seul reviewer (ex. design-review)")
    p.set_defaults(func=cmd_help)

    p = sub.add_parser("docs", parents=[globals_only],
                       help="génère la doc Markdown de référence (docs/reference-controles.md)")
    p.add_argument("--out", default=None,
                   help="fichier de sortie (défaut LarcForge/docs/reference-controles.md)")
    p.set_defaults(func=cmd_docs)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"larcforge {__version__}")
        return 0
    if not args.command:
        parser.print_help()
        return 2

    try:
        args.root = cfg.find_root(args.root)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
