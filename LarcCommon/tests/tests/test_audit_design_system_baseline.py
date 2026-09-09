import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from audit_design_system import AuditeurDesignSystem


def test_check_baseline_mode_exists_and_splits_known_vs_new(tmp_path, monkeypatch):
    from _baseline import save_baseline, violation_key

    auditeur = AuditeurDesignSystem()
    known = {"fichier": "a.py", "ligne": 1, "categorie": "P0"}
    new = {"fichier": "b.py", "ligne": 2, "categorie": "P0"}
    auditeur.issues = [known, new]

    baseline_path = tmp_path / "baseline.json"
    save_baseline(baseline_path, [known])

    from _baseline import load_baseline, split_new
    baseline = load_baseline(baseline_path)
    new_findings, known_findings = split_new(auditeur.issues, baseline)

    assert len(new_findings) == 1 and new_findings[0]["fichier"] == "b.py"
    assert len(known_findings) == 1 and known_findings[0]["fichier"] == "a.py"
