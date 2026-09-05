"""test_lint_dlinter.py — Vérifie que tous les projets Larc respectent le design system.

Le test lance le linter D1+J7+D3+D4+D5+D6+D7 sur TOUS les projets Larc
et échoue si une seule violation est détectée. C'est le filet de sécurité
qui empêche tout hardcoding (hex, text_soft, HTML sans color, etc.).

Usage :
    pytest tests/test_lint_dlinter.py -v
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


# Chemin du linter (racine C:\projets)
LINTER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "lint_d1_color_checker.py"
# Toutes les règles actives
RULES = "D1+J7+D3+D4+D5+D6+D7"
# Projets à auditer (standard + LarcHub si présent)
PROJECTS = [
    "LarcCommon/larccommon",
    "LarcSuperviseur",
    "LarcSecretaire",
    "LarcProf",
    "LarcHub",
]


def test_linter_zero_violations():
    """Le linter D1+J7+D3+D4+D5+D6+D7 doit retourner 0 violation sur tous les projets Larc."""
    if not LINTER_PATH.exists():
        pytest.skip(f"Linter introuvable : {LINTER_PATH}")

    cmd = [
        sys.executable,
        str(LINTER_PATH),
        "--rule", RULES,
        "--json",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(LINTER_PATH.parents[1]),  # C:\projets
        timeout=120,
    )

    # Vérifier que le script a fonctionné
    assert result.returncode in (0, 1), (
        f"Le linter a planté (code {result.returncode}) :\n"
        f"stderr: {result.stderr[:500]}"
    )

    # Parser le JSON de sortie
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(
            f"Impossible de parser la sortie JSON du linter : {e}\n"
            f"stdout: {result.stdout[:1000]}\n"
            f"stderr: {result.stderr[:500]}"
        )

    total = output.get("total", -1)
    details = output.get("results", {})

    if total > 0:
        # Construire un message d'échec détaillé
        lines = [
            f"❌ {total} violation(s) détectée(s) — le design system Larc n'est pas respecté !",
            "",
        ]
        for project, violations in details.items():
            for v in violations:
                lines.append(
                    f"  [{v['rule']}] {v['file']}:{v['line']}  {v['detail']}"
                )
        lines.append("")
        lines.append("💡 Lancer le linter manuellement :")
        lines.append(f"    python scripts/lint_d1_color_checker.py --rule {RULES}")
        pytest.fail("\n".join(lines))

    # Vérifier que tous les projets attendus ont été scannés
    found_projects = set(details.keys())
    expected = {p for p in PROJECTS if (LINTER_PATH.parents[1] / p).exists()}
    missing = expected - found_projects
    if missing:
        pytest.fail(
            f"Projets non scannés par le linter : {', '.join(sorted(missing))}\n"
            f"Projets trouvés : {', '.join(sorted(found_projects))}"
        )


def test_linter_script_exists():
    """Le script du linter doit exister à l'emplacement attendu."""
    assert LINTER_PATH.exists(), (
        f"Linter introuvable : {LINTER_PATH}\n"
        f"Vérifier que scripts/lint_d1_color_checker.py est présent dans C:\\projets"
    )


def test_linter_has_all_rules():
    """Le script doit supporter toutes les règles actives (D6 et D7 notamment)."""
    if not LINTER_PATH.exists():
        pytest.skip("Linter introuvable")

    content = LINTER_PATH.read_text(encoding="utf-8")

    assert "def scan_d6_violations" in content, "Règle D6 manquante dans le linter"
    assert "def scan_d7_violations" in content, "Règle D7 manquante dans le linter"
    assert "D6" in content, "Règle D6 absente du parsing CLI"
    assert "D7" in content, "Règle D7 absente du parsing CLI"

    # Vérifier que --help mentionne D6 et D7 (en lançant le script)
    help_result = subprocess.run(
        [sys.executable, str(LINTER_PATH), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(LINTER_PATH.parents[1]),
        timeout=30,
    )
    help_output = help_result.stdout + help_result.stderr
    assert "D6" in help_output, "--help devrait mentionner la règle D6"
    assert "D7" in help_output, "--help devrait mentionner la règle D7"
