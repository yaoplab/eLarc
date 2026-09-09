#!/usr/bin/env python3
"""
lint_qss_hardcoding.py — Linter QSS pour le Design System Larc.

Détecte les valeurs en pixels hardcodées (border-radius, padding, font-size,
setFixedHeight, etc.) qui devraient utiliser les tokens ds.space_*, ds.radius_*,
s(), ou theme_manager.image.*.

Usage:
    python scripts/lint_qss_hardcoding.py
    python scripts/lint_qss_hardcoding.py --dir .\\LarcSuperviseur     # rapport détaillé par fichier
    python scripts/lint_qss_hardcoding.py --dir .\\LarcCommon          # répartition larccommon vs phibuilder
    python scripts/lint_qss_hardcoding.py --dir .\\LarcCommon --group-by package   # par package (ex: larccommon/widgets)
    python scripts/lint_qss_hardcoding.py --dir .\\LarcCommon --group-by file      # liste plate
    python scripts/lint_qss_hardcoding.py --dir .\\LarcCommon --group-by auto      # auto : package si profondeur ≥ 2, sinon subdir
    python scripts/lint_qss_hardcoding.py --fix
    python scripts/lint_qss_hardcoding.py --threshold P0
    python scripts/lint_qss_hardcoding.py --json
    python scripts/lint_qss_hardcoding.py --fix-only         # compact fichier:ligne (pre-commit, comme lint-dlinter)
    python scripts/lint_qss_hardcoding.py --rule Q2w        # audit étendu : états vides .information + .warning

Conforme au Sous-système R du skill design-system-larc.

Règle Q1+Q3 (companion des correctifs ergonomiques du Sous-système Q) :
    Toute table M3TableWidget/QTableWidget INTERACTIVE (cellDoubleClicked,
    cellClicked, itemDoubleClicked ou itemClicked connecté) doit avoir :
      • viewport().setCursor(Qt.PointingHandCursor)   (Q1 — affordance)
      • installEventFilter(self)                      (Q3 — Entrée-ouvre)
      • une méthode def eventFilter() dans le même bloc (Q3 — sinon
        l'installEventFilter est orphelin et Qt l'ignore silencieusement)

Règle Q2 (companion du Sous-système Q) :
    Tout QMessageBox.information dont le message est un état vide (zéro résultat :
    clé i18n .no_xxx (.no_users / .no_address / .no_results...), littéral FR/EN
    « aucun / rien / vide / introuvable / not found / no results / empty... »)
    DOIT être remplacé par un état vide INLINE (_empty_state : icône + message dans
    le panneau, tableau caché). Jamais de popup modale pour 0 résultat.
    Variante --rule Q2w (opt-in, audit) : étend la détection aux
    QMessageBox.warning contenant un marqueur d'état vide (ex: parent.error.no_address).
    Les validations (_selected / _available / _required) ne sont PAS des états vides.
"""

LINTER_META = {
    "key": "R",
    "label": "Hardcoding QSS",
    "category": "theme",
    "description": "Valeurs px/couleurs codées en dur dans les QSS (tokens ds.* attendus)",
    "skill": "zero-hardcoding",
}

import argparse
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# Force UTF-8 (Windows cp1252 fix) — appliqué dans main() uniquement
# pour éviter un double wrapping du sys.stdout/stderr

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "scripts" / ".qss_hardcoding_baseline.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _baseline import load_baseline, save_baseline, split_new  # noqa: E402


def _rel_to_root(filepath: str) -> str:
    """Chemin relatif à ROOT pour que les clés de baseline survivent un
    déplacement du repo (worktree -> emplacement final). Retombe sur le
    chemin tel quel si le fichier est hors ROOT — même pattern que
    lint_widget_purity.py/audit_design_system.py (Finding 1, 2026-09-09)."""
    try:
        return str(Path(filepath).resolve().relative_to(ROOT))
    except ValueError:
        return str(filepath)


