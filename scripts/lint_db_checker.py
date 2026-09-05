#!/usr/bin/env python3
"""Linter: vérifie les règles du skill database-operations.

Détecte :
  - import psycopg2 hors de database.py
  - Instanciation directe de Database() (doit utiliser le singleton db)
  - db.server_conn sans vérification is_server_connected
  - Credentials de connexion en dur

Usage:
  python scripts/lint_db_checker.py                        # Tous les projets
  python scripts/lint_db_checker.py --dir .\LarcProf         # Un seul projet
  python scripts/lint_db_checker.py --json                   # Sortie JSON
"""

LINTER_META = {
    "key": "DB",
    "label": "Connexions DB",
    "category": "data",
    "description": "Import psycopg2 hors database.py, singleton ignoré, credentials en dur",
    "skill": "database-operations",
}

import re
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJETS = [ROOT / n for n in (
    "LarcSuperviseur",
    "LarcSecretaire",
    "LarcProf",
    "LarcHub",
    "LarcCommon",
)]

DB_MODULE = 'database.py'
VIOLATIONS = []


def scan_file(filepath: Path):
    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception:
        return
    lines = source.split('\n')
    is_db_module = DB_MODULE in str(filepath)

    # 1. import psycopg2 hors de database.py
    for i, line in enumerate(lines, 1):
        if re.match(r'^(import psycopg2|from psycopg2)', line):
            if not is_db_module:
                VIOLATIONS.append({
                    'file': str(filepath),
                    'line': i,
                    'rule': 'db-C1',
                    'severity': 'P0',
                    'message': 'import psycopg2 hors de database.py',
                    'fix': 'Utiliser : from larccommon.database import db',
                })

    # 2. Database() instancié directement
    for i, line in enumerate(lines, 1):
        if 'Database()' in line and 'class Database' not in line and not is_db_module:
            # Exclure les commentaires
            if line.strip().startswith('#'):
                continue
            VIOLATIONS.append({
                'file': str(filepath),
                'line': i,
                'rule': 'db-C2',
                'severity': 'P0',
                'message': 'Database() instancié directement',
                'fix': 'Utiliser le singleton : from larccommon.database import db',
            })

    # 3. db.server_conn.cursor() sans vérification is_server_connected
    if not is_db_module:
        has_conn = 'db.server_conn' in source or 'server_conn.cursor()' in source
        has_check = 'is_server_connected' in source or 'if db.server_conn' in source or 'if conn is None' in source
        if has_conn and not has_check:
            VIOLATIONS.append({
                'file': str(filepath),
                'line': 0,
                'rule': 'db-C3',
                'severity': 'P1',
                'message': 'db.server_conn utilisé sans vérifier is_server_connected',
                'fix': 'Ajouter : if not db.is_server_connected: return',
            })

    # 4. Connexion directe psycopg2.connect()
    for i, line in enumerate(lines, 1):
        if 'psycopg2.connect(' in line and not is_db_module:
            VIOLATIONS.append({
                'file': str(filepath),
                'line': i,
                'rule': 'db-C4',
                'severity': 'P0',
                'message': 'psycopg2.connect() direct hors de database.py',
                'fix': 'Utiliser db.connect_intranet() ou db.connect_cloud()',
            })

    # 5. Credentials de connexion en dur
    cred_patterns = [
        (r"host\s*=\s*['\"]\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}['\"]", "Host IP en dur"),
        (r"port\s*=\s*5432", "Port PostgreSQL en dur"),
        (r"dbname\s*=\s*['\"]\w+['\"]", "Nom de DB en dur"),
        (r"user\s*=\s*['\"]postgres['\"]", "User postgres en dur"),
    ]
    for i, line in enumerate(lines, 1):
        for pattern, msg in cred_patterns:
            if re.search(pattern, line) and not is_db_module and 'fallback=' not in line:
                VIOLATIONS.append({
                    'file': str(filepath),
                    'line': i,
                    'rule': 'db-C5',
                    'severity': 'P0',
                    'message': msg,
                    'fix': 'Lire depuis config.ini via Database._pg_params()',
                })


def scan_directory(directory: Path):
    for filepath in directory.rglob("*.py"):
        if '__pycache__' in str(filepath):
            continue
        if 'test_' in filepath.name:
            continue
        if '.venv' in str(filepath):
            continue
        scan_file(filepath)


def main():
    # Force UTF-8 pour la sortie terminal (Windows cp1252 fix)
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    import argparse
    parser = argparse.ArgumentParser(description="Linter database Larc")
    parser.add_argument("--dir", help="Repertoire a scanner")
    parser.add_argument("--json", action="store_true", help="Sortie JSON")
    parser.add_argument("--fix", action="store_true", help="Afficher les suggestions de correction")
    args = parser.parse_args()

    if args.dir:
        dirs = [Path(args.dir)]
    else:
        dirs = [Path(d) for d in PROJETS if Path(d).exists()]

    for d in dirs:
        if d.exists():
            scan_directory(d)

    if args.json:
        import json
        print(json.dumps(VIOLATIONS, ensure_ascii=False, indent=2))
    else:
        if not VIOLATIONS:
            print("OK 0 violation - base de donnees conforme")
            return 0

        p0 = [v for v in VIOLATIONS if v['severity'] == 'P0']
        p1 = [v for v in VIOLATIONS if v['severity'] == 'P1']
        print(f"X {len(p0)} P0, {len(p1)} P1 violations\n")
        for v in sorted(VIOLATIONS, key=lambda x: (x['severity'], x['file'])):
            print(f"  [{v['rule']}] {v['file']}:{v['line']} — {v['message']}")
            print(f"       → {v['fix']}\n")
        return 1 if p0 else 0


if __name__ == "__main__":
    sys.exit(main())
