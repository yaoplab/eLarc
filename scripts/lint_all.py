#!/usr/bin/env python3
"""
lint_all.py — Lance les 4 linters (R + D + V + C) sur un ou tous les projets.

Usage:
  python scripts/lint_all.py                    # Tous les projets
  python scripts/lint_all.py LarcRH             # Un seul projet (nom court)
  python scripts/lint_all.py LarcRH          # Un seul projet (chemin)
  python scripts/lint_all.py --json             # Sortie JSON
"""

import sys
import os
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJETS_DIR = Path(__file__).resolve().parents[1]

PROJETS = {
    "LarcCommon":      PROJETS_DIR / "LarcCommon",
    "LarcSuperviseur": PROJETS_DIR / "LarcSuperviseur",
    "LarcSecretaire":  PROJETS_DIR / "LarcSecretaire",
    "LarcProf":        PROJETS_DIR / "LarcProf",
    "LarcHub":         PROJETS_DIR / "LarcHub",
    "LarcConfig":      PROJETS_DIR / "LarcConfig",
    "LarcRH":          PROJETS_DIR / "LarcRH",
    "LarcCompta":      PROJETS_DIR / "LarcCompta",
}

LINTERS = [
    ("R", "lint_qss_hardcoding.py"),
    ("D", "lint_d1_color_checker.py"),
    ("V", "lint_ui_quality.py"),
    ("C", "lint_preflight.py"),
]


def run_linter(script: Path, target: Path) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, str(script), "--dir", str(target)],
        capture_output=True, text=True, cwd=str(PROJETS_DIR),
        env=env, encoding="utf-8", errors="replace",
    )
    return result.returncode, (result.stdout or "").strip()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Lance les 4 linters sur un ou tous les projets")
    parser.add_argument("target", nargs="?", help="Nom du projet (ex: LarcRH) ou chemin")
    parser.add_argument("--json", action="store_true", help="Sortie JSON")
    args = parser.parse_args()

    # Resolve targets
    if args.target:
        t = args.target
        if os.path.isdir(t):
            targets = [Path(t).resolve()]
        elif t in PROJETS:
            targets = [PROJETS[t]]
        else:
            print(f"Projet inconnu : {t}")
            print(f"Projets disponibles : {', '.join(PROJETS.keys())}")
            return 1
    else:
        targets = [p for p in PROJETS.values() if p.is_dir()]

    total_failures = 0
    all_results: dict[str, dict] = {}

    for target in targets:
        name = target.name
        all_results[name] = {}
        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"{'='*60}")

        for linter_key, linter_file in LINTERS:
            script_path = SCRIPTS_DIR / linter_file
            if not script_path.exists():
                print(f"  [{linter_key}] MANQUANT — {linter_file}")
                all_results[name][linter_key] = "MISSING"
                total_failures += 1
                continue

            rc, output = run_linter(script_path, target)
            if rc == 0:
                last_line = output.split('\n')[-1] if output else "OK"
                print(f"  [{linter_key}] PASS  {last_line[:60]}")
                all_results[name][linter_key] = "PASS"
            else:
                n_violations = output.count("violation")
                print(f"  [{linter_key}] FAIL  ({n_violations} violations)")
                all_results[name][linter_key] = "FAIL"
                total_failures += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"  RECAPITULATIF")
    print(f"{'='*60}")
    header = f"{'Projet':<20} " + " ".join(f" [{k}] " for k, _ in LINTERS)
    print(header)
    print("-" * len(header))
    for name, results in all_results.items():
        row = f"{name:<20}"
        for k, _ in LINTERS:
            status = results.get(k, "—")
            row += f"  {'OK' if status == 'PASS' else '!!' if status == 'FAIL' else '??'} "
        print(row)

    if total_failures == 0:
        print(f"\n  TOUS LES PROJETS PASSENT - 0 violation")
    else:
        print(f"\n  {total_failures} echec(s) - corriger avant de soumettre")

    return total_failures


if __name__ == "__main__":
    sys.exit(main())
