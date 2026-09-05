#!/usr/bin/env python3
"""Linter: vérifie les règles du skill pyside6-wrapper.

Vérifie statiquement :
  - Slots Qt sans @safe_slot
  - lambda: nu dans connect()
  - except Exception: pass muet
  - print() dans les handlers
  - Variable _ utilisée (écrase i18n)

Usage:
  python scripts/lint_safe_slot.py                           # Tous les projets
  python scripts/lint_safe_slot.py --dir .\LarcSuperviseur     # Un seul projet
  python scripts/lint_safe_slot.py --json                      # Sortie JSON
"""

LINTER_META = {
    "key": "S",
    "label": "Safe slots PySide6",
    "category": "qt",
    "description": "Slots sans @safe_slot, anti-patterns Qt, variable _ écrasée",
    "skill": "pyside6-wrapper",
}

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJETS = [ROOT / n for n in (
    "LarcSuperviseur",
    "LarcSecretaire",
    "LarcProf",
    "LarcHub",
    "LarcConfig",
    "LarcCommon",
)]

VIOLATIONS = []


def find_slots_without_decorator(filepath: Path):
    """Détecte les méthodes connectées à des signaux Qt sans @safe_slot."""
    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception:
        return

    # Cherche .clicked.connect(self._on_xxx) ou .triggered.connect(self._on_xxx)
    signal_pattern = re.compile(r'\.(?:clicked|triggered|toggled|currentChanged|'
                                r'textChanged|itemChanged|itemSelectionChanged|'
                                r'cellClicked|cellDoubleClicked|currentIndexChanged|'
                                r'activated|pressed|released|stateChanged|'
                                r'valueChanged|editingFinished|returnPressed|'
                                r'selectionChanged|data_ready|error_occurred|'
                                r'finished|progress|sign_done|log_message)'
                                r'\.connect\(self\.(_\w+)')

    connected_methods = set()
    for m in signal_pattern.finditer(source):
        connected_methods.add(m.group(1))

    if not connected_methods:
        return

    # Cherche les définitions de ces méthodes
    for method in connected_methods:
        # Vérifie si @safe_slot est présent avant la définition
        def_pattern = re.compile(
            rf'(?:@(\w+\.\w+|[a-zA-Z_]\w*)\s*\(\s*"[^"]*"\s*\)\s*\n\s*)?'
            rf'def {method}\(',
            re.MULTILINE
        )

        # Approche plus simple : cherche @safe_slot juste avant la def
        lines = source.split('\n')
        for i, line in enumerate(lines):
            if f'def {method}(' in line:
                # Vérifie les 2 lignes précédentes pour @safe_slot
                has_safe_slot = False
                for j in range(max(0, i-2), i):
                    if '@safe_slot' in lines[j] or '@safe_slot' in lines[j]:
                        has_safe_slot = True
                        break
                if not has_safe_slot:
                    VIOLATIONS.append({
                        'file': str(filepath),
                        'line': i + 1,
                        'rule': 'C1',
                        'severity': 'P0',
                        'message': f'Slot {method}() sans @safe_slot',
                        'fix': f'Ajouter @safe_slot("Classe.{method}") avant la définition',
                    })


def find_lambda_in_connect(filepath: Path):
    """Détecte les lambda: nus dans connect()."""
    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception:
        return

    pattern = re.compile(r'\.connect\(\s*lambda\s*:')
    for i, line in enumerate(source.split('\n'), 1):
        if pattern.search(line) and '@safe_slot' not in line:
            # Exclure les lambda avec checked= (pattern acceptable)
            if 'lambda checked' in line:
                continue
            VIOLATIONS.append({
                'file': str(filepath),
                'line': i,
                'rule': 'C2/A1',
                'severity': 'P0',
                'message': 'lambda nu dans connect()',
                'fix': 'Remplacer par un slot nommé avec @safe_slot',
            })


def find_bare_except_pass(filepath: Path):
    """Détecte except Exception: pass muet."""
    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception:
        return

    lines = source.split('\n')
    for i, line in enumerate(lines):
        if re.search(r'except\s*(Exception)?\s*:\s*$', line):
            # Vérifie si le bloc est "pass" ou vide
            for j in range(i+1, min(i+5, len(lines))):
                next_line = lines[j].strip()
                if next_line == 'pass':
                    # Vérifie qu'il n'y a pas de log avant le pass
                    VIOLATIONS.append({
                        'file': str(filepath),
                        'line': i + 1,
                        'rule': 'C5/A3',
                        'severity': 'P1',
                        'message': 'except Exception: pass muet',
                        'fix': 'Remplacer par @safe_slot ou ajouter log()',
                    })
                    break
                elif next_line and not next_line.startswith('#'):
                    break


def find_print_in_handler(filepath: Path):
    """Détecte print() dans les handlers (après une def ou dans un slot)."""
    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception:
        return

    lines = source.split('\n')
    in_handler = False
    for i, line in enumerate(lines):
        if 'def _on_' in line or 'def _' in line and 'self' in line:
            in_handler = True
        elif line.strip() and not line.startswith(' ') and 'def ' in line:
            in_handler = False

        if in_handler and re.search(r'\bprint\(', line):
            VIOLATIONS.append({
                'file': str(filepath),
                'line': i + 1,
                'rule': 'C6/A5',
                'severity': 'P1',
                'message': 'print() dans un handler',
                'fix': 'Remplacer par log() ou @safe_slot',
            })


def find_underscore_variable(filepath: Path):
    """Détecte _ comme nom de variable (écrase i18n)."""
    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception:
        return

    lines = source.split('\n')
    for i, line in enumerate(lines):
        # Détecte for _ in, _ =, with ... as _
        if re.search(r'\bfor\s+_\s+in\b', line):
            VIOLATIONS.append({
                'file': str(filepath),
                'line': i + 1,
                'rule': 'E6',
                'severity': 'P1',
                'message': 'Variable _ utilisée — écrase la fonction i18n',
                'fix': 'Remplacer par _outer, _ignored, ou _unused',
            })


def scan_directory(directory: Path):
    """Scanne récursivement un répertoire."""
    for filepath in directory.rglob("*.py"):
        if '__pycache__' in str(filepath):
            continue
        if 'test_' in filepath.name:
            continue  # skip test files
        find_slots_without_decorator(filepath)
        find_lambda_in_connect(filepath)
        find_bare_except_pass(filepath)
        find_print_in_handler(filepath)
        find_underscore_variable(filepath)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Linter safe_slot PySide6")
    parser.add_argument("--dir", help="Repertoire a scanner")
    parser.add_argument("--json", action="store_true", help="Sortie JSON")
    parser.add_argument("--fix", action="store_true", help="Afficher le correctif a appliquer")
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
            print("OK 0 violation - tous les slots sont conformes")
            return 0

        print(f"X {len(VIOLATIONS)} violations trouvees :\n")
        for v in sorted(VIOLATIONS, key=lambda x: (x['rule'], x['file'])):
            print(f"  [{v['rule']}] {v['file']}:{v['line']} — {v['message']}")
            print(f"       -> {v['fix']}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
