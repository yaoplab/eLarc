#!/usr/bin/env python3
"""Linter : tout except qui avale une exception doit la reporter (error_reporting).

Règle R-ERR (skill telemetry) : un `except Exception` qui capture une erreur
(log, affichage, pass, rollback…) sans appeler `get_reporter().report_exception`
rend l'erreur invisible pour LarcForge (error_log). Ce linter signale ces
handlers pour que les modifications futures piègent leurs erreurs.

Usage:
  python scripts/lint_error_reporting.py                     # Tous les projets
  python scripts/lint_error_reporting.py --dir .\\LarcSuperviseur
  python scripts/lint_error_reporting.py --json
"""

LINTER_META = {
    "key": "RERR",
    "label": "Reporting des erreurs",
    "category": "telemetry",
    "description": "except Exception sans report_exception — erreur invisible pour LarcForge",
    "skill": "telemetry",
}

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJETS = [ROOT / n for n in (
    "LarcSuperviseur", "LarcSecretaire", "LarcProf", "LarcHub",
    "LarcConfig", "LarcCommon", "LarcRH", "LarcCompta",
)]
EXCLUDE = {"tests", "__pycache__", ".venv", "dist", "build", "sql"}
# Le mécanisme de reporting lui-même : le reporter ne doit pas se rapporter
EXCLUDE_FILES = {
    "LarcCommon/larccommon/error_reporting.py",
    "LarcCommon/larccommon/logger.py",
}


def _has_report(body) -> bool:
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
            if "report" in name or "get_reporter" in name:
                return True
    return False


def scan_file(path: Path) -> list[dict]:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    if rel in EXCLUDE_FILES:
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    issues = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if handler.type is None:
                continue  # except nu — autre règle (C13)
            name = getattr(handler.type, "id", "") or getattr(handler.type, "attr", "")
            if name not in ("Exception", "BaseException", "RuntimeError", "ValueError",
                            "KeyError", "TypeError", "OSError", "ConnectionError",
                            "psycopg2", "ImportError"):
                continue
            if _has_report(handler.body):
                continue
            # except avec corps réel qui avale sans report → violation
            issues.append({
                "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                "line": handler.lineno,
                "rule": "RERR",
                "message": "except sans report_exception — erreur invisible pour LarcForge",
                "func": "",
                "level": "WARNING",
            })
    return issues


def main() -> int:
    args = sys.argv[1:]
    target = None
    as_json = "--json" in args
    if "--dir" in args:
        target = ROOT / args[args.index("--dir") + 1]
    projects = [target] if target else PROJETS
    all_issues = []
    for proot in projects:
        if not proot.exists():
            continue
        for path in proot.rglob("*.py"):
            if any(part in EXCLUDE for part in path.parts):
                continue
            all_issues.extend(scan_file(path))
    all_issues.sort(key=lambda i: (i["file"], i["line"]))
    if as_json:
        print(json.dumps(all_issues, ensure_ascii=False, indent=1))
    else:
        for i in all_issues:
            print(f"{i['file']}:{i['line']}  {i['message']}")
        print(f"\n{len(all_issues)} handler(s) sans report_exception")
    return 1 if all_issues else 0


if __name__ == "__main__":
    sys.exit(main())
