"""Tests ciblés pour scripts/lint_qss_hardcoding.py (Task 6 : gap addSpacing ;
baseline : test_lint_qss.py::test_linter_zero_hardcodings_global laissé en
suspens, la dette pré-existante du repo bloquait ce test à tolérance zéro
et bloquerait aussi le hook pre-commit lint-rlinter réparé — mêmes causes
que Tasks 7-9)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from lint_qss_hardcoding import ROOT, _rel_to_root, find_hardcodings


def test_detects_addspacing_literal(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("outer.addSpacing(21)\n", encoding="utf-8")
    results = find_hardcodings(f, threshold="P0")
    assert len(results) == 1
    assert results[0]["value"] == 21


def test_rel_to_root_relativizes_path_under_root():
    p = ROOT / "LarcCommon" / "larccommon" / "login.py"
    assert _rel_to_root(str(p)) == "LarcCommon\\larccommon\\login.py" or _rel_to_root(
        str(p)
    ) == "LarcCommon/larccommon/login.py"


def test_rel_to_root_falls_back_to_absolute_outside_root(tmp_path):
    outside = tmp_path / "not_under_root.py"
    assert _rel_to_root(str(outside)) == str(outside)


def test_baseline_roundtrip_hides_known_violation(tmp_path):
    from _baseline import load_baseline, save_baseline, split_new

    baseline_path = tmp_path / "baseline.json"
    known = {"file": "LarcCommon/larccommon/login.py", "line": 21, "rule": "R"}
    new = {"file": "LarcSuperviseur/views/login.py", "line": 9, "rule": "R"}
    save_baseline(baseline_path, [known])

    baseline = load_baseline(baseline_path)
    new_findings, known_findings = split_new([known, new], baseline)

    assert len(new_findings) == 1 and new_findings[0]["file"] == new["file"]
    assert len(known_findings) == 1 and known_findings[0]["file"] == known["file"]