def _flat_findings_relative(all_findings: dict) -> list[dict]:
    """Aplatit all_findings (par projet) avec 'file' relativisé à ROOT —
    uniquement pour les clés de baseline, n'affecte pas --json/--report/
    --fix-only qui gardent leurs chemins tels quels (comme
    audit_design_system.py, pas comme lint_widget_purity.py — cf. la
    review finale du 2026-09-09 sur l'incohérence entre les deux)."""
    flat = []
    for findings in all_findings.values():
        for f in findings:
            flat.append({**f, "file": _rel_to_root(f["file"])})
    return flat


# ── Configuration ─────────────────────────────────────────────────────────────

PROJECTS = [
    "LarcCommon/larccommon",
    "LarcSuperviseur",
    "LarcSecretaire",
    "LarcProf",
    "LarcHub",
]

EXCLUDE_DIRS = {"__pycache__", ".git", ".ruff_cache", "venv", ".venv", "node_modules", "__pycache__", "tools", "docs", "img", "photos", "sql", "tests"}

# Valeurs autorisées sans token (R10)
ALLOWED_VALUES = {0, 1, 17}

# Règle Q1+Q3 — détection des créations de tables (M3TableWidget / QTableWidget)
TABLE_CREATION_RE = re.compile(r'(\w+)\s*=\s*(?:M3TableWidget|QTableWidget)\s*\(')
# Signaux qui rendent une table « interactive » (double-clic ou clic simple)
INTERACTIVE_SIGNAL_RE = re.compile(r'\.(?:cellDoubleClicked|cellClicked|itemDoubleClicked|itemClicked)\.connect')
# Curseur main sur le viewport ou le widget
CURSOR_RE = re.compile(r'\.(?:viewport\(\)\.)?setCursor\s*\(\s*Qt\.PointingHandCursor')
# Installation d'un eventFilter (Entrée-ouvre)
EVENTFILTER_RE = re.compile(r'\.installEventFilter\s*\(')
# Règle Q2 — marqueurs d'état vide (zéro résultat) dans un QMessageBox.information
# Clés i18n : suffixe _no_xxx dans la clé (share_no_users, copy_address_no_address)
# ou littéraux FR/EN (aucun, aucune, rien, vide, introuvable, not found,
# no results, empty...). NB : le préfixe est « _ » ou « . » (jamais « \b » —
# l'underscore est un caractère de mot, donc \bno_ ne matche pas après un _).
EMPTY_STATE_MARKERS = re.compile(
    r"(?:"
    r"(?:^|_|\.)no_(?:users|address|results?|data|records?|entries|items?|files?|documents?|students?|parents?|children|grades?|notes?|photos?|events?)(?!_selected|_available|_required)"  # clés i18n _no_xxx (hors validations)
    r"|\baucun\w*|\brien\b|\bvide\b|\bintrouvable\b"  # littéraux FR
    r"|\bnot ?found\b|\bno (?:results?|data|records?|entries|items?|users|address)\b"  # littéraux EN
    r"|\bempty\b|\bnone found\b"
    r")",
    re.IGNORECASE,
)


# Patterns de détection — regex pour trouver les valeurs en pixels
# On capture la ligne entière pour analyse
DETECT_PATTERNS = {
    "P0": [
        # border-radius: Npx (sauf si déjà tokenisé)
        re.compile(r'border-radius:\s*(\d+)\s*px', re.IGNORECASE),
        # setFixedHeight(N)  où N > 10
        re.compile(r'setFixedHeight\((\d+)\)'),
        # setFixedWidth(N)  où N > 10
        re.compile(r'setFixedWidth\((\d+)\)'),
        # addSpacing(N) -- espacement vertical/horizontal en dur (QBoxLayout)
        re.compile(r'addSpacing\((\d+)\)'),
    ],
    "P1": [
        # padding: Npx (dans QSS)
        re.compile(r'(?<!border-)padding:\s*(\d+)\s*px', re.IGNORECASE),
        # padding: Xpx Ypx (deux valeurs, on vérifie les deux)
        re.compile(r'padding:\s*(\d+)\s*px\s+(\d+)\s*px', re.IGNORECASE),
        # margin: Npx
        re.compile(r'margin:\s*(\d+)\s*px', re.IGNORECASE),
        # font-size: Npx
        re.compile(r'font-size:\s*(\d+)\s*px', re.IGNORECASE),
        # setContentsMargins(N, ...)  où N > 0
        re.compile(r'setContentsMargins\((\d+)'),
        # setSpacing(N)  où N > 0
        re.compile(r'setSpacing\((\d+)\)'),
        # setFixedSize(N, ...)  où N > 10
        re.compile(r'setFixedSize\((\d+),'),
        # setMinimumSize / setMaximumSize / setMinimumWidth / setMaximumWidth / setMinimumHeight / setMaximumHeight (R9b)
        re.compile(r'set(?:Minimum|Maximum)(?:Size|Width|Height)\((\d+)'),
        # min-width / max-width / min-height / max-height en QSS inline (R6b)
        re.compile(r'(?:min|max)-(?:width|height):\s*(\d+)\s*px', re.IGNORECASE),
    ],
}


