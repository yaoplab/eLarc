#!/usr/bin/env python3
"""
lint_preflight.py - Linter de pre-soumission (check-list mecanique C1-C12).

Regles verifiees automatiquement :
  C1  - on_primary_container interdit (crash runtime)
  C2  - QMessageBox + QLineEdit/QTextEdit interdit (utiliser ThemedDialog)
  C3  - QDialog direct interdit (heriter de ThemedDialog)
  C4  - Label AU-DESSUS du champ (Q8) - jamais addWidget(QLabel) apres addWidget(field)
  C5  - theme_manager.image.X restreint a logo et theme_btn
  C6  - Colonnes de tableau coherentes (max(col) < len(headers))
  C7  - @safe_slot obligatoire sur tout slot _on_*
  C9  - Tooltip obligatoire sur bouton icone-seul
  C11 - QDateEdit/QDateTimeEdit doit avoir setMinimumWidth (Q10d)
  C12 - QDateTimeEdit/QDateEdit/QComboBox QSS sans padding uniforme >= space_sm (Q10c)
  C13 - Erreurs silencieuses : except:pass, print_exc() sans QMessageBox, return muet

Usage:
  python scripts/lint_preflight.py --dir .\\LarcRH
  python scripts/lint_preflight.py --json
"""

LINTER_META = {
    "key": "C",
    "label": "Pré-soumission",
    "category": "checklist",
    "description": "Check-list mécanique C1-C13 avant soumission",
    "skill": "preflight",
}

import ast
import re
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJETS = [ROOT / n for n in (
    "LarcSuperviseur",
    "LarcSecretaire",
    "LarcProf",
    "LarcHub",
    "LarcConfig",
    "LarcRH",
    "LarcCompta",
)]

EXCLUDE_FILES = {"theme.py"}


def _is_common_dir(filepath: Path) -> bool:
    """C13 exempted for data layers (common/) where print_exc is acceptable."""
    return 'common' in filepath.parts


def lint_file(filepath: Path) -> list[dict]:
    violations = []
    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception:
        return violations

    is_common = _is_common_dir(filepath)
    lines = source.split('\n')

    if filepath.name not in EXCLUDE_FILES:
        for i, line in enumerate(lines, 1):
            if 'on_primary_container' in line and not line.strip().startswith('#'):
                violations.append({
                    'line': i, 'rule': 'C1',
                    'message': 'p.on_primary_container interdit - utiliser p.text_strong',
                })

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        if re.search(r'class\s+\w+\(QDialog\)', stripped):
            violations.append({
                'line': i, 'rule': 'C3',
                'message': 'QDialog direct interdit - heriter de ThemedDialog',
            })

    image_pattern = re.compile(r'theme_manager\.image\.(\w+)')
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        for m in image_pattern.finditer(stripped):
            attr = m.group(1)
            if attr not in ('logo', 'theme_btn'):
                violations.append({
                    'line': i, 'rule': 'C5',
                    'message': f'theme_manager.image.{attr} interdit - seuls logo et theme_btn sont autorises. Utiliser ds.*',
                })

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return violations

    violations.extend(check_c2(tree))
    violations.extend(check_c4_consecutive(tree))
    violations.extend(check_c6(tree))
    violations.extend(check_c7(tree, lines))
    violations.extend(check_c9(tree))
    violations.extend(check_c11(tree))
    violations.extend(check_c12(tree, source))
    if not is_common:
        violations.extend(check_c13(tree))

    return violations


# C2 - QMessageBox + input widgets in same scope

def check_c2(tree: ast.AST) -> list[dict]:
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            has_qm = False
            has_input = False
            qm_line = 0
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                    if sub.func.id == 'QMessageBox':
                        has_qm = True
                        qm_line = sub.lineno
                    if sub.func.id in ('QLineEdit', 'QTextEdit'):
                        has_input = True
            if has_qm and has_input:
                violations.append({
                    'line': qm_line, 'rule': 'C2',
                    'message': 'QMessageBox + QLineEdit/QTextEdit interdit - utiliser ThemedDialog',
                })
    return violations


# C4 - Label AU-DESSUS du champ: detect consecutive addWidget(field) then addWidget(QLabel)

