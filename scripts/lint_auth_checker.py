#!/usr/bin/env python3
"""Linter: vérifie les règles des skills auth (auth-oauth2, auth-intranet, auth-pin).

Détecte :
  - Credentials en dur dans le code source
  - session.is_authenticated = True hors de LoginWindow
  - Mots de passe en clair dans les logs
  - appels db.server_conn sans vérifier is_server_connected

Usage:
  python scripts/lint_auth_checker.py                      # Tous les projets
  python scripts/lint_auth_checker.py --dir .\LarcProf       # Un seul projet
  python scripts/lint_auth_checker.py --json                 # Sortie JSON
"""

LINTER_META = {
    "key": "AUTH",
    "label": "Authentification",
    "category": "auth",
    "description": "Credentials en dur, session contournée, mots de passe en clair",
    "skill": "auth-intranet",
}

import re
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

CREDENTIALS_PATTERNS = [
    (r"password\s*=\s*['\"][^'\"]{3,}['\"]", "Mot de passe en dur"),
    (r"pass\s*=\s*['\"][^'\"]{3,}['\"]", "Mot de passe en dur (pass=)"),
    (r"ApiKey\s*=\s*['\"][^'\"]{8,}['\"]", "Clé API en dur"),
    (r"ClientSecret\s*=\s*['\"][^'\"]{8,}['\"]", "ClientSecret en dur"),
]

VIOLATIONS = []


def scan_file(filepath: Path):
    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception:
        return
    lines = source.split('\n')

    # 1. Credentials en dur
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip comments, docstrings, and config files
        if stripped.startswith('#') or stripped.startswith(';') or stripped.startswith('"') or stripped.startswith("'"):
            continue
        if 'config_loader' in str(filepath) or 'database.py' in str(filepath):
            continue
        if 'fallback=' in line or 'get(' in line:
            continue
        for pattern, msg in CREDENTIALS_PATTERNS:
            if re.search(pattern, line):
                VIOLATIONS.append({
                    'file': str(filepath),
                    'line': i,
                    'rule': 'auth-C1',
                    'severity': 'P0',
                    'message': f'{msg}',
                    'fix': 'Stocker dans config.ini (section [OAuth2] ou [IntranetDatabase])',
                })

    # 2. session.is_authenticated = True hors LoginWindow
    #    (les mixins login_auth/login_creation/login_helpers appartiennent à LoginWindow)
    if not any(x in str(filepath).lower() for x in ('login.py', 'login_auth', 'login_creation', 'login_helpers')):
        for i, line in enumerate(lines, 1):
            if 'session.is_authenticated' in line and '= True' in line:
                VIOLATIONS.append({
                    'file': str(filepath),
                    'line': i,
                    'rule': 'auth-C2',
                    'severity': 'P0',
                    'message': 'session.is_authenticated modifié hors LoginWindow',
                    'fix': "L'authentification doit passer par AuthManager, pas par session directe",
                })

    # 3. Mots de passe dans les logs (uniquement dans l'argument chaîne du log)
    _LOG_PASS_RE = re.compile(
        r'(?:self\._log|log)\(\s*[fb]?[\'"][^\'"]*\b(?:password|pass|pin)\b[^\'"]*[\'"]',
        re.IGNORECASE,
    )
    for i, line in enumerate(lines, 1):
        if _LOG_PASS_RE.search(line) and 'hash' not in line.lower():
            VIOLATIONS.append({
                    'file': str(filepath),
                    'line': i,
                    'rule': 'auth-C3',
                    'severity': 'P0',
                    'message': 'Mot de passe/PIN potentiellement loggé en clair',
                    'fix': 'Ne jamais logger les mots de passe. Logger uniquement les hash ou les emails.',
                })

    # 4. db.server_conn sans vérifier is_server_connected
    if 'database.py' not in str(filepath):
        has_safety_check = 'is_server_connected' in source or 'if db.server_conn' in source or 'if conn is None' in source
        uses_server_conn = 'db.server_conn' in source or 'server_conn.cursor()' in source
        if uses_server_conn and not has_safety_check:
            VIOLATIONS.append({
                'file': str(filepath),
                'line': 0,
                'rule': 'auth-C4',
                'severity': 'P1',
                'message': 'db.server_conn utilisé sans vérifier is_server_connected',
                'fix': 'Ajouter : if not db.is_server_connected: return',
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
    import argparse
    parser = argparse.ArgumentParser(description="Linter auth Larc")
    parser.add_argument("--dir", help="Répertoire à scanner")
    parser.add_argument("--json", action="store_true", help="Sortie JSON")
    parser.add_argument("--fix", action="store_true", help="Afficher les corrections suggerees")
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
    elif args.fix:
        if not VIOLATIONS:
            print("OK 0 violation - authentification conforme")
            return 0
        for v in sorted(VIOLATIONS, key=lambda x: (x['severity'], x['file'])):
            print(f"  {v['file']}:{v['line']}")
            print(f"  {v['fix']}\n")
        return 1
    else:
        if not VIOLATIONS:
            print("OK 0 violation - authentification conforme")
            return 0
        p0 = [v for v in VIOLATIONS if v['severity'] == 'P0']
        p1 = [v for v in VIOLATIONS if v['severity'] == 'P1']
        print(f"X {len(p0)} P0, {len(p1)} P1 violations\n")
        for v in sorted(VIOLATIONS, key=lambda x: (x['severity'], x['file'])):
            print(f"  [{v['rule']}] {v['file']}:{v['line']} - {v['message']}")
            print(f"       -> {v['fix']}\n")
        return 1 if p0 else 0


if __name__ == "__main__":
    sys.exit(main())
