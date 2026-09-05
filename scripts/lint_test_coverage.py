#!/usr/bin/env python3
"""Linter: vérifie la couverture de tests (skill testing).

Vérifie que chaque module common/ et views/ a un fichier de test correspondant.

Usage:
  python scripts/lint_test_coverage.py                        # Tous les projets
  python scripts/lint_test_coverage.py --dir .\LarcSuperviseur  # Un seul projet
  python scripts/lint_test_coverage.py --json                   # Sortie JSON
"""

LINTER_META = {
    "key": "COV",
    "label": "Couverture de tests",
    "category": "tests",
    "description": "Modules common/views sans fichier de test correspondant",
    "skill": "larc-testing",
}

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

VIOLATIONS = []


def scan_project(project_path: Path):
    """Scanne un projet et vérifie la couverture de tests."""
    tests_dir = project_path / "tests"
    if not tests_dir.exists():
        VIOLATIONS.append({
            'project': project_path.name,
            'severity': 'P0',
            'message': 'Pas de dossier tests/',
            'fix': 'Créer tests/ avec conftest.py et au moins 1 fichier de test',
        })
        return

    # Modules à tester
    source_dirs = []
    for src in ['common', 'views', 'core', 'larccommon', 'phibuilder']:
        d = project_path / src
        if d.exists():
            source_dirs.append(d)

    if not source_dirs:
        return

    # Fichiers de test existants
    test_files = set()
    for tf in tests_dir.rglob("test_*.py"):
        test_files.add(tf.stem.replace('test_', ''))

    covered = 0
    total = 0

    for src_dir in source_dirs:
        for py_file in src_dir.rglob("*.py"):
            if py_file.name.startswith('__'):
                continue
            if '__pycache__' in str(py_file):
                continue

            total += 1
            module_name = py_file.stem

            if module_name in test_files:
                covered += 1
            else:
                VIOLATIONS.append({
                    'project': project_path.name,
                    'file': str(py_file.relative_to(project_path)),
                    'severity': 'P1',
                    'message': f'Pas de test pour {module_name}',
                    'fix': f'Créer tests/test_{module_name}.py',
                })

    if total > 0 and covered == total:
        pass  # Tout est couvert — pas de violation


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Linter couverture de tests")
    parser.add_argument("--dir", help="Repertoire a scanner")
    parser.add_argument("--json", action="store_true", help="Sortie JSON")
    parser.add_argument("--stats", action="store_true", help="Statistiques de couverture")
    args = parser.parse_args()

    if args.dir:
        dirs = [Path(args.dir)]
    else:
        dirs = [Path(d) for d in PROJETS if Path(d).exists()]

    for d in dirs:
        if d.exists():
            scan_project(d)

    if args.json:
        import json
        print(json.dumps(VIOLATIONS, ensure_ascii=False, indent=2))
    elif args.stats:
        if not VIOLATIONS:
            print("OK Couverture 100% - tous les modules ont un test")
            return 0
        p0 = [v for v in VIOLATIONS if v['severity'] == 'P0']
        p1 = [v for v in VIOLATIONS if v['severity'] == 'P1']
        by_project = {}
        for v in VIOLATIONS:
            by_project.setdefault(v['project'], []).append(v)
        for proj, violations in sorted(by_project.items()):
            p0c = sum(1 for v in violations if v['severity'] == 'P0')
            p1c = len(violations) - p0c
            print(f"  {proj}: {p0c} P0, {p1c} P1")
        return 1 if p0 else 0
    else:
        if not VIOLATIONS:
            print("OK Tous les modules ont un fichier de test")
            return 0

        p0 = [v for v in VIOLATIONS if v['severity'] == 'P0']
        p1 = [v for v in VIOLATIONS if v['severity'] == 'P1']
        print(f"X {len(p0)} P0 (pas de tests/), {len(p1)} P1 (modules sans test)\n")
        for v in p0:
            print(f"  [P0] {v['project']} - {v['message']}")
            print(f"       -> {v['fix']}\n")
        for v in sorted(p1, key=lambda x: x['file'])[:20]:
            print(f"  [P1] {v['project']}/{v['file']} - {v['message']}")
        if len(p1) > 20:
            print(f"  ... et {len(p1) - 20} autres")
        return 1 if p0 else 0


if __name__ == "__main__":
    sys.exit(main())