def check_value(value: int, context: str) -> Optional[str]:
    """Vérifie si une valeur est acceptable ou propose un remplacement.

    Retourne None si OK, ou un message d'erreur avec suggestion.
    """
    if value in ALLOWED_VALUES:
        return None

    # Table de suggestion (R12)
    suggestions = {
        3: "⚠️ INTERDIT — pas de token 3px (utiliser ds.space_xxs=4 ou ds.space_xs=8)",
        4: "ds.space_xxs (espacement) / ds.radius_xs (shape)",
        5: "⚠️ INTERDIT — pas de token 5px (utiliser ds.space_xs=8 ou ds.space_sm=12)",
        6: "⚠️ INTERDIT — utiliser ds.space_xs(8) ou ds.space_sm(12)",
        8: "ds.space_xs (espacement) / ds.radius_sm (shape)",
        10: "s(10) (police)",
        11: "s(11) (police)",
        12: "ds.space_sm / ds.radius_md / s(12)",
        13: "s(13) (police label-large)",
        14: "s(14) (police body-medium)",
        16: "ds.space_m3 (M3) / ds.radius_lg (shape)",
        18: "theme_manager.image.icon_btn / s(18)",
        20: "ds.space_md",
        21: "s(21) (police title-large) / ds.table_row_min (ligne tableau)",
        22: "s(22) (police headline-small)",
        24: "s(24) (police headline-medium)",
        28: "ds.radius_xl (shape) / s(28) (police)",
        32: "ds.space_lg / ds.field_height (hauteur champ) / s(32)",
        34: "theme_manager.image.theme_btn / theme_manager.image.profile_btn",
        36: "s(36) (police headline-large)",
        40: "hauteur bouton M3 standard (40px)",
        45: "s(45) (police display-small)",
        48: "setMinimumHeight(48) → ds.space_xl(52) ou hauteur personnalisée",
        52: "ds.space_xl / ds.button_height / ds.header_height",
        55: "theme_manager.image.logo_small",
        57: "s(57) (police display-large)",
        84: "ds.space_xxl",
        89: "theme_manager.image.logo",
        100: "theme_manager.image.add_btn",
        136: "ds.space_xxxl",
        150: "theme_manager.image.avatar / theme_manager.image.photo",
        233: "ds.sidebar_width",
    }

    if value in suggestions:
        return suggestions[value]

    # Valeur non reconnue
    return f"⚠️ Valeur {value}px non reconnue — utiliser un token ds.space_*/ds.radius_*/s()"


