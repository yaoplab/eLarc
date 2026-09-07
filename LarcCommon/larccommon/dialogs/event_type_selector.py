"""EventTypeSelectorWidget — sélecteur hiérarchique partagé (création ET édition d'événement).

Composant unique consommé par EventGeneratorDialog (création) et par les flux d'édition
(main_events.py, EventEditDialog) — évite de dupliquer la logique arbre + recherche +
confirmation à chaque endroit où un type d'événement doit être choisi.
"""
from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from larccommon.design_system import ds
from larccommon.event_type_service import EventTypeNode, event_type_service
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from phibuilder.widgets import M3Button, M3Card, M3Label, M3TextField, M3TreeWidget
from phibuilder.widgets.button import ButtonVariant
from phibuilder.widgets.card import CardVariant


class EventTypeSelectorWidget(QWidget):
    """Arbre de types d'événements + recherche + bouton de confirmation + badge résumé."""

    type_confirmed = Signal(object)  # EventTypeNode

    def __init__(self, hierarchies: Dict[str, EventTypeNode], parent=None):
        super().__init__(parent)
        self._hierarchies = hierarchies
        self._roots = list(hierarchies.values())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.space_sm)

        self._search = M3TextField(placeholder=_("event.tree_search_placeholder"))
        self._search.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search)

        self._tree = M3TreeWidget(theme=theme_manager.phi_theme)
        self._tree.setMinimumHeight(ds.space_xxl * 3)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._tree.node_activated.connect(self._on_node_activated)
        self._tree.set_data(
            self._roots,
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
        self._tree.filter_text(text)

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
        self._tree.select_node(node, chain)
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
