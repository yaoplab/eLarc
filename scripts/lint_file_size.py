#!/usr/bin/env python3
r"""Linter: vérifie la règle des 1000 lignes (skill pyside6-wrapper, sous-système F).

Usage:
  python scripts/lint_file_size.py                           # Tous les projets
  python scripts/lint_file_size.py --dir .\LarcSuperviseur     # Un seul projet
  python scripts/lint_file_size.py --threshold 500             # Seuil personnalisé
  python scripts/lint_file_size.py --json                      # Sortie JSON
"""

LINTER_META = {
    "key": "FS",
    "label": "Taille des fichiers",
    "category": "filesize",
    "description": "Fichiers dépassant 1000 lignes — refactorisation requise",
    "skill": "pyside6-wrapper",
}

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _baseline import load_baseline, save_baseline, split_new

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "scripts" / ".file_size_baseline.json"
PROJETS = [ROOT / n for n in (
    "LarcSuperviseur",
    "LarcSecretaire",
    "LarcProf",
    "LarcHub",
    "LarcConfig",
    "LarcCommon",
    "LarcRH",
    "LarcCompta",
)]

EXCLUDED = [
    '__pycache__', '.venv', '.git', 'node_modules',
    'egg-info', '.pytest_cache',
    'locale',  # JSON de traduction
    'sql',     # Fichiers SQL générés
    'migrations',
    '*.svg', '*.png', '*.jpg', '*.json', '*.sql', '*.ini', '*.toml',
]

VIOLATIONS = []


def should_skip(filepath: Path) -> bool:
    for excl in EXCLUDED:
        if excl.startswith('*.'):
            if filepath.suffix == excl[1:]:
                return True
        elif excl in str(filepath):
            return True
    return False


def scan_directory(directory: Path, threshold: int = 1000):
    for filepath in directory.rglob("*.py"):
        if should_skip(filepath):
            continue
        try:
            line_count = sum(1 for _ in open(filepath, encoding='utf-8'))
        except Exception:
            continue

        severity = 'P0' if line_count > 1000 else ('P1' if line_count > 500 else 'OK')

        if severity != 'OK':
            VIOLATIONS.append({
                'file': str(filepath),
                'lines': line_count,
                'severity': severity,
                'message': f'{line_count} lignes (limite: {threshold})',
                'fix': f"Fractionner en sous-modules (< {threshold} lignes chacun)",
            })


def scan_with_stats(directory: Path, threshold: int = 1000):
    """Scanne avec statistiques detaillees."""
    stats = {"total_files": 0, "total_lines": 0, "largest": None, "by_dir": {}}
    all_files = []
    for filepath in directory.rglob("*.py"):
        if should_skip(filepath):
            continue
        try:
            lc = sum(1 for _ in open(filepath, encoding='utf-8'))
        except Exception:
            continue
        stats["total_files"] += 1
        stats["total_lines"] += lc
        parent = str(filepath.parent.relative_to(directory)) if directory in filepath.parents else str(filepath.parent.name)
        stats["by_dir"].setdefault(parent, []).append(lc)
        all_files.append((str(filepath), lc))
        if lc > threshold:
            VIOLATIONS.append({
                'file': str(filepath), 'lines': lc,
                'severity': 'P0' if lc > 1000 else ('P1' if lc > 500 else 'OK'),
                'message': f'{lc} lignes (limite: {threshold})',
                'fix': f'Fractionner en sous-modules (< {threshold} lignes chacun)',
            })
    if all_files:
        stats["largest"] = max(all_files, key=lambda x: x[1])
        stats["avg_lines"] = stats["total_lines"] // stats["total_files"]
        stats["by_dir_avg"] = {d: sum(v)//len(v) for d, v in stats["by_dir"].items()}
    return stats


def main():
    import argparse, json
    parser = argparse.ArgumentParser(description="Linter taille des fichiers")
    parser.add_argument("--dir", help="Repertoire a scanner")
    parser.add_argument("--threshold", type=int, default=1000, help="Seuil max de lignes")
    parser.add_argument("--json", action="store_true", help="Sortie JSON")
    parser.add_argument("--stats", action="store_true", help="Afficher les statistiques")
    parser.add_argument("--baseline", action="store_true", help="(Re)genere la baseline avec les violations actuelles")
    parser.add_argument("--check-baseline", action="store_true", help="N'echoue que sur les violations absentes de la baseline (pre-commit)")
    args = parser.parse_args()

    if args.dir:
        dirs = [Path(args.dir)]
    else:
        dirs = [Path(d) for d in PROJETS if Path(d).exists()]

    all_stats = {}
    for d in dirs:
        if d.exists():
            all_stats[d.name] = scan_with_stats(d, args.threshold)

    flat_findings = [{'file': v['file'], 'line': 0, 'rule': 'F1'} for v in VIOLATIONS]

    if args.baseline:
        save_baseline(BASELINE_PATH, flat_findings)
        print(f"[baseline] {len(flat_findings)} violation(s) figee(s) dans {BASELINE_PATH}")
        return 0

    if args.check_baseline:
        baseline = load_baseline(BASELINE_PATH)
        new, known = split_new(flat_findings, baseline)
        print(f"lint_file_size: {len(new)} nouvelle(s) violation(s), {len(known)} connue(s) (baseline, non bloquant)")
        new_files = {f['file'] for f in new}
        for v in sorted(VIOLATIONS, key=lambda x: -x['lines']):
            if v['file'] in new_files:
                print(f"  [{v['severity']}] {v['file']}")
                print(f"       {v['lines']} lignes -> {v['fix']}")
        return 1 if new else 0

    if args.json:
        print(json.dumps({
            "violations": VIOLATIONS,
            "stats": {k: {"files": v["total_files"], "lines": v["total_lines"],
                          "avg": v.get("avg_lines", 0),
                          "largest": v["largest"][0] if v["largest"] else None}
                      for k, v in all_stats.items()}
        }, ensure_ascii=False, indent=2))
        return 0

    if args.stats:
        for name, st in all_stats.items():
            print(f"\n--- {name} ---")
            print(f"  Fichiers: {st['total_files']}  |  Lignes totales: {st['total_lines']}  |  Moyenne: {st.get('avg_lines', 0)} l/fichier")
            if st['largest']:
                print(f"  Plus grand: {st['largest'][0]} ({st['largest'][1]} lignes)")
            print(f"  Par repertoire:")
            for d, avg in sorted(st.get('by_dir_avg', {}).items(), key=lambda x: -x[1]):
                print(f"    {d:<30} moy {avg} l/fichier")

    if not VIOLATIONS:
        print(f"\nOK Tous les fichiers < {args.threshold} lignes")
        return 0

    print(f"\nX {len(VIOLATIONS)} fichiers depassent la limite :\n")
    for v in sorted(VIOLATIONS, key=lambda x: -x['lines']):
        print(f"  [{v['severity']}] {v['file']}")
        print(f"       {v['lines']} lignes -> {v['fix']}\n")

    p0_count = sum(1 for v in VIOLATIONS if v['severity'] == 'P0')
    p1_count = len(VIOLATIONS) - p0_count
    print(f"Resume: {p0_count} P0 (>1000 lignes), {p1_count} P1 (>500 lignes)")
    return 1 if p0_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
