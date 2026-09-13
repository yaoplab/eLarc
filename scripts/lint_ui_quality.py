#!/usr/bin/env python3
"""
lint_ui_quality.py — Linter de qualité visuelle et finition UI.

Détecte les défauts de finition que les linters de tokens (D-linter, R-linter)
ne voient pas : emojis, widgets orphelins, tooltips manquants, layouts sans stretch.

Règles couvertes :
  V1 — Emojis dans l'UI (doit utiliser md3_icon())
  V2 — Tailles codées en dur sans token ds.*
  V6 — Boutons icône-seuls sans setToolTip()
  V7 — Layouts sans addStretch()
  V8 — Boutons icône+texte sans text-align: left (gap icône↔texte, sidebar-spec K26)

Usage:
  python scripts/lint_ui_quality.py                      # Tous les projets
  python scripts/lint_ui_quality.py --dir .\\LarcRH        # Un seul projet
  python scripts/lint_ui_quality.py --json                 # Sortie JSON
  python scripts/lint_ui_quality.py --fix                  # Rapport avec suggestions
"""

LINTER_META = {
    "key": "V",
    "label": "Finitions UI",
    "category": "ui",
    "description": "Emojis, tooltips manquants, layouts sans stretch, gaps icône-texte",
    "skill": "ui-quality",
}

import ast
import re
import sys
import os
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _baseline import load_baseline, save_baseline, split_new

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "scripts" / ".ui_quality_baseline.json"
PROJETS = [ROOT / n for n in (
    "LarcSuperviseur",
    "LarcSecretaire",
    "LarcProf",
    "LarcHub",
    "LarcConfig",
    "LarcRH",
    "LarcCompta",
)]

# Emoji Unicode ranges (simplified — covers common emoji blocks)
EMOJI_PATTERN = re.compile(
    '[\U0001F300-\U0001F9FF'   # Miscellaneous Symbols, Emoticons, etc.
    '\U0001FA00-\U0001FA6F'    # Chess Symbols
    '\U0001FA70-\U0001FAFF'    # Symbols Extended-A
    '\U00002600-\U000027BF'    # Misc symbols (includes checkmarks, X marks)
    '\U00002700-\U000027BF'    # Dingbats
    ']'
)

# Emoji characters that are COMMONLY misused as UI icons
EMOJI_ICONS = {
    '👥': 'group',
    '📝': 'assignment',
    '✕': 'cancel',
    '✗': 'cancel',
    '✘': 'cancel',
    '⏳': 'schedule',
    '⚠': 'warning',
    '📄': 'description',
    '✅': 'check_circle',
    '❌': 'cancel',
    '🔍': 'search',
    '➕': 'add',
    '📋': 'assignment',
    '📌': 'push_pin',
    '🔔': 'notifications',
    '🔒': 'lock',
    '🔓': 'lock_open',
    '⭐': 'star',
    '❤': 'favorite',
    '💬': 'chat',
    '📧': 'mail',
    '📅': 'calendar_today',
    '📊': 'bar_chart',
    '📈': 'trending_up',
    '📉': 'trending_down',
    '🏠': 'home',
    '⚙': 'settings',
    '🔄': 'refresh',
    '💾': 'save',
    '🗑': 'delete',
    '✏': 'edit',
    '👤': 'person',
    '📁': 'folder',
    '📂': 'folder_open',
}

VIOLATIONS = []


# Allowed literal values for V2 (M3 standard sizes, separators)
V2_ALLOWED = {
    0,   # spacers
    1,   # separator line height
    24,  # M3 icon button
    32,  # ds.field_height
    48,  # M3 snackbar
    52,  # ds.button_height / ds.header_height
    56,  # M3 FAB
}

def is_hardcoded_size(node: ast.Call) -> Optional[str]:
    """Check setFixedSize/setMinimumSize with hardcoded literals (multi-arg only).

    Single-arg calls (setFixedHeight, setFixedWidth) are already caught by the R-linter.
    This check focuses on multi-arg calls that the R-linter may miss.
    """
    multi_arg_funcs = {'setFixedSize', 'setMinimumSize', 'setMaximumSize'}
    if isinstance(node.func, ast.Attribute) and node.func.attr in multi_arg_funcs:
        if len(node.args) >= 2:
            for arg in node.args[:2]:  # check width and height
                if isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)):
                    val = int(arg.value)
                    if val not in V2_ALLOWED and val > 1:
                        return f"V2 — {node.func.attr}({val}, ...) -> utiliser un token ds.*"
    return None


