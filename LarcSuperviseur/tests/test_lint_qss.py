"""test_lint_qss.py — Vérifie que le R-linter (ZERO hardcoding) fonctionne partout.

Le test lance lint_qss_hardcoding.py (Sous-système R du skill design-system-larc)
sur TOUS les projets Larc et échoue si une seule valeur en pixels hardcodée est
détectée. Il verrouille aussi les 4 modes --group-by (subdir, package, file, auto)
et la sortie --json pure (parsable par json.load).

Usage :
    pytest tests/test_lint_qss.py -v
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest


# Chemin du linter (racine C:\projets)
LINTER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "lint_qss_hardcoding.py"
# Projets à auditer (mêmes que le D-linter)
PROJECTS = [
    "LarcCommon/larccommon",
    "LarcSuperviseur",
    "LarcSecretaire",
    "LarcProf",
    "LarcHub",
]
# Les 3 modes de regroupement attendus (+ auto = détection)
GROUP_MODES = ["subdir", "package", "file", "auto"]


def _run_linter(*extra_args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """Lance le R-linter depuis C:\\projets et retourne le résultat.

    encoding="utf-8" est OBLIGATOIRE : le linter émet des emojis UTF-8,
    et le décodage cp1252 par défaut de subprocess sur Windows casse stdout.
    """
    cmd = [sys.executable, str(LINTER_PATH), *extra_args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(LINTER_PATH.parents[1]),  # C:\projets
        timeout=timeout,
    )


def test_linter_script_exists():
    """Le script du linter doit exister à l'emplacement attendu."""
    assert LINTER_PATH.exists(), (
        f"Linter introuvable : {LINTER_PATH}\n"
        f"Vérifier que scripts/lint_qss_hardcoding.py est présent dans C:\\projets"
    )


def test_linter_zero_hardcodings_global():
    """Le R-linter doit retourner 0 hardcoding sur tous les projets Larc."""
    if not LINTER_PATH.exists():
        pytest.skip(f"Linter introuvable : {LINTER_PATH}")

    result = _run_linter("--json")

    # Le script retourne 1 si violations > 0, 0 sinon — les deux sont valides
    assert result.returncode in (0, 1), (
        f"Le linter a planté (code {result.returncode}) :\n"
        f"stderr: {result.stderr[:500]}"
    )

    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(
            f"Sortie --json non parsable : {e}\n"
            f"stdout: {result.stdout[:1000]}\n"
            f"stderr: {result.stderr[:500]}"
        )

    total = output.get("total", -1)
    details = output.get("results", {})

    if total > 0:
        lines = [
            f"❌ {total} hardcoding(s) détecté(s) — la règle ZERO hardcoding est violée !",
            "",
        ]
        for project, findings in details.items():
            for f in findings:
                lines.append(f"  {f['file']}:{f['line']}  {f['context']}")
        lines.append("")
        lines.append("💡 Lancer le linter manuellement :")
        lines.append("    python scripts/lint_qss_hardcoding.py")
        pytest.fail("\n".join(lines))

    # Vérifier que tous les projets attendus ont été scannés
    found_projects = set(details.keys())
    expected = {p for p in PROJECTS if (LINTER_PATH.parents[1] / p).exists()}
    missing = expected - found_projects
    if missing:
        pytest.fail(
            f"Projets non scannés par le R-linter : {', '.join(sorted(missing))}\n"
            f"Projets trouvés : {', '.join(sorted(found_projects))}"
        )


@pytest.mark.parametrize("group_mode", GROUP_MODES)
def test_group_by_modes(group_mode: str):
    """Chaque mode --group-by doit s'exécuter sans erreur sur LarcCommon (inclut phibuilder)."""
    if not LINTER_PATH.exists():
        pytest.skip(f"Linter introuvable : {LINTER_PATH}")

    result = _run_linter("--dir", "./LarcCommon", "--group-by", group_mode)
    assert result.returncode in (0, 1), (
        f"--group-by {group_mode} a planté (code {result.returncode}) :\n"
        f"stderr: {result.stderr[:500]}"
    )

    # Le rapport texte doit mentionner larccommon ET phibuilder (LarcCommon les couvre)
    assert "larccommon" in result.stdout, (
        f"--group-by {group_mode} : larccommon absent du rapport"
    )
    assert "phibuilder" in result.stdout, (
        f"--group-by {group_mode} : phibuilder absent du rapport"
    )

    # Le mode file ne doit PAS avoir d'en-têtes de groupe (lignes '— N fichier(s)')
    if group_mode == "file":
        assert "fichier(s)" not in result.stdout, (
            "mode file : des en-têtes de groupe sont présents, il doit être une liste plate"
        )


