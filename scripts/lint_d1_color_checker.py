#!/usr/bin/env python3
"""
lint_d1_color_checker.py — Linter Design System Larc (règles D1, D3, D4, D5, J7).

Vérifications disponibles :

  D1 — setText() HTML : chaque balise (<b>, <span>, etc.) DOIT avoir
       `color:{p.text_strong}` ou `color:{p.text_soft}` explicite.
       Sans cela, le texte hérite du QPalette (NOIR) et devient illisible
       en mode dark.

  J7 — WA_StyledBackground : tout M3Frame/QWidget/QFrame avec un background
       via QSS DOIT avoir `setAttribute(Qt.WA_StyledBackground, True)`.
       Sans cela, le widget utilise son rendu interne (phibuilder / Qt natif)
       et le fond QSS est ignoré.

  D3 — Couleurs hex hardcodées : toute couleur hex (#xxxxxx) dans un
       setStyleSheet() NE réagit PAS au changement de thème.
       Remplacer par les tokens {p.primary}, {p.surface}, etc.

  D4 — Contrastes insuffisants :
       D4a : font-size < 12px AVEC color: {p.text_soft}
       D4b : background: {p.surface_variant} AVEC color: {p.text_soft}

  D5 — text_soft dans setStyleSheet() inline : toute occurrence de
       `color: {p.text_soft}` dans un setStyleSheet() avec string literal
       (pas _STYLE). Ces appels échappent à l'analyse de contexte et
       créent du "gris sur gris" en dark si le widget hérite d'un fond
       surface_variant.

  D6 — Réactivité au thème : toute classe qui utilise des tokens palette
       dans un setStyleSheet() inline DOIT avoir une connexion
       `ds.theme_changed.connect(...)` ou `theme_changed.connect(...)`
       dans son __init__ ou _build_ui. Sans cela, le widget ne réagit
       pas au changement de thème et conserve ses couleurs d'origine.
       Les classes héritant de ThemedWidget ou ThemedDialog sont exonérées.

  D7 — Complétude de _restyle() : toute classe qui a theme_changed.connect
       ET des setStyleSheet() palette-dépendants DOIT avoir une méthode
       _restyle() qui met à jour TOUS les widgets concernés.
       D7 compare les targets de setStyleSheet() dans __init__/_build_ui
       avec ceux dans _restyle(). Si un widget est stylé dans le builder
       mais PAS dans _restyle() → violation.

Usage:
    python scripts/lint_d1_color_checker.py
    python scripts/lint_d1_color_checker.py --dir .\\LarcSuperviseur
    python scripts/lint_d1_color_checker.py --json
    python scripts/lint_d1_color_checker.py --fix-only
    python scripts/lint_d1_color_checker.py --rule D5       # Uniquement D5
    python scripts/lint_d1_color_checker.py --rule D1+J7+D3+D4+D5  # Tout
"""

LINTER_META = {
    "key": "D",
    "label": "Couleurs palette",
    "category": "theme",
    "description": "Couleurs hex hardcodées et contrastes non conformes à la palette",
    "skill": "color-rules",
}

import argparse
import io
import json
import os
import re
import sys
from pathlib import Path

# Force UTF-8 pour eviter UnicodeEncodeError sous Windows (cp1252)
# — appliqué dans main() uniquement pour éviter un double wrapping


# ── Configuration ─────────────────────────────────────────────────────────────

PROJECTS = [
    "LarcCommon/larccommon",
    "LarcSuperviseur",
    "LarcSecretaire",
    "LarcProf",
    "LarcHub",
]

# Couleurs hex qui sont des exceptions acceptables (couleurs fonctionnelles)
HEX_ALLOWLIST = {
    "#FFF", "#fff", "#FFFFFF", "#ffffff",   # Blanc — acceptable pour compatibilité
    "#000", "#000000",                       # Noir — acceptable pour compatibilité
}

EXCLUDE_DIRS = {"__pycache__", ".git", ".ruff_cache", "venv", ".venv", "node_modules",
                "tools", "docs", "img", "photos", "sql", "tests", ".github"}

# Balises HTML qui contiennent du texte et nécessitent color: explicite (D1)
TEXT_TAGS = {"b", "span", "div", "p", "h1", "h2", "h3", "h4", "h5", "h6",
             "td", "li", "a", "label", "strong", "em", "i", "u", "small",
             "caption", "legend", "figcaption", "blockquote", "pre", "code"}

# Widgets concernés par la règle J7 (WA_StyledBackground)
J7_WIDGETS = {"M3Frame", "QWidget", "QFrame"}
# Widgets déjà protégés (à exclure de J7)
J7_EXEMPT = {"ThemedWidget", "ThemedDialog", "StudentCard"}

# Regex D1
SETTEXT_RE = re.compile(r'setText\s*\(')
HAS_HTML_RE = re.compile(r'<\s*[a-z]', re.IGNORECASE)
HAS_COLOR_RE = re.compile(r'color\s*:', re.IGNORECASE)
TAG_OPEN_RE = re.compile(r'<([a-z]+)(?:\s+[^>]*)?>', re.IGNORECASE)
STYLED_TAG_RE = re.compile(
    r'<([a-z]+)(?:\s+[^>]*?(?:style\s*=\s*["\'][^"\']*?'
    r'(?:color\s*:|;\s*color\s*:)[^"\']*["\']))',
    re.IGNORECASE
)

# Regex J7
WIDGET_CREATION_RE = re.compile(
    r'((?:\w+\.)*\w+)\s*=\s*(M3Frame|QWidget|QFrame)\s*\('
)

# Regex D3 — hex colors dans setStyleSheet (exclut les tokens dans les f-strings)
HEX_COLOR_RE = re.compile(r'#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?|#[0-9a-fA-F]{3}(?![0-9a-fA-F])')
STYLESHEET_CALL_RE = re.compile(r'\.setStyleSheet\s*\(')