def has_tooltip_in_block(block_stmts: list, btn_var: str) -> bool:
    """Check if a button variable has setToolTip called on it in the same block."""
    for stmt in block_stmts:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == 'setToolTip':
                if isinstance(call.func.value, ast.Name) and call.func.value.id == btn_var:
                    return True
            # Also check chained calls: btn.setIcon(...).setToolTip(...) — unlikely but possible
    return False


def find_button_tooltip_violations(tree: ast.AST, source_lines: list[str]) -> list[dict]:
    """V6: Find icon-only QPushButton without setToolTip."""
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Find QPushButton() assignments
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name) and isinstance(stmt.value, ast.Call):
                            call = stmt.value
                            if isinstance(call.func, ast.Name) and call.func.id == 'QPushButton':
                                btn_var = target.id
                                has_text = any(
                                    isinstance(kw, ast.keyword) and kw.arg == 'text'
                                    for kw in call.keywords
                                )
                                if has_text:
                                    continue  # Has visible text → no tooltip needed

                                # Check if setText() is called later
                                set_text_found = False
                                set_icon_found = False
                                has_tooltip = False
                                for sub in ast.walk(node):
                                    if isinstance(sub, ast.Expr) and isinstance(sub.value, ast.Call):
                                        sc = sub.value
                                        if isinstance(sc.func, ast.Attribute) and isinstance(sc.func.value, ast.Name) and sc.func.value.id == btn_var:
                                            if sc.func.attr == 'setText':
                                                set_text_found = True
                                            if sc.func.attr == 'setIcon':
                                                set_icon_found = True
                                            if sc.func.attr == 'setToolTip':
                                                has_tooltip = True

                                if set_text_found:
                                    continue  # Has visible text
                                if not set_icon_found:
                                    continue  # No icon either → not an icon-only button
                                if not has_tooltip:
                                    violations.append({
                                        'line': stmt.lineno,
                                        'rule': 'V6',
                                        'message': f'Bouton icône-seul "{btn_var}" sans setToolTip()',
                                    })
    return violations


def find_layout_stretch_violations(tree: ast.AST) -> list[dict]:
    """V7: Find QHBoxLayout/QVBoxLayout without addStretch or stretch factor."""
    violations = []
    layout_types = {'QHBoxLayout', 'QVBoxLayout'}

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Track layout variables and their stretch counts
            layout_vars: dict[str, dict] = {}
            for stmt in ast.walk(node):
                # Detect: var = QHBoxLayout() or var = QVBoxLayout()
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name) and isinstance(stmt.value, ast.Call):
                            call = stmt.value
                            if isinstance(call.func, ast.Name) and call.func.id in layout_types:
                                layout_vars[target.id] = {
                                    'line': stmt.lineno,
                                    'has_stretch': False,
                                    'type': call.func.id,
                                }

                # Detect: var.addStretch()
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    call = stmt.value
                    if isinstance(call.func, ast.Attribute) and call.func.attr == 'addStretch':
                        if isinstance(call.func.value, ast.Name):
                            name = call.func.value.id
                            if name in layout_vars:
                                layout_vars[name]['has_stretch'] = True

                # Detect: var.addWidget(..., stretch=N)
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    call = stmt.value
                    if isinstance(call.func, ast.Attribute) and call.func.attr == 'addWidget':
                        # Check keyword 'stretch' or positional arg at index 1 for addWidget
                        if len(call.args) >= 2:
                            arg1 = call.args[1]
                            if isinstance(arg1, ast.Constant) and isinstance(arg1.value, (int, float)) and arg1.value >= 1:
                                if isinstance(call.func.value, ast.Name):
                                    name = call.func.value.id
                                    if name in layout_vars:
                                        layout_vars[name]['has_stretch'] = True

                # Detect: layout.addLayout(sub_layout, stretch=N)
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    call = stmt.value
                    if isinstance(call.func, ast.Attribute) and call.func.attr == 'addLayout':
                        if len(call.args) >= 2:
                            arg1 = call.args[1]
                            if isinstance(arg1, ast.Constant) and isinstance(arg1.value, (int, float)) and arg1.value >= 1:
                                if isinstance(call.func.value, ast.Name):
                                    name = call.func.value.id
                                    if name in layout_vars:
                                        layout_vars[name]['has_stretch'] = True

            # Report layouts without stretch
            for var_name, info in layout_vars.items():
                if not info['has_stretch']:
                    # Skip layouts that are sub-layouts (nested) — only flag top-level ones
                    violations.append({
                        'line': info['line'],
                        'rule': 'V7',
                        'message': f'{info["type"]} "{var_name}" sans addStretch() ni stretch>=1',
                    })

    return violations


