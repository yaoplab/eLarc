#!/usr/bin/env python3
"""
Audit de réactivité au thème — LarcSuperviseur, LarcSecretaire, LarcProf.

Scanne tous les fichiers Python des répertoires views/ des 3 modules.
Pour chaque classe, détecte :
  - Les appels setStyleSheet() qui utilisent une palette dynamique
    (p.X, ds.p.X, theme_manager.palette.X)
  - La présence d'une connexion theme_changed (ds.theme_changed.connect)
  - La présence d'une méthode _restyle / restyle

Rapporte les classes non conformes sous forme de tableau.
"""

LINTER_META = {
    "key": "REACT",
    "label": "Réactivité thème",
    "category": "theme",
    "description": "Classes non conformes à la réactivité thème (_STYLE / _restyle)",
    "skill": "theme-reactivity",
}

import ast
import io
import json
import os
import re
import sys
from pathlib import Path

# Force UTF-8 (Windows cp1252 fix)
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Racine des projets
ROOT = Path(__file__).resolve().parents[1]
PROJETS = {
    "LarcSuperviseur": ROOT / "LarcSuperviseur" / "views",
    "LarcSecretaire":   ROOT / "LarcSecretaire" / "views",
    "LarcProf":         ROOT / "LarcProf" / "views",
}

# ──────────────────────────────────────────────
#  Patterns de détection
# ──────────────────────────────────────────────

# Expressions régulières pour repérer les appels palette-dépendants dans setStyleSheet
_PALETTE_PATTERNS = [
    re.compile(r'\bds\.p\.\w+'),
    re.compile(r'\bp\.\w+'),
    re.compile(r'\bp\[[''"]'),
    re.compile(r'\btheme_manager\.palette\.\w+'),
    re.compile(r'\btheme_manager\.phi_theme'),
    re.compile(r'\bds\.phi'),
    re.compile(r'\bds\.sp\('),
    re.compile(r'\bds\.space_\w+'),
    re.compile(r'\bds\.table_qss\b'),
    re.compile(r'\bds\.flat_input_qss\b'),
    re.compile(r'\bds\.button_height\b'),
]

# Patterns pour les tokens de spacing (SpacingToken)
_SPACING_PATTERNS = [
    re.compile(r'\bsp\(SpacingToken\.\w+\)'),
    re.compile(r'\bds\.sp\(SpacingToken\.\w+\)'),
]


def has_palette_dependency(line: str) -> bool:
    """Vérifie si une ligne utilise des couleurs/espacements dynamiques."""
    for pat in _PALETTE_PATTERNS + _SPACING_PATTERNS:
        if pat.search(line):
            return True
    return False


# ──────────────────────────────────────────────
#  Analyseur par fichier (via AST + regex)
# ──────────────────────────────────────────────


class ThemeReactivityAnalyzer(ast.NodeVisitor):
    """Analyse un fichier Python pour la réactivité au thème."""

    class _ClassInfo:
        def __init__(self, name: str, lineno: int):
            self.name = name
            self.lineno = lineno
            self.setstyle_lines: list[int] = []       # lignes setStyleSheet avec palette
            self.has_theme_connect: bool = False
            self.has_restyle_method: bool = False
            self.has_theme_changed_ref: bool = False  # toute référence à theme_changed

        @property
        def is_protected(self) -> bool:
            return self.has_theme_connect and (self.has_restyle_method or self.has_theme_changed_ref)

        @property
        def vulnerability_count(self) -> int:
            return len(self.setstyle_lines)

    def __init__(self, source: str, filepath: str):
        self.source = source
        self.lines = source.split('\n')
        self.filepath = filepath
        self.classes: dict[str, '_ClassInfo'] = {}
        self.current_class: str | None = None
        self.current_class_info: '_ClassInfo' | None = None

    def visit_ClassDef(self, node):
        old_class = self.current_class
        old_info = self.current_class_info

        # Empiler la classe
        self.current_class = node.name
        info = self._ClassInfo(node.name, node.lineno)
        self.classes[node.name] = info
        self.current_class_info = info

        # Analyser le corps de la classe
        self.generic_visit(node)

        # Restaurer
        self.current_class = old_class
        self.current_class_info = old_info

    def visit_FunctionDef(self, node):
        """Détecte _restyle / restyle et theme_changed dans les méthodes."""
        if self.current_class_info is None:
            return

        name = node.name
        if name in ('_restyle', 'restyle'):
            self.current_class_info.has_restyle_method = True

        # Vérifier le corps de la méthode pour theme_changed
        body_text = ast.get_source_segment(self.source, node) or ''
        if 'theme_changed' in body_text:
            self.current_class_info.has_theme_changed_ref = True

        # Analyser les appels dans le corps
        self.generic_visit(node)

    def visit_Assign(self, node):
        """Vérifie les connexions theme_changed hors méthodes (dans __init__)."""
        if self.current_class_info is None:
            return
        val = node.value
        if isinstance(val, ast.Call):
            # Vérifier si c'est un appel du type .connect()
            if isinstance(val.func, ast.Attribute) and val.func.attr == 'connect':
                # Vérifier si l'objet est theme_changed
                obj = val.func.value
                try:
                    obj_name = ast.unparse(obj) if hasattr(ast, 'unparse') else ''
                    if 'theme_changed' in obj_name:
                        self.current_class_info.has_theme_connect = True
                        self.current_class_info.has_theme_changed_ref = True
                except Exception:
                    pass

    def visit_Call(self, node):
        """Analyse les appels setStyleSheet."""
        if self.current_class_info is None:
            return

        # Vérifier si c'est un appel à .setStyleSheet()
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'setStyleSheet':
            # Récupérer le texte source de l'appel
            source_seg = ast.get_source_segment(self.source, node)
            if source_seg and has_palette_dependency(source_seg):
                self.current_class_info.setstyle_lines.append(node.lineno)
                return

        # Vérifier les appels connect() nommés theme_changed
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'connect':
            try:
                obj_name = ast.unparse(node.func.value) if hasattr(ast, 'unparse') else ''
                if 'theme_changed' in obj_name or 'theme_changed' in str(node.func.value.attr if isinstance(node.func.value, ast.Attribute) else ''):
                    self.current_class_info.has_theme_connect = True
                    self.current_class_info.has_theme_changed_ref = True
            except Exception:
                pass

        # Descendre dans les sous-arbres
        self.generic_visit(node)

    def visit_Expr(self, node):
        """Vérifie les appels en mode expression (ligne seule)."""
        if self.current_class_info is None:
            return
        # generic_visit traversera node.value (Call) → visit_Call sera dispatché
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        """Délègue à visit_FunctionDef pour les coroutines."""
        self.visit_FunctionDef(node)


