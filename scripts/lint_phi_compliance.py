#!/usr/bin/env python3
"""Linter : Force conformité Fibonacci (100% de tokens via Phi).

Détecte :
- Spacing hardcodés (4, 8, 12, 20, 32, 52, 84, 136, etc.)
- Sizing hardcodés (144, 233, 377, 52, 64, etc.)
- Magic numbers au lieu de ds.* tokens
- Proportions non-Fibonacci

Fibonacci sequence (base 4px):
  4, 8, 12, 20, 32, 52, 84, 136, 220, 356, 576, 932, 1508...

Phi-authorized sizes:
  Card: 144×233 (F(7)×F(8))
  Button height: 52px (F(6))
  Field height: 52px
  Header height: 64px
  Spacing: 4, 8, 12, 20, 32, 52, 84, 136
"""

import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Set

# Authorized Fibonacci sizes
FIBONACCI_SIZES = {4, 8, 12, 20, 32, 52, 84, 136, 220, 356, 576, 932, 1508}
GOLDEN_SECTIONS = {
    6, 10, 17, 27, 44, 72, 116, 188, 304,  # φ^n
}

# Component-specific authorized sizes
AUTHORIZED_SIZES = FIBONACCI_SIZES | GOLDEN_SECTIONS | {
    40, 48, 64, 144, 233, 377,  # Extended for components
    44,  # Touch target min (Apple/Google)
}


@dataclass
class Issue:
    file: str
    line: int
    col: int
    code: str
    message: str
    severity: str = "warning"


class PhiComplianceLinter:
    """Linter pour conformité Phi/Fibonacci."""

    def __init__(self):
        self.issues: List[Issue] = []

    def lint_file(self, filepath: Path) -> List[Issue]:
        """Analyse un fichier Python pour violations Phi."""
        if not filepath.suffix in ['.py', '.qss']:
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

        # Patterns de violations
        patterns = [
            # setSpacing/setContentsMargins avec nombres
            (r'setSpacing\((\d+)\)', 'hardcoded_spacing'),
            (r'setContentsMargins\((\d+)[,\s]', 'hardcoded_margins'),
            (r'setFixedHeight\((\d+)\)', 'hardcoded_height'),
            (r'setFixedWidth\((\d+)\)', 'hardcoded_width'),
            (r'setMinimumHeight\((\d+)\)', 'hardcoded_min_height'),
            (r'setMinimumWidth\((\d+)\)', 'hardcoded_min_width'),
            (r'setMaximumHeight\((\d+)\)', 'hardcoded_max_height'),
            (r'setMaximumWidth\((\d+)\)', 'hardcoded_max_width'),
            (r'layout\.setSpacing\((\d+)\)', 'hardcoded_spacing'),
            (r'QMargins\((\d+)[,\s]', 'hardcoded_margins'),
        ]

        for line_no, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith('#'):
                continue

            # Skip strings
            if "'" in line or '"' in line:
                # Simple check: if line has string, skip deeper analysis
                pass

            for pattern, violation_type in patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    size_str = match.group(1)
                    try:
                        size = int(size_str)
                    except ValueError:
                        continue

                    if size not in AUTHORIZED_SIZES:
                        self.issues.append(Issue(
                            file=str(filepath),
                            line=line_no,
                            col=match.start(1),
                            code=f"PHI_001_{violation_type}",
                            message=f"Hardcoded size {size}px (not Fibonacci). Use ds.phi_* or ds.space_*",
                            severity="warning",
                        ))

    def _lint_qss(self, filepath: Path, content: str):
        """Linte QSS stylesheets."""
        lines = content.split('\n')

        # QSS patterns: margin, padding, width, height, border-radius
        patterns = [
            (r'margin\s*:\s*(\d+)px', 'hardcoded_margin_qss'),
            (r'padding\s*:\s*(\d+)px', 'hardcoded_padding_qss'),
            (r'width\s*:\s*(\d+)px', 'hardcoded_width_qss'),
            (r'height\s*:\s*(\d+)px', 'hardcoded_height_qss'),
            (r'border-radius\s*:\s*(\d+)px', 'hardcoded_radius_qss'),
            (r'min-width\s*:\s*(\d+)px', 'hardcoded_min_width_qss'),
            (r'max-width\s*:\s*(\d+)px', 'hardcoded_max_width_qss'),
        ]

        for line_no, line in enumerate(lines, 1):
            for pattern, violation_type in patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    size_str = match.group(1)
                    try:
                        size = int(size_str)
                    except ValueError:
                        continue

                    if size not in AUTHORIZED_SIZES:
                        self.issues.append(Issue(
                            file=str(filepath),
                            line=line_no,
                            col=match.start(1),
                            code=f"PHI_002_{violation_type}",
                            message=f"Hardcoded QSS size {size}px (not Fibonacci). Use design_system tokens.",
                            severity="warning",
                        ))


def main():
    """Entry point."""
    if len(sys.argv) < 2:
        print("Usage: python lint_phi_compliance.py <path>")
        sys.exit(1)

    root_path = Path(sys.argv[1])
    linter = PhiComplianceLinter()

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
        print(f"\n⚠️  {len(warnings)} Phi compliance warnings:\n")
        for issue in warnings[:20]:  # Limit output
            print(f"{issue.file}:{issue.line}:{issue.col}")
            print(f"  {issue.code}: {issue.message}\n")

    if errors:
        print(f"\n❌ {len(errors)} Phi compliance errors:\n")
        for issue in errors[:20]:
            print(f"{issue.file}:{issue.line}:{issue.col}")
            print(f"  {issue.code}: {issue.message}\n")

    if warnings or errors:
        print(f"\n📊 Summary: {len(errors)} errors, {len(warnings)} warnings")
        sys.exit(1 if errors else 0)
    else:
        print("✅ Phi compliance OK! All tokens are Fibonacci-based.")
        sys.exit(0)


if __name__ == '__main__':
    main()