def find_hardcodings(filepath: Path, threshold: str = "P1") -> list[dict]:
    """Analyse un fichier Python et retourne les hardcodings détectés."""
    results = []

    try:
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
    except (UnicodeDecodeError, IOError):
        return results

    active_patterns = []
    if threshold == "P0":
        active_patterns = DETECT_PATTERNS["P0"]
    else:  # P1 et tout
        for key in ("P0", "P1"):
            active_patterns.extend(DETECT_PATTERNS[key])

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()

        # Ignorer les commentaires et les lignes vides
        if not stripped or stripped.startswith("#"):
            continue

        # Masquer les interpolations f-string {expr} → {TOKEN} pour ne détecter
        # QUE les valeurs littérales. Une ligne peut mélanger tokens ET valeurs
        # en dur (ex: f"border-radius: {ds.radius_sm}px; padding: 2px;") — les
        # tokens sont masqués, les littéraux restent signalés (R2/R6b).
        # Les blocs QSS échappés {{ }} sont PROTÉGÉS d'abord (placeholder \x01/\x02)
        # pour ne pas avaler les valeurs littérales qu'ils contiennent.
        masked = stripped.replace("{{", "@@LB@@").replace("}}", "@@RB@@")
        masked = re.sub(r'\{[^}]*\}', '{TOKEN}', masked)
        masked = masked.replace("@@LB@@", "{{").replace("@@RB@@", "}}")

        for pattern in active_patterns:
            matches = pattern.findall(masked)
            if matches:
                # matches peut être un tuple (padding X Y) ou une string unique
                if isinstance(matches[0], tuple):
                    values = [int(v) for v in matches[0]]
                else:
                    values = [int(m) for m in matches]

                for val in values:
                    suggestion = check_value(val, stripped)
                    if suggestion is not None:
                        results.append({
                            "file": str(filepath),
                            "line": lineno,
                            "value": val,
                            "context": stripped[:120],
                            "suggestion": suggestion,
                        })

    return results


# ═══════════════════════════════════════════════════════════════════════════════
#  Règle Q1+Q3 — companion ergonomique (Sous-système Q)
# ═══════════════════════════════════════════════════════════════════════════════


def _split_top_level_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """Découpe le fichier en blocs de niveau supérieur (class/def à indentation 0).

    Retourne une liste de (start, end) en indices 0-based. Permet à la règle
    Q1+Q3 d'analyser une table dans SA classe (pas à l'échelle du fichier) —
    sinon deux classes du même fichier partageant le même nom de variable
    (ex: _Page._table et _TimelinePage._table) créeraient des faux positifs.
    """
    blocks = []
    start = 0
    for i, line in enumerate(lines):
        if i == 0:
            continue
        if re.match(r'^(class|def)\s+\w+', line):
            blocks.append((start, i))
            start = i
    blocks.append((start, len(lines)))
    return blocks