def test_group_by_auto_resolution():
    """--group-by auto doit résoudre en 'package' sur LarcCommon (profondeur ≥ 2)."""
    if not LINTER_PATH.exists():
        pytest.skip(f"Linter introuvable : {LINTER_PATH}")

    result = _run_linter("--dir", "./LarcCommon", "--group-by", "auto")
    assert result.returncode in (0, 1)

    # La ligne ⚙️ indique le mode résolu
    assert "auto → package" in result.stdout, (
        f"--group-by auto devrait résoudre en package sur LarcCommon :\n{result.stdout[:500]}"
    )
    assert "profondeur max =" in result.stdout, (
        "La ligne ⚙️ devrait afficher la profondeur max détectée"
    )


def test_json_output_pure():
    """La sortie --json doit être du JSON pur, sans ligne 'Scan de...' parasite."""
    if not LINTER_PATH.exists():
        pytest.skip(f"Linter introuvable : {LINTER_PATH}")

    result = _run_linter("--dir", "./LarcCommon", "--json")
    assert result.returncode in (0, 1)

    # json.loads doit réussir sur la sortie brute (sans prétraitement)
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(
            f"Sortie --json non parsable (ligne parasite ?) : {e}\n"
            f"stdout: {result.stdout[:1000]}"
        )

    assert "total" in output, "Le JSON doit contenir un champ 'total'"
    assert "results" in output, "Le JSON doit contenir un champ 'results'"
    # Cohérence : total = somme des findings
    assert output["total"] == sum(
        len(f) for f in output["results"].values()
    ), "Le total JSON doit être égal à la somme des findings"


def test_q1q3_rule_detects_interactive_table_without_cursor(tmp_path):
    """Règle Q1+Q3 : une table interactive (cellDoubleClicked) sans curseur main
    ni installEventFilter doit être signalée [Q1+Q3] ; une table conforme non."""
    if not LINTER_PATH.exists():
        pytest.skip(f"Linter introuvable : {LINTER_PATH}")

    # Table NON conforme : cellDoubleClicked sans curseur ni eventFilter
    bad = tmp_path / "bad_table.py"
    bad.write_text(
        "from phibuilder.widgets import M3TableWidget\n"
        "class BadPanel:\n"
        "    def _build(self):\n"
        "        self._table = M3TableWidget()\n"
        "        self._table.cellDoubleClicked.connect(self._on_open)\n",
        encoding="utf-8",
    )

    # Table conforme : curseur + eventFilter + connect
    good = tmp_path / "good_table.py"
    good.write_text(
        "from phibuilder.widgets import M3TableWidget\n"
        "from PySide6.QtCore import Qt, QEvent\n"
        "class GoodPanel:\n"
        "    def _build(self):\n"
        "        self._table = M3TableWidget()\n"
        "        self._table.viewport().setCursor(Qt.PointingHandCursor)\n"
        "        self._table.installEventFilter(self)\n"
        "        self._table.cellDoubleClicked.connect(self._on_open)\n"
        "    def eventFilter(self, obj, event):\n"
        "        return super().eventFilter(obj, event)\n",
        encoding="utf-8",
    )

    result = _run_linter("--dir", str(tmp_path), "--json")
    assert result.returncode in (0, 1), (
        f"Le linter a planté : {result.stderr[:500]}"
    )

    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"Sortie --json non parsable : {e}\n{result.stdout[:1000]}")

    findings = output.get("results", {})
    flat = [f for v in findings.values() for f in v]

    # La table non conforme est détectée avec la règle Q1+Q3
    q1q3 = [f for f in flat if f.get("rule") == "Q1+Q3"]
    assert len(q1q3) == 1, (
        f"Attendu 1 violation Q1+Q3, trouvé {len(q1q3)} :\n{json.dumps(flat, ensure_ascii=False, indent=2)}"
    )
    assert "bad_table.py" in q1q3[0]["file"]
    assert "PointingHandCursor" in q1q3[0]["suggestion"]
    assert "installEventFilter" in q1q3[0]["suggestion"]

    # La table conforme ne doit PAS être signalée
    bad_files = [f["file"] for f in flat]
    assert not any("good_table.py" in p for p in bad_files), (
        f"La table conforme ne doit pas être signalée :\n{json.dumps(flat, ensure_ascii=False, indent=2)}"
    )

    # Le champ 'rule' est présent dans tous les findings JSON
    for f in flat:
        assert "rule" in f, f"Le finding JSON doit avoir un champ 'rule' : {f}"


