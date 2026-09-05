#!/usr/bin/env python3
"""Auto-fix: ajoute @safe_slot aux slots Qt non proteges.

Usage:
  python scripts/fix_safe_slot.py --dry-run    # Preview
  python scripts/fix_safe_slot.py              # Appliquer
"""

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

EXCLUDE = ['test_', '__pycache__', '.venv', 'database.py', 'logger.py',
           'safe_slot.py', 'network.py', 'auth.py', 'sync.py', 'sqlite_init.py']

FIXES = []


def find_class_for_method(lines, method_line):
    """Trouve la classe contenant la methode."""
    for i in range(method_line - 1, max(method_line - 100, 0), -1):
        m = re.match(r'class\s+(\w+)', lines[i])
        if m:
            return m.group(1)
    return "Unknown"


def scan_file(filepath: Path):
    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception:
        return
    lines = source.split('\n')

    # Trouve les slots connectes sans @safe_slot
    connected = set()
    for i, line in enumerate(lines):
        m = re.search(r'\.connect\(self\.(_\w+)', line)
        if m:
            connected.add(m.group(1))

    if not connected:
        return

    for method_name in connected:
        for i, line in enumerate(lines):
            if f'def {method_name}(' in line:
                # Verifie si @safe_slot est deja present
                has_decorator = False
                for j in range(max(0, i - 3), i):
                    if '@safe_slot' in lines[j]:
                        has_decorator = True
                        break
                if not has_decorator:
                    class_name = find_class_for_method(lines, i)
                    label = f"{class_name}.{method_name}"
                    FIXES.append({
                        'file': str(filepath),
                        'line': i + 1,
                        'method': method_name,
                        'label': label,
                        'indent': len(line) - len(line.lstrip()),
                    })


def apply_fix(filepath: str, fixes_for_file: list, dry_run: bool):
    with open(filepath, encoding='utf-8') as f:
        lines = f.readlines()

    # Appliquer de bas en haut pour preserver les numeros de ligne
    for fix in sorted(fixes_for_file, key=lambda x: -x['line']):
        idx = fix['line'] - 1
        indent = ' ' * fix['indent']
        decorator = f'{indent}@safe_slot("{fix["label"]}")\n'
        lines.insert(idx, decorator)

    # Ajouter l'import si necessaire
    needs_import = 'from larccommon.safe_slot import safe_slot' not in ''.join(lines)
    if needs_import and not dry_run:
        last_import = 0
        for i, line in enumerate(lines):
            if line.startswith('from ') or line.startswith('import '):
                last_import = i
        lines.insert(last_import + 1, 'from larccommon.safe_slot import safe_slot\n')

    if dry_run:
        print(f"  [DRY-RUN] {filepath}: {len(fixes_for_file)} slots" + (" +import" if needs_import else ""))
    else:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"  [FIXED] {filepath}: {len(fixes_for_file)} slots")


def main():
    dry_run = '--dry-run' in sys.argv

    for proj in PROJETS:
        d = Path(proj)
        if not d.exists():
            continue
        for fp in d.rglob("*.py"):
            skip = any(ex in str(fp) for ex in EXCLUDE)
            if skip:
                continue
            scan_file(fp)

    if not FIXES:
        print("OK Aucun slot non protege trouve.")
        return 0

    # Grouper par fichier
    by_file = {}
    for fix in FIXES:
        by_file.setdefault(fix['file'], []).append(fix)

    print(f"\n{'DRY-RUN' if dry_run else 'FIX'} {len(FIXES)} slots dans {len(by_file)} fichiers :\n")

    for filepath, fixes in sorted(by_file.items()):
        apply_fix(filepath, fixes, dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