# Regex D4 — contrastes insuffisants
# D4a : font-size < 12px AVEC color: text_soft (toute forme)
# Note: {s(N)} est fixe (seule forme utilisée pour font-size), mais
# color: peut être {p.text_soft}, {theme_manager.palette.text_soft}, etc.
FONT_SIZE_SOFT_RE = re.compile(
    r'font-size:\s*\{s\((\d+)\)\}px\s*;.{0,200}?color:\s*\{\w+(?:\.\w+)*\.text_soft\}'
    r'|'
    r'color:\s*\{\w+(?:\.\w+)*\.text_soft\}\s*;.{0,200}?font-size:\s*\{s\((\d+)\)\}px',
    re.DOTALL | re.IGNORECASE
)
# D4b : background: surface_variant AVEC color: text_soft (toute forme)
BG_SOFT_RE = re.compile(
    r'background:\s*\{\w+(?:\.\w+)*\.surface_variant\}\s*;.{0,200}?color:\s*\{\w+(?:\.\w+)*\.text_soft\}'
    r'|'
    r'color:\s*\{\w+(?:\.\w+)*\.text_soft\}\s*;.{0,200}?background:\s*\{\w+(?:\.\w+)*\.surface_variant\}',
    re.DOTALL | re.IGNORECASE
)


# ═══════════════════════════════════════════════════════════════════════════════
#  RÈGLE D5  — color: {p.text_soft} dans setStyleSheet() inline
#
#  D5a : string literal directe — f"...{p.text_soft}..." inline
#  D5b : indirection par variable — qss = f"...{p.text_soft}..."; widget.setStyleSheet(qss)
#
#  Les _STYLE properties (gérées centralement) sont EXCLUES car passées
#  par référence (self._STYLE) — leur contenu QSS ne transite pas via
#  une string literal dans l'appel setStyleSheet().
# ═══════════════════════════════════════════════════════════════════════════════

# Regex D5 — détection de .text_soft sous toutes ses formes dans un token f-string
# (p.text_soft, theme_manager.palette.text_soft, ds.p.text_soft, etc.)
# Le groupe (1) capture la forme exacte (ex: "p.text_soft", "ds.p.text_soft")
D5_TEXT_SOFT_RE = re.compile(r'\{(\w+(?:\.\w+)*\.text_soft)\}')

# Regex D5b — variable assignment contenant .text_soft dans un f-string
D5B_VAR_ASSIGN_RE = re.compile(
    r'(?:self\.)?(\w+)\s*=\s*f["\'][^"\']*\{\w+(?:\.\w+)*\.text_soft\}[^"\']*["\']'
)
# Regex D5b — setStyleSheet() dont l'argument est une variable (pas une string literal)
D5B_SETSTYLE_VAR_RE = re.compile(
    r'\.setStyleSheet\s*\(\s*(\w+(?:\.\w+)*)\s*\)'
)


# ═══════════════════════════════════════════════════════════════════════════════
#  RÈGLE D6  — Réactivité au thème
#
#  Toute classe qui utilise des tokens palette (p.primary, p.surface, etc.)
#  dans un setStyleSheet() inline DOIT avoir une connexion
#  `ds.theme_changed.connect(...)` ou `theme_changed.connect(...)`
#  dans son __init__ ou _build_ui. Sans cela, le widget ne réagit pas
#  au changement de thème et conserve ses couleurs d'origine.
#
#  Classes héritant de ThemedWidget ou ThemedDialog sont exonérées
#  (elles connectent automatiquement via leur classe parent).
# ═══════════════════════════════════════════════════════════════════════════════

# Regex D6 — tokens palette dans setStyleSheet()
PALETTE_TOKEN_RE = re.compile(
    r'\{(?:p|ds\.p|theme_manager\.palette|theme_manager\.theme\.palette)\.'
)
# Regex D6 — connexion theme_changed
THEME_CHANGED_CONNECT_RE = re.compile(
    r'(?:ds\.)?theme_changed\.connect'
)
# Regex D6 — classes exemptées (héritent ThemedWidget/ThemedDialog)
THEMED_BASE_RE = re.compile(
    r'class\s+\w+\s*\([^)]*Themed(?:Widget|Dialog)[^)]*\)'
)
# Regex D6 — infrastructure de thème (génère le QSS par définition)
THEME_INFRA_RE = re.compile(
    r'class\s+\w*(?:ThemeManager|QssHelper|ThemeManagerWrapper)\w*\b'
)
# Regex D6 — objets éphémères : dialogues modaux & delegates (palette lue à la construction)
EPHEMERAL_BASE_RE = re.compile(
    r'\((?:[^)]*)(?:M3Dialog|QDialog|QStyledItemDelegate)(?:[^)]*)\)'
)
# Regex D6 — écrans de démarrage (thème figé avant affichage, pas de bascule)
LOGIN_SCREEN_RE = re.compile(r'class\s+LoginWindow\b')
# Regex D6 — hook de restyle présent (pattern restyle piloté par le parent)
RESTYLE_HOOK_RE = re.compile(
    r'def\s+(?:_restyle|restyle|_restyle_all|refresh_theme|_update_style|_apply_style)\s*\('
    r'|def\s+_STYLE\s*\('
)
# Regex D6 — début de classe
CLASS_START_RE = re.compile(r'^(\s*)class\s+(\w+)')


def find_class_boundaries(lines: list[str]) -> list[dict]:
    """Détecte les classes Python avec leurs limites (début, fin).

    Retourne une liste de dicts :
        name: str — nom de la classe
        bases: str — texte des parenthèses (héritage)
        start: int — ligne de début (0-based)
        end: int — ligne de fin (exclusive, 0-based)
        indent: int — niveau d'indentation de la classe
    """
    classes = []
    for i, line in enumerate(lines):
        m = CLASS_START_RE.match(line)
        if not m:
            continue
        indent = len(m.group(1))
        name = m.group(2)

        # Capturer les bases : tout entre ( et la première ) non-imbriquée
        # après le nom de la classe
        bases = ""
        paren_start = line.find('(')
        if paren_start >= 0:
            paren_count = 0
            for pos in range(paren_start, len(line)):
                if line[pos] == '(':
                    paren_count += 1
                elif line[pos] == ')':
                    paren_count -= 1
                    if paren_count == 0:
                        bases = line[paren_start:pos + 1].strip()
                        break

        # Trouver la fin de la classe : prochaine ligne au même niveau
        # d'indentation (ou inférieur) qui n'est pas vide, commentaire,
        # décorateur, ou continuation de la déclaration
        end = len(lines)
        for j in range(i + 1, len(lines)):
            l = lines[j]
            if not l.strip() or l.strip().startswith('#'):
                continue
            # Vérifier l'indentation de la ligne
            leading = len(l) - len(l.lstrip())
            if not l.strip():
                continue
            if leading < indent:
                # Ligne moins indentée que la classe → la classe est terminée
                end = j
                break
            if leading == indent:
                # Même indentation que class → nouvelle classe/fonction/code racine
                end = j
                break

        classes.append({
            "name": name,
            "bases": bases,
            "start": i,
            "end": end,
            "indent": indent,
        })

    return classes


