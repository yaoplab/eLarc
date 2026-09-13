#!/usr/bin/env python3
"""
lint_widget_purity.py -- Linter "widgets phibuilder uniquement" pour LarcCommon.

Detecte l'instanciation de widgets PySide6 bruts en dehors des exceptions
autorisees par CLAUDE.md (RE GLE ABSOLUE : toujours phibuilder.widgets, jamais
PySide6.QtWidgets direct), dans tout fichier sous views/, dialogs/, panels/.

Usage:
    python scripts/lint_widget_purity.py                    # rapport
    python scripts/lint_widget_purity.py --baseline          # (re)genere la baseline
    python scripts/lint_widget_purity.py --check-baseline    # echoue seulement sur le NOUVEAU (pre-commit)
    python scripts/lint_widget_purity.py --json
"""
import argparse
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _baseline import load_baseline, save_baseline, split_new

LINTER_META = {
    "key": "W1",
    "label": "Widgets phibuilder uniquement",
    "category": "design-system",
    "description": "Widget PySide6 brut hors exceptions CLAUDE.md -- remplacer par phibuilder.widgets",
    "skill": "pyside6-wrapper",
}

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = [
    "LarcCommon/larccommon", "LarcSuperviseur", "LarcSecretaire",
    "LarcProf", "LarcHub", "LarcRH", "LarcCompta", "LarcConfig", "LarcDocs",
]
SCAN_SUBDIRS = ("views", "dialogs", "panels")
EXCLUDE_DIRS = {"__pycache__", ".git", ".claude", ".venv", "venv", "tests", "tools", "docs", "_backup_rerr"}
BASELINE_PATH = ROOT / "scripts" / ".widget_purity_baseline.json"

# CLAUDE.md -- exceptions autorisees (jamais signalees)
ALLOWED = {
    "QMessageBox", "QApplication", "QVBoxLayout", "QHBoxLayout",
    "QGridLayout", "QButtonGroup", "QTableWidgetItem", "QWidget",
}

# Widget brut -> suggestion phibuilder (None = pas d'equivalent connu, signale quand meme)
SUGGESTIONS = {
    "QPushButton": "M3Button", "QLineEdit": "M3TextField", "QLabel": "M3Label",
    "QComboBox": "M3ComboBox", "QListWidget": "M3ListWidget", "QTableWidget": "M3TableWidget",
    "QTabWidget": "M3TabWidget", "QDateEdit": "M3DateEdit", "QTimeEdit": "M3TimeEdit",
    "QScrollArea": "M3ScrollArea", "QStackedWidget": "M3StackedWidget", "QMenu": "M3Menu",
    "QHeaderView": "M3HeaderView", "QTextEdit": "M3TextEdit", "QProgressBar": "M3ProgressBar",
    "QGroupBox": "M3GroupBox", "QSplitter": "M3Splitter", "QFrame": "M3Frame",
    "QDialog": "M3Dialog", "QCheckBox": None,
}

INSTANTIATION_RE = re.compile(r'\b(' + '|'.join(SUGGESTIONS) + r')\s*\(')


def _rel_to_root(filepath: Path) -> str:
    """Chemin relatif a ROOT pour que les cles de baseline survivent un
    deplacement du repo (worktree -> emplacement final). Retombe sur le
    chemin tel quel si le fichier est hors ROOT (ex: fichiers de test tmp_path)."""
    try:
        return str(filepath.resolve().relative_to(ROOT))
    except ValueError:
        return str(filepath)


def find_violations(filepath: Path) -> list[dict]:
    results = []
    try:
        lines = filepath.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, IOError):
        return results

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("class "):
            continue  # heritage (class Foo(QDialog):), pas une instanciation
        m = INSTANTIATION_RE.search(stripped)
        if not m:
            continue
        widget = m.group(1)
        if widget in ALLOWED:
            continue  # exceptions CLAUDE.md -- defense en profondeur (deja hors SUGGESTIONS)
        suggestion = SUGGESTIONS.get(widget)
        results.append({
            "file": _rel_to_root(filepath),
            "line": lineno,
            "rule": "W1",
            "widget": widget,
            "context": stripped[:120],
            "suggestion": (
                f"Utiliser phibuilder.widgets.{suggestion} au lieu de {widget} brut"
                if suggestion else
                f"{widget} brut -- aucun widget phibuilder equivalent actuellement, "
                f"signale pour visibilite (RE GLE ABSOLUE CLAUDE.md)"
            ),
        })
    return results


def scan_projects() -> list[dict]:
    findings = []
    seen: set[Path] = set()
    for project in PROJECTS:
        proj_path = ROOT / project
        if not proj_path.exists():
            continue
        candidates = [proj_path / sub for sub in SCAN_SUBDIRS if (proj_path / sub).exists()]
        candidates.append(proj_path)  # couvre LarcCommon/larccommon/dialogs (pas de sous-dossier views/)
        for base in candidates:
            for pyfile in base.rglob("*.py"):
                if pyfile in seen:
                    continue
                if any(part in EXCLUDE_DIRS for part in pyfile.parts):
                    continue
                seen.add(pyfile)
                findings.extend(find_violations(pyfile))
    return findings


def main():
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true", help="(Re)genere la baseline avec les violations actuelles")
    parser.add_argument("--check-baseline", action="store_true", help="N'echoue que sur les violations absentes de la baseline (pre-commit)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    findings = scan_projects()

    if args.baseline:
        save_baseline(BASELINE_PATH, findings)
        print(f"[baseline] {len(findings)} violation(s) figee(s) dans {BASELINE_PATH}")
        return 0

    if args.check_baseline:
        baseline = load_baseline(BASELINE_PATH)
        new, known = split_new(findings, baseline)
        print(f"lint_widget_purity: {len(new)} nouvelle(s) violation(s), {len(known)} connue(s) (baseline, non bloquant)")
        for f in new:
            print(f"  [W1] {f['file']}:{f['line']}  {f['context']}")
            print(f"       -> {f['suggestion']}")
        return 1 if new else 0

    if args.json:
        import json as _json
        print(_json.dumps(findings, indent=2, ensure_ascii=False))
        return 1 if findings else 0

    if not findings:
        print("lint_widget_purity: 0 violation -- FELICITATIONS !")
        return 0
    print(f"lint_widget_purity: {len(findings)} violation(s)")
    for f in findings:
        print(f"  [W1] {f['file']}:{f['line']}  {f['context']}")
        print(f"       -> {f['suggestion']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