def check_c4_consecutive(tree: ast.AST) -> list[dict]:
    """Flag only consecutive addWidget(field) -> addWidget(QLabel) on same layout.

    This catches the real bug (label under field) without false positives
    on pairs that are separated by other statements."""
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        body = node.body
        for i in range(len(body) - 1):
            curr_stmt = body[i]
            next_stmt = body[i + 1]

            # Current must be addWidget on a layout
            if not _is_add_widget(curr_stmt):
                continue
            curr_call = curr_stmt.value
            curr_layout = _layout_var(curr_call)
            if not curr_layout:
                continue

            # Current must be a FIELD (not a QLabel)
            if curr_call.args and _is_label_arg(curr_call.args[0]):
                continue  # label, skip

            # Next must be addWidget on same layout
            if not _is_add_widget(next_stmt):
                continue
            next_call = next_stmt.value
            next_layout = _layout_var(next_call)
            if next_layout != curr_layout:
                continue

            # Next must be a QLabel
            if not next_call.args:
                continue
            if not _is_label_arg(next_call.args[0]):
                continue

            violations.append({
                'line': next_stmt.lineno, 'rule': 'C4',
                'message': f'QLabel place APRES le champ en lignes consecutives (layout "{next_layout}") - inverser (Q8)',
            })
    return violations


def _is_label_arg(arg) -> bool:
    """Check if an arg to addWidget() is a label (new QLabel or existing var ending in _lbl)."""
    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == 'QLabel':
        return True
    if isinstance(arg, ast.Attribute):
        attr = arg.attr
        if attr.endswith('_lbl') or attr.endswith('_label'):
            return True
    return False


def _is_add_widget(stmt) -> bool:
    if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)):
        return False
    call = stmt.value
    return isinstance(call.func, ast.Attribute) and call.func.attr == 'addWidget'


def _layout_var(call: ast.Call):
    func = call.func
    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name):
            return func.value.id
        if isinstance(func.value, ast.Attribute):
            return func.value.attr
    return None


# C6 - Table column mismatch

def check_c6(tree: ast.AST) -> list[dict]:
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        header_counts = {}
        max_cols = {}
        for sub in ast.walk(node):
            if not (isinstance(sub, ast.Expr) and isinstance(sub.value, ast.Call)):
                continue
            call = sub.value
            if not isinstance(call.func, ast.Attribute):
                continue
            if call.func.attr == 'set_headers':
                tv = _table_var(call)
                if tv and call.args and isinstance(call.args[0], (ast.List, ast.Tuple)):
                    header_counts[tv] = len(call.args[0].elts)
            if call.func.attr in ('setItem', 'setCellWidget'):
                tv = _table_var(call)
                if tv and len(call.args) >= 2:
                    col_arg = call.args[1]
                    if isinstance(col_arg, ast.Constant) and isinstance(col_arg.value, int):
                        max_cols[tv] = max(max_cols.get(tv, 0), col_arg.value + 1)

        for tv, mc in max_cols.items():
            expected = header_counts.get(tv)
            if expected is not None and mc > expected:
                violations.append({
                    'line': node.lineno + 1, 'rule': 'C6',
                    'message': f'Table "{tv}": set_headers a {expected} colonnes mais utilise la colonne {mc - 1} - ajouter une colonne dans set_headers',
                })
    return violations


def _table_var(call: ast.Call):
    func = call.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute):
        return func.value.attr
    return None


# C7 - @safe_slot missing

def check_c7(tree: ast.AST, lines: list[str]) -> list[dict]:
    violations = []
    safe_slotted = set()
    # Collect all method names defined in the module
    defined_methods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            defined_methods.add(node.name)
            for d in node.decorator_list:
                if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == 'safe_slot':
                    safe_slotted.add(node.name)

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
            continue
        call = node.value
        if not (isinstance(call.func, ast.Attribute) and call.func.attr == 'connect'):
            continue
        for arg in call.args:
            methods = set()
            if isinstance(arg, ast.Lambda):
                for sub in ast.walk(arg.body):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                        if isinstance(sub.func.value, ast.Name) and sub.func.value.id == 'self':
                            methods.add(sub.func.attr)
            elif isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) and arg.value.id == 'self':
                methods.add(arg.attr)
            for m in methods:
                if m.startswith('_on_') and m not in safe_slotted and m in defined_methods:
                    violations.append({
                        'line': call.lineno, 'rule': 'C7',
                        'message': f'Slot "{m}" connecte sans @safe_slot',
                    })
    return violations


# C9 - Icon-only button without tooltip

def check_c9(tree: ast.AST) -> list[dict]:
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        btn_props = {}
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name) and isinstance(stmt.value, ast.Call):
                        c = stmt.value
                        if isinstance(c.func, ast.Name) and c.func.id == 'QPushButton':
                            btn_props[t.id] = {'has_icon': False, 'has_text': False, 'has_tooltip': False, 'line': stmt.lineno}
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                c = stmt.value
                if isinstance(c.func, ast.Attribute):
                    a = c.func.attr
                    if isinstance(c.func.value, ast.Name):
                        v = c.func.value.id
                        if v in btn_props:
                            if a == 'setIcon': btn_props[v]['has_icon'] = True
                            if a == 'setText': btn_props[v]['has_text'] = True
                            if a == 'setToolTip': btn_props[v]['has_tooltip'] = True

        for var, props in btn_props.items():
            if props['has_icon'] and not props['has_text'] and not props['has_tooltip']:
                violations.append({
                    'line': props['line'], 'rule': 'C9',
                    'message': f'Bouton icone-seul "{var}" sans setToolTip()',
                })
    return violations