def class_body_text(lines: list[str], cls: dict) -> str:
    """Extrait le texte du corps d'une classe (entre la déclaration et la fin)."""
    if cls["start"] + 1 >= cls["end"]:
        return ""
    return "".join(lines[cls["start"]:cls["end"]])


def scan_d6_violations(lines: list[str], filepath: Path) -> list[dict]:
    """Scanne les violations D6 (setStyleSheet palette sans theme_changed).

    Stratégie :
      1. Trouver toutes les classes Python
      2. Pour chaque classe :
         a. Vérifier si elle a des setStyleSheet() avec tokens palette
         b. Vérifier si elle a theme_changed.connect
         c. Vérifier si elle hérite de ThemedWidget/ThemedDialog (exempté)
         d. Si (a) sans (b) et sans (c) → violation D6
    """
    violations = []

    classes = find_class_boundaries(lines)
    if not classes:
        return violations

    for cls in classes:
        body = class_body_text(lines, cls)
        if not body:
            continue

        # Vérifier si la classe hérite de ThemedWidget/ThemedDialog (exemptée)
        # On reconstruit la signature à partir des bases capturées
        if THEMED_BASE_RE.search(f"class {cls['name']} {cls['bases']}:"):
            continue

        # 0. Fragments de classe (Mixin) : la réactivité au thème est portée
        #    par la classe parente qui les compose (pattern LarcProf)
        if cls['name'].endswith('Mixin'):
            continue

        # Exemptions architecture Larc (règles D6 documentées dans le skill)
        # 1. Infrastructure de thème : ThemeManager/QssHelper génèrent le QSS
        if THEME_INFRA_RE.search(f"class {cls['name']} {cls['bases']}:"):
            continue
        # 2. Objets éphémères : dialogues modaux & delegates (palette à la construction)
        if EPHEMERAL_BASE_RE.search(cls["bases"]):
            continue
        # 3. Écrans de démarrage : login, thème figé avant l'affichage
        if LOGIN_SCREEN_RE.search(f"class {cls['name']} {cls['bases']}:"):
            continue

        # Chercher des setStyleSheet() avec tokens palette dans le corps
        has_palette_stylesheet = bool(PALETTE_TOKEN_RE.search(body))
        if not has_palette_stylesheet:
            continue

        # Chercher theme_changed.connect dans le corps
        has_theme_connect = bool(THEME_CHANGED_CONNECT_RE.search(body))
        if has_theme_connect:
            continue

        # 4. Hook de restyle présent (pattern piloté par le parent) :
        #    _restyle/restyle/_restyle_all/refresh_theme/_update_style/_STYLE
        if RESTYLE_HOOK_RE.search(body):
            continue

        # Violation : palette setStyleSheet sans theme_changed
        violations.append({
            "rule": "D6",
            "line": cls["start"] + 1,  # 1-based
            "detail": (
                f"{cls['name']} utilise des tokens palette dans setStyleSheet() "
                f"mais n'a PAS de connexion theme_changed → ne réagit pas "
                f"au changement de thème"
            ),
            "raw": f"class {cls['name']}{cls['bases']}",
            "file": str(filepath),
        })

    return violations


# ═══════════════════════════════════════════════════════════════════════════════
#  RÈGLE D7  — Complétude de _restyle()
#
#  Pour les classes qui ONT theme_changed.connect ET utilisent des tokens
#  palette dans des setStyleSheet() inline, D7 vérifie que la méthode
#  _restyle() couvre BIEN TOUS les widgets qui reçoivent un setStyleSheet()
#  palette-dépendant dans __init__ ou _build_ui.
#
#  Fonctionnement :
#    1. Trouver la méthode _restyle() dans la classe
#    2. Collecter les targets de setStyleSheet() palette-dépendants
#       dans le BUILDER (tout sauf _restyle) et dans RESTYLE
#    3. Si un target est présent dans BUILDER mais PAS dans RESTYLE → D7
#
#  Exemptions : classes héritant de ThemedWidget/ThemedDialog
# ═══════════════════════════════════════════════════════════════════════════════

# Regex D7 — target du setStyleSheet (le widget avant .setStyleSheet)
SS_TARGET_RE = re.compile(r'(\w+(?:\.\w+)*)\.setStyleSheet\s*\(')
# Regex D7 — début de méthode
METHOD_DEF_RE = re.compile(r'^(\s*)def\s+(\w+)\s*\(')


def find_method_def(cls: dict, method_name: str, lines: list[str]) -> int | None:
    """Trouve la ligne (0-based) de la définition d'une méthode dans une classe."""
    for i in range(cls["start"], cls["end"]):
        m = METHOD_DEF_RE.match(lines[i])
        if m and m.group(2) == method_name:
            return i
    return None


def find_method_end(cls: dict, method_start: int, method_indent: int, lines: list[str]) -> int:
    """Trouve la ligne de fin (0-based, exclusive) d'une méthode.
    
    La méthode se termine à la prochaine ligne non-vide/non-commentaire
    avec une indentation <= method_indent.
    """
    for j in range(method_start + 1, cls["end"]):
        l = lines[j]
        if not l.strip() or l.strip().startswith('#'):
            continue
        leading = len(l) - len(l.lstrip())
        if leading <= method_indent:
            return j
    return cls["end"]


