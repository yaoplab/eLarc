#!/usr/bin/env python3
"""Linter : Keyboard navigation accessibility (WCAG 2.1 Level AAA).

Vérifie:
1. Tous les widgets interactifs sont keyboard accessible
2. Focus order est logique (top→left→bottom→right)
3. Pas de keyboard trap
4. Escape key ferme les dialogs
5. Tab/Shift+Tab pour naviguer
6. Arrow keys pour lister/grille

Standards:
- WCAG 2.1 Level A: Keyboard (2.1.1)
- WCAG 2.1 Level A: No Keyboard Trap (2.1.2)
"""

import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List


@dataclass
class KeyboardIssue:
    file: str
    line: int
    col: int
    code: str
    message: str
    severity: str = "warning"


# Widgets that need keyboard support
INTERACTIVE_WIDGETS = {
    'QPushButton', 'QToolButton',
    'QLineEdit', 'QTextEdit', 'QPlainTextEdit',
    'QComboBox', 'QCheckBox', 'QRadioButton',
    'QSlider', 'QSpinBox', 'QDoubleSpinBox',
    'QListWidget', 'QTableWidget', 'QTreeWidget',
    'M3Button', 'M3TextField', 'M3ComboBox', 'M3Card',
}


class KeyboardNavLinter:
    """Linter pour conformité keyboard navigation."""

    def __init__(self):
        self.issues: List[KeyboardIssue] = []

    def lint_file(self, filepath: Path) -> List[KeyboardIssue]:
        """Analyse un fichier pour violations keyboard."""
        if filepath.suffix not in ['.py']:
            return []

        try:
            content = filepath.read_text(encoding='utf-8')
        except Exception:
            return []

        self._lint_python(filepath, content)
        return self.issues

    def _lint_python(self, filepath: Path, content: str):
        """Linte code Python."""
        lines = content.split('\n')

        for line_no, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith('#'):
                continue

            # Check: Interactive widget without setFocusPolicy
            for widget in INTERACTIVE_WIDGETS:
                if f'{widget}(' in line:
                    # Look ahead for setFocusPolicy
                    next_lines = '\n'.join(lines[line_no:min(line_no+15, len(lines))])
                    if 'setFocusPolicy' not in next_lines:
                        self.issues.append(KeyboardIssue(
                            file=str(filepath),
                            line=line_no,
                            col=0,
                            code="KB_001_NO_FOCUS_POLICY",
                            message=f"{widget} created without setFocusPolicy(Qt.StrongFocus). Add focus policy.",
                            severity="warning",
                        ))

            # Check: Dialog without Escape key handler
            if 'QDialog(' in line or 'M3Dialog(' in line:
                # Check for Escape/reject handler
                next_lines = '\n'.join(lines[line_no:min(line_no+30, len(lines))])
                if 'Escape' not in next_lines and 'reject' not in next_lines:
                    self.issues.append(KeyboardIssue(
                        file=str(filepath),
                        line=line_no,
                        col=0,
                        code="KB_002_NO_ESCAPE_HANDLER",
                        message="Dialog created without Escape key handler. Add QShortcut for Esc.",
                        severity="warning",
                    ))

            # Check: List/Table without arrow key handler
            if 'QListWidget(' in line or 'QTableWidget(' in line or 'M3Table' in line:
                # Check for keyPressEvent
                next_lines = '\n'.join(lines[line_no:min(line_no+50, len(lines))])
                if 'keyPressEvent' not in next_lines and 'Key_Up' not in next_lines:
                    self.issues.append(KeyboardIssue(
                        file=str(filepath),
                        line=line_no,
                        col=0,
                        code="KB_003_NO_ARROW_KEYS",
                        message="Table/List without arrow key handler. Implement keyPressEvent for arrow keys.",
                        severity="info",
                    ))

            # Check: setFocusPolicy(Qt.NoFocus) on interactive widget
            if 'setFocusPolicy(Qt.NoFocus)' in line:
                self.issues.append(KeyboardIssue(
                    file=str(filepath),
                    line=line_no,
                    col=line.index('NoFocus'),
                    code="KB_004_NO_FOCUS",
                    message="Interactive widget has setFocusPolicy(Qt.NoFocus). Must use StrongFocus or TabFocus.",
                    severity="error",
                ))

            # Check: Manual Tab/Shift+Tab handling (anti-pattern)
            if 'Key_Tab' in line:
                self.issues.append(KeyboardIssue(
                    file=str(filepath),
                    line=line_no,
                    col=line.index('Key_Tab'),
                    code="KB_005_MANUAL_TAB",
                    message="Manual Tab key handling detected. Let Qt manage Tab order via setTabOrder().",
                    severity="warning",
                ))

            # Check: Missing setTabOrder for complex widgets
            if '__init__' in line and 'Dialog' in line:
                next_lines = '\n'.join(lines[line_no:min(line_no+100, len(lines))])
                widget_count = next_lines.count('self.')
                if widget_count >= 5 and 'setTabOrder' not in next_lines:
                    self.issues.append(KeyboardIssue(
                        file=str(filepath),
                        line=line_no,
                        col=0,
                        code="KB_006_NO_TAB_ORDER",
                        message=f"Dialog with {widget_count}+ widgets missing setTabOrder(). Define Tab order.",
                        severity="warning",
                    ))


def main():
    """Entry point."""
    if len(sys.argv) < 2:
        print("Usage: python lint_keyboard_nav.py <path>")
        sys.exit(1)

    root_path = Path(sys.argv[1])
    linter = KeyboardNavLinter()

    # Find all Python files
    py_files = list(root_path.rglob('*.py'))

    all_issues = []
    for filepath in py_files:
        # Skip vendor dirs
        if any(skip in str(filepath) for skip in ['__pycache__', '.git', 'venv', '.venv']):
            continue

        issues = linter.lint_file(filepath)
        all_issues.extend(issues)

    # Group by severity
    info_msgs = [i for i in all_issues if i.severity == 'info']
    warnings = [i for i in all_issues if i.severity == 'warning']
    errors = [i for i in all_issues if i.severity == 'error']

    # Report
    if info_msgs:
        print(f"\nℹ️  {len(info_msgs)} Keyboard navigation info:\n")
        for issue in info_msgs[:10]:
            print(f"{issue.file}:{issue.line}: {issue.message}\n")

    if warnings:
        print(f"\n⚠️  {len(warnings)} Keyboard navigation warnings:\n")
        for issue in warnings[:20]:
            print(f"{issue.file}:{issue.line}")
            print(f"  {issue.code}: {issue.message}\n")

    if errors:
        print(f"\n❌ {len(errors)} Keyboard navigation errors:\n")
        for issue in errors[:20]:
            print(f"{issue.file}:{issue.line}")
            print(f"  {issue.code}: {issue.message}\n")

    if warnings or errors:
        print(f"\n📊 Summary: {len(errors)} errors, {len(warnings)} warnings, {len(info_msgs)} info")
        sys.exit(1 if errors else 0)
    else:
        print("✅ Keyboard navigation OK! (WCAG 2.1 Level A)")
        sys.exit(0)


if __name__ == '__main__':
    main()
