"""Taxonomie des types d'erreur LarcForge — auto-découverte des linters/skills.

Principe « organique » : ajouter un linter = déposer un script dans scripts/
qui s'auto-déclare via une constante module-level ``LINTER_META``. Cette
constante est lue par **AST** (``ast.literal_eval``), donc sans import — aucun
effet de bord, pas de dépendance à PyInstaller/PySide6 au scan.

La catégorie d'une issue est dérivée de sa ``source`` **au rendu** : aucune
migration DB, la taxonomie s'applique aussi aux issues historiques et se met à
jour dès qu'un nouveau linter est déposé.
"""

from __future__ import annotations

import ast
import re
import warnings
from dataclasses import dataclass
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Catégories v1 — clé → (label, icône MD3, description, skill par défaut).
# L'icône est un nom valide de larccommon.icons._PATHS. Les couleurs, elles,
# vivent dans larccommon.theme (ERROR_CATEGORY_COLORS) — seul endroit où des
# hex sont autorisés (zéro hardcoding ailleurs).
# ─────────────────────────────────────────────────────────────────────────────
CATEGORIES: dict[str, dict] = {
    "theme": {
        "label": "Thème & Design",
        "icon": "contrast",
        "description": "Couleurs, QSS et réactivité au thème — tokens ds.* obligatoires",
        "skill": "theme-reactivity",
    },
    "ui": {
        "label": "Interface & UX",
        "icon": "view_module",
        "description": "Finitions visuelles : icônes, tooltips, gaps, alignements",
        "skill": "ui-quality",
    },
    "qt": {
        "label": "PySide6 / Qt",
        "icon": "bolt",
        "description": "Anti-patterns Qt : @safe_slot, slots, héritage",
        "skill": "pyside6-wrapper",
    },
    "checklist": {
        "label": "Pré-soumission",
        "icon": "check",
        "description": "Check-list de pré-soumission (patterns interdits)",
        "skill": "preflight",
    },
    "filesize": {
        "label": "Taille / refactoring",
        "icon": "description",
        "description": "Fichiers trop volumineux — refactorisation requise",
        "skill": "pyside6-wrapper",
    },
    "data": {
        "label": "Base de données",
        "icon": "cloud",
        "description": "Connexions, requêtes et singleton DB",
        "skill": "database-operations",
    },
    "auth": {
        "label": "Authentification",
        "icon": "lock",
        "description": "Flux d'authentification (Intranet, OAuth2, PIN)",
        "skill": "auth-intranet",
    },
    "tests": {
        "label": "Tests & couverture",
        "icon": "check_circle",
        "description": "Couverture et résultats des tests",
        "skill": "larc-testing",
    },
    "runtime": {
        "label": "Erreurs d'application",
        "icon": "error",
        "description": "Erreurs remontées par les applications (error_log)",
        "skill": "error-reporting",
    },
    "build": {
        "label": "Build / packaging",
        "icon": "work",
        "description": "Compilation et packaging (PyInstaller, setup)",
        "skill": None,
    },
}

DEFAULT_CATEGORY = "ui"

# Sources non-linter → catégorie fixe (source = clé exacte de l'issue).
SOURCE_CATEGORY: dict[str, str] = {
    "pytest": "tests",
    "errorlog": "runtime",
    "larcforge:build": "build",
}

# Clés linter → catégorie. Fallback statique (les 10 linters v1), enrichi par
# discover_linters() dès qu'un script avec LINTER_META est découvert.
_KEY_CATEGORY: dict[str, str] = {
    "R": "theme",
    "D": "theme",
    "REACT": "theme",
    "V": "ui",
    "S": "qt",
    "C": "checklist",
    "FS": "filesize",
    "DB": "data",
    "AUTH": "auth",
    "COV": "tests",
}


# ─────────────────────────────────────────────────────────────────────────────
# Découverte
# ─────────────────────────────────────────────────────────────────────────────