def collect_ss_targets(lines: list[str], start: int, end: int,
                          require_palette: bool = True) -> set[str]:
    """Collecte les targets de setStyleSheet() avec tokens palette.

    Utilise extract_stylesheet_calls() pour gérer les appels multi-lignes où
    le token palette peut être sur une ligne différente de .setStyleSheet(
    (ex: widget.setStyleSheet(\n    f"...color: {p.primary};..."\n)).

    Filtre les variables locales : seules les targets avec self.xxx ou self
    sont des membres de la classe qui nécessitent une mise à jour dans _restyle().
    Les variables locales (ex: dlg, ed, lbl, sep) créées dans des event handlers
    ne sont pas des membres et n'ont pas besoin de _restyle.
    """
    targets = set()
    # Utiliser extract_stylesheet_calls() qui gère correctement les multi-lignes
    calls = extract_stylesheet_calls(lines[start:end])
    for call in calls:
        raw = call["raw"]
        m = SS_TARGET_RE.search(raw)
        if not m:
            continue
        if require_palette and not PALETTE_TOKEN_RE.search(raw):
            continue
        target = m.group(1)
        # Ignorer les variables locales (sans self.) — faux positifs
        # Les membres de classe commencent par self.
        # self.setStyleSheet(...) est aussi un target valide
        if target and (target.startswith('self.') or target == 'self'):
            targets.add(target)
    return targets


def scan_d7_violations(lines: list[str], filepath: Path) -> list[dict]:
    """Scanne les violations D7 (setStyleSheet builder non repris dans _restyle).

    Stratégie :
      1. Pour chaque classe avec theme_changed.connect ET palette setStyleSheet :
         a. Localiser la méthode _restyle()
         b. Collecter les targets palette setStyleSheet AVANT _restyle (builder)
         c. Collecter les targets palette setStyleSheet APRÈS _restyle (builder)
         d. Collecter les targets palette setStyleSheet DANS _restyle
         e. Si un target builder n'est PAS dans restyle → violation D7
      2. Si theme_changed.connect existe MAIS pas de _restyle() → violation D7
    """
    violations = []

    classes = find_class_boundaries(lines)
    if not classes:
        return violations

    for cls in classes:
        body = class_body_text(lines, cls)
        if not body:
            continue

        # Exempté ?
        if THEMED_BASE_RE.search(f"class {cls['name']} {cls['bases']}:"):
            continue

        # Doit avoir theme_changed.connect ET palette setStyleSheet
        if not THEME_CHANGED_CONNECT_RE.search(body):
            continue
        if not PALETTE_TOKEN_RE.search(body):
            continue

        # Trouver la méthode _restyle() et ses alias éventuels
        # (_restyle → _rebuild / _restyle_all / restyle / _update_style)
        restyle_start = find_method_def(cls, "_restyle", lines)

        # Pas de méthode _restyle() littérale : essayer les alias comme
        # candidats PRIMAIRES (une classe peut connecter theme_changed
        # directement à _restyle_all/restyle/etc. sans wrapper _restyle)
        if restyle_start is None:
            for alias_name in (
                "_restyle_all", "restyle", "_rebuild", "_update_style", "refresh_theme"
            ):
                restyle_start = find_method_def(cls, alias_name, lines)
                if restyle_start is not None:
                    break

        if restyle_start is None:
            # a theme_changed.connect MAIS pas de _restyle (ni alias) → D7
            violations.append({
                "rule": "D7",
                "line": cls["start"] + 1,
                "detail": (
                    f"{cls['name']} a theme_changed.connect mais PAS de "
                    f"méthode _restyle() → connexion inefficace"
                ),
                "raw": f"class {cls['name']}{cls['bases']}",
                "file": str(filepath),
            })
            continue

        # Déterminer l'indentation de la méthode _restyle
        restyle_indent = len(lines[restyle_start]) - len(lines[restyle_start].lstrip())
        restyle_end = find_method_end(cls, restyle_start, restyle_indent, lines)

        # Suivre les alias : si _restyle délègue à _rebuild/_restyle_all/restyle,
        # scanner AUSSI le corps de la méthode appelée
        restyle_ranges: list[tuple[int, int]] = [(restyle_start, restyle_end)]
        _restyle_body = "".join(lines[restyle_start:restyle_end])
        for alias in ("_rebuild", "_restyle_all", "restyle", "_update_style", "refresh_theme"):
            if re.search(rf"self\.{alias}\s*\(", _restyle_body):
                a_start = find_method_def(cls, alias, lines)
                if a_start is not None:
                    a_indent = len(lines[a_start]) - len(lines[a_start].lstrip())
                    a_end = find_method_end(cls, a_start, a_indent, lines)
                    restyle_ranges.append((a_start, a_end))

        # Builder = toute la classe MOINS les plages de restyle (avec palette)
        builder_targets: set[str] = set()
        _sorted_ranges = sorted(restyle_ranges, key=lambda r: r[0])
        cursor = cls["start"]
        for rs, re_ in _sorted_ranges:
            if cursor < rs:
                builder_targets |= collect_ss_targets(lines, cursor, rs)
            cursor = max(cursor, re_)
        if cursor < cls["end"]:
            builder_targets |= collect_ss_targets(lines, cursor, cls["end"])

        # Restyle = dans les méthodes de restyle, SANS exigence de token palette
        # inline (l'indirection qss = f"...{p.x}..." puis setStyleSheet(qss)
        # doit compter comme couverte par _restyle)
        restyle_targets: set[str] = set()
        for rs, re_ in restyle_ranges:
            if rs + 1 < re_:
                restyle_targets |= collect_ss_targets(
                    lines, rs + 1, re_, require_palette=False
                )

        # Comparer
        missing = builder_targets - restyle_targets
        if missing:
            targets_str = ", ".join(sorted(missing))
            violations.append({
                "rule": "D7",
                "line": cls["start"] + 1,
                "detail": (
                    f"{cls['name']} ne met pas à jour dans _restyle() les "
                    f"widgets suivants : {targets_str}"
                ),
                "raw": f"class {cls['name']}{cls['bases']}",
                "file": str(filepath),
            })

    return violations


