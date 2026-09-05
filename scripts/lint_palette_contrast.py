#!/usr/bin/env python3
"""Linter : contraste de la palette — texte vs fond (skill color-rules, règle D8).

Vérifie que les variables de TEXTE (text_strong / text_soft / text_disabled)
sont correctement contrastées vis-à-vis des variables de FOND
(surface / background / surface_variant), dans ``larccommon/theme.py`` :

  - thème clair  : texte plus FONCÉ que le fond (luminance texte < fond)
  - thème sombre : texte plus CLAIR que le fond  (luminance texte > fond)
  - ratio WCAG minimum par paire (AA 4.5:1 pour le texte normal, 3:1 seuil dur)

Lecture par AST (comme larcforge/taxonomy.py) — aucun import, donc aucun effet
de bord PySide6/phibuilder, le scan reste valide même si theme.py ne s'importe pas.

Usage:
  python scripts/lint_palette_contrast.py            # Rapport texte
  python scripts/lint_palette_contrast.py --json     # Sortie JSON (liste)
  python scripts/lint_palette_contrast.py --fix-only # Liste compacte
"""

LINTER_META = {
    "key": "CTR",
    "label": "Contraste palette",
    "category": "theme",
    "description": "Contraste texte/fond insuffisant ou inversé dans la palette (background vs text)",
    "skill": "color-rules",
}

import argparse
import ast
import io
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME_PATH = ROOT / "LarcCommon" / "larccommon" / "theme.py"

# (texte, fond, seuil AA, seuil dur P0, vérifier la direction)
# text_disabled est exempté WCAG : pas de P0, pas de direction (gris « muet » voulu).
PAIRS = [
    ("text_strong", "surface", 4.5, 3.0, True),
    ("text_strong", "background", 4.5, 3.0, True),
    ("text_soft", "surface", 4.5, 3.0, True),
    ("text_soft", "background", 4.5, 3.0, True),
    ("text_soft", "surface_variant", 4.5, 3.0, True),
    ("text_disabled", "surface", 2.0, 0.0, False),
]


# ── Lecture AST ──────────────────────────────────────────────────────────────


def _palette_kwargs(call_node) -> dict[str, str]:
    """Extrait les kwargs d'un appel Palette(key="...") en dict hex."""
    out: dict[str, str] = {}
    if isinstance(call_node, ast.Call):
        for kw in call_node.keywords:
            if kw.arg and isinstance(kw.value, ast.Constant) \
                    and isinstance(kw.value.value, str):
                out[kw.arg] = kw.value.value
    return out


def read_themes() -> tuple[dict[str, bool], dict[str, dict[str, str]]]:
    """(is_dark par thème, palette hex par thème) lus par AST, sans import.

    THEMES_CONFIG = [("blue", "Bleu", "#1F4494", False), ...] (literal)
    _THEME_PALETTES = {"blue": Palette(...), ...}               (appels)
    """
    try:
        source = THEME_PATH.read_text(encoding="utf-8")
    except OSError:
        return {}, {}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {}, {}

    is_dark: dict[str, bool] = {}
    palettes: dict[str, dict[str, str]] = {}

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "THEMES_CONFIG":
                try:
                    config = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    config = []
                for entry in config:
                    if isinstance(entry, (tuple, list)) and len(entry) >= 4:
                        is_dark[str(entry[0])] = bool(entry[3])
            elif target.id == "_THEME_PALETTES":
                if isinstance(node.value, ast.Dict):
                    for key, value in zip(node.value.keys, node.value.values):
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            palettes[key.value] = _palette_kwargs(value)

    return is_dark, palettes


# ── Contraste WCAG ───────────────────────────────────────────────────────────


def _linear(channel: int) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    h = hex_color.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) < 6 or not all(c in "0123456789abcdefABCDEF" for c in h):
        return 0.0
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast_ratio(fg: str, bg: str) -> float:
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


# ── Scan ─────────────────────────────────────────────────────────────────────


def scan_palette() -> list[dict]:
    is_dark, palettes = read_themes()
    violations: list[dict] = []

    if not palettes:
        violations.append({
            "rule": "D8",
            "severity": "P0",
            "message": f"Impossible de lire _THEME_PALETTES dans {THEME_PATH.name}",
            "file": str(THEME_PATH),
        })
        return violations

    for theme, pal in palettes.items():
        dark = is_dark.get(theme, False)
        decl = "sombre" if dark else "clair"

        for text_token, bg_token, threshold, hard, check_dir in PAIRS:
            hex_text = pal.get(text_token)
            hex_bg = pal.get(bg_token)
            if not hex_text or not hex_bg:
                continue  # token absent de la palette — non audité ici

            ratio = contrast_ratio(hex_text, hex_bg)
            l_text = relative_luminance(hex_text)
            l_bg = relative_luminance(hex_bg)

            # Direction : le texte doit être « beaucoup plus foncé » (clair)
            # ou « beaucoup plus clair » (sombre) que le fond.
            inverted = (l_text >= l_bg) if not dark else (l_text <= l_bg)

            if check_dir and inverted:
                want = "plus clair" if dark else "plus foncé"
                violations.append({
                    "rule": "D8",
                    "severity": "P0",
                    "message": (
                        f"{theme} ({decl}) : {text_token} {hex_text} n'est pas "
                        f"{want} que {bg_token} {hex_bg} — contraste inversé"
                    ),
                    "file": str(THEME_PATH),
                })
            elif hard and ratio < hard:
                violations.append({
                    "rule": "D8",
                    "severity": "P0",
                    "message": (
                        f"{theme} ({decl}) : {text_token} {hex_text} sur "
                        f"{bg_token} {hex_bg} → {ratio:.2f}:1 (< {hard:g}:1)"
                    ),
                    "file": str(THEME_PATH),
                })
            elif ratio < threshold:
                violations.append({
                    "rule": "D8",
                    "severity": "P1",
                    "message": (
                        f"{theme} ({decl}) : {text_token} {hex_text} sur "
                        f"{bg_token} {hex_bg} → {ratio:.2f}:1 "
                        f"(seuil {threshold:g}:1)"
                    ),
                    "file": str(THEME_PATH),
                })

    return violations


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Linter contraste palette (D8)")
    parser.add_argument("--dir", default="", help="Ignoré — audite la palette centrale")
    parser.add_argument("--json", action="store_true", help="Sortie JSON (liste)")
    parser.add_argument("--fix-only", action="store_true", help="Liste compacte")
    parser.add_argument("--rule", default="D8", help="Réservé (seule D8 existe)")
    args = parser.parse_args()

    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

    violations = scan_palette()
    p0 = sum(1 for v in violations if v.get("severity") == "P0")
    p1 = sum(1 for v in violations if v.get("severity") == "P1")

    if args.json:
        print(json.dumps(violations, indent=2, ensure_ascii=False))
        return 1 if p0 > 0 else 0

    if args.fix_only:
        for v in violations:
            print(f"  [{v['severity']}] {v['message']}")
        return 1 if p0 > 0 else 0

    print(f"🔍 Contraste palette ({THEME_PATH.name})")
    if not violations:
        print("  ✅ Toutes les paires texte/fond sont correctement contrastées.")
    else:
        for v in violations:
            mark = "❌" if v["severity"] == "P0" else "⚠️"
            print(f"  {mark} [{v['severity']}] {v['message']}")

    print(f"\n📊 Résultat : {len(violations)} écart(s) — {p0} P0 (bloquant), {p1} P1 (sous AA)")
    if p0 == 0 and p1 == 0:
        print("🎉 FÉLICITATIONS — Palette conforme.")
    return 1 if p0 > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
