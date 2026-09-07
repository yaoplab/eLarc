"""M3TreeWidget: Material Design 3 generic tree widget.

Features:
- Hiérarchie générique (fonction enfants/label/icône fournie par l'appelant)
- Recherche/filtre : filter_text() masque les branches non correspondantes, déplie les parents des correspondances
- Navigation clavier : flèches (natif QTreeWidget), Entrée (déplier/replier ou activer une feuille), Espace (activer), Echap (désélectionner)
- Focus visible : 2px outline
- Accessibilité : setData(Qt.AccessibleTextRole, ...) par item
- Touch target : 44px minimum par ligne (QSS)
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QKeyEvent
from PySide6.QtWidgets import QAbstractItemView, QSizePolicy, QTreeWidget, QTreeWidgetItem

from phibuilder.theme import Theme
from phibuilder.phi.scale import SpacingToken


class M3TreeWidget(QTreeWidget):
    """Arbre M3 générique avec recherche, clavier et accessibilité."""

    node_activated = Signal(object)

    def __init__(self, theme: Theme | None = None, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._children_fn: Callable[[object], list] = lambda n: []
        self._label_fn: Callable[[object], str] = lambda n: str(n)
        self._icon_fn: Optional[Callable[[object], QIcon]] = None

        self.setHeaderHidden(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAccessibleName("Arbre de types d'événements")
        self.setAccessibleDescription(
            "Flèches pour naviguer, Entrée pour déplier/replier, Espace pour confirmer le choix"
        )

        self._update_style()

    def _update_style(self):
        if self._theme is None:
            return
        c, s, t = self._theme.colors, self._theme.spacing, self._theme.typo
        padding_v = s.spacing(SpacingToken.XXS)
        padding_h = s.spacing(SpacingToken.XS)
        radius = s.spacing(SpacingToken.SM)
        row_height = 24  # dense — évite de scroller sur les catégories chargées (~25 nœuds)

        self.setStyleSheet(f"""
M3TreeWidget {{
    background-color: {c.surface};
    border: 1px solid {c.outline};
    border-radius: {radius}px;
    outline: none;
    font-family: '{t.family}';
    font-size: {t.body_medium.size}px;
    color: {c.on_surface};
}}
M3TreeWidget::item {{
    padding: {padding_v}px {padding_h}px;
    min-height: {row_height}px;
}}
M3TreeWidget::item:selected {{
    background-color: {c.primary_container};
    color: {c.on_primary_container};
}}
M3TreeWidget::item:hover {{
    background-color: {c.surface_container_highest};
}}
M3TreeWidget::item:focus {{
    outline: 2px solid {c.primary};
    outline-offset: 0px;
}}
""")

    def set_data(
        self,
        roots: list,
        children_fn: Callable[[object], list],
        label_fn: Callable[[object], str],
        icon_fn: Optional[Callable[[object], QIcon]] = None,
    ):
        """Charge la hiérarchie. `children_fn`/`label_fn` sont appliqués à chaque nœud."""
        self._children_fn = children_fn
        self._label_fn = label_fn
        self._icon_fn = icon_fn
        self.clear()
        for root in roots:
            self._add_node(root, self.invisibleRootItem())
        self.expandToDepth(0)

    def _add_node(self, node: object, parent_item: QTreeWidgetItem) -> QTreeWidgetItem:
        item = QTreeWidgetItem(parent_item)
        label = self._label_fn(node)
        item.setText(0, label)
        item.setData(0, Qt.UserRole, node)
        item.setData(0, Qt.AccessibleTextRole, label)
        if self._icon_fn:
            ic = self._icon_fn(node)
            if ic:
                item.setIcon(0, ic)
        for child in self._children_fn(node):
            self._add_node(child, item)
        return item

    def current_node(self) -> Optional[object]:
        item = self.currentItem()
        return item.data(0, Qt.UserRole) if item else None

    def select_node(self, node: object, path: list):
        """Déplie le chemin racine→nœud puis sélectionne le nœud."""
        self._select_recursive(self.invisibleRootItem(), path, 0, node)

    def _select_recursive(self, parent_item: QTreeWidgetItem, path: list, depth: int, target):
        for i in range(parent_item.childCount()):
            child_item = parent_item.child(i)
            child_node = child_item.data(0, Qt.UserRole)
            if depth < len(path) and child_node is path[depth]:
                child_item.setExpanded(True)
                if child_node is target:
                    self.setCurrentItem(child_item)
                    self.scrollToItem(child_item)
                    return True
                if self._select_recursive(child_item, path, depth + 1, target):
                    return True
        return False

    def filter_text(self, text: str):
        """Masque les branches ne contenant aucune correspondance ; déplie les parents des matches."""
        text = (text or "").strip().lower()
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            self._filter_recursive(root.child(i), text)

    def _filter_recursive(self, item: QTreeWidgetItem, text: str) -> bool:
        self_match = (not text) or (text in item.text(0).lower())
        child_match = False
        for i in range(item.childCount()):
            if self._filter_recursive(item.child(i), text):
                child_match = True
        visible = self_match or child_match
        item.setHidden(not visible)
        if text and child_match:
            item.setExpanded(True)
        return visible

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            item = self.currentItem()
            if item and item.childCount() > 0:
                item.setExpanded(not item.isExpanded())
            elif item:
                self.node_activated.emit(self.current_node())
            event.accept()
        elif event.key() == Qt.Key_Space:
            node = self.current_node()
            if node is not None:
                self.node_activated.emit(node)
            event.accept()
        elif event.key() == Qt.Key_Escape:
            self.clearSelection()
            event.accept()
        else:
            super().keyPressEvent(event)

    def refresh(self):
        """Restyle based on current theme."""
        self._update_style()