def scan_d5_violations(lines: list[str], filepath: Path) -> list[dict]:
    """Scanne les violations D5a (text_soft dans setStyleSheet inline direct).

    Détecte TOUTES les formes d'accès à text_soft :
      {p.text_soft}, {theme_manager.palette.text_soft}, {ds.p.text_soft}, etc.

    _STYLE properties sont exclues (contenu géré centralement).
    """
    violations = []
    calls = extract_stylesheet_calls(lines)

    for call in calls:
        raw = call["raw"]
        # Utilise une regex avec groupe capturant pour détecter
        # TOUTES les formes de .text_soft dans un token f-string
        m = D5_TEXT_SOFT_RE.search(raw)
        if not m:
            continue
        if '_STYLE' in raw or '._style()' in raw:
            continue

        form = m.group(1)  # "p.text_soft", "ds.p.text_soft", "theme_manager.palette.text_soft", etc.

        violations.append({
            "rule": "D5",
            "line": call["start_line"],
            "detail": (
                f"{form} dans setStyleSheet() inline = "
                f"risque gris-sur-gris en dark (utiliser text_strong)"
            ),
            "raw": raw.strip()[:150],
            "file": str(filepath),
        })

    return violations


def scan_d5b_violations(lines: list[str], filepath: Path) -> list[dict]:
    """Scanne les violations D5b (indirection par variable).

    Détecte :
      qss = f"...color: {p.text_soft}..."   # variable taintée
      widget.setStyleSheet(qss)               # usage indirect

    Approche :
      1. Collecter toutes les variables assignées avec .text_soft (toute forme),
         enregistrer la ligne de l'assignation
      2. Pour chaque setStyleSheet(), vérifier si l'argument est
         une variable taintée DANS LE MÊME SCOPE (proximité ≤ 30 lignes)
      3. Normaliser les noms : self.xxx et xxx sont considérés identiques
    """
    violations = []

    # 1. Collecter les variables taintées avec leur numéro de ligne
    tainted: dict[str, int] = {}  # var_name → line_number
    for lineno, line in enumerate(lines):
        m = D5B_VAR_ASSIGN_RE.search(line)
        if m:
            var_name = m.group(1)
            tainted[var_name] = lineno + 1  # 1-based

    if not tainted:
        return violations

    # 2. Scanner les appels setStyleSheet() pour les variables taintées
    calls = extract_stylesheet_calls(lines)
    for call in calls:
        raw = call["raw"]
        # Exclure les string literals directes (déjà D5a)
        if 'f"' in raw or "f'" in raw or '"""' in raw:
            continue
        # Exclure les _STYLE / _style (gérés centralement)
        if '_STYLE' in raw or '._style()' in raw:
            continue

        # Vérifier si l'argument est une variable taintée
        m = D5B_SETSTYLE_VAR_RE.search(raw)
        if not m:
            continue

        var_usage = m.group(1)
        # Normaliser : self.xxx → xxx
        var_usage_normalized = var_usage.replace("self.", "")

        # Chercher dans les variables taintées (nom exact ou avec self.)
        matched_var = None
        for tv_name, tv_line in tainted.items():
            if tv_name == var_usage or tv_name == var_usage_normalized:
                matched_var = (tv_name, tv_line)
                break
            # Aussi vérifier l'inverse : si var_usage = xxx et tv_name = self.xxx
            if f"self.{tv_name}" == var_usage:
                matched_var = (tv_name, tv_line)
                break

        if matched_var is None:
            continue

        tv_name, tv_line = matched_var
        call_line = call["start_line"]

        # Vérifier la proximité : l'assignation doit précéder l'usage
        # et pas plus de 30 lignes entre les deux (évite les faux positifs
        # entre fonctions différentes du même fichier)
        if not (tv_line <= call_line <= tv_line + 30):
            continue

        violations.append({
            "rule": "D5b",
            "line": call_line,
            "detail": (
                f"variable '{var_usage}' taintée L{tv_line} avec "
                f".text_soft utilisée dans setStyleSheet() = "
                f"risque gris-sur-gris en dark"
            ),
            "raw": raw.strip()[:150],
            "file": str(filepath),
        })

    return violations


# ═══════════════════════════════════════════════════════════════════════════════
#  RÈGLE D1  — setText() HTML sans color: explicite
# ═══════════════════════════════════════════════════════════════════════════════


def has_text_content(tag_name: str) -> bool:
    return tag_name.lower() in TEXT_TAGS


def extract_settext_calls(lines: list[str]) -> list[dict]:
    """Extrait tous les appels setText() du code, y compris multi-lignes.
    
    Utilise le comptage de parenthèses avec enumerate() pour gérer
    correctement les parenthèses ouvrantes avant setText( sur la même ligne.
    """
    calls = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if SETTEXT_RE.search(line):
            start_line = i
            paren_count = 0
            in_settext = False
            buffer = []
            found_paren = False
            j = i
            max_lines = j + 100  # Garde-fou : pas plus de 100 lignes par appel

            while j < len(lines) and j <= max_lines:
                l = lines[j]
                buffer.append(l)

                for pos, ch in enumerate(l):
                    if ch == '(':
                        if SETTEXT_RE.search(l) and not in_settext:
                            idx = l.find('setText(')
                            if idx >= 0:
                                paren_start = l.index('(', idx)
                                if pos >= paren_start:
                                    in_settext = True
                                    paren_count += 1
                                    found_paren = True
                        elif in_settext:
                            paren_count += 1
                    elif ch == ')':
                        if in_settext:
                            paren_count -= 1

                if in_settext and paren_count == 0 and found_paren:
                    raw = "".join(buffer).strip()
                    calls.append({
                        "start_line": start_line + 1,
                        "end_line": j + 1,
                        "raw": raw,
                    })
                    i = j
                    break
                j += 1
                    # Si on sort sans trouver la fermeture, on continue
        i += 1
    return calls


