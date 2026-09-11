#!/usr/bin/env python3
"""
audit_design_system.py — Audit et correction automatique des hardcodings Design System
pour les projets Larc PySide6.

Scanne recursivement les fichiers .py des projets Larc, detecte les valeurs en dur
(margins, spacing, fixed sizes, QSS), et peut les corriger automatiquement.

Usage:
    python scripts/audit_design_system.py                         # Audit tous les projets
    python scripts/audit_design_system.py --auto-fix              # Audit + correction auto
    python scripts/audit_design_system.py --dry-run               # Preview des corrections
    python scripts/audit_design_system.py --path LarcProf         # Un seul projet
    python scripts/audit_design_system.py --report rapport.md     # Rapport Markdown
    python scripts/audit_design_system.py --fix                   # Suggestions seulement
    python scripts/audit_design_system.py --csv hardcodings.csv   # Export CSV
    python scripts/audit_design_system.py --include-tests         # Inclure tests/
    python scripts/audit_design_system.py --quiet                 # Mode silencieux
"""

import re
import io
import sys
import csv
from datetime import datetime
from pathlib import Path
from collections import defaultdict, Counter

# =========================================================================
# CONFIGURATION
# =========================================================================

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOTS = [
    ROOT / "LarcProf",
    ROOT / "LarcSuperviseur",
    ROOT / "LarcSecretaire",
    ROOT / "LarcCommon",
]

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _baseline import load_baseline, save_baseline, split_new

BASELINE_PATH = ROOT / "scripts" / ".design_system_baseline.json"

EXCLUDE_DIRS = {
    '.git', '.venv', '__pycache__', '.ruff_cache', '.aider.tags.cache.v4',
    '.github', 'node_modules', 'egg-info', 'tests', 'deepseek', 'docs',
    'a_faire', 'DbInit', 'img', 'grid_configs', 'algo', 'old', 'backup',
}

# =========================================================================
# MAPE DE SUGGESTION
# =========================================================================

TOKEN_SUGGESTIONS = {
    0:  "(acceptable si intentionnel)",
    1:  "ds.border_width",
    2:  "ds.space_xxs // 2",
    3:  "ds.space_xxs - 1  ou  ds.space_xxs // 2 + 1",
    4:  "ds.space_xxs",
    5:  "ds.space_xxs + 1  ou  ds.space_xs - 3",
    6:  "d.spacing (theme_manager.design.spacing)",
    7:  "ds.space_xs - 1",
    8:  "ds.space_xs",
    10: "ds.space_xs + 2  ou  ds.space_sm - 2",
    11: "theme_manager.font_size(11)",
    12: "ds.space_sm",
    13: "theme_manager.font_size(13)  ou  ds.space_sm + 1",
    14: "ds.font_size_lg",
    16: "ds.space_sm + ds.space_xxs",
    18: "ds.icon_sm  ou  ds.table_min_section",
    20: "ds.space_md",
    21: "ds.table_row_min",
    22: "ds.table_row_min + 1  ou  ds.space_md + 2",
    24: "ds.space_md + ds.space_xxs",
    26: "ds.icon_btn_size - ds.space_xxs",
    30: "ds.icon_btn_size",
    32: "ds.space_lg  ou  ds.icon_md",
    34: "ds.idx_label_width",
    36: "ds.font_btn_width",
    40: "ds.space_md * 2",
    44: "ds.space_lg + ds.space_sm",
    48: "ds.button_height - ds.space_xxs",
    50: "ds.kpi_card_height - ds.space_lg  ou  ds.space_xl - 2",
    52: "ds.space_xl  ou  ds.button_height  ou  ds.header_height",
    55: "ds.button_height + 3  ou  ds.header_height + 3",
    56: "ds.space_xl + ds.space_xxs",
    60: "ds.kpi_card_height - ds.space_md",
    64: "ds.space_lg * 2",
    68: "ds.space_xl + ds.space_sm + ds.space_xxs",
    80: "ds.kpi_card_height",
    84: "ds.space_xxl",
    88: "ds.space_xxl + ds.space_xxs",
    90: "ds.space_xxl + ds.space_xs - 2",
    100: "ds.space_xxl + ds.space_sm + ds.space_xxs",
    120: "ds.kpi_card_height + ds.space_md  ou  ds.space_xl * 2 + ds.space_sm + ds.space_xxs",
    144: "ds.jugements_width  ou  ds.scroll_max_height  ou  ds.workspace_min_height",
    150: "ds.jugements_width + ds.space_xs - 2",
    178: "ds.nature_label_width",
    180: "ds.workspace_min_height + ds.space_lg + ds.space_xxs",
    200: "ds.sidebar_width - ds.space_lg - 1",
    210: "ds.sidebar_width - ds.space_md - 3  ou  ds.window_width // 6 + ds.space_xs",
    213: "ds.sidebar_width - ds.space_md",
    220: "ds.sidebar_width - ds.space_sm - 1",
    233: "ds.sidebar_width",
    300: "ds.window_height // 3 + ds.space_lg",
    400: "ds.window_width // 3  ou  ds.kpi_card_height * 5",
    420: "ds.window_width // 3 + ds.space_md",
    480: "ds.window_width * 2 // 5",
    500: "ds.kpi_card_height * 6 + ds.space_md",
    600: "ds.window_height - ds.window_width // 3",
    610: "ds.sidebar_width * 2 + ds.space_xl - ds.space_md",
    679: "int(420 * ds.GOLDEN)",
    800: "ds.window_height",
    900: "ds.window_width - ds.sidebar_width - ds.space_lg - ds.space_xxs",
    1200: "ds.window_width",
}