def analyze_file(filepath: str) -> dict | None:
    """Analyse un fichier avec AST, retourne les classes non protégées."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
    except Exception as e:
        return {"error": str(e), "path": filepath}

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        return {"error": f"SyntaxError: {e}", "path": filepath}

    analyzer = ThemeReactivityAnalyzer(source, filepath)
    analyzer.visit(tree)

    # Collecter les classes vulnérables
    vulnerable = []
    protected = []
    for name, info in analyzer.classes.items():
        if not info.setstyle_lines:
            continue  # Pas de setStyleSheet palette-dépendant → OK
        if name.endswith('Mixin'):
            continue  # Mixin : pas un widget autonome — la classe finale (widget) est auditée via connect + _restyle
        if info.is_protected:
            protected.append({"name": name, "lines": info.setstyle_lines})
        else:
            vulnerable.append({
                "name": name,
                "lineno": info.lineno,
                "lines": info.setstyle_lines,
                "has_theme_connect": info.has_theme_connect,
                "has_restyle": info.has_restyle_method,
                "vulnerability_count": info.vulnerability_count,
            })

    return {
        "path": filepath,
        "vulnerable": vulnerable,
        "protected": protected,
        "total_vulnerable": len(vulnerable),
        "total_protected": len(protected),
    }


# ──────────────────────────────────────────────
#  Exploration récursive des répertoires
# ──────────────────────────────────────────────


def collect_py_files(root_dir: str) -> list[str]:
    """Collecte tous les fichiers .py d'un répertoire (récursif)."""
    files = []
    root = Path(root_dir)
    if not root.exists():
        return files
    for pyfile in root.rglob("*.py"):
        if '__pycache__' in str(pyfile):
            continue
        if pyfile.name == '__init__.py':
            continue
        files.append(str(pyfile))
    return sorted(files)


# ──────────────────────────────────────────────
#  Rapport
# ──────────────────────────────────────────────


COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"


def print_header(text: str):
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}{'=' * 70}{COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_CYAN}  {text}{COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_CYAN}{'=' * 70}{COLOR_RESET}\n")


def print_report(results: dict, module_name: str):
    vulnerable = results.get("vulnerable", [])
    protected = results.get("protected", [])
    path = results.get("path", "")

    rel_path = os.path.relpath(path, os.path.dirname(os.path.dirname(path)))
    short = os.path.basename(os.path.dirname(path)) + "/" + os.path.basename(path)

    if not vulnerable and not protected:
        return  # Pas de setStyleSheet palette-dépendant du tout

    if vulnerable:
        print(f"  {COLOR_RED}⚠  {short}{COLOR_RESET}")
        for cls in vulnerable:
            print(f"     {COLOR_BOLD}{cls['name']}{COLOR_RESET} (L{cls['lineno']}) — "
                  f"{cls['vulnerability_count']} setStyleSheet palette-dépendant(s)")
            for ln in cls['lines']:
                print(f"       L{ln}")
            missing = []
            if not cls['has_theme_connect']:
                missing.append("theme_changed.connect")
            if not cls['has_restyle']:
                missing.append("_restyle()")
            print(f"       {COLOR_YELLOW}→ Manque: {', '.join(missing)}{COLOR_RESET}")
        print()
    else:
        print(f"  {COLOR_GREEN}✔  {short}{COLOR_RESET}")
        if protected:
            names = ", ".join(p["name"] for p in protected)
            print(f"     {COLOR_GREEN}Protégé: {names}{COLOR_RESET}")
        print()