# C11 - QDateEdit/QDateTimeEdit without setMinimumWidth (Q10d)

def check_c11(tree: ast.AST) -> list[dict]:
    """QDateEdit/QDateTimeEdit must have setMinimumWidth (Q10d: 136px minimum)."""
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        date_vars: dict[str, int] = {}  # var_name -> creation_line
        date_has_minwidth: set[str] = set()

        for stmt in ast.walk(node):
            # Detect creation: var = QDateEdit() or var = QDateTimeEdit()
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name) and isinstance(stmt.value, ast.Call):
                        c = stmt.value
                        if isinstance(c.func, ast.Name) and c.func.id in ('QDateEdit', 'QDateTimeEdit'):
                            date_vars[t.id] = stmt.lineno

            # Detect setMinimumWidth called on the var
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                c = stmt.value
                if isinstance(c.func, ast.Attribute) and c.func.attr == 'setMinimumWidth':
                    if isinstance(c.func.value, ast.Name):
                        date_has_minwidth.add(c.func.value.id)

        for var, line in date_vars.items():
            if var not in date_has_minwidth:
                violations.append({
                    'line': line, 'rule': 'C11',
                    'message': f'{var} (QDateEdit/QDateTimeEdit) sans setMinimumWidth — ajouter setMinimumWidth(ds.sp(SpacingToken.XXXL)) (Q10d)',
                })
    return violations


# C12 - QDateTimeEdit/QDateEdit/QComboBox QSS without asymmetric padding (Q10c)

PADDING_SINGLE_PATTERN = re.compile(
    r'Q(?:DateTimeEdit|DateEdit|ComboBox)\s*\{[^}]*padding:\s*(?:{ds\.space_sm}|{ds\.space_md}|{ds\.space_lg}|\d{2,})\s*px[^}]*\}',
    re.DOTALL,
)

def check_c12(tree: ast.AST, source: str) -> list[dict]:
    """QDateTimeEdit/QDateEdit/QComboBox QSS blocks must use asymmetric padding (Q10c)."""
    violations = []
    # Check in the raw source for single-value padding on date/combo QSS blocks
    pattern = re.compile(
        r'Q(?:DateTimeEdit|DateEdit|ComboBox)\b[^{]*\{([^}]*)\}',
        re.DOTALL,
    )
    for m in pattern.finditer(source):
        block = m.group(1)
        # Find padding declarations
        pad_match = re.search(r'padding:\s*([^;]+);', block)
        if not pad_match:
            continue
        pad_val = pad_match.group(1).strip()
        # Single value means uniform padding. Check if it's >= 12px
        parts = pad_val.split()
        if len(parts) == 1:
            val_str = parts[0]
            # Check for literal numbers >= 12
            lit_match = re.match(r'(\d+)px', val_str)
            if lit_match and int(lit_match.group(1)) >= 12:
                violations.append({
                    'line': 0, 'rule': 'C12',
                    'message': f'Padding uniforme {val_str} sur QComboBox/QDateEdit — utiliser padding: Xpx Ypx (Q10c: vertical <= space_xs)',
                })
            # Check for ds.space_sm, ds.space_md, ds.space_lg tokens
            if re.search(r'ds\.space_(sm|md|lg)\b', val_str):
                violations.append({
                    'line': 0, 'rule': 'C12',
                    'message': f'Padding uniforme {val_str} sur QComboBox/QDateEdit — utiliser padding: Xpx Ypx (Q10c: vertical <= space_xs)',
                })
    return violations


# C13 - Silent error handling: except:pass, print_exc() without QMessageBox, return without message

