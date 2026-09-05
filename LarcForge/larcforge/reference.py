"""Rendu de l'espace de référence des contrôles (linters + reviewers).

S'appuie sur l'auto-découverte de ``taxonomy.discover_checks()`` — aucune liste
codée en dur : un linter déposé dans ``scripts/`` (avec ``LINTER_META`` + sa
docstring) ou un reviewer déposé dans ``.claude/skills/*-review.md`` apparaît
automatiquement dans la référence.
"""

from __future__ import annotations

import re

_HEADER_RE = re.compile(r"^(#{1,6})\s")


def _fence(text: str, lang: str = "") -> str:
    """Entoure un bloc dans un garde-fou triple-backtick si absent."""
    text = text.strip()
    if not text:
        return ""
    return f"```{lang}\n{text}\n```"


def _demote_headers(text: str, levels: int = 2) -> str:
    """Rétrograde les titres Markdown (``##`` → ``####``…) d'un corps imbriqué.

    Les reviewers contiennent leurs propres ``## Procédure``/``### Sous-section`` :
    sans rétrogradation, ils casseraient le plan du document (niveau égal à
    ``## Linters``/``## Reviewers``). On les abaisse de ``levels`` crans pour les
    rattacher au ``### <reviewer>`` qui les contient.
    """
    out: list[str] = []
    for line in text.splitlines():
        m = _HEADER_RE.match(line)
        if m:
            hashes = m.group(1)
            n = min(len(hashes) + levels, 6)
            line = "#" * n + line[len(hashes):]
        out.append(line)
    return "\n".join(out)


def render_markdown(checks: dict, title: str = "Référence des contrôles") -> str:
    """Génère la doc Markdown de référence à partir de discover_checks().

    ``checks`` : dict {"linters": [...], "reviewers": [...]} — chaque linter
    porte ``key/label/category/description/skill/script/doc`` ; chaque reviewer
    porte ``name/description/category/trigger/body``.
    """
    linters: list[dict] = checks.get("linters", [])
    reviewers: list[dict] = checks.get("reviewers", [])

    lines: list[str] = [
        f"# {title}",
        "",
        "> Généré automatiquement par `python -m larcforge docs` à partir de",
        "> l'auto-découverte des linters (`scripts/*.py`) et des reviewers",
        "> (`.claude/skills/*-review.md`). **Ne pas éditer à la main** — toute",
        "> modification doit se faire dans le script/skill source puis régénérer.",
        "",
    ]

    lines.append(f"## Linters ({len(linters)})")
    lines.append("")
    if not linters:
        lines.append("_Aucun linter découvert._")
    for m in linters:
        head = f"[{m.get('key', '?')}] {m.get('label', m.get('key', '?'))}"
        lines.append(f"### {head}")
        lines.append("")
        meta = [f"- **Script** : `{m.get('script', '?')}`",
                f"- **Catégorie** : `{m.get('category', '?')}`"]
        if m.get("skill"):
            meta.append(f"- **Skill** : `{m['skill']}`")
        meta.append(f"- **Description** : {m.get('description', '')}")
        lines.extend(meta)
        doc = (m.get("doc") or "").strip()
        if doc:
            lines.append("")
            lines.append("**Vérifications exactes** (docstring du linter) :")
            lines.append("")
            lines.extend(_fence(doc, "text").splitlines())
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append(f"## Reviewers ({len(reviewers)})")
    lines.append("")
    if not reviewers:
        lines.append("_Aucun reviewer découvert._")
    for r in reviewers:
        lines.append(f"### {r.get('name', '?')}")
        lines.append("")
        meta = [f"- **Catégorie** : `{r.get('category', '?')}`"]
        if r.get("trigger"):
            meta.append(f"- **Déclencheur** : {r['trigger']}")
        meta.append(f"- **Description** : {r.get('description', '')}")
        lines.extend(meta)
        body = (r.get("body") or "").strip()
        if body:
            lines.append("")
            lines.append("**Procédure et vérifications exactes** :")
            lines.append("")
            lines.extend(_demote_headers(body).splitlines())
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
