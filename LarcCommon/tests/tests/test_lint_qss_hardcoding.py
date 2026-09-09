"""Tests ciblés pour scripts/lint_qss_hardcoding.py (Task 6 : gap addSpacing)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from lint_qss_hardcoding import find_hardcodings


def test_detects_addspacing_literal(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("outer.addSpacing(21)\n", encoding="utf-8")
    results = find_hardcodings(f, threshold="P0")
    assert len(results) == 1
    assert results[0]["value"] == 21
