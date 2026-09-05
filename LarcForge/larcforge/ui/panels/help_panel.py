"""Panneau Aide : pas-à-pas intégré + référence auto-découverte des contrôles.

Deux contenus :
  1. L'onboarding (écrans, pas-à-pas) — statique.
  2. La **référence des contrôles** — chaque linter (`scripts/*.py`, docstring)
     et chaque reviewer (`.claude/skills/*-review.md`, corps complet), découverts
     automatiquement via ``taxonomy.discover_checks`` : aucune liste en dur.

Le guide complet (docs/GUIDE_DEBUTANT.md) s'ouvre dans le navigateur via le
bouton « Ouvrir le guide » (QDesktopServices — aucun widget Qt direct).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QVBoxLayout, QWidget

from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from phibuilder.widgets import M3Button, M3Card, M3ScrollArea
from phibuilder.widgets.button import ButtonVariant

from ...taxonomy import discover_checks
from .common import (BodyLabel, SectionTitle, TypeBadge, restyle_card,
                     restyle_label)

_GUIDE_PATH = Path(__file__).resolve().parents[3] / "docs" / "GUIDE_DEBUTANT.md"

_SECTIONS = [
    ("1. Le tableau de bord (Accueil)",
     "Les 4 grands chiffres (ouvertes, régressions, résolues, total), les "
     "alertes et les derniers runs. C'est l'état des lieux : rien à faire, "
     "tout se traite depuis le Registre."),
    ("2. Lancer une vérification",
     "Choisissez « Tout vérifier » (recommandé), cochez les projets, "
     "linters et tests, puis « Lancer ». Le bandeau indique si la "
     "résolution automatique des fiches est active."),
    ("3. Traiter les fiches (Registre)",
     "Cliquez sur une fiche pour le détail, « Résoudre avec une note » "
     "pour la fermer (la note est conservée), « Réouvrir » si le problème "
     "revient. Filtrez par statut, application, source ou recherche."),
    ("4. Adapter à votre école (Configuration)",
     "Marque : nom de l'école et thème. Connexions : une base par école, "
     "testée avant activation. Profils de vérification : vos contrôles "
     "pré-remplis automatiquement."),
    ("5. Problèmes courants",
     "« Base de données indisponible » → démarrez PostgreSQL puis "
     "« Réessayer ». Fenêtre qui ne s'ouvre pas → installez l'interface : "
     "pip install \"larcforge[gui]\"."),
]


class HelpPanel(QWidget):
    """Aide pas-à-pas + référence des contrôles (auto-découverte)."""

    def __init__(self, ctx):
        super().__init__()
        self._ctx = ctx
        # Conteneurs de restyle (réactivité thème : pattern _STYLE + _restyle).
        self._section_titles: list[SectionTitle] = []
        self._cards: list[M3Card] = []
        self._strong: list[BodyLabel] = []
        self._bodies: list[BodyLabel] = []
        self._badges: list[TypeBadge] = []
        self._build_ui()

    # ── Helpers de construction (labels suivis pour le restyle) ─────────────

    def _body(self, text: str) -> BodyLabel:
        lbl = BodyLabel(text)
        lbl.setWordWrap(True)
        self._bodies.append(lbl)
        return lbl

    def _strong_label(self, text: str) -> BodyLabel:
        """Titre de carte (plus affirmé que le corps — text_strong)."""
        lbl = BodyLabel(text)
        lbl.setWordWrap(True)
        restyle_label(lbl, "title_medium", theme_manager.palette.text_strong)
        self._strong.append(lbl)
        return lbl

    def _add_card(self, cl, title: str, rows: list, category: str | None = None):
        """Ajoute une carte au layout ``cl`` : badge (si catégorie) + titre + lignes."""
        card = M3Card(theme=theme_manager.phi_theme, variant=ds.CARD_FILLED)
        ccl = card.content_layout()
        ccl.setSpacing(ds.space_sm)
        if category:
            badge = TypeBadge(category)
            self._badges.append(badge)
            ccl.addWidget(badge, alignment=Qt.AlignLeft)
        ccl.addWidget(self._strong_label(title))
        for row in rows:
            if row:
                ccl.addWidget(self._body(row))
        cl.addWidget(card)
        self._cards.append(card)

    # ── Construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        phi = theme_manager.phi_theme
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ds.space_lg, ds.space_lg, ds.space_lg, ds.space_lg)
        lay.setSpacing(ds.space_sm)

        title = SectionTitle("Aide")
        self._section_titles.append(title)
        lay.addWidget(title)
        lay.addWidget(self._body(
            "Voici l'essentiel pour chaque écran, puis la référence exacte de "
            "chaque contrôle (linters et reviewers). Le guide complet s'ouvre "
            "avec le bouton ci-dessous."))

        scroll = M3ScrollArea(theme=phi)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(M3ScrollArea.NoFrame)
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(ds.space_xs, ds.space_xs, ds.space_xs, ds.space_xs)
        cl.setSpacing(ds.space_sm)

        # 1. Onboarding (pas-à-pas des écrans).
        for sec_title, body in _SECTIONS:
            self._add_card(cl, sec_title, [body])

        # 2. Référence des contrôles (auto-découverte).
        checks = discover_checks(self._ctx.root)
        linters = checks["linters"]
        reviewers = checks["reviewers"]

        ref_title = SectionTitle("Référence des contrôles")
        self._section_titles.append(ref_title)
        cl.addSpacing(ds.space_sm)
        cl.addWidget(ref_title)
        cl.addWidget(self._body(
            f"Découverte automatique : {len(linters)} linter(s) et "
            f"{len(reviewers)} reviewer(s). Ajouter un linter dans scripts/ ou "
            f"un reviewer dans .claude/skills/ le fait apparaître ici sans "
            f"modifier le moindre code."))

        if not linters and not reviewers:
            cl.addWidget(self._body(
                "Aucun contrôle découvert — vérifiez que le dossier racine "
                "pointe sur le monorepo (scripts/ et .claude/skills/)."))

        for m in linters:
            key = m.get("key", "?")
            rows = [m.get("description", ""), (m.get("doc") or "").strip()]
            self._add_card(cl, f"[{key}] {m.get('label', key)}", rows,
                           category=m.get("category"))

        for r in reviewers:
            rows = [r.get("description", ""), (r.get("body") or "").strip()]
            self._add_card(cl, r.get("name", "?"), rows)

        cl.addStretch()
        scroll.setWidget(content)
        lay.addWidget(scroll, 1)

        btn = M3Button("Ouvrir le guide complet", theme=phi,
                       variant=ButtonVariant.FILLED)
        btn.setIcon(md3_icon("info", color=theme_manager.palette.on_primary,
                             size=ds.icon_md))
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self._open_guide)
        lay.addWidget(btn, alignment=Qt.AlignLeft)

    # ── Actions ─────────────────────────────────────────────────────────────

    @safe_slot("HelpPanel.open_guide")
    def _open_guide(self):
        """Ouvre docs/GUIDE_DEBUTANT.md dans le navigateur par défaut."""
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(_GUIDE_PATH)))

    def reload(self):
        """Contenu découvert à la construction — rien à recharger en cours de run."""

    def _restyle(self):
        for t in self._section_titles:
            t.restyle()
        for card in self._cards:
            restyle_card(card)
        for lbl in self._strong:
            restyle_label(lbl, "title_medium", theme_manager.palette.text_strong)
        for lbl in self._bodies:
            lbl.restyle()
        for badge in self._badges:
            badge.restyle()