def _string_value(node: ast.AST) -> Optional[str]:
    """Valeur d'une chaîne littérale (Constant) ou f-string sans formatage (JoinedStr)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
        if parts:
            return "".join(parts)
    return None


def _iter_scope_stmts(scope: ast.AST):
    """Parcourt les statements d'une portée SANS descendre dans les portées imbriquées."""
    for stmt in ast.walk(scope):
        if stmt is scope:
            continue
        if isinstance(stmt, (ast.FunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(stmt, ast.stmt):
            yield stmt


def _target_of(base: ast.AST) -> Optional[str]:
    """Nom qualifié de la cible d'un appel : ``self``, ``btn``, ``self._x``."""
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        chain = []
        node = base
        while isinstance(node, ast.Attribute):
            chain.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            chain.append(node.id)
            return ".".join(reversed(chain))
    return None


def find_icon_text_gap_violations(tree: ast.AST) -> list[dict]:
    """V8: Bouton icône+texte sans `text-align` dans un QSS de la même portée.

    Qt centre par défaut le groupe icône+texte d'un QPushButton : l'icône
    dérive selon la longueur du libellé et le gap n'est pas contrôlé.
    La règle K26 (sidebar-spec) impose `text-align: left` → gap natif
    8px = ds.space_xs. NavButton/M3Button appliquent l'alignement en interne
    (text_align) et sont donc exclus.
    """
    violations = []
    for scope in ast.walk(tree):
        if not isinstance(scope, (ast.FunctionDef, ast.ClassDef)):
            continue
        btn_vars: dict[str, int] = {}   # nom var → ligne
        icon_btns: set[str] = set()
        text_btns: set[str] = set()
        has_text_align = False

        for stmt in _iter_scope_stmts(scope):
            # x = QPushButton(...) / QToolButton(...)
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name) and isinstance(stmt.value, ast.Call):
                        call = stmt.value
                        if (isinstance(call.func, ast.Name)
                                and call.func.id in ('QPushButton', 'QToolButton')):
                            btn_vars[t.id] = stmt.lineno
                            for kw in call.keywords:
                                if kw.arg == 'text' and kw.value is not None:
                                    text_btns.add(t.id)

            if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
                continue
            call = stmt.value
            if not isinstance(call.func, ast.Attribute):
                continue
            target = _target_of(call.func.value)
            if target is None:
                continue

            if call.func.attr == 'setIcon':
                if target == 'self' or target in btn_vars:
                    icon_btns.add(target)
            elif call.func.attr == 'setText':
                if target == 'self' or target in btn_vars:
                    text_btns.add(target)
            elif call.func.attr == 'setStyleSheet':
                for arg in call.args:
                    val = _string_value(arg)
                    if val and 'text-align' in val:
                        has_text_align = True
                        break

        if has_text_align:
            continue

        # self : la classe EST le bouton (ex: _CategoryButton)
        if 'self' in icon_btns and 'self' in text_btns:
            violations.append({
                'line': getattr(scope, 'lineno', 0),
                'rule': 'V8',
                'message': (f'Bouton icône+texte ({scope.name}) sans text-align: left '
                            f'(K26 — gap icône↔texte = ds.space_xs)'),
            })
            continue
        # boutons nommés (var locale ou self._x) : icône ET texte sur le MÊME bouton
        same_targets = icon_btns & text_btns
        for name in sorted(same_targets, key=lambda n: btn_vars.get(n, 10**9)):
            line = btn_vars.get(name, getattr(scope, 'lineno', 0))
            violations.append({
                'line': line,
                'rule': 'V8',
                'message': (f'Bouton icône+texte "{name}" sans text-align: left '
                            f'dans son QSS (K26 — gap icône↔texte = ds.space_xs)'),
            })
    return violations


def lint_file(filepath: Path) -> list[dict]:
    """Run all V-rule checks on a single .py file."""
    violations = []
    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception:
        return violations

    lines = source.split('\n')

    # ── V1: Emojis ──
    for i, line in enumerate(lines, 1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith('#'):
            continue

        # Check for emoji characters in string literals
        for emoji, icon_name in EMOJI_ICONS.items():
            if emoji in stripped:
                violations.append({
                    'line': i,
                    'rule': 'V1',
                    'message': f'Emoji {emoji} -> utiliser md3_icon("{icon_name}", ...)',
                })

    # ── AST-based checks ──
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return violations

    # V2: Hardcoded sizes
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            msg = is_hardcoded_size(node)
            if msg:
                violations.append({
                    'line': node.lineno,
                    'rule': 'V2',
                    'message': msg,
                })

    # V6: Icon-only buttons without tooltip
    violations.extend(find_button_tooltip_violations(tree, lines))

    # V8: Boutons icône+texte sans text-align: left (gap icône↔texte K26)
    violations.extend(find_icon_text_gap_violations(tree))

    # V7: Layouts without stretch — revue manuelle uniquement
    # (trop de faux positifs sur les layouts internes de cards)

    return violations


def format_violations(filepath: Path, violations: list[dict]) -> str:
    """Format violations for a single file."""
    lines = []
    lines.append(f"\n{'='*60}")
    try:
        rel = filepath.relative_to(Path.cwd())
    except ValueError:
        rel = filepath.resolve().relative_to(Path.cwd().resolve())
    lines.append(f"File: {rel}")
    lines.append(f"{'='*60}")

    by_rule = {}
    for v in violations:
        by_rule.setdefault(v['rule'], []).append(v)

    for rule in sorted(by_rule.keys()):
        for v in by_rule[rule]:
            lines.append(f"  L{v['line']:>4d}  {v['rule']}  {v['message']}")

    return '\n'.join(lines)


def _emoji_name(emoji: str) -> str:
    """Return a safe description of an emoji for console output."""
    return f'U+{ord(emoji):04X}'


def main():
    import argparse
    # Force UTF-8 output on Windows
    sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
    parser = argparse.ArgumentParser(description="Linter de qualité visuelle UI")
    parser.add_argument('--dir', type=str, help='Répertoire à auditer')
    parser.add_argument('--json', action='store_true', help='Sortie JSON')
    parser.add_argument('--fix', action='store_true', help='Afficher les suggestions de correction')
    parser.add_argument('--baseline', action='store_true', help="(Re)genere la baseline avec les violations actuelles")
    parser.add_argument('--check-baseline', action='store_true', help="N'echoue que sur les violations absentes de la baseline (pre-commit)")
    args = parser.parse_args()

    targets = [Path(args.dir).resolve()] if args.dir else [Path(p).resolve() for p in PROJETS if os.path.isdir(p)]

    all_violations = []

    for target in targets:
        if target.is_dir():
            for py_file in target.rglob('*.py'):
                # Skip __pycache__ and tests
                if '__pycache__' in str(py_file) or 'tests' in str(py_file):
                    continue
                v = lint_file(py_file)
                if v:
                    all_violations.append((py_file, v))
        elif target.is_file() and target.suffix == '.py':
            v = lint_file(target)
            if v:
                all_violations.append((target, v))

    flat_findings = [
        {'file': str(fp.resolve().relative_to(ROOT)), 'line': v['line'], 'rule': v['rule'], 'message': v['message']}
        for fp, vs in all_violations for v in vs
    ]

    if args.baseline:
        save_baseline(BASELINE_PATH, flat_findings)
        print(f"[baseline] {len(flat_findings)} violation(s) figee(s) dans {BASELINE_PATH}")
        return 0

    if args.check_baseline:
        baseline = load_baseline(BASELINE_PATH)
        new, known = split_new(flat_findings, baseline)
        print(f"lint_ui_quality: {len(new)} nouvelle(s) violation(s), {len(known)} connue(s) (baseline, non bloquant)")
        for f in new:
            print(f"  [{f['rule']}] {f['file']}:{f['line']}  {f['message']}")
        return 1 if new else 0

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
        print("[OK] UI Quality - 0 violation")
        return 0

    total = sum(len(vs) for _, vs in all_violations)
    print(f"\n{'='*60}")
    print(f"[UI Quality Linter] {total} violation(s)")
    print(f"{'='*60}")

    for fp, vs in all_violations:
        print(format_violations(fp, vs))

    # Summary
    p0_count = total
    print(f"\n{'='*60}")
    print(f"Total: {p0_count} violation(s) -> cible 0")
    print(f"{'='*60}\n")

    if args.fix:
        print("Suggestions de correction :")
        for fp, vs in all_violations:
            for v in vs:
                if v['rule'] == 'V1':
                    # Extract emoji from message
                    for emoji, icon in EMOJI_ICONS.items():
                        if emoji in v['message']:
                            print(f"  {fp}:{v['line']} -> remplacer {emoji} par md3_icon(\"{icon}\")")
                            break
                elif v['rule'] == 'V6':
                    print(f"  {fp}:{v['line']} -> ajouter btn.setToolTip(\"Description de l'action\")")
                elif v['rule'] == 'V8':
                    print(f"  {fp}:{v['line']} -> ajouter btn.setStyleSheet(\"QPushButton {{ text-align: left; }}\") "
                          f"+ setIconSize (K26, gap 8px = ds.space_xs)")

    return 1 if total > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