QSS_TOKEN_SUGGESTIONS = {
    2:  "ds.space_xxs // 2",
    3:  "d.radius  ou  ds.space_xxs - 1",
    4:  "ds.space_xxs",
    6:  "d.btn_sm_pad_v",
    7:  "ds.space_xxs + 3",
    8:  "theme_manager.font_size(8)  ou  ds.space_xs",
    9:  "theme_manager.font_size(9)",
    10: "theme_manager.font_size(10)",
    11: "theme_manager.font_size(11)  ou  ds.font_size_sm",
    12: "theme_manager.font_size(12)",
    13: "theme_manager.font_size(13)  ou  ds.font_size_md",
    14: "theme_manager.font_size(14)  ou  ds.font_size_lg",
    16: "ds.space_sm + ds.space_xxs",
    21: "ds.font_size_title  ou  ds.space_md + 1",
    22: "ds.font_size_title + 1",
}

# =========================================================================
# AUTO-FIX MAP — Remplacements triviaux automatiques
# =========================================================================
# Format: (type_issue, valeur) → token_string
# Seules les valeurs EXACTES et SURES sont incluses.
# Les multi-value patterns (setContentsMargins, setFixedSize, etc.)
# sont gerees position par position via str.replace(old, new, 1).

AUTO_FIX_MAP = {
    # ---- P0 - Layout ----
    ('setSpacing', 3): 'ds.space_xxs',
    ('setSpacing', 4): 'ds.space_xxs',
    ('setSpacing', 5): 'ds.space_xxs',
    ('setSpacing', 6): 'd.spacing',
    ('setSpacing', 8): 'ds.space_xs',
    ('setSpacing', 12): 'ds.space_sm',
    ('addSpacing', 3): 'ds.space_xxs',
    ('addSpacing', 4): 'ds.space_xxs',
    ('addSpacing', 5): 'ds.space_xxs',
    ('addSpacing', 6): 'd.spacing',
    ('addSpacing', 8): 'ds.space_xs',
    ('addSpacing', 12): 'ds.space_sm',
    ('addSpacing', 13): 'ds.space_sm',
    ('addSpacing', 16): 'ds.space_sm + ds.space_xxs',
    ('addSpacing', 20): 'ds.space_md',
    ('addSpacing', 21): 'ds.space_md',
    ('addSpacing', 24): 'ds.space_md + ds.space_xxs',
    ('addSpacing', 32): 'ds.space_lg',
    ('addSpacing', 34): 'ds.space_lg',
    ('setContentsMargins', 4): 'ds.space_xxs',
    ('setContentsMargins', 8): 'ds.space_xs',
    ('setContentsMargins', 12): 'ds.space_sm',
    ('setContentsMargins', 20): 'ds.space_md',
    # ---- P1 - Fixed sizes ----
    ('setFixedHeight', 18): 'ds.icon_sm',
    ('setFixedHeight', 21): 'ds.table_row_min',
    ('setFixedHeight', 30): 'ds.icon_btn_size',
    ('setFixedHeight', 52): 'ds.button_height',
    ('setFixedHeight', 55): 'ds.button_height',
    ('setFixedWidth', 18): 'ds.icon_sm',
    ('setFixedWidth', 34): 'ds.idx_label_width',
    ('setFixedWidth', 144): 'ds.jugements_width',
    ('setFixedWidth', 178): 'ds.nature_label_width',
    ('setFixedWidth', 233): 'ds.sidebar_width',
    ('setFixedSize', 30): 'ds.icon_btn_size',
    ('setFixedSize', 52): 'ds.button_height',
    ('setDefaultSectionSize', 22): 'ds.table_row_min',
    ('setMinimumSectionSize', 18): 'ds.table_min_section',
    ('resize', 800): 'ds.window_height',
    ('resize', 1200): 'ds.window_width',
    ('scaledToHeight', 88): 'ds.space_xxl + ds.space_xxs',
    # ---- QSize ----
    ('QSize', 18): 'ds.icon_sm',
    ('QSize', 30): 'ds.icon_btn_size',
}


