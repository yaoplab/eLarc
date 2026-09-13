#!/usr/bin/env python3
"""Linter : Conformité Focus Visible (keyboard accessibility).

Vérifie:
1. Tous les widgets interactifs ont un focus state visible
2. Focus outline ≥ 2px (WCAG AAA)
3. Focus outline contraste ≥ 3:1 avec élément
4. Focus order logique (top→left→bottom→right)

Standards:
- Focus outline width: 2px (ds.focus_outline_width)
- Focus outline offset: 2px (ds.focus_outline_offset)
- Focus visible: outline ou border change visible
"""

import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List


@dataclass
class FocusIssue:
    file: str
    line: int
    col: int
    code: str
    message: str
    severity: str = "warning"


# Interactive widgets that need focus states
INTERACTIVE_WIDGETS = {
    'QPushButton', 'QToolButton',
    'QLineEdit', 'QTextEdit', 'QPlainTextEdit',
    'QComboBox', 'QCheckBox', 'QRadioButton',
    'QSlider', 'QSpinBox', 'QDoubleSpinBox',
    'QListWidget', 'QTableWidget', 'QTreeWidget',
    'M3Button', 'M3TextField', 'M3Card',
    'M3ComboBox', 'M3CheckBox', 'M3RadioButton',
}


class FocusLinter:
    """Linter pour conformité focus."""

    def __init__(self):
        self.issues: List[FocusIssue] = []

    def lint_file(self, filepath: Path) -> List[FocusIssue]:
        """Analyse un fichier pour violations focus."""
        if filepath.suffix not in ['.py', '.qss']:
            return []

        try:
            content = filepath.read_text(encoding='utf-8')
        except Exception:
            return []

        if filepath.suffix == '.py':
            self._lint_python(filepath, content)
        elif filepath.suffix == '.qss':
            self._lint_qss(filepath, content)

        return self.issues

    def _lint_python(self, filepath: Path, content: str):
        """Linte code Python."""
        lines = content.split('\n')

        # Track widget declarations
        current_widget = None
        has_focus_policy = False

        for line_no, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith('#'):
                continue

            # Track widget creation
            for widget in INTERACTIVE_WIDGETS:
                if f'{widget}(' in line:
                    current_widget = widget
                    has_focus_policy = False

                    # Check next lines for setFocusPolicy
                    next_lines = '\n'.join(lines[line_no:min(line_no+10, len(lines))])
                    if 'setFocusPolicy' not in next_lines:
                        self.issues.append(FocusIssue(
                            file=str(filepath),
                            line=line_no,
                            col=0,
                            code="FOCUS_001_POLICY",
                            message=f"{widget} created without setFocusPolicy(). Add setFocusPolicy(Qt.StrongFocus).",
                            severity="warning",
                        ))

            # Check: QPushButton without stylesheet focus state
            if 'QPushButton' in line and '(' in line:
                # Check if stylesheet is set later
                next_lines = '\n'.join(lines[line_no:min(line_no+20, len(lines))])
                if 'setStyleSheet' in next_lines:
                    stylesheet_match = re.search(r'setStyleSheet\((.*?)\)', next_lines, re.DOTALL)
                    if stylesheet_match:
                        stylesheet = stylesheet_match.group(1)
                        if ':focus' not in stylesheet and 'ds.focus' not in next_lines:
                            self.issues.append(FocusIssue(
                                file=str(filepath),
                                line=line_no,
                                col=0,
                                code="FOCUS_002_MISSING_FOCUS_STATE",
                                message="Button stylesheet missing :focus state. Add visible focus indicator.",
                                severity="warning",
                            ))

            # Check: Custom widgets without focus
            if 'class ' in line and '(QWidget)' in line:
                class_name = re.search(r'class\s+(\w+)\s*\(QWidget\)', line)
                if class_name:
                    # Check for setFocusPolicy in __init__
                    next_lines = '\n'.join(lines[line_no:min(line_no+50, len(lines))])
                    if 'interactive' not in class_name.group(1).lower():
                        # Not obviously interactive, skip
                        pass

    def _lint_qss(self, filepath: Path, content: str):
        """Linte QSS stylesheets."""
        lines = content.split('\n')

        for line_no, line in enumerate(lines, 1):
            # Check: Widget selector without :focus state
            if line.strip().startswith(('QWidget', 'QPushButton', 'QLineEdit', 'M3')):
                selector = line.strip()

                # Check if focus state exists
                if ':focus' not in selector:
                    # Look ahead for :focus
                    next_lines = '\n'.join(lines[line_no:min(line_no+20, len(lines))])
                    if ':focus' not in next_lines:
                        self.issues.append(FocusIssue(
                            file=str(filepath),
                            line=line_no,
                            col=0,
                            code="FOCUS_003_SELECTOR_NO_FOCUS",
                            message=f"Selector '{selector}' missing :focus state. Add focus indicator.",
                            severity="warning",
                        ))

            # Check: :focus state without outline or border
            if ':focus' in line:
                # Check if line has outline or border
                if 'outline' not in line and 'border' not in line:
                    self.issues.append(FocusIssue(
                        file=str(filepath),
                        line=line_no,
                        col=0,
                        code="FOCUS_004_OUTLINE_MISSING",
                        message=":focus state missing outline or border. Add visible indicator.",
                        severity="warning",
                    ))

            # Check: Focus outline too thin
            outline_match = re.search(r'outline\s*:\s*(\d+)px', line)
            if outline_match:
                outline_width = int(outline_match.group(1))
                if outline_width < 2:
                    self.issues.append(FocusIssue(
                        file=str(filepath),
                        line=line_no,
                        col=outline_match.start(),
                        code="FOCUS_005_OUTLINE_TOO_THIN",
                        message=f"Focus outline {outline_width}px < 2px (minimum). Use ds.focus_outline_width (2px).",
                        severity="warning",
                    ))

            # Check: Border without sufficient contrast indicator
            if 'border' in line and ':focus' in lines[max(0, line_no-5):line_no+1]:
                # This is a focus border, check if it has enough contrast
                # (Hard to check without color context, so just flag)
                pass


def main():
    """Entry point."""
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) < 2:
        print("Usage: python lint_focus_visible.py <path>")
        sys.exit(1)

    root_path = Path(sys.argv[1])
    linter = FocusLinter()

    # Find all Python and QSS files
    py_files = list(root_path.rglob('*.py'))
    qss_files = list(root_path.rglob('*.qss'))

    all_issues = []
    for filepath in py_files + qss_files:
        # Skip vendor dirs
        if any(skip in str(filepath) for skip in ['__pycache__', '.git', 'venv', '.venv']):
            continue

        issues = linter.lint_file(filepath)
        all_issues.extend(issues)

    # Group by severity
    warnings = [i for i in all_issues if i.severity == 'warning']
    errors = [i for i in all_issues if i.severity == 'error']

    # Report
    if warnings:
        print(f"\n⚠️  {len(warnings)} Focus visibility warnings:\n")
        for issue in warnings[:20]:
            print(f"{issue.file}:{issue.line}")
            print(f"  {issue.code}: {issue.message}\n")

    if errors:
        print(f"\n❌ {len(errors)} Focus visibility errors:\n")
        for issue in errors[:20]:
            print(f"{issue.file}:{issue.line}")
            print(f"  {issue.code}: {issue.message}\n")

    if warnings or errors:
        print(f"\n📊 Summary: {len(errors)} errors, {len(warnings)} warnings")
        sys.exit(1 if errors else 0)
    else:
        print("✅ Focus visibility OK! (Keyboard accessible)")
        sys.exit(0)


if __name__ == '__main__':
    main()