def detect_missing_color(call: dict) -> list[dict]:
    """Analyse un appel setText() et détecte les violations D1."""
    violations = []
    raw = call["raw"]

    if not HAS_HTML_RE.search(raw):
        return violations

    has_color = bool(HAS_COLOR_RE.search(raw))

    if not has_color:
        tags_found = set()
        for m in TAG_OPEN_RE.finditer(raw):
            tagname = m.group(1).lower()
            if has_text_content(tagname):
                tags_found.add(tagname)

        if tags_found:
            violations.append({
                "rule": "D1a",
                "tag": ", ".join(sorted(tags_found)),
                "line": call["start_line"],
                "detail": f"Balises HTML (<{', '.join(sorted(tags_found))}>) sans color: explicite",
                "raw": raw[:200],
            })
    else:
        tags_with_style = set()
        for m in STYLED_TAG_RE.finditer(raw):
            tags_with_style.add(m.group(1).lower())

        all_text_tags = set()
        for m in TAG_OPEN_RE.finditer(raw):
            tagname = m.group(1).lower()
            if has_text_content(tagname):
                all_text_tags.add(tagname)

        missing = all_text_tags - tags_with_style
        if missing:
            violations.append({
                "rule": "D1a",
                "tag": ", ".join(sorted(missing)),
                "line": call["start_line"],
                "detail": f"Balises <{', '.join(sorted(missing))}> sans color: (autres balises en ont)",
                "raw": raw[:200],
            })

    return violations


def scan_d1_violations(lines: list[str], filepath: Path) -> list[dict]:
    """Scanne les violations D1 (setText HTML sans color:) dans un fichier."""
    violations = []
    calls = extract_settext_calls(lines)
    for call in calls:
        found = detect_missing_color(call)
        for v in found:
            v["file"] = str(filepath)
            violations.append(v)
    return violations


# ═══════════════════════════════════════════════════════════════════════════════
#  RÈGLE J7  — M3Frame/QWidget/QFrame avec background QSS mais sans
#              WA_StyledBackground
# ═══════════════════════════════════════════════════════════════════════════════


def scan_j7_violations(lines: list[str], filepath: Path) -> list[dict]:
    """Scanne les violations J7 (widget avec background QSS sans WA_StyledBackground).
    
    Stratégie :
    1. Trouve toutes les créations de M3Frame/QWidget/QFrame avec leur variable
    2. Pour chaque variable, regarde les ~15 lignes suivantes pour :
       - setStyleSheet avec background:  → besoin de WA_StyledBackground
       - setAttribute(Qt.WA_StyledBackground, True) → déjà protégé
    3. Si background QSS trouvé mais PAS WA_StyledBackground → violation J7
    """
    violations = []
    lookahead = 15  # Lignes à inspecter après la création du widget

    # Trouver toutes les créations de widget
    widgets = []
    for lineno, line in enumerate(lines):
        m = WIDGET_CREATION_RE.search(line)
        if m:
            var_name = m.group(1)
            widget_type = m.group(2)
            widgets.append({
                "var": var_name,
                "type": widget_type,
                "line": lineno + 1,  # 1-based
            })

    for w in widgets:
        var = w["var"]
        has_stylesheet_bg = False
        has_wa_styled = False
        bg_line = 0
        bg_snippet = ""
        block_lines = []

        # Collecter les lignes du bloc (jusqu'à lookahead)
        start = w["line"]  # 1-based
        for offset in range(1, lookahead + 1):
            idx = start - 1 + offset  # 0-based
            if idx >= len(lines):
                break
            block_lines.append(lines[idx])

        # Scanner le bloc UNIQUE pour background: (supporte multi-lignes)
        block_text = "".join(block_lines)

        bg_match = re.search(
            rf'{re.escape(var)}\.setStyleSheet\s*\(.*?background\s*:',
            block_text, re.IGNORECASE | re.DOTALL
        )
        if bg_match:
            has_stylesheet_bg = True
            # Trouver la ligne la plus proche du match
            match_pos = bg_match.start()
            char_count = 0
            for offset, bl in enumerate(block_lines):
                if char_count + len(bl) > match_pos:
                    bg_line = start + 1 + offset
                    bg_snippet = bl.strip()[:120]
                    break
                char_count += len(bl)

        # Vérifier si setAttribute(Qt.WA_StyledBackground est appelé
        wa_match = re.search(
            rf'{re.escape(var)}\.setAttribute\s*\(\s*Qt\.WA_StyledBackground',
            block_text, re.IGNORECASE
        )
        if wa_match:
            has_wa_styled = True

        # Si background QSS mais PAS WA_StyledBackground → violation
        if has_stylesheet_bg and not has_wa_styled:
            violations.append({
                "rule": "J7",
                "line": w["line"],
                "tag": w["type"],
                "detail": (
                    f"{w['type']} '{var}' a un background QSS (L{bg_line}) "
                    f"mais PAS de setAttribute(Qt.WA_StyledBackground, True)"
                ),
                "raw": bg_snippet,
                "file": str(filepath),
            })

    return violations


# ═══════════════════════════════════════════════════════════════════════════════
#  RÈGLE D3  — Couleurs hex hardcodées dans setStyleSheet()
#
#  Les couleurs hex (#xxxxxx) dans setStyleSheet() NE réagissent PAS au
#  changement de thème. Utiliser les tokens {p.primary}, {p.surface}, etc.
# ═══════════════════════════════════════════════════════════════════════════════


def extract_stylesheet_calls(lines: list[str]) -> list[dict]:
    """Extrait tous les appels setStyleSheet() multi-lignes.
    
    Utilise lines[i].index('(', m.start()) pour trouver la position
    exacte de la parenthèse ouvrante de setStyleSheet( — ignorer
    les '(' qui précèdent éventuellement (ex: foo(x).setStyleSheet(...)).
    """
    calls = []
    i = 0
    while i < len(lines):
        m = STYLESHEET_CALL_RE.search(lines[i])
        if m:
            start_line = i
            # Trouver '(' exact de setStyleSheet(
            paren_idx = lines[i].index('(', m.start())
            paren_count = 0
            buffer = []
            j = i
            max_lines = j + 100
            started = False

            while j < len(lines) and j <= max_lines:
                l = lines[j]
                buffer.append(l)
                for pos, ch in enumerate(l):
                    if j == i and pos < paren_idx:
                        continue  # Ignorer les '(' avant setStyleSheet(
                    if ch == '(':
                        started = True
                        paren_count += 1
                    elif ch == ')':
                        if started:
                            paren_count -= 1

                if started and paren_count == 0:
                    raw = "".join(buffer)
                    calls.append({
                        "start_line": start_line + 1,
                        "end_line": j + 1,
                        "raw": raw,
                    })
                    i = j
                    break
                j += 1
        i += 1
    return calls