# =========================================================================
# WHITELIST
# =========================================================================

ALLOWED_TOKENS = re.compile(
    r'\b('
    r'ds\.\w+|d\.\w+|self\._sp\(|theme_manager\.\w+|s\(\d+\)'
    r'|SpacingToken\.\w+|{ds\.|{d\.|{theme_manager\.|{s\('
    r'|sp\(SpacingToken'
    r')\b'
)


# =========================================================================
# MOTEUR D'AUDIT
# =========================================================================

class AuditeurDesignSystem:
    """Moteur d'audit du design system pour projets PySide6."""

    def __init__(self, include_tests: bool = False):
        self.include_tests = include_tests
        self.issues: list[dict] = []
        self.files_scanned = 0
        self.files_with_issues: set[str] = set()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _est_hardcode(ligne: str, valeur: int) -> bool:
        if valeur == 0:
            return False
        if ALLOWED_TOKENS.search(ligne):
            return False
        return True

    @staticmethod
    def _rel_path(chemin: str) -> str:
        p = Path(chemin)
        for root in PROJECT_ROOTS:
            try:
                return str(p.relative_to(root.parent))
            except ValueError:
                continue
        return chemin

    def _ajouter(self, issues: list, no_lig: int, ligne: str,
                 categorie: str, type_issue: str, desc: str,
                 valeur: int):
        issues.append({
            'fichier': None,
            'ligne': no_lig,
            'code': ligne.strip()[:150],
            'categorie': categorie,
            'type': type_issue,
            'description': desc,
            'valeur': valeur,
            'suggestion': QSS_TOKEN_SUGGESTIONS.get(valeur)
                          if categorie == 'P2'
                          else TOKEN_SUGGESTIONS.get(valeur, ''),
        })

    # ------------------------------------------------------------------
    # Detection P0
    # ------------------------------------------------------------------

    def _p0_layout(self, no_lig: int, ligne_brute: str, ligne: str, issues: list):
        for m in re.finditer(
            r'\.setContentsMargins\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)',
            ligne
        ):
            vals = [int(m.group(i)) for i in range(1, 5)]
            if any(not self._est_hardcode(ligne_brute, v) for v in vals):
                continue
            labels = ['gauche', 'haut', 'droite', 'bas']
            for i, v in enumerate(vals):
                if v != 0:
                    self._ajouter(issues, no_lig, ligne_brute,
                        'P0', 'setContentsMargins', f'Margin {labels[i]}', v)
            return

        for m in re.finditer(r'\.setSpacing\(\s*(\d+)\s*\)', ligne):
            v = int(m.group(1))
            if self._est_hardcode(ligne_brute, v):
                self._ajouter(issues, no_lig, ligne_brute,
                    'P0', 'setSpacing', 'Spacing', v)

        for m in re.finditer(r'\.addSpacing\(\s*(\d+)\s*\)', ligne):
            v = int(m.group(1))
            if self._est_hardcode(ligne_brute, v):
                self._ajouter(issues, no_lig, ligne_brute,
                    'P0', 'addSpacing', 'Spacing vertical', v)

    # ------------------------------------------------------------------
    # Detection P1
    # ------------------------------------------------------------------

    def _p1_fixed(self, no_lig: int, ligne_brute: str, ligne: str, issues: list):
        patterns = [
            (r'\.setFixedSize\(\s*(\d+)\s*,\s*(\d+)\s*\)',   'setFixedSize'),
            (r'\.setFixedWidth\(\s*(\d+)\s*\)',               'setFixedWidth'),
            (r'\.setFixedHeight\(\s*(\d+)\s*\)',              'setFixedHeight'),
            (r'\.resize\(\s*(\d+)\s*,\s*(\d+)\s*\)',          'resize'),
            (r'\.setMinimumWidth\(\s*(\d+)\s*\)',             'setMinimumWidth'),
            (r'\.setMinimumHeight\(\s*(\d+)\s*\)',            'setMinimumHeight'),
            (r'\.setMaximumWidth\(\s*(\d+)\s*\)',             'setMaximumWidth'),
            (r'\.setMaximumHeight\(\s*(\d+)\s*\)',            'setMaximumHeight'),
            (r'\.setMinimumSize\(\s*(\d+)\s*,\s*(\d+)\s*\)', 'setMinimumSize'),
            (r'\.setMaximumSize\(\s*(\d+)\s*,\s*(\d+)\s*\)', 'setMaximumSize'),
            (r'QSize\(\s*(\d+)\s*,\s*(\d+)\s*\)',            'QSize'),
            (r'\.scaledToHeight\(\s*(\d+)\s*\)',              'scaledToHeight'),
            (r'\.setDefaultSectionSize\(\s*(\d+)\s*\)',      'setDefaultSectionSize'),
            (r'\.setMinimumSectionSize\(\s*(\d+)\s*\)',      'setMinimumSectionSize'),
        ]

        for regex, label in patterns:
            for m in re.finditer(regex, ligne):
                v1 = int(m.group(1))
                has_v2 = m.lastindex is not None and m.lastindex >= 2
                v2 = int(m.group(2)) if has_v2 else None

                if self._est_hardcode(ligne_brute, v1):
                    self._ajouter(issues, no_lig, ligne_brute,
                        'P1', label, f'{label}: {v1}', v1)
                if v2 is not None and self._est_hardcode(ligne_brute, v2):
                    self._ajouter(issues, no_lig, ligne_brute,
                        'P1', label, f'{label}: {v2}', v2)

    # ------------------------------------------------------------------
    # Detection P2
    # ------------------------------------------------------------------

    def _p2_qss(self, no_lig: int, ligne_brute: str, ligne: str, issues: list):
        patterns = [
            (r'border-radius:\s*(\d+)px(?!.*\{\w+)', 'border-radius'),
            (r'(?<!letter-)font-size:\s*(\d+)px(?!.*theme_manager)(?!.*\{\w+)', 'font-size'),
            (r'(?<!\w)padding:\s*(\d+)px\b(?!.*\{\w+)', 'padding'),
            (r'(?<!letter-)spacing:\s*(\d+)px(?!.*\{\w+)', 'spacing'),
        ]

        for regex, label in patterns:
            for m in re.finditer(regex, ligne):
                v = int(m.group(1))
                if self._est_hardcode(ligne_brute, v):
                    sugg = QSS_TOKEN_SUGGESTIONS.get(v, TOKEN_SUGGESTIONS.get(v, ''))
                    self._ajouter(issues, no_lig, ligne_brute,
                        'P2', f'QSS_{label}', f'{label} en dur dans QSS', v)
                    issues[-1]['suggestion'] = sugg

    # ------------------------------------------------------------------
    # Scan fichier
    # ------------------------------------------------------------------

    def _scanner(self, chemin: Path) -> list[dict]:
        issues: list[dict] = []
        try:
            contenu = chemin.read_text(encoding='utf-8', errors='replace')
        except Exception:
            return issues

        for no_lig, ligne in enumerate(contenu.split('\n'), 1):
            ligne_strip = ligne.strip()
            if not ligne_strip or ligne_strip.startswith('#'):
                continue
            self._p0_layout(no_lig, ligne, ligne_strip, issues)
            self._p1_fixed(no_lig, ligne, ligne_strip, issues)
            self._p2_qss(no_lig, ligne, ligne_strip, issues)

        return issues

    # ------------------------------------------------------------------
    # Scan complet
    # ------------------------------------------------------------------

    def scanner(self, racines: list[Path]) -> list[dict]:
        self.issues = []
        self.files_scanned = 0
        self.files_with_issues = set()

        for racine in racines:
            if not racine.exists():
                print(f"  [SKIP] {racine} — introuvable")
                continue
            projet = racine.name
            print(f"  {projet}...", end='', flush=True)
            count = 0
            for pyfile in sorted(racine.rglob('*.py')):
                if pyfile.name in ('__init__.py', 'setup.py', 'conftest.py'):
                    continue
                rel = pyfile.relative_to(racine)
                if any(p.startswith('.') or p in EXCLUDE_DIRS for p in rel.parts):
                    continue
                if not self.include_tests and 'tests' in rel.parts:
                    continue
                self.files_scanned += 1
                issues = self._scanner(pyfile)
                for iss in issues:
                    iss['fichier'] = str(pyfile)
                    iss['projet'] = projet
                if issues:
                    count += len(issues)
                    self.files_with_issues.add(str(pyfile))
                    self.issues.extend(issues)
            print(f" {count} hardcodings")
        return self.issues

    # ------------------------------------------------------------------
    # MOTEUR DE CORRECTION AUTOMATIQUE
    # ------------------------------------------------------------------

    @staticmethod
    def _get_fix_token(type_issue: str, valeur: int) -> str | None:
        """Retourne le token de remplacement pour un (type, valeur)."""
        return AUTO_FIX_MAP.get((type_issue, valeur))

    @classmethod
    def _try_fix_line(cls, ligne: str, type_issue: str, valeur: int) -> str | None:
        """Tente de corriger une ligne. Retourne la ligne modifiee ou None."""
        token = cls._get_fix_token(type_issue, valeur)
        if not token:
            return None

        sv = str(valeur)
        st = str(token)

        # ---- Methodes a valeur unique ----
        single = {'setSpacing', 'addSpacing', 'setFixedHeight', 'setFixedWidth',
                  'setMinimumWidth', 'setMinimumHeight', 'setMaximumWidth',
                  'setMaximumHeight', 'scaledToHeight',
                  'setDefaultSectionSize', 'setMinimumSectionSize'}

        if type_issue in single:
            # setMethod(N) → setMethod(token)
            for fmt in (f'{type_issue}({sv}', f'{type_issue}( {sv}'):
                if fmt in ligne:
                    return ligne.replace(fmt, f'{type_issue}({st}', 1)
            return None

        # ---- setContentsMargins - 4 positions ----
        if type_issue == 'setContentsMargins':
            # Position 1: apres '('
            for fmt in (f'setContentsMargins({sv},', f'setContentsMargins( {sv},'):
                if fmt in ligne:
                    return ligne.replace(fmt, f'setContentsMargins({st},', 1)
            # Positions 2-3: entre virgules
            for fmt in (f', {sv},', f',{sv},'):
                if fmt in ligne:
                    return ligne.replace(fmt, f', {st},', 1)
            # Position 4: avant ')'
            for fmt in (f', {sv})', f',{sv})'):
                if fmt in ligne:
                    return ligne.replace(fmt, f', {st})', 1)
            return None

        # ---- setFixedSize, resize, QSize, setMinimumSize, setMaximumSize ----
        # Position 1: apres '('
        multi_first = {'setFixedSize', 'resize', 'setMinimumSize',
                       'setMaximumSize', 'QSize'}
        if type_issue in multi_first:
            for fmt in (f'{type_issue}({sv},', f'{type_issue}( {sv},'):
                if fmt in ligne:
                    return ligne.replace(fmt, f'{type_issue}({st},', 1)
            # Position 2: avant ')'
            for fmt in (f', {sv})', f',{sv})'):
                if fmt in ligne:
                    return ligne.replace(fmt, f', {st})', 1)
            return None

        return None

    def auto_fixer(self, dry_run: bool = False) -> dict:
        """
        Corrige automatiquement les hardcodings dans les fichiers sources.

        Args:
            dry_run: si True, ne modifie pas les fichiers (simple preview).

        Retourne:
            dict avec les statistiques : fichiers_modifies, corrections, ignorés, erreurs.
        """
        stats = {'fichiers_modifies': 0, 'corrections': 0,
                 'ignores': 0, 'erreurs': 0}

        # Grouper les issues par fichier
        par_fichier: dict[str, list[dict]] = defaultdict(list)
        for iss in self.issues:
            if self._get_fix_token(iss['type'], iss['valeur']):
                par_fichier[iss['fichier']].append(iss)

        if not par_fichier:
            print("\n[AUTO-FIX] Aucune correction automatique possible.")
            return stats

        action = "PREVIEW" if dry_run else "FIX"
        print(f"\n[AUTO-FIX] {action} — {len(par_fichier)} fichier(s) avec corrections possibles\n")

        for chemin in sorted(par_fichier.keys()):
            issues = par_fichier[chemin]
            try:
                contenu = Path(chemin).read_text(encoding='utf-8')
            except Exception as e:
                print(f"  [ERREUR] {self._rel_path(chemin)} — {e}")
                stats['erreurs'] += 1
                continue

            lignes = contenu.split('\n')
            fixes = 0

            # Traiter en ordre decroissant de ligne pour ne pas casser les numeros
            for iss in sorted(issues, key=lambda x: x['ligne'], reverse=True):
                no_lig = iss['ligne'] - 1
                if no_lig >= len(lignes):
                    continue
                ligne_originale = lignes[no_lig]
                ligne_corrigee = self._try_fix_line(
                    ligne_originale, iss['type'], iss['valeur']
                )
                if ligne_corrigee and ligne_corrigee != ligne_originale:
                    lignes[no_lig] = ligne_corrigee
                    fixes += 1

            if fixes > 0:
                if not dry_run:
                    Path(chemin).write_text('\n'.join(lignes), encoding='utf-8')
                prefix = "[DRY]" if dry_run else "[OK]"
                rel = self._rel_path(chemin)
                print(f"  {prefix} {rel}  ({fixes} correction(s))")
                stats['fichiers_modifies'] += 1
                stats['corrections'] += fixes
            else:
                stats['ignores'] += 1

        # Resumer
        if not dry_run and stats['corrections'] > 0:
            print(f"\n[AUTO-FIX] Termine : {stats['fichiers_modifies']} fichier(s), "
                  f"{stats['corrections']} correction(s) appliquee(s)")
        elif dry_run and stats['corrections'] > 0:
            print(f"\n[AUTO-FIX] Preview : {stats['fichiers_modifies']} fichier(s), "
                  f"{stats['corrections']} correction(s) possibles. "
                  "Reexecuter sans --dry-run pour appliquer.")
        else:
            print("\n[AUTO-FIX] Aucune correction appliquee.")

        return stats

    # ------------------------------------------------------------------
    # Rapports
    # ------------------------------------------------------------------

    def resumer(self) -> str:
        if not self.issues:
            return "Aucun hardcoding detecte — 100% conforme !"

        par_cat = Counter(i['categorie'] for i in self.issues)
        par_projet = Counter(i['projet'] for i in self.issues)
        par_valeur = Counter(i['valeur'] for i in self.issues)
        fixable = sum(1 for i in self.issues
                      if self._get_fix_token(i['type'], i['valeur']))

        lignes = []
        lignes.append("=" * 60)
        lignes.append("RAPPORT D'AUDIT DESIGN SYSTEM — PROJETS LARC")
        lignes.append(f"   {datetime.now():%Y-%m-%d %H:%M}")
        lignes.append(f"   Fichiers scannes: {self.files_scanned}")
        lignes.append(f"   Fichiers avec issues: {len(self.files_with_issues)}")
        lignes.append(f"   Total hardcodings: {len(self.issues)}")
        lignes.append(f"   Corrections auto possibles: {fixable}")
        lignes.append("=" * 60)

        lignes.append(f"\nPAR CATEGORIE:")
        for cat, label in [('P0', 'Margins/Spacing'), ('P1', 'Fixed sizes'), ('P2', 'QSS valeurs')]:
            lignes.append(f"   {cat} ({label}): {par_cat.get(cat, 0)}")
        lignes.append(f"   {'--' * 15}")
        lignes.append(f"   TOTAL: {len(self.issues)}")

        lignes.append(f"\nPAR PROJET:")
        for proj, count in sorted(par_projet.items()):
            lignes.append(f"   {proj}: {count}")
        lignes.append(f"   {'--' * 15}")
        lignes.append(f"   TOTAL: {len(self.issues)}")

        lignes.append(f"\nVALEURS LES PLUS FREQUENTES:")
        for val, count in par_valeur.most_common(10):
            sugg = QSS_TOKEN_SUGGESTIONS.get(val, TOKEN_SUGGESTIONS.get(val, ''))
            fixable_val = any(self._get_fix_token(i['type'], i['valeur'])
                              for i in self.issues if i['valeur'] == val)
            auto = " [AUTO]" if fixable_val else ""
            lignes.append(f"   {val:>4}px x {count:<3}  ->  {sugg}{auto}")

        lignes.append(f"\nPAR FICHIER:")
        par_fichier = defaultdict(list)
        for iss in self.issues:
            par_fichier[iss['fichier']].append(iss)
        for chemin, iss_list in sorted(par_fichier.items()):
            p0 = sum(1 for i in iss_list if i['categorie'] == 'P0')
            p1 = sum(1 for i in iss_list if i['categorie'] == 'P1')
            p2 = sum(1 for i in iss_list if i['categorie'] == 'P2')
            nf = sum(1 for i in iss_list if self._get_fix_token(i['type'], i['valeur']))
            badges = []
            if p0: badges.append(f'P0={p0}')
            if p1: badges.append(f'P1={p1}')
            if p2: badges.append(f'P2={p2}')
            if nf: badges.append(f'AUTO={nf}')
            rel = self._rel_path(chemin)
            lignes.append(f"   {rel}  {' '.join(badges)}")

        return '\n'.join(lignes)

    def rapporter_markdown(self) -> str:
        if not self.issues:
            return ("# Audit Design System\n\n"
                    "Aucun hardcoding detecte — tous les fichiers sont 100% conformes.")

        par_cat = Counter(i['categorie'] for i in self.issues)
        par_projet = Counter(i['projet'] for i in self.issues)
        fixable = sum(1 for i in self.issues
                      if self._get_fix_token(i['type'], i['valeur']))

        lignes = []
        lignes.append("# Rapport d'audit Design System — Projets Larc\n")
        lignes.append(f"**Date :** {datetime.now():%Y-%m-%d %H:%M}")
        lignes.append(f"**Fichiers scannes :** {self.files_scanned}")
        lignes.append(f"**Fichiers avec issues :** {len(self.files_with_issues)}")
        lignes.append(f"**Total hardcodings :** {len(self.issues)}")
        lignes.append(f"**Corrections auto disponibles :** {fixable}\n")

        lignes.append("## Resume\n")
        lignes.append("| Categorie | Description | Nombre | Priorite | Auto-fix |")
        lignes.append("|---|---|---|---|---|")
        for cat, label in [('P0', 'Margins/Spacing'), ('P1', 'Fixed sizes'), ('P2', 'QSS valeurs')]:
            p = 'Haute' if cat == 'P0' else ('Moyenne' if cat == 'P1' else 'Basse')
            nb = par_cat.get(cat, 0)
            af = sum(1 for i in self.issues if i['categorie'] == cat
                     and self._get_fix_token(i['type'], i['valeur']))
            a = f'Oui ({af})' if af > 0 else 'Non'
            lignes.append(f"| {cat} | {label} | {nb} | {p} | {a} |")
        lignes.append(f"| **Total** | | **{len(self.issues)}** | | **{fixable}** |\n")

        lignes.append("## Par projet\n")
        lignes.append("| Projet | P0 | P1 | P2 | Total | Auto-fix | Statut |")
        lignes.append("|---|---|---|---|---|---|---|")
        for proj in sorted(par_projet.keys()):
            p0 = sum(1 for i in self.issues if i['projet'] == proj and i['categorie'] == 'P0')
            p1 = sum(1 for i in self.issues if i['projet'] == proj and i['categorie'] == 'P1')
            p2 = sum(1 for i in self.issues if i['projet'] == proj and i['categorie'] == 'P2')
            total = p0 + p1 + p2
            af = sum(1 for i in self.issues if i['projet'] == proj
                     and self._get_fix_token(i['type'], i['valeur']))
            statut = 'Bon' if total < 5 else ('Moyen' if total < 15 else 'A corriger')
            lignes.append(f"| {proj} | {p0} | {p1} | {p2} | {total} | {af} | {statut} |")
        lignes.append("")

        par_valeur = Counter(i['valeur'] for i in self.issues)
        lignes.append("## Top 15 valeurs les plus frequentes\n")
        lignes.append("| Valeur (px) | Occurrences | Auto-fix | Suggestion |")
        lignes.append("|---|---|---|---|")
        for val, count in par_valeur.most_common(15):
            sugg = QSS_TOKEN_SUGGESTIONS.get(val, TOKEN_SUGGESTIONS.get(val, ''))
            af = any(self._get_fix_token(i['type'], i['valeur'])
                     for i in self.issues if i['valeur'] == val)
            lignes.append(f"| {val} | {count} | {'Oui' if af else 'Non'} | `{sugg}` |")
        lignes.append("")

        lignes.append("## Detail par fichier\n")
        par_fichier = defaultdict(list)
        for iss in self.issues:
            par_fichier[iss['fichier']].append(iss)

        for chemin, iss_list in sorted(par_fichier.items()):
            p0 = sum(1 for i in iss_list if i['categorie'] == 'P0')
            p1 = sum(1 for i in iss_list if i['categorie'] == 'P1')
            p2 = sum(1 for i in iss_list if i['categorie'] == 'P2')
            nf = sum(1 for i in iss_list if self._get_fix_token(i['type'], i['valeur']))
            badges = []
            if p0: badges.append(f'P0={p0}')
            if p1: badges.append(f'P1={p1}')
            if p2: badges.append(f'P2={p2}')
            if nf: badges.append(f'AUTO={nf}')
            lignes.append(f"### `{self._rel_path(chemin)}`  {' '.join(badges)}\n")
            lignes.append("| Ligne | Cat | Type | Valeur | Auto | Suggestion | Code |")
            lignes.append("|---|---|---|---|---|---|---|")
            for iss in iss_list:
                af = 'Oui' if self._get_fix_token(iss['type'], iss['valeur']) else ''
                code_court = iss['code'][:80]
                lignes.append(
                    f"| {iss['ligne']} | {iss['categorie']} | {iss['type']} "
                    f"| {iss['valeur']} | {af} | `{iss['suggestion']}` | `{code_court}` |"
                )
            lignes.append("")

        lignes.append("---")
        lignes.append(f"*Genere par `audit_design_system.py` le {datetime.now():%Y-%m-%d %H:%M}*")
        return '\n'.join(lignes)

    def exporter_csv(self, chemin: Path):
        with open(chemin, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Fichier', 'Ligne', 'Categorie', 'Type', 'Description',
                            'Valeur (px)', 'Suggestion', 'Auto-fix', 'Code'])
            for iss in self.issues:
                af = 'Oui' if self._get_fix_token(iss['type'], iss['valeur']) else ''
                writer.writerow([
                    iss['fichier'], iss['ligne'], iss['categorie'],
                    iss['type'], iss['description'], iss['valeur'],
                    iss['suggestion'], af, iss['code'],
                ])

    def remediations(self):
        if not self.issues:
            print("Aucun hardcoding a corriger.")
            return

        par_valeur = defaultdict(list)
        for iss in self.issues:
            par_valeur[iss['valeur']].append(iss)

        print("\n" + "=" * 60)
        print("SUGGESTIONS DE CORRECTION PAR VALEUR")
        print("=" * 60)

        for val in sorted(par_valeur.keys()):
            items = par_valeur[val]
            sugg = QSS_TOKEN_SUGGESTIONS.get(val, TOKEN_SUGGESTIONS.get(val, '?'))
            auto = any(self._get_fix_token(i['type'], i['valeur']) for i in items)
            tag = " [AUTO]" if auto else ""
            exemples = []
            for iss in items[:3]:
                nom_fich = Path(iss['fichier']).name
                exemples.append(f"      {nom_fich}:{iss['ligne']}  ({iss['type']})")
            print(f"\n  {val}px  ->  `{sugg}`{tag}  ({len(items)} occurrence(s))")
            for ex in exemples:
                print(ex)
            if len(items) > 3:
                print(f"      ... et {len(items) - 3} autres")