def test_q2_rule_detects_empty_state_messagebox(tmp_path):
    """Règle Q2 : un QMessageBox.information utilisé comme état vide (zéro
    résultat) doit être signalé [Q2] ; un message de succès non."""
    if not LINTER_PATH.exists():
        pytest.skip(f"Linter introuvable : {LINTER_PATH}")

    # NON conforme : clé i18n .no_users (état vide « aucun utilisateur »)
    bad = tmp_path / "bad_msgbox.py"
    bad.write_text(
        "from PySide6.QtWidgets import QMessageBox\n"
        "class BadPanel:\n"
        "    def share(self):\n"
        "        candidates = []\n"
        "        if not candidates:\n"
        "            QMessageBox.information(self, _('parent.share_address'), _('parent.error.share_no_users'))\n"
        "            return\n",
        encoding="utf-8",
    )

    # NON conforme : littéral FR « Aucun » multi-lignes
    bad2 = tmp_path / "bad_msgbox2.py"
    bad2.write_text(
        "from PySide6.QtWidgets import QMessageBox\n"
        "class BadPanel2:\n"
        "    def show_empty(self):\n"
        "        QMessageBox.information(\n"
        "            self, _('common.dialog.info_title'), _('Aucun résultat trouvé'))\n",
        encoding="utf-8",
    )

    # Conforme : message de succès (aucun marqueur)
    good = tmp_path / "good_msgbox.py"
    good.write_text(
        "from PySide6.QtWidgets import QMessageBox\n"
        "class GoodPanel:\n"
        "    def save(self):\n"
        "        QMessageBox.information(self, _('common.label.success'), _('notes.export_pdf_success'))\n",
        encoding="utf-8",
    )

    result = _run_linter("--dir", str(tmp_path), "--json")
    assert result.returncode in (0, 1), (
        f"Le linter a planté : {result.stderr[:500]}"
    )

    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"Sortie --json non parsable : {e}\n{result.stdout[:1000]}")

    findings = output.get("results", {})
    flat = [f for v in findings.values() for f in v]

    # Les deux états vides sont détectés avec la règle Q2
    q2 = [f for f in flat if f.get("rule") == "Q2"]
    assert len(q2) == 2, (
        f"Attendu 2 violations Q2, trouvé {len(q2)} :\n{json.dumps(flat, ensure_ascii=False, indent=2)}"
    )
    assert any("bad_msgbox.py" in f["file"] for f in q2)
    assert any("bad_msgbox2.py" in f["file"] for f in q2)
    assert all("INLINE" in f["suggestion"] for f in q2)

    # Le message de succès ne doit PAS être signalé
    assert not any("good_msgbox.py" in f["file"] for f in flat), (
        f"Le message de succès ne doit pas être signalé :\n{json.dumps(flat, ensure_ascii=False, indent=2)}"
    )