def _parse_linter(path: Path) -> tuple[dict | None, str]:
    """Lit LINTER_META + la docstring module d'un script par AST (sans import).

    Retourne (meta, doc) — ``meta`` est None si LINTER_META est absent/invalide ;
    ``doc`` contient la docstring du module (les vérifications exactes décrites
    par l'auteur du linter), chaîne vide si absente.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None, ""
    # Les scripts scannés peuvent porter des séquences `\L` (usage Windows) dans
    # leurs docstrings : on neutralise le SyntaxWarning pendant le scan — sans
    # conséquence, seul le dict LINTER_META et la docstring nous intéressent.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None, ""
    doc = (ast.get_docstring(tree, clean=True) or "").strip()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "LINTER_META":
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    return None, doc
                if isinstance(value, dict) and {"key", "label", "category"} <= value.keys():
                    return value, doc
                return None, doc
    return None, doc


def discover_linters(scripts_dir: Path | str) -> list[dict]:
    """Linters auto-découverts via LINTER_META (triés par clé).

    Un script sans LINTER_META est ignoré (la note console est laissée à
    l'appelant). Met à jour la table clé → catégorie utilisée par category_for().
    """
    scripts_dir = Path(scripts_dir)
    found: list[dict] = []
    if not scripts_dir.is_dir():
        return found
    for path in sorted(scripts_dir.glob("*.py")):
        meta, _doc = _parse_linter(path)
        if meta is None:
            continue
        meta["script"] = path.name
        found.append(meta)
        _KEY_CATEGORY[meta["key"]] = meta["category"]
    found.sort(key=lambda m: m["key"])
    return found


def linter_checks(scripts_dir: Path | str) -> list[dict]:
    """Linters enrichis de leur docstring — la description EXACTE des contrôles.

    Même auto-découverte que discover_linters(), mais chaque entrée porte en plus
    ``doc`` (docstring du module) et ``script``. C'est la matière première de
    l'espace de référence (CLI ``help``, UI Aide, doc Markdown).
    """
    scripts_dir = Path(scripts_dir)
    found: list[dict] = []
    if not scripts_dir.is_dir():
        return found
    for path in sorted(scripts_dir.glob("*.py")):
        meta, doc = _parse_linter(path)
        if meta is None:
            continue
        meta["script"] = path.name
        meta["doc"] = doc
        found.append(meta)
    found.sort(key=lambda m: m["key"])
    return found


_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, str]:
    m = _FM_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


def discover_skills(root: Path | str) -> dict[str, str]:
    """Lookup slug → description des skills (frontmatter .claude/skills/*.md).

    Les fichiers *-review.md sont des revues, pas des skills résolvables par
    slug — exclus. Retourne {name: description}.
    """
    skills_dir = Path(root) / ".claude" / "skills"
    lookup: dict[str, str] = {}
    if not skills_dir.is_dir():
        return lookup
    for path in sorted(skills_dir.glob("*.md")):
        if path.name.endswith("-review.md"):
            continue
        fm = _parse_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
        name = fm.get("name") or path.stem
        desc = fm.get("description") or fm.get("trigger") or ""
        if name and desc:
            lookup[name] = desc
    return lookup


def discover_reviewers(root: Path | str) -> list[dict]:
    """Reviewers auto-découverts — les 9 fichiers .claude/skills/*-review.md.

    Chaque entrée porte le frontmatter (name/description/category/trigger) ET le
    corps Markdown complet (procédure + check-list = les vérifications exactes).
    Triés par nom.
    """
    reviews_dir = Path(root) / ".claude" / "skills"
    found: list[dict] = []
    if not reviews_dir.is_dir():
        return found
    for path in sorted(reviews_dir.glob("*-review.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        fm = _parse_frontmatter(text)
        body = _FM_RE.sub("", text, count=1).strip()
        found.append({
            "name": fm.get("name") or path.stem,
            "description": fm.get("description") or "",
            "category": fm.get("category") or "",
            "trigger": fm.get("trigger") or "",
            "body": body,
        })
    found.sort(key=lambda r: r["name"])
    return found


def discover_checks(root: Path | str) -> dict[str, list[dict]]:
    """Référence complète des contrôles : linters (doc) + reviewers (corps).

    Point d'entrée unique de l'espace de référence — consommé par la CLI
    ``larcforge help``, le panneau UI Aide et la doc Markdown générée.
    """
    root = Path(root)
    return {
        "linters": linter_checks(root / "scripts"),
        "reviewers": discover_reviewers(root),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Résolution
# ─────────────────────────────────────────────────────────────────────────────


def category_for(source: str | None, rule: str | None = None) -> str:
    """Catégorie d'une issue à partir de sa source (rule réservé au raffinement).

    ``linter:<clé>`` → catégorie du linter découvert ; ``pytest``, ``errorlog``,
    ``larcforge:build`` → catégories fixes ; sinon ``ui``.
    """
    if source and source.startswith("linter:"):
        key = source.split(":", 1)[1]
        return _KEY_CATEGORY.get(key, DEFAULT_CATEGORY)
    return SOURCE_CATEGORY.get(source or "", DEFAULT_CATEGORY)


def category_info(cat: str) -> dict:
    """{label, icon, description, skill} d'une catégorie (défaut ui)."""
    return CATEGORIES.get(cat, CATEGORIES[DEFAULT_CATEGORY])


@dataclass(frozen=True)
class ErrorType:
    """Type d'erreur résolu (catégorie + métadonnées) pour une source donnée."""

    key: str                 # clé de catégorie ("theme", …)
    label: str
    icon: str
    description: str
    skill: str | None        # slug de skill
    skill_label: str | None  # description résolue de la skill (si connue)


def resolve_type(source: str | None, rule: str | None = None,
                 skills: dict[str, str] | None = None) -> ErrorType:
    """Résout une source en ErrorType. ``skills`` = résultat de discover_skills()."""
    cat = category_for(source, rule)
    info = category_info(cat)
    skill = info.get("skill")
    skill_label = None
    if skill and skills:
        skill_label = skills.get(skill)
    return ErrorType(
        key=cat,
        label=info["label"],
        icon=info["icon"],
        description=info["description"],
        skill=skill,
        skill_label=skill_label,
    )


def type_colors(cat: str) -> tuple[str, str, str]:
    """(badge, conteneur, texte) d'une catégorie — import paresseux de la palette.

    Résolu à l'appel : un badge relu au paint/restyle suit le thème actif.
    """
    from larccommon.theme import error_category_color
    return error_category_color(cat)


def all_categories() -> list[str]:
    """Clés de catégories, ordonnées (pour la CLI ``types`` et l'Accueil)."""
    return list(CATEGORIES.keys())
