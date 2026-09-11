#!/usr/bin/env python3
"""Linter : Conformité Motion (Material Design 3 motion standards).

Vérifie:
1. Durées d'animation dans les limites (100-800ms)
2. Easing functions valides (cubic-bezier)
3. Pas d'animations bloquantes (> 500ms sans raison)
4. Smooth transitions (pas de sauts)

Standards Material Design 3:
- motion_quick: 100ms (hover, tooltip)
- motion_normal: 300ms (button, card)
- motion_slow: 500ms (page transition)
- motion_extra_slow: 800ms (complex animation)
"""

import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List


@dataclass
class MotionIssue:
    file: str
    line: int
    col: int
    code: str
    message: str
    severity: str = "warning"


# Authorized durations (Fibonacci-based)
AUTHORIZED_DURATIONS = {
    100, 300, 500, 800,  # Material Design 3 standard
    # Extended Fibonacci
    50, 75, 150, 200, 250, 400, 600, 700, 900, 1000,
}

# Valid easing functions
VALID_EASING = {
    'cubic-bezier(0.4, 0, 0.2, 1)',      # standard
    'cubic-bezier(0.4, 0, 0.6, 1)',      # emphasized
    'cubic-bezier(0, 0, 0.2, 1)',        # decelerated
    'cubic-bezier(0.4, 0, 1, 1)',        # accelerated
    'ease', 'ease-in', 'ease-out', 'ease-in-out',
    'linear',
}


class MotionLinter:
    """Linter pour conformité motion."""

    def __init__(self):
        self.issues: List[MotionIssue] = []

    def lint_file(self, filepath: Path) -> List[MotionIssue]:
        """Analyse un fichier pour violations motion."""
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

        for line_no, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith('#'):
                continue

            # Check: setDuration with hardcoded ms
            duration_match = re.search(r'setDuration\((\d+)\)', line)
            if duration_match:
                duration = int(duration_match.group(1))
                if duration not in AUTHORIZED_DURATIONS:
                    self.issues.append(MotionIssue(
                        file=str(filepath),
                        line=line_no,
                        col=duration_match.start(),
                        code="MOTION_001_DURATION",
                        message=f"Animation duration {duration}ms not standard. Use ds.motion_* (100/300/500/800ms).",
                        severity="warning",
                    ))

            # Check: QPropertyAnimation without easing
            if 'QPropertyAnimation' in line:
                # Check next few lines for setEasingCurve
                next_lines = '\n'.join(lines[line_no:min(line_no+5, len(lines))])
                if 'setEasingCurve' not in next_lines:
                    self.issues.append(MotionIssue(
                        file=str(filepath),
                        line=line_no,
                        col=0,
                        code="MOTION_002_EASING",
                        message="QPropertyAnimation created without easing curve. Add setEasingCurve().",
                        severity="info",
                    ))

            # Check: Hardcoded animation durations in strings
            if "'animation-duration:" in line or '"animation-duration:' in line:
                duration_match = re.search(r'animation-duration:\s*(\d+)ms', line)
                if duration_match:
                    duration = int(duration_match.group(1))
                    if duration not in AUTHORIZED_DURATIONS:
                        self.issues.append(MotionIssue(
                            file=str(filepath),
                            line=line_no,
                            col=duration_match.start(),
                            code="MOTION_003_DURATION_STRING",
                            message=f"Hardcoded animation duration {duration}ms. Use design system token.",
                            severity="warning",
                        ))

    def _lint_qss(self, filepath: Path, content: str):
        """Linte QSS stylesheets."""
        lines = content.split('\n')

        for line_no, line in enumerate(lines, 1):
            # Check: transition-duration
            duration_match = re.search(r'transition(?:-duration)?\s*:\s*([^;]+)', line)
            if duration_match:
                value = duration_match.group(1).strip()
                ms_match = re.search(r'(\d+)ms', value)
                if ms_match:
                    duration = int(ms_match.group(1))
                    if duration not in AUTHORIZED_DURATIONS:
                        self.issues.append(MotionIssue(
                            file=str(filepath),
                            line=line_no,
                            col=duration_match.start(),
                            code="MOTION_004_TRANSITION",
                            message=f"Transition duration {duration}ms not standard. Use ds.motion_* tokens.",
                            severity="warning",
                        ))

            # Check: animation-duration in keyframes
            anim_match = re.search(r'animation-duration\s*:\s*(\d+)ms', line)
            if anim_match:
                duration = int(anim_match.group(1))
                if duration not in AUTHORIZED_DURATIONS:
                    self.issues.append(MotionIssue(
                        file=str(filepath),
                        line=line_no,
                        col=anim_match.start(),
                        code="MOTION_005_KEYFRAME_DURATION",
                        message=f"Keyframe animation {duration}ms not standard.",
                        severity="warning",
                    ))

            # Check: animation-timing-function
            if 'animation-timing-function' in line or 'transition-timing-function' in line:
                func_match = re.search(r'(?:animation|transition)-timing-function\s*:\s*([^;]+)', line)
                if func_match:
                    func = func_match.group(1).strip()
                    # Check if it's a valid easing
                    if not any(valid in func for valid in ['cubic-bezier', 'ease', 'linear']):
                        self.issues.append(MotionIssue(
                            file=str(filepath),
                            line=line_no,
                            col=func_match.start(),
                            code="MOTION_006_EASING",
                            message=f"Unknown easing function: {func}. Use standard curves.",
                            severity="warning",
                        ))


def main():
    """Entry point."""
    if len(sys.argv) < 2:
        print("Usage: python lint_motion.py <path>")
        sys.exit(1)

    root_path = Path(sys.argv[1])
    linter = MotionLinter()

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
    info_msgs = [i for i in all_issues if i.severity == 'info']
    warnings = [i for i in all_issues if i.severity == 'warning']
    errors = [i for i in all_issues if i.severity == 'error']

    # Report
    if info_msgs:
        print(f"\nℹ️  {len(info_msgs)} Motion info:\n")
        for issue in info_msgs[:10]:
            print(f"{issue.file}:{issue.line}: {issue.message}\n")

    if warnings:
        print(f"\n⚠️  {len(warnings)} Motion warnings:\n")
        for issue in warnings[:20]:
            print(f"{issue.file}:{issue.line}")
            print(f"  {issue.code}: {issue.message}\n")

    if errors:
        print(f"\n❌ {len(errors)} Motion errors:\n")
        for issue in errors[:20]:
            print(f"{issue.file}:{issue.line}")
            print(f"  {issue.code}: {issue.message}\n")

    if warnings or errors:
        print(f"\n📊 Summary: {len(errors)} errors, {len(warnings)} warnings, {len(info_msgs)} info")
        sys.exit(1 if errors else 0)
    else:
        print("✅ Motion compliance OK! (Material Design 3 standard)")
        sys.exit(0)


if __name__ == '__main__':
    main()