def test_q2w_rule_detects_warning_empty_state(tmp_path):
    """Règle Q2w (--rule Q2w) : un QMessageBox.warning contenant un marqueur
    d'état vide (ex: parent.error.no_address) doit être signalé [Q2w].
    Le scan par défaut (périmètre .information-only) ne doit PAS le signaler,
    et les validations (no_parent_selected) ne doivent jamais l'être."""
    if not LINTER_PATH.exists():
        pytest.skip(f"Linter introuvable : {LINTER_PATH}")

    # NON conforme (Q2w) : warning état vide — aucune adresse à partager
    bad = tmp_path / "bad_warning.py"
    bad.write_text(
        "from PySide6.QtWidgets import QMessageBox\n"
        "class BadPanel:\n"
        "    def share(self):\n"
        "        QMessageBox.warning(self, _('common.dialog.error_title'), _('parent.error.no_address'))\n"
        "        return\n",
        encoding="utf-8",
    )

    # Conforme : warning de VALIDATION (pas un état vide) — jamais signalé
    validation = tmp_path / "validation_warning.py"
    validation.write_text(
        "from PySide6.QtWidgets import QMessageBox\n"
        "class ValidationPanel:\n"
        "    def link(self):\n"
        "        QMessageBox.warning(self, _('common.dialog.error_title'), _('parent.error.no_parent_selected'))\n"
        "        return\n",
        encoding="utf-8",
    )

    # Scan par défaut : le .warning n'est PAS scanné (périmètre .information-only)
    result_default = _run_linter("--dir", str(tmp_path), "--json")
    output_default = json.loads(result_default.stdout)
    flat_default = [f for v in output_default.get("results", {}).values() for f in v]
    assert not any("bad_warning.py" in f["file"] for f in flat_default), (
        "Le scan par défaut ne doit PAS signaler les QMessageBox.warning "
        "(périmètre .information-only documenté)"
    )

    # Audit étendu --rule Q2w : le warning état vide est signalé [Q2w]
    result = _run_linter("--dir", str(tmp_path), "--rule", "Q2w", "--json")
    assert result.returncode in (0, 1), (
        f"Le linter a planté : {result.stderr[:500]}"
    )

    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"Sortie --json non parsable : {e}\n{result.stdout[:1000]}")

    findings = output.get("results", {})
    flat = [f for v in findings.values() for f in v]

    q2w = [f for f in flat if f.get("rule") == "Q2w"]
    assert len(q2w) == 1, (
        f"Attendu 1 violation Q2w, trouvé {len(q2w)} :\n{json.dumps(flat, ensure_ascii=False, indent=2)}"
    )
    assert "bad_warning.py" in q2w[0]["file"]
    assert "INLINE" in q2w[0]["suggestion"]

    # La validation (no_parent_selected) ne doit JAMAIS être signalée
    assert not any("validation_warning.py" in f["file"] for f in flat), (
        f"Les validations ne doivent pas être signalées :\n{json.dumps(flat, ensure_ascii=False, indent=2)}"
    )


def test_fix_only_compact_output(tmp_path):
    """--fix-only doit afficher des lignes compactes [Règle] fichier:ligne  contexte
    (compatible pre-commit, comme lint-dlinter) et rien quand 0 violation."""
    if not LINTER_PATH.exists():
        pytest.skip(f"Linter introuvable : {LINTER_PATH}")

    # Fichier avec une violation (hardcoding px) + une table interactive sans Q1+Q3
    bad = tmp_path / "bad.py"
    bad.write_text(
        "from phibuilder.widgets import M3TableWidget\n"
        "class Bad:\n"
        "    def _build(self):\n"
        "        self._table = M3TableWidget()\n"
        "        self._table.setStyleSheet(\"padding: 8px;\")\n"
        "        self._table.cellDoubleClicked.connect(self._on_open)\n",
        encoding="utf-8",
    )

    result = _run_linter("--dir", str(tmp_path), "--fix-only")
    # Code retour 1 = violations détectées → bloque le commit pre-commit
    assert result.returncode == 1, (
        f"--fix-only avec violations doit retourner 1 (bloque le commit), obtenu {result.returncode} :\n{result.stdout}"
    )

    out = result.stdout
    # Lignes compactes attendues : [R] et [Q1+Q3]
    assert "[R] " in out, f"--fix-only devrait afficher une ligne [R] :\n{out}"
    assert "[Q1+Q3] " in out, f"--fix-only devrait afficher une ligne [Q1+Q3] :\n{out}"
    # Format fichier:ligne (regex : [R] ...bad.py:6  ...)
    assert re.search(r"\[R\] .*bad\.py:\d+", out), f"Format [R] fichier:ligne attendu :\n{out}"
    assert re.search(r"\[Q1\+Q3\] .*bad\.py:\d+", out), f"Format [Q1+Q3] fichier:ligne attendu :\n{out}"
    # Pas de rapport détaillé (RÉSULTAT GLOBAL / émojis de scan)
    assert "RÉSULTAT GLOBAL" not in out, "--fix-only ne doit pas afficher le rapport détaillé"

    # Répertoire propre → aucune sortie + code retour 0
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "ok.py").write_text("x = 1\n", encoding="utf-8")
    result2 = _run_linter("--dir", str(clean), "--fix-only")
    assert result2.returncode == 0, (
        f"--fix-only sans violation doit retourner 0, obtenu {result2.returncode} :\n{result2.stdout}"
    )
    assert result2.stdout.strip() == "", (
        f"--fix-only avec 0 violation devrait être vide :\n{result2.stdout}"
    )