def scan_q1q3_violations(filepath: Path) -> list[dict]:
    """Règle Q1+Q3 — toute table interactive doit avoir curseur main + eventFilter.

    Une M3TableWidget/QTableWidget est « interactive » si l'un de ces signaux
    est connecté : cellDoubleClicked, cellClicked, itemDoubleClicked, itemClicked.
    Une table interactive DOIT avoir :
      • viewport().setCursor(Qt.PointingHandCursor)   (Q1 — affordance de clic)
      • installEventFilter(self)                      (Q3 — Entrée-ouvre)
      • une méthode def eventFilter() dans le même bloc (Q3 — Entrée-ouvre réel,
        pas un installEventFilter orphelin que Qt ignore silencieusement)

    L'analyse est limitée au bloc top-level (classe/fonction) où la table est
    créée — mêmes conventions que la règle J7 du D-linter (lookahead de classe).
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
    except (UnicodeDecodeError, IOError):
        return []

    results = []

    for start, end in _split_top_level_blocks(lines):
        block = lines[start:end]

        # 1) Créations de tables dans ce bloc
        tables: dict[str, int] = {}
        for local, line in enumerate(block):
            m = TABLE_CREATION_RE.search(line)
            if m:
                tables[m.group(1)] = start + local + 1  # 1-based absolu

        if not tables:
            continue

        # 2) Pour chaque table : interactivité + curseur + eventFilter + méthode
        for var, creation_line in tables.items():
            has_interactive = False
            has_cursor = False
            has_efilter = False
            has_method = False
            for line in block:
                if re.search(rf'{re.escape(var)}{INTERACTIVE_SIGNAL_RE.pattern}', line):
                    has_interactive = True
                if re.search(rf'{re.escape(var)}{CURSOR_RE.pattern}', line):
                    has_cursor = True
                if re.search(rf'{re.escape(var)}{EVENTFILTER_RE.pattern}', line):
                    has_efilter = True
                if re.match(r'\s*def\s+eventFilter\s*\(', line):
                    has_method = True
            # Classe composant des mixins (pattern LarcProf) : eventFilter peut
            # être porté par un fragment importé — le parent en hérite via MRO
            if 'Mixin' in block[0]:
                has_method = True

            if not has_interactive:
                continue  # table non interactive — Q1+Q3 ne s'applique pas

            missing = []
            if not has_cursor:
                missing.append("viewport().setCursor(Qt.PointingHandCursor)")
            if not has_efilter:
                missing.append("installEventFilter(self)")
            if not has_method:
                missing.append("méthode def eventFilter()")

            if missing:
                results.append({
                    "rule": "Q1+Q3",
                    "line": creation_line,
                    "value": 0,
                    "context": lines[creation_line - 1].strip()[:120],
                    "suggestion": (
                        f"Table interactive '{var}' sans {' ni '.join(missing)} — "
                        f"appliquer Q1+Q3 : {var}.viewport().setCursor(Qt.PointingHandCursor) "
                        f"+ {var}.installEventFilter(self) + méthode eventFilter() (Entrée-ouvre)"
                    ),
                    "file": str(filepath),
                })

    return results


def scan_q2_violations(filepath: Path, include_warning: bool = False) -> list[dict]:
    """Règle Q2 / Q2w — QMessageBox modal utilisé comme état vide (zéro résultat).

    Le skill Q2 impose un état vide INLINE (_empty_state : icône + message dans
    le panneau, tableau caché) au lieu d'un QMessageBox modal pour les cas
    « zéro résultat » (aucun utilisateur, aucune adresse, aucun résultat...).

    Périmètre par défaut (--rule all / Q2) : QMessageBox.information uniquement
    (décision documentée dans le skill — le hook pre-commit garde ce défaut).
    --rule Q2w : étend la détection aux QMessageBox.warning contenant un marqueur
    d'état vide (ex: parent.error.no_address), findings taggés [Q2w].
    Les validations (no_parent_selected, no_student_available, validation_required)
    ne sont PAS des états vides — le lookahead (?!_selected|_available|_required)
    de EMPTY_STATE_MARKERS les exclut.

    Les messages de succès (save_success, share_success, export_pdf_success...),
    de redémarrage (restart_needed), d'expiration (session_expired) ou d'aide
    (search_info_msg) ne contiennent aucun marqueur → non signalés.
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
    except (UnicodeDecodeError, IOError):
        return []

    methods = ("QMessageBox.information(",)
    if include_warning:
        methods = ("QMessageBox.information(", "QMessageBox.warning(")

    results = []
    for idx, line in enumerate(lines):
        method = next((m for m in methods if m in line), None)
        if method is None:
            continue
        # Reconstituer l'appel complet (multi-lignes possible jusqu'à l'équilibre des parenthèses).
        # Limite connue : un littéral contenant des parenthèses déséquilibrées dans l'appel
        # fausserait le comptage — aucun cas dans la base actuelle, heuristique acceptée.
        call_lines = [line]
        depth = line.count("(") - line.count(")")
        j = idx
        while depth > 0 and j + 1 < len(lines):
            j += 1
            call_lines.append(lines[j])
            depth += lines[j].count("(") - lines[j].count(")")
        call_text = " ".join(call_lines)
        if EMPTY_STATE_MARKERS.search(call_text):
            rule = "Q2w" if method == "QMessageBox.warning(" else "Q2"
            results.append({
                "rule": rule,
                "line": idx + 1,
                "value": 0,
                "context": line.strip()[:120],
                "suggestion": (
                    f"{method[:-1]} utilisé comme état vide ('{call_text.strip()[:60]}') "
                    f"— appliquer Q2 : état vide INLINE (_empty_state : icône + message "
                    f"dans le panneau, tableau caché), jamais de popup modale pour 0 résultat"
                ),
                "file": str(filepath),
            })

    return results


