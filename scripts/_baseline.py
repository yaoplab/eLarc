"""Baseline (ratchet) partagee par les linters LarcCommon.

Une baseline fige les violations connues au moment de sa generation : elles
restent visibles dans les rapports mais ne bloquent plus le pre-commit. Toute
violation absente de la baseline (fichier neuf, ligne modifiee qui en introduit
une nouvelle) bloque le commit. Voir docs/superpowers/specs/2026-09-08-larccommon-ui-quality-enforcement-design.md.
"""
import json
from pathlib import Path


def violation_key(finding: dict) -> str:
    """Cle stable (fichier, ligne, regle) pour comparer une violation a la baseline.

    Accepte les deux conventions de nommage utilisees dans ce repo :
    lint_widget_purity.py (file/line/rule) et audit_design_system.py
    (fichier/ligne/categorie ou type).
    """
    file = finding.get("file") or finding.get("fichier")
    line = finding.get("line") or finding.get("ligne")
    rule = finding.get("rule") or finding.get("type") or finding.get("categorie") or "?"
    return f"{file}:{line}:{rule}"


def load_baseline(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data.get("violations", []))


def save_baseline(path: Path, findings: list[dict]) -> None:
    keys = sorted({violation_key(f) for f in findings})
    path.write_text(
        json.dumps({"violations": keys}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def split_new(findings: list[dict], baseline: set[str]) -> tuple[list[dict], list[dict]]:
    """Retourne (nouvelles, connues) -- nouvelles = absentes de la baseline."""
    new, known = [], []
    for f in findings:
        (known if violation_key(f) in baseline else new).append(f)
    return new, known
