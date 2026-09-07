"""EventTypeSelectorWidget — sélecteur hiérarchique partagé (création ET édition d'événement).

Composant unique consommé par EventGeneratorDialog (création) et par les flux d'édition
(main_events.py, EventEditDialog) — évite de dupliquer la logique arbre + recherche +
confirmation à chaque endroit où un type d'événement doit être choisi.
"""
from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from larccommon.design_system import ds
from larccommon.event_type_service import EventTypeNode, event_type_service
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from phibuilder.widgets import M3Button, M3Card, M3ChipBar, M3Label, M3TextField, M3TreeWidget
from phibuilder.widgets.button import ButtonVariant
from phibuilder.widgets.card import CardVariant

# Ordre d'affichage des chips de catégorie + couleur d'identité stable (indépendante du
# thème actif) — même principe que event_helpers.event_color(), volontairement hors du
# système ds.*/palette réactif au thème : une catégorie doit rester reconnaissable quel
# que soit le thème choisi par l'utilisateur.
_CATEGORY_ORDER = ["absence", "retard", "sortie", "evenement"]
_CATEGORY_COLORS = {
    "absence": "#e67e22",
    "retard": "#c0392b",
    "sortie": "#1976d2",
    "evenement": "#8e44ad",
}


def category_color(category: str) -> str:
    """Couleur d'identité stable d'une catégorie de type d'événement."""
    return _CATEGORY_COLORS.get(category, "#616161")


def _ordered_roots(hierarchies: Dict[str, EventTypeNode]) -> list:
    def sort_key(root: EventTypeNode):
        try:
            return _CATEGORY_ORDER.index(root.category)
        except ValueError:
            return len(_CATEGORY_ORDER)
    return sorted(hierarchies.values(), key=sort_key)


def _node_matches(node: EventTypeNode, text: str) -> bool:
    """Recherche récursive insensible à la casse sur le libellé (texte déjà en minuscules)."""
    if text in node.label.lower():
        return True
    return any(_node_matches(c, text) for c in node.children)


class EventTypeSelectorWidget(QWidget):
    """Arbre de types d'événements + recherche + bouton de confirmation + badge résumé.

    L'arbre n'affiche que la catégorie active (sélectionnée via une barre de chips
    colorés) au lieu des ~105 nœuds toutes catégories confondues — évite le scroll sur
    les grosses catégories. La recherche élargit automatiquement aux autres catégories
    si le texte tapé n'existe pas dans la catégorie active.
    """

    type_confirmed = Signal(object)  # EventTypeNode

    def __init__(self, hierarchies: Dict[str, EventTypeNode], parent=None):
        super().__init__(parent)
        self._hierarchies = hierarchies
        self._roots = _ordered_roots(hierarchies)
        self._active_root: EventTypeNode | None = self._roots[0] if self._roots else None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.space_sm)

        self._chip_bar = M3ChipBar(
            [root.label for root in self._roots],
            theme=theme_manager.phi_theme,
            colors=[category_color(root.category) for root in self._roots],
        )
        self._chip_bar.current_changed.connect(self._on_category_changed)
        layout.addWidget(self._chip_bar)

        self._search = M3TextField(placeholder=_("event.tree_search_placeholder"))
        self._search.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search)

        self._tree = M3TreeWidget(theme=theme_manager.phi_theme)
        self._tree.setMinimumHeight(ds.space_xxl * 3)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._tree.node_activated.connect(self._on_node_activated)
        self._tree.set_data(
            [self._active_root] if self._active_root else [],
            children_fn=lambda n: n.children,
            label_fn=lambda n: n.label,
        )
        layout.addWidget(self._tree, 1)

        self._badge = M3Card(variant=CardVariant.FILLED, parent=self)
        badge_layout = self._badge.content_layout()
        badge_layout.setContentsMargins(ds.space_md, ds.space_xs, ds.space_md, ds.space_xs)
        self._badge_text = M3Label("", style="body_medium")
        self._badge_text.setWordWrap(True)
        badge_layout.addWidget(self._badge_text)
        self._badge.hide()
        layout.addWidget(self._badge)

        self._confirm_btn = M3Button(_("event.confirm_choice"), variant=ButtonVariant.FILLED)
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._on_confirm_clicked)
        layout.addWidget(self._confirm_btn)

    @staticmethod
    def is_leaf(node: EventTypeNode) -> bool:
        """Un nœud est une feuille (y compris 'Autre') s'il n'a aucun enfant."""
        return len(node.children) == 0

    @safe_slot("EventTypeSelectorWidget._on_search_changed")
    def _on_search_changed(self, text: str):
        stripped = text.strip().lower()
        if stripped and self._active_root and not _node_matches(self._active_root, stripped):
            for i, root in enumerate(self._roots):
                if root is not self._active_root and _node_matches(root, stripped):
                    self._chip_bar.set_current(i)  # déclenche _on_category_changed, qui
                    return  # réapplique déjà le filtre sur la nouvelle catégorie
        self._tree.filter_text(text)

    @safe_slot("EventTypeSelectorWidget._on_category_changed")
    def _on_category_changed(self, index: int):
        self._active_root = self._roots[index]
        self._tree.set_data(
            [self._active_root],
            children_fn=lambda n: n.children,
            label_fn=lambda n: n.label,
        )
        self._tree.filter_text(self._search.text())

    @safe_slot("EventTypeSelectorWidget._on_selection_changed")
    def _on_selection_changed(self):
        node = self._tree.current_node()
        self._confirm_btn.setEnabled(node is not None)
        if node is not None:
            self._badge_text.setText(event_type_service.get_path(node))
            self._badge.show()
        else:
            self._badge.hide()

    @safe_slot("EventTypeSelectorWidget._on_node_activated")
    def _on_node_activated(self, node: EventTypeNode):
        """Espace/Entrée sur une feuille = raccourci clavier équivalent au bouton Confirmer."""
        if node is not None and self.is_leaf(node):
            self.type_confirmed.emit(node)

    @safe_slot("EventTypeSelectorWidget._on_confirm_clicked")
    def _on_confirm_clicked(self):
        node = self._tree.current_node()
        if node is not None:
            self.type_confirmed.emit(node)

    def preselect(self, node: EventTypeNode):
        """Déplie/sélectionne un nœud existant (rouverture en édition)."""
        # Reconstruit le chemin racine→nœud à partir de la hiérarchie déjà chargée par ce
        # widget (self._roots), plutôt que via event_type_service.get_by_id() : ce dernier
        # dépend du cache DB du singleton (vide tant qu'aucune connexion n'a appelé
        # load_hierarchy()), et même peuplé, renverrait des instances EventTypeNode
        # distinctes de celles déjà attachées aux items de l'arbre — M3TreeWidget.select_node
        # compare par identité d'objet (`is`), pas par égalité de valeur.
        chain = self._find_path(self._roots, node)
        if not chain:
            return
        root_index = self._roots.index(chain[0])
        if root_index != self._chip_bar.current_index():
            self._chip_bar.set_current(root_index)  # rescope l'arbre sur la bonne catégorie
        self._tree.select_node(chain[-1], chain)
        self._on_selection_changed()

    def _find_path(self, nodes: list, target: EventTypeNode) -> list:
        """Cherche `target` (par id) dans la hiérarchie et retourne le chemin racine→nœud,
        composé des objets EventTypeNode réellement attachés aux items de l'arbre."""
        for n in nodes:
            if n.id == target.id:
                return [n]
            found = self._find_path(n.children, target)
            if found:
                return [n] + found
        return []