def auto_fix(filepath: Path, findings: list[dict]) -> int:
    """Applique les corrections automatiques pour les valeurs triviales."""
    fixes = {
        8: "ds.space_xs",
        12: "ds.space_sm",
        20: "ds.space_md",
        32: "ds.space_lg",
        52: "ds.space_xl",
        84: "ds.space_xxl",
        233: "ds.sidebar_width",
    }

    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, IOError):
        return 0

    applied = 0
    for finding in findings:
        if finding.get("rule") in ("Q1+Q3", "Q2", "Q2w"):
            continue  # règle structurelle — pas d'auto-fix pixel
        val = finding["value"]
        if val in fixes:
            token = fixes[val]
            # Remplacer la valeur exacte dans le contexte approprié
            old = str(val)
            new = token
            if content.count(old):
                content = content.replace(old, new, 1)
                applied += 1

    if applied > 0:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
        except IOError:
            return 0

    return applied


def scan_directory(directory: Path, threshold: str = "P1", rules: str = "all") -> dict[str, list[dict]]:
    """Scanne récursivement un répertoire → {chemin absolu: findings}.

    Retourne TOUS les fichiers .py scannés (y compris sans violation) pour
    permettre un rapport détaillé fichier par fichier en mode --dir.

    --rule all (défaut) : R + Q1+Q3 + Q2 (information uniquement).
    --rule Q2 / Q2w   : seule la règle Q2 tourne (Q2w = .information + .warning).
    """
    by_file: dict[str, list[dict]] = {}

    if not directory.exists():
        print(f"  ❌ Répertoire introuvable : {directory}")
        return by_file

    run_r = rules in ("all", "R")
    run_q1q3 = rules in ("all", "Q1+Q3")
    run_q2 = rules in ("all", "Q2", "Q2w")
    q2_warning = rules == "Q2w"

    for root, dirs, files in os.walk(directory):
        # Exclure les répertoires système
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for file in files:
            if not file.endswith(".py"):
                continue
            # Exclure les fichiers backup (*.pyold.py, *.bak) — R-linter R17
            if ".pyold" in file or file.endswith(".bak") or file.endswith(".old"):
                continue
            filepath = Path(root) / file
            findings: list[dict] = []
            if run_r:
                findings += find_hardcodings(filepath, threshold)
            if run_q1q3:
                findings += scan_q1q3_violations(filepath)
            if run_q2:
                findings += scan_q2_violations(filepath, include_warning=q2_warning)
            by_file[str(filepath)] = findings

    return by_file


def flatten_findings(by_file: dict[str, list[dict]]) -> list[dict]:
    """Aplatit {fichier: findings} en liste plate (compat JSON / rapports)."""
    return [f for findings in by_file.values() for f in findings]


def _group_key(rel: str, group_by: str) -> str:
    """Calcule la clé de groupe d'un chemin relatif selon le mode --group-by."""
    if group_by == "file":
        return rel
    if group_by == "package":
        return os.path.dirname(rel) or "(racine)"
    # subdir — sous-répertoire de premier niveau
    return rel.split("/")[0] if "/" in rel else "(racine)"


def _resolve_group_by(group_by: str, by_file: dict[str, list[dict]], directory: Path) -> tuple[str, int]:
    """Résout le mode --group-by auto → (mode, profondeur max).

    Détecte la profondeur maximale des fichiers par rapport au répertoire scanné.
    Si un fichier est à profondeur ≥ 2 (ex: larccommon/widgets/x.py) → package
    (plus lisible). Sinon → subdir.
    """
    if group_by != "auto":
        return group_by, 0

    max_depth = 0
    for filepath in by_file:
        rel = os.path.relpath(filepath, start=directory).replace(os.sep, "/")
        depth = len(rel.split("/")) - 1  # nombre de segments de répertoire
        max_depth = max(max_depth, depth)

    return ("package" if max_depth >= 2 else "subdir"), max_depth


