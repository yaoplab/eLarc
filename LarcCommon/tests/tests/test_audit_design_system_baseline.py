import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from audit_design_system import ROOT, AuditeurDesignSystem, _issues_relative_to_root


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


def test_issues_relative_to_root_strips_absolute_prefix():
    """Regression pour la CRITIQUE de la review finale : les cles de baseline
    doivent etre relatives a ROOT (portables entre worktree et emplacement
    final), meme si `auditeur.issues` (utilise par auto-fix/rapports/CSV)
    continue de porter des chemins absolus."""
    auditeur = AuditeurDesignSystem()
    abs_file = str(ROOT / "LarcCommon" / "larccommon" / "design_system.py")
    issues = [{"fichier": abs_file, "ligne": 42, "categorie": "P0"}]

    relativized = _issues_relative_to_root(auditeur, issues)

    assert relativized[0]["fichier"] == str(
        Path("LarcCommon") / "larccommon" / "design_system.py"
    )
    assert not Path(relativized[0]["fichier"]).is_absolute()
    # L'original n'est pas mute -- auto-fix/rapports/CSV gardent le chemin absolu.
    assert issues[0]["fichier"] == abs_file


def test_issues_relative_to_root_falls_back_outside_root():
    """Un fichier hors de tous les PROJECT_ROOTS retombe sur le chemin
    d'origine (comportement historique de _rel_path)."""
    auditeur = AuditeurDesignSystem()
    outside = str(Path("C:/ailleurs/fichier.py"))
    issues = [{"fichier": outside, "ligne": 1, "categorie": "P0"}]

    relativized = _issues_relative_to_root(auditeur, issues)

    assert relativized[0]["fichier"] == outside