def check_c13(tree: ast.AST) -> list[dict]:
    """Detect silent error handling patterns."""
    violations = []

    # Allowed except types — standard Python patterns
    C13_EXEMPT = {'RuntimeError', 'ValueError', 'OSError', 'SyntaxError', 'StopIteration',
                  'KeyError', 'IndexError', 'TypeError', 'AttributeError'}

    for node in ast.walk(tree):
        # C13a: except Exception / except: pass (excluding standard exempted types)
        if isinstance(node, ast.ExceptHandler):
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                # Check if the excepted type is exempted
                exempted = False
                if node.type:
                    if isinstance(node.type, ast.Name) and node.type.id in C13_EXEMPT:
                        exempted = True
                    elif isinstance(node.type, ast.Tuple):
                        exempted = all(
                            isinstance(e, ast.Name) and e.id in C13_EXEMPT
                            for e in node.type.elts
                        )
                if not exempted:
                    violations.append({
                        'line': node.lineno, 'rule': 'C13',
                        'message': 'except: pass interdit — avertir l\'utilisateur en cas d\'erreur',
                    })

        # C13b: except with traceback.print_exc() but no QMessageBox
        if isinstance(node, ast.ExceptHandler):
            has_print_exc = False
            has_qmessage = False
            for sub in ast.walk(node):
                if isinstance(sub, ast.Expr) and isinstance(sub.value, ast.Call):
                    call = sub.value
                    if isinstance(call.func, ast.Attribute) and call.func.attr == 'print_exc':
                        has_print_exc = True
                # QMessageBox is imported inline, check for .warning or .information on any call
                if isinstance(sub, ast.Expr) and isinstance(sub.value, ast.Call):
                    call = sub.value
                    if isinstance(call.func, ast.Attribute):
                        if call.func.attr in ('warning', 'information', 'critical', 'question'):
                            has_qmessage = True
                # Also check for self._show_error(...)
                if isinstance(sub, ast.Expr) and isinstance(sub.value, ast.Call):
                    call = sub.value
                    if isinstance(call.func, ast.Attribute) and call.func.attr == '_show_error':
                        has_qmessage = True
            if has_print_exc and not has_qmessage:
                violations.append({
                    'line': node.lineno, 'rule': 'C13',
                    'message': 'print_exc() sans QMessageBox — ajouter un message utilisateur',
                })

        # C13c: return in _on_save / _on_validate without prior QMessageBox
        if isinstance(node, ast.FunctionDef) and node.name in ('_on_save', '_on_validate'):
            for sub in ast.walk(node):
                if isinstance(sub, ast.If):
                    for direct_child in sub.body:
                        if isinstance(direct_child, ast.Return) and direct_child.value is None:
                            # Direct "if ... : return" — check for message in siblings
                            has_msg = False
                            for s in sub.body:
                                if s is direct_child:
                                    break
                                if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call):
                                    call = s.value
                                    if isinstance(call.func, ast.Attribute):
                                        if call.func.attr in ('warning', 'information', 'critical',
                                                              'question', '_show_error', '_show_success'):
                                            has_msg = True
                            if not has_msg:
                                violations.append({
                                    'line': direct_child.lineno, 'rule': 'C13',
                                    'message': 'return muet sans message utilisateur — ajouter QMessageBox avant le return',
                                })

    return violations


# Main

def format_violations(filepath: Path, violations: list[dict]) -> str:
    lines = []
    rel = str(filepath.resolve().relative_to(Path.cwd().resolve()))
    lines.append(f"\n{'='*60}")
    lines.append(f"File: {rel}")
    lines.append(f"{'='*60}")
    for v in sorted(violations, key=lambda x: (x['rule'], x['line'])):
        lines.append(f"  L{v['line']:>4d}  {v['rule']}  {v['message']}")
    return '\n'.join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Linter de pre-soumission (C1-C7, C9)")
    parser.add_argument('--dir', type=str, help='Repertoire a auditer')
    parser.add_argument('--json', action='store_true', help='Sortie JSON')
    args = parser.parse_args()

    targets = [Path(args.dir).resolve()] if args.dir else [Path(p).resolve() for p in PROJETS if os.path.isdir(p)]

    all_violations = []
    for target in targets:
        if not target.is_dir():
            continue
        for py_file in target.rglob('*.py'):
            if '__pycache__' in str(py_file) or 'tests' in str(py_file):
                continue
            v = lint_file(py_file)
            if v:
                all_violations.append((py_file, v))

    if args.json:
        import json
        output = []
        for fp, vs in all_violations:
            for v in vs:
                output.append({
                    'file': str(fp.resolve().relative_to(Path.cwd().resolve())),
                    'line': v['line'],
                    'rule': v['rule'],
                    'message': v['message'],
                })
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return 1 if output else 0

    if not all_violations:
        print("[OK] Preflight - 0 violation")
        return 0

    total = sum(len(vs) for _, vs in all_violations)
    print(f"\n[Preflight] {total} violation(s)")
    for fp, vs in all_violations:
        print(format_violations(fp, vs))
    print(f"\nTotal: {total} violation(s) -> cible 0")
    return 1


if __name__ == '__main__':
    sys.exit(main())