def print_dir_report(
    project_name: str,
    directory: Path,
    by_file: dict[str, list[dict]],
    fix_mode: bool = False,
    group_by: str = "subdir",
):
    """Rapport --dir : groupé selon --group-by, détail fichier par fichier.

    Modes : subdir (sous-répertoire, ex: larccommon vs phibuilder), package
    (chemin de package, ex: larccommon/widgets), file (liste plate),
    auto (détection : package si profondeur ≥ 2, sinon subdir).
    """
    total = sum(len(f) for f in by_file.values())

    resolved, max_depth = _resolve_group_by(group_by, by_file, directory)
    if group_by == "auto":
        print(f"\n  ⚙️  --group-by auto → {resolved} (profondeur max = {max_depth})")

    print(f"\n  {'='*50}")
    print(f"  📋 {project_name} — {total} hardcoding(s)/violation(s) sur {len(by_file)} fichiers scannés")
    print(f"  {'='*50}")

    # Grouper les fichiers selon le mode demandé
    groups: dict[str, list[str]] = {}
    for filepath in by_file:
        rel = os.path.relpath(filepath, start=directory).replace(os.sep, "/")
        groups.setdefault(_group_key(rel, resolved), []).append(filepath)

    show_headers = group_by != "file"

    for key in sorted(groups, key=lambda g: (g == "(racine)", g)):
        files = sorted(groups[key])
        sub_total = sum(len(by_file[f]) for f in files)
        if show_headers:
            status = "❌" if sub_total else "✅"
            display_key = key if key.endswith("/") else key + "/"
            print(f"\n  {status} {display_key} — {sub_total} hardcoding(s) — {len(files)} fichier(s)")
        for filepath in files:
            relpath = os.path.relpath(filepath, start=os.getcwd())
            findings = by_file[filepath]
            if findings:
                print(f"    ❌ {relpath} — {len(findings)} hardcoding(s)/violation(s)")
                for f in findings:
                    rule = f.get("rule")
                    tag = f"[{rule}] " if rule else ""
                    print(f"      L{f['line']:>4}  {tag}{f['context']}")
                    print(f"            → 💡 {f['suggestion']}")
            else:
                print(f"    ✅ {relpath} — 0")

    if total == 0:
        print(f"\n  🎉 {project_name} — Zéro hardcoding ni violation détecté !")

    if fix_mode and total > 0:
        total_fixed = 0
        for filepath, findings in by_file.items():
            if not findings:
                continue
            fixed = auto_fix(Path(filepath), findings)
            if fixed > 0:
                relpath = os.path.relpath(filepath, start=os.getcwd())
                print(f"\n  🔧 Auto-fix : {relpath} — {fixed} correction(s)")
                total_fixed += fixed
        print(f"\n  🔧 Total auto-fix : {total_fixed} correction(s)")

    print()