def _issues_relative_to_root(auditeur: 'AuditeurDesignSystem', issues: list[dict]) -> list[dict]:
    """Copie superficielle des issues avec 'fichier' relativise a ROOT.

    Utilise uniquement pour les cles de baseline (--baseline/--check-baseline) :
    des chemins absolus rendraient la baseline invalide des que le repo change
    d'emplacement (worktree -> chemin final). Le reste du pipeline (auto-fix,
    rapports, CSV) continue d'utiliser le chemin absolu d'origine dans
    `auditeur.issues`, inchange.
    """
    return [
        {**iss, 'fichier': auditeur._rel_path(iss['fichier'])}
        for iss in issues
    ]


# =========================================================================
# POINT D'ENTREE
# =========================================================================

def main():
    # Force UTF-8 (Windows cp1252 fix) -- uniquement en execution CLI reelle,
    # jamais a l'import (casse la capture stdout de pytest sinon).
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    import argparse
    parser = argparse.ArgumentParser(
        description="Audit et correction Design System pour projets PySide6 Larc",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--path', type=str, default='',
                        help='Projet a scanner (ex: LarcProf). Defaut: tous')
    parser.add_argument('--report', type=str, default='',
                        help='Generer rapport Markdown (.md)')
    parser.add_argument('--csv', type=str, default='',
                        help='Exporter en CSV (.csv)')
    parser.add_argument('--fix', action='store_true',
                        help='Afficher les suggestions de correction')
    parser.add_argument('--auto-fix', action='store_true',
                        help='APPLIQUER les corrections automatiques dans les fichiers')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview des corrections auto sans modifier les fichiers')
    parser.add_argument('--include-tests', action='store_true',
                        help='Inclure les dossiers tests/')
    parser.add_argument('--quiet', action='store_true',
                        help='Mode silencieux (pas de sortie texte)')
    parser.add_argument('--baseline', action='store_true',
                        help='(Re)genere la baseline avec les violations actuelles')
    parser.add_argument('--check-baseline', action='store_true',
                        help="N'echoue que sur les violations absentes de la baseline (pre-commit)")

    args = parser.parse_args()

    auditeur = AuditeurDesignSystem(include_tests=args.include_tests)

    if args.path:
        racines = [ROOT / args.path]
    else:
        racines = PROJECT_ROOTS

    issues = auditeur.scanner(racines)

    if args.baseline:
        baseline_issues = _issues_relative_to_root(auditeur, issues)
        save_baseline(BASELINE_PATH, baseline_issues)
        print(f"[baseline] {len(issues)} violation(s) figee(s) dans {BASELINE_PATH}")
        return 0

    if args.check_baseline:
        baseline = load_baseline(BASELINE_PATH)
        baseline_issues = _issues_relative_to_root(auditeur, issues)
        new, known = split_new(baseline_issues, baseline)
        print(f"audit_design_system: {len(new)} nouvelle(s) violation(s), {len(known)} connue(s) (baseline, non bloquant)")
        for iss in new:
            print(f"  [{iss['categorie']}] {iss['fichier']}:{iss['ligne']}  {iss['code']}")
        return 1 if new else 0

    if not args.quiet:
        print(auditeur.resumer())

    if args.fix:
        auditeur.remediations()

    if args.auto_fix:
        auditeur.auto_fixer(dry_run=args.dry_run)
    elif args.dry_run:
        auditeur.auto_fixer(dry_run=True)

    if args.report:
        Path(args.report).write_text(auditeur.rapporter_markdown(), encoding='utf-8')
        print(f"\n[OK] Rapport Markdown : {args.report}")

    if args.csv:
        auditeur.exporter_csv(Path(args.csv))
        print(f"\n[OK] Export CSV : {args.csv}")

    if args.auto_fix:
        # 2eme scan apres corrections pour verifier le resultat
        print("\n[AUTO-FIX] Verification apres correction...")
        auditeur2 = AuditeurDesignSystem(include_tests=args.include_tests)
        auditeur2.scanner(racines)
        restants = len(auditeur2.issues)
        if restants == 0:
            print("[AUTO-FIX] Aucun hardcoding restant !")
        else:
            encore_fixable = sum(1 for i in auditeur2.issues
                                 if AuditeurDesignSystem._get_fix_token(i['type'], i['valeur']))
            print(f"[AUTO-FIX] {restants} hardcoding(s) restant(s) "
                  f"(dont {encore_fixable} auto-fixable(s))")

    return 0 if len(issues) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
