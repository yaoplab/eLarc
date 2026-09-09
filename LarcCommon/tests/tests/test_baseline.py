import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from _baseline import violation_key, load_baseline, save_baseline, split_new


def test_violation_key_stable_across_field_name_variants():
    a = {"file": "x.py", "line": 5, "rule": "W1"}
    b = {"fichier": "x.py", "ligne": 5, "categorie": "W1"}
    assert violation_key(a) == violation_key(b)


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "baseline.json"
    findings = [{"file": "a.py", "line": 1, "rule": "W1"}, {"file": "b.py", "line": 2, "rule": "R"}]
    save_baseline(path, findings)
    loaded = load_baseline(path)
    assert loaded == {violation_key(f) for f in findings}


def test_load_missing_file_returns_empty_set(tmp_path):
    assert load_baseline(tmp_path / "does_not_exist.json") == set()


def test_split_new_separates_known_from_new():
    baseline = {"a.py:1:W1"}
    findings = [{"file": "a.py", "line": 1, "rule": "W1"}, {"file": "b.py", "line": 2, "rule": "W1"}]
    new, known = split_new(findings, baseline)
    assert len(new) == 1 and new[0]["file"] == "b.py"
    assert len(known) == 1 and known[0]["file"] == "a.py"