def print_summary(module_name: str, all_results: list[dict]):
    total_vuln = sum(r["total_vulnerable"] for r in all_results)
    total_prot = sum(r["total_protected"] for r in all_results)
    total_files_with_setstyle = len([r for r in all_results if r["total_vulnerable"] > 0 or r["total_protected"] > 0])
    vuln_files = [r for r in all_results if r["total_vulnerable"] > 0]

    if total_vuln == 0:
        print(f"  {COLOR_GREEN}✅ Aucune classe vulnérable — module {module_name} 100% conforme{COLOR_RESET}")
    else:
        print(f"  {COLOR_RED}{COLOR_BOLD}⚠  {total_vuln} classe(s) vulnérable(s) dans {len(vuln_files)} fichier(s){COLOR_RESET}")
        for vf in vuln_files:
            rel = os.path.basename(os.path.dirname(vf["path"])) + "/" + os.path.basename(vf["path"])
            for cls in vf["vulnerable"]:
                missing = []
                if not cls['has_theme_connect']:
                    missing.append("theme_changed")
                if not cls['has_restyle']:
                    missing.append("_restyle()")
                print(f"    {COLOR_RED}• {rel} → {cls['name']} (L{cls['lineno']}) "
                      f"— manque {', '.join(missing)}{COLOR_RESET}")
    print(f"  Classes protégées: {total_prot}")
    print(f"  Fichiers avec setStyleSheet palette: {total_files_with_setstyle}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Audit de reactivite au theme Larc")
    parser.add_argument("--dir", help="Repertoire a scanner (defaut: tous les projets)")
    parser.add_argument("--json", action="store_true", help="Sortie JSON")
    args = parser.parse_args()

    if args.dir:
        dirs = {"Cible": args.dir}
    else:
        dirs = {k: v for k, v in PROJETS.items() if os.path.isdir(v)}

    all_json = {}
    grand_total_vuln = 0
    grand_total_prot = 0

    for module_name, views_dir in dirs.items():
        if not os.path.isdir(views_dir):
            if not args.json:
                print(f"\n{COLOR_YELLOW}* Repertoire introuvable: {views_dir}{COLOR_RESET}\n")
            continue

        py_files = collect_py_files(views_dir)
        if not py_files:
            if not args.json:
                print(f"\n{COLOR_YELLOW}* Aucun fichier .py dans {views_dir}{COLOR_RESET}\n")
            continue

        if not args.json:
            print_header(f"{module_name} ({len(py_files)} fichiers)")

        all_results = []
        for fp in py_files:
            result = analyze_file(fp)
            if result:
                all_results.append(result)
                if not args.json:
                    print_report(result, module_name)

        module_vuln = sum(r["total_vulnerable"] for r in all_results)
        module_prot = sum(r["total_protected"] for r in all_results)
        grand_total_vuln += module_vuln
        grand_total_prot += module_prot

        all_json[module_name] = {
            "files": len(py_files),
            "total_vulnerable": module_vuln,
            "total_protected": module_prot,
            "results": all_results,
        }

        if not args.json:
            print_summary(module_name, all_results)
            print()

    if args.json:
        print(json.dumps({
            "grand_total_vulnerable": grand_total_vuln,
            "grand_total_protected": grand_total_prot,
            "modules": all_json,
        }, ensure_ascii=False, indent=2))
        return 0 if grand_total_vuln == 0 else 1

    # Grand total
    print_header("RÉSUMÉ GLOBAL")
    print(f"  {COLOR_BOLD}Total classes vulnérables : {grand_total_vuln}{COLOR_RESET}")
    print(f"  {COLOR_BOLD}Total classes protégées   : {grand_total_prot}{COLOR_RESET}")
    if grand_total_vuln == 0:
        print(f"\n  {COLOR_GREEN}{COLOR_BOLD}🏆 Tous les modules sont 100% conformes !{COLOR_RESET}")
    else:
        print(f"\n  {COLOR_YELLOW}Corrigez les classes ci-dessus pour atteindre 100% de conformité.{COLOR_RESET}")

    print()


if __name__ == "__main__":
    main()