def scan_d3_violations(lines: list[str], filepath: Path) -> list[dict]:
    """Scanne les violations D3 (hex colors hardcodés dans setStyleSheet)."""
    violations = []
    calls = extract_stylesheet_calls(lines)

    for call in calls:
        raw = call["raw"]
        # Nettoyer les tokens f-string {p.xxx} et {ds.xxx} pour éviter les faux positifs
        # (un token {p.primary} peut contenir "primary" qui ressemble à "#fff" mais ne l'est pas)
        cleaned = re.sub(r'\{[^}]+\}', ' TOKEN ', raw)
        # Nettoyer aussi les triple quotes f"""..."""
        cleaned = re.sub(r'f"""', '', cleaned)
        cleaned = re.sub(r'"""', '', cleaned)

        hex_found = set()
        for m in HEX_COLOR_RE.finditer(cleaned):
            hex_color = m.group()
            if hex_color not in HEX_ALLOWLIST:
                hex_found.add(hex_color)

        if hex_found:
            colors_str = ", ".join(sorted(hex_found))
            violations.append({
                "rule": "D3",
                "line": call["start_line"],
                "detail": f"setStyleSheet contient {len(hex_found)} hex hardcodé(s) : {colors_str}",
                "raw": f"{len(hex_found)} hex — {colors_str}",
                "file": str(filepath),
            })

    return violations


# ═══════════════════════════════════════════════════════════════════════════════
#  RÈGLE D4  — Contrastes insuffisants
#
#  D4a : font-size < 12px AVEC color: {p.text_soft}
#        → le texte trop petit avec une couleur trop pâle devient illisible
#          en mode dark (contraste ~5:1 au lieu des 15:1 nécessaires pour 10px)
#
#  D4b : background: {p.surface_variant} AVEC color: {p.text_soft}
#        → le fond #2D2D2D + texte #9E9E9E donne du "gris sur gris" en dark
# ═══════════════════════════════════════════════════════════════════════════════


def scan_d4_violations(lines: list[str], filepath: Path) -> list[dict]:
    """Scanne les violations D4 (contrastes insuffisants dans les QSS).
    
    Technique : recherche ligne par ligne avec un lookahead de 3 lignes
    pour gérer les QSS multi-lignes. Les tokens {s(10)} et {p.text_soft}
    sont détectés dans le code source Python.
    """
    violations = []
    lookahead = 3  # Lignes à inspecter après la ligne courante

    for lineno, line in enumerate(lines):
        # Ne scanner que les lignes contenant du QSS
        if not ('color:' in line or 'font-size:' in line or 'background:' in line):
            continue

        # Construire un bloc de lignes pour le lookahead
        block_lines = [line]
        for offset in range(1, lookahead + 1):
            idx = lineno + offset
            if idx < len(lines):
                block_lines.append(lines[idx])
        block_text = "".join(block_lines)

        # D4a : font-size < 12px + color: text_soft
        for m in FONT_SIZE_SOFT_RE.finditer(block_text):
            fs1 = m.group(1)
            fs2 = m.group(2)
            fs = int(fs1 or fs2 or 99)
            if fs < 12:
                violations.append({
                    "rule": "D4a",
                    "line": lineno + 1,
                    "detail": f"font-size {fs}px + color: text_soft = contraste insuffisant en dark ({fs}px < 12px → utiliser text_strong)",
                    "raw": line.strip()[:120],
                    "file": str(filepath),
                })
                break  # Une seule violation par ligne

        # D4b : background: surface_variant + color: text_soft
        if BG_SOFT_RE.search(block_text):
            # Vérifier qu'on a pas déjà une violation D4a sur cette ligne
            already_reported = any(v["line"] == lineno + 1 for v in violations)
            if not already_reported:
                violations.append({
                    "rule": "D4b",
                    "line": lineno + 1,
                    "detail": "background: surface_variant + color: text_soft = gris sur gris en dark (utiliser text_strong)",
                    "raw": line.strip()[:120],
                    "file": str(filepath),
                })

    return violations


# ═══════════════════════════════════════════════════════════════════════════════
#  Scan générique
# ═══════════════════════════════════════════════════════════════════════════════


def scan_file(filepath: Path, rules: set[str]) -> list[dict]:
    """Scanne un fichier Python pour les violations D1, J7, D3, D4 et/ou D5."""
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
            lines = content.splitlines(keepends=True)
    except (UnicodeDecodeError, IOError):
        return []

    if not lines:
        return []

    violations = []

    if "D1" in rules:
        violations.extend(scan_d1_violations(lines, filepath))
    if "J7" in rules:
        violations.extend(scan_j7_violations(lines, filepath))
    if "D3" in rules:
        violations.extend(scan_d3_violations(lines, filepath))
    if "D4" in rules:
        violations.extend(scan_d4_violations(lines, filepath))
    if "D5" in rules:
        violations.extend(scan_d5_violations(lines, filepath))
        violations.extend(scan_d5b_violations(lines, filepath))
    if "D5B" in rules:
        violations.extend(scan_d5b_violations(lines, filepath))
    if "D6" in rules:
        violations.extend(scan_d6_violations(lines, filepath))
    if "D7" in rules:
        violations.extend(scan_d7_violations(lines, filepath))

    return violations


def scan_directory(directory: Path, rules: set[str]) -> list[dict]:
    """Scanne récursivement un répertoire."""
    all_violations = []

    if not directory.exists():
        print(f"  ❌ Répertoire introuvable : {directory}")
        return []

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for file in files:
            if not file.endswith(".py"):
                continue
            filepath = Path(root) / file
            v = scan_file(filepath, rules)
            if v:
                all_violations.extend(v)

    return all_violations


# ═══════════════════════════════════════════════════════════════════════════════
#  Rapports
# ═══════════════════════════════════════════════════════════════════════════════