def print_report(project_name: str, findings: list[dict], fix_mode: bool = False):
    """Affiche le rapport de linter formaté."""
    if not findings:
        print(f"  ✅ {project_name} — 0 hardcoding ni violation — FÉLICITATIONS !")
        return

    print(f"\n  {'='*50}")
    print(f"  📋 {project_name} — {len(findings)} hardcoding(s)/violation(s) trouvé(s)")
    print(f"  {'='*50}")

    # Grouper par fichier
    by_file: dict[str, list[dict]] = {}
    for f in findings:
        by_file.setdefault(f["file"], []).append(f)

    for filepath, file_findings in by_file.items():
        relpath = os.path.relpath(filepath, start=os.getcwd())
        print(f"\n  📄 {relpath}")
        for f in file_findings:
            rule = f.get("rule")
            tag = f"[{rule}] " if rule else ""
            print(f"    L{f['line']:>4}  {tag}{f['context']}")
            print(f"          → 💡 {f['suggestion']}")

    if fix_mode:
        total_fixed = 0
        for filepath, file_findings in by_file.items():
            fixed = auto_fix(Path(filepath), file_findings)
            if fixed > 0:
                relpath = os.path.relpath(filepath, start=os.getcwd())
                print(f"\n  🔧 Auto-fix : {relpath} — {fixed} correction(s)")
                total_fixed += fixed
        print(f"\n  🔧 Total auto-fix : {total_fixed} correction(s)")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Linter QSS — détecte les hardcodings pixels dans les apps Larc"
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="",
        help="Répertoire à analyser (par défaut : tous les projets Larc)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Mode auto-fix pour les valeurs triviales (8→ds.space_xs, 12→ds.space_sm, etc.)",
    )
    parser.add_argument(
        "--threshold",
        type=str,
        default="P1",
        choices=["P0", "P1"],
        help="Seuil minimal : P0 (bloquant) ou P1 (tout)",
    )
    parser.add_argument(
        "--group-by",
        type=str,
        default="subdir",
        choices=["subdir", "file", "package", "auto"],
        help="Niveau de regroupement du rapport --dir : subdir (sous-répertoire), file (liste plate), package (chemin de package), auto (détection profondeur)",
    )
    parser.add_argument(
        "--fix-only",
        action="store_true",
        help="Mode compact — seulement les fichiers et lignes (compatible pre-commit, comme lint-dlinter)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Sortie JSON au lieu du texte",
    )
    parser.add_argument(
        "--rule",
        type=str,
        default="all",
        choices=["all", "Q2", "Q2w"],
        help="Règles à exécuter : all (R+Q1+Q3+Q2, information uniquement), Q2 (Q2 seul), Q2w (Q2 étendu aux QMessageBox.warning)",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="(Re)génère la baseline avec les violations actuelles",
    )
    parser.add_argument(
        "--check-baseline",
        action="store_true",
        help="N'échoue que sur les violations absentes de la baseline (pre-commit)",
    )
    args = parser.parse_args()
    quiet = args.json or args.fix_only or args.baseline or args.check_baseline

    # Forcer UTF-8 pour la sortie terminal (compatible pre-commit sur Windows cp1252)
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    all_findings = {}

    if args.dir:
        # Analyser un seul répertoire
        projects_to_scan = [args.dir]
    else:
        projects_to_scan = PROJECTS

    base_path = Path(os.getcwd())

    for project in projects_to_scan:
        project_path = base_path / project
        if not project_path.exists():
            # Essayer chemin relatif au projet
            alt_path = base_path.parent / project
            if alt_path.exists():
                project_path = alt_path
            else:
                print(f"  ⚠️  Répertoire non trouvé : {project}")
                continue

        if not quiet:
            print(f"\n🔍 Scan de {project}...")
        by_file = scan_directory(project_path, args.threshold, args.rule)
        flat = flatten_findings(by_file)
        all_findings[project] = flat

        if not quiet:
            if args.dir:
                print_dir_report(project, project_path, by_file, args.fix, args.group_by)
            else:
                print_report(project, flat, args.fix)
        elif args.fix_only and not args.json and flat:
            for f in flat:
                try:
                    relpath = os.path.relpath(f["file"], start=os.getcwd())
                except ValueError:  # drives différents (fichier sur C:, cwd sur F:)
                    relpath = f["file"]
                rule = f.get("rule", "R")
                print(f"  [{rule}] {relpath}:{f['line']}  {f['context']}")

    # Rapport global
    total = sum(len(f) for f in all_findings.values())
    if not quiet:
        print(f"\n{'='*50}")
        print(f"📊 RÉSULTAT GLOBAL : {total} hardcoding(s)/violation(s) sur {len(all_findings)} projets")
        if total == 0:
            print("🎉 FÉLICITATIONS — Zéro hardcoding ni violation détecté !")
        print(f"{'='*50}")

    if args.baseline:
        rel_findings = _flat_findings_relative(all_findings)
        save_baseline(BASELINE_PATH, rel_findings)
        print(f"[baseline] {len(rel_findings)} violation(s) figée(s) dans {BASELINE_PATH}")
        return 0

    if args.check_baseline:
        rel_findings = _flat_findings_relative(all_findings)
        baseline = load_baseline(BASELINE_PATH)
        new, known = split_new(rel_findings, baseline)
        print(
            f"lint_qss_hardcoding: {len(new)} nouvelle(s) violation(s), "
            f"{len(known)} connue(s) (baseline, non bloquant)"
        )
        for f in new:
            print(f"  [{f.get('rule', 'R')}] {f['file']}:{f['line']}  {f['context']}")
        return 1 if new else 0

    if args.json:
        output = {
            "results": {
                proj: [
                    {
                        "file": f["file"],
                        "line": f["line"],
                        "rule": f.get("rule", "R"),
                        "value": f.get("value", 0),
                        "context": f["context"],
                        "suggestion": f["suggestion"],
                    }
                    for f in findings
                ]
                for proj, findings in all_findings.items()
            },
            "total": total,
            "threshold": args.threshold,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))

    return 1 if total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
