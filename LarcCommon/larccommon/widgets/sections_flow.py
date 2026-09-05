"""SectionsFlow — flux responsive de cartes de section (skill input-ergonomics).

Les cartes (sections, tableaux…) se répartissent en colonnes égales :
N = max(1, largeur // (largeur_min + espacement)). Sur un écran large,
elles remontent sur la même ligne ; sur un écran étroit, elles s'empilent.
Largeurs strictement égales calculées par la section (IE5) — les sizeHint
des cartes diffèrent, sans largeur fixe les colonnes seraient inégales.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QGridLayout, QWidget, QSizePolicy, QLabel, QVBoxLayout,
)

from larccommon.design_system import ds
from larccommon.theme import theme_manager


def table_section(title: str, table: QWidget) -> QWidget:
    """Carte de section labellisée autour d'un tableau (IE8 : le tableau
    reste DANS sa section, jamais nu en pleine largeur). Thème réactif."""
    card = QWidget()
    card.setAttribute(Qt.WA_StyledBackground, True)
    lbl = QLabel(title)

    def _style():
        p = theme_manager.palette
        s = theme_manager.font_size
        card.setStyleSheet(
            f"background: {p.surface}; border: 1px solid {p.outline_variant}; "
            f"border-radius: {ds.radius_sm}px;")
        lbl.setStyleSheet(
            f"font-size: {s(16)}px; font-weight: bold; color: {p.text_strong}; "
            f"border: none;")

    v = QVBoxLayout(card)
    v.setContentsMargins(ds.space_md, ds.space_sm, ds.space_md, ds.space_md)
    v.setSpacing(ds.space_sm)
    v.addWidget(lbl)
    v.addWidget(table, 1)
    _style()
    ds.theme_changed.connect(_style)
    return card


class SectionsFlow(QWidget):
    """Flux responsive de cartes de section.

    min_width : largeur minimale par carte (défaut 2 × F₂₀ = 466 px).
    """

    def __init__(self, cards: list[QWidget], parent=None,
                 min_width: int | None = None, fill_vertical: bool = False):
        super().__init__(parent)
        self._cards = list(cards)
        self._cols = 0
        self._last_w = 0
        self._fill = fill_vertical
        self._min_w = min_width if min_width is not None else ds.sidebar_width * 2
        if self._fill:
            # Le flux absorbe toute la hauteur disponible de sa page
            self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.setMinimumWidth(self._min_w)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(ds.space_md)
        self._reflow()

    def _reflow(self):
        spacing = self._grid.spacing()
        cols = min(len(self._cards), max(1, self.width() // (self._min_w + spacing)))
        col_w = (self.width() - (cols - 1) * spacing) // cols
        if cols == self._cols and col_w == self._last_w:
            return
        self._cols = cols
        self._last_w = col_w
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item and item.widget():
                self._grid.removeWidget(item.widget())
        for c in range(self._grid.columnCount()):
            self._grid.setColumnStretch(c, 0)
        self._grid.setColumnStretch(cols, 1)  # espace restant à droite
        for r in range(self._grid.rowCount() + 1):
            self._grid.setRowStretch(r, 0)
        # Remplissage vertical uniquement quand tout est côte à côte
        fill_now = self._fill and cols == len(self._cards)
        for card in self._cards:
            card.setFixedWidth(col_w)
            if fill_now:
                card.setSizePolicy(card.sizePolicy().horizontalPolicy(),
                                   QSizePolicy.Expanding)
        for i, card in enumerate(self._cards):
            # AlignTop seulement hors remplissage (sinon la carte garde sa
            # hauteur de contenu et le stretch vertical est ignoré)
            align = Qt.Alignment() if fill_now else Qt.AlignTop
            self._grid.addWidget(card, i // cols, i % cols, align)
        if fill_now:
            for r in range((len(self._cards) + cols - 1) // cols):
                self._grid.setRowStretch(r, 1)
        else:
            self._grid.setRowStretch(self._grid.rowCount(), 1)
        # Les changements de stretch ne déclenchent pas de re-layout : forcer
        self._grid.activate()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Déféré : dans un scroll imbriqué, la largeur finale n'est connue
        # qu'après la passe de layout complète.
        QTimer.singleShot(0, self._reflow)