def print_report(project_name: str, violations: list[dict]):
    """Affiche le rapport formaté."""
    if not violations:
        print(f"  ✅ {project_name} — 0 violation — FÉLICITATIONS !")
        return

    # Grouper par règle
    rules = set(v.get("rule", "D1") for v in violations)
    rule_label = "+".join(sorted(rules))

    print(f"\n  {'='*60}")
    print(f"  🔍 {project_name} — {len(violations)} violation(s) [{rule_label}]")
    print(f"  {'='*60}")

    by_file: dict[str, list[dict]] = {}
    for v in violations:
        by_file.setdefault(v["file"], []).append(v)

    for filepath, file_violations in by_file.items():
        relpath = os.path.relpath(filepath, start=os.getcwd())
        print(f"\n  📄 {relpath}")
        for v in file_violations:
            rule = v.get("rule", "D1")
            if rule == "J7":
                print(f"    L{v['line']:>4}  [J7] ❌ {v['detail']}")
            elif rule == "D3":
                print(f"    L{v['line']:>4}  [D3] ❌ {v['detail']}")
            elif rule in ("D4a", "D4b"):
                print(f"    L{v['line']:>4}  [{rule}] ❌ {v['detail']}")
            elif rule in ("D5", "D5b"):
                print(f"    L{v['line']:>4}  [{rule}] ❌ {v['detail']}")
            elif rule == "D6":
                print(f"    L{v['line']:>4}  [D6] ❌ {v['detail']}")
            elif rule == "D7":
                print(f"    L{v['line']:>4}  [D7] ❌ {v['detail']}")
            else:
                print(f"    L{v['line']:>4}  [D1] ❌ {v['detail']}")
            snippet = v.get("raw", "")
            if snippet and len(snippet) > 5:
                s = snippet.strip()[:150]
                print(f"          └─ {s}…")

    print()


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="Linter D1+J7 — couleurs explicites dans HTML + WA_StyledBackground"
    )
    parser.add_argument(
        "--dir", type=str, default="",
        help="Répertoire à analyser (par défaut : tous les projets Larc)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Sortie JSON",
    )
    parser.add_argument(
        "--fix-only", action="store_true",
        help="Mode compact — seulement les fichiers et lignes",
    )
    parser.add_argument(
        "--rule", type=str, default="D1+J7",
        help="Règles : D1, J7, D3, D4 (ou D4a/D4b), D5, D5B, D6, D7, D1+J7 (défaut), D1+J7+D3+D4+D5+D6+D7",
    )
    args = parser.parse_args()

    # Forcer UTF-8 pour la sortie terminal (compatible pre-commit sur Windows cp1252)
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    # Déterminer les règles à appliquer — parsing GÉNÉRIQUE (split sur '+')
    # pour supporter toute combinaison (D1+J7+D3+D4+D5+D6+D7, D5B, etc.)
    ALL_RULES = {"D1", "J7", "D3", "D4", "D5", "D5B", "D6", "D7"}
    rule_key = args.rule.upper().strip()
    # Normaliser les sous-règles : D4A → D4, D4B → D4
    rule_key = rule_key.replace("D4A", "D4").replace("D4B", "D4")

    requested = {part for part in rule_key.split("+") if part}
    if requested and requested <= ALL_RULES:
        rules = requested
    else:
        rules = {"D1", "J7"}  # D1+J7 par défaut (clé inconnue)

    rule_label = "+".join(sorted(rules))

    all_violations = {}

    if args.dir:
        projects_to_scan = [args.dir]
    else:
        projects_to_scan = PROJECTS

    base_path = Path(os.getcwd())

    for project in projects_to_scan:
        project_path = base_path / project
        if not project_path.exists():
            alt_path = base_path.parent / project
            if alt_path.exists():
                project_path = alt_path
            else:
                print(f"  ⚠️  Répertoire non trouvé : {project}")
                continue

        if not args.json and not args.fix_only:
            print(f"\n🔍 Scan {rule_label} de {project}...")
        violations = scan_directory(project_path, rules)
        all_violations[project] = violations

        if not args.json and not args.fix_only:
            print_report(project, violations)
        elif args.fix_only and violations:
            for v in violations:
                relpath = os.path.relpath(v["file"], start=os.getcwd())
                rule = v.get("rule", "D1")
                print(f"  [{rule}] {relpath}:{v['line']}  {v['detail']}")

    total = sum(len(v) for v in all_violations.values())

    if not args.json and not args.fix_only:
        print(f"\n{'='*60}")
        print(f"📊 RÉSULTAT GLOBAL [{rule_label}] : {total} violation(s)")
        if total == 0:
            print("🎉 FÉLICITATIONS — Aucune violation détectée !")
        else:
            # Compter par règle
            d1 = sum(1 for v in sum(all_violations.values(), []) if v.get("rule") == "D1")
            j7 = sum(1 for v in sum(all_violations.values(), []) if v.get("rule") == "J7")
            d3 = sum(1 for v in sum(all_violations.values(), []) if v.get("rule") == "D3")
            d4a = sum(1 for v in sum(all_violations.values(), []) if v.get("rule") == "D4a")
            d4b = sum(1 for v in sum(all_violations.values(), []) if v.get("rule") == "D4b")
            d5 = sum(1 for v in sum(all_violations.values(), []) if v.get("rule") == "D5")
            d5b = sum(1 for v in sum(all_violations.values(), []) if v.get("rule") == "D5b")
            d6 = sum(1 for v in sum(all_violations.values(), []) if v.get("rule") == "D6")
            d7 = sum(1 for v in sum(all_violations.values(), []) if v.get("rule") == "D7")
            counts = []
            if d1: counts.append(f"D1={d1}")
            if j7: counts.append(f"J7={j7}")
            if d3: counts.append(f"D3={d3}")
            if d4a: counts.append(f"D4a={d4a}")
            if d4b: counts.append(f"D4b={d4b}")
            if d5: counts.append(f"D5={d5}")
            if d5b: counts.append(f"D5b={d5b}")
            if d6: counts.append(f"D6={d6}")
            if d7: counts.append(f"D7={d7}")
            print(f"   Détail : {' | '.join(counts)}")
        print(f"{'='*60}\n")

    if args.json:
        output = {
            "rules": rule_label,
            "results": {
                proj: [
                    {
                        "file": v["file"],
                        "line": v["line"],
                        "rule": v.get("rule", "D1"),
                        "detail": v["detail"],
                    }
                    for v in violations
                ]
                for proj, violations in all_violations.items()
            },
            "total": total,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))

    return 1 if total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
