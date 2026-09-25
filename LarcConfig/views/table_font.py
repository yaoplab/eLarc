"""Réglage de la taille de police d'un tableau (boutons « A− » / « A »).

Le style de M3TableWidget fixe la police dans son QSS : on ajoute donc, après ce
QSS, une règle de même sélecteur qui prend le dessus (dernière règle gagnante).
La hauteur des lignes suit la police. Le réglage est mémorisé d'une session à
l'autre (QSettings), par clé de tableau.
"""
from __future__ import annotations

from larccommon.design_system import ds
from larccommon.theme import theme_manager
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QHeaderView, QTableWidget

MAX_STEPS = 4      # paliers de réduction (1 px chacun) sous la taille normale
_SETTINGS = QSettings("Larc", "LarcConfig")


class TableFontControl:
    def __init__(self, table: QTableWidget, key: str, lines: int = 1, header_lines: int = 1):
        self._table = table
        self._key = f"table_font/{key}"
        self._lines = lines
        self._header_lines = header_lines
        typo = theme_manager.phi_theme.typo
        # Tailles de base (px) du corps et de l'en-tête, telles que le thème les a posées.
        self._body_px = typo.body_medium.size
        self._head_px = typo.label_large.size
        self._table_qss = table.styleSheet()
        self._head_qss = table.horizontalHeader().styleSheet()
        self._steps = 0
        try:
            self._steps = max(0, min(MAX_STEPS, int(_SETTINGS.value(self._key, 0))))
        except (TypeError, ValueError):
            self._steps = 0
        self.apply()

    @property
    def steps(self) -> int:
        return self._steps

    def reduce(self) -> None:
        self._set(self._steps + 1)

    def reset(self) -> None:
        self._set(0)

    def _set(self, steps: int) -> None:
        self._steps = max(0, min(MAX_STEPS, steps))
        _SETTINGS.setValue(self._key, self._steps)
        self.apply()

    def apply(self) -> None:
        body, head = self._body_px - self._steps, self._head_px - self._steps
        self._table.setStyleSheet(f"{self._table_qss}\nM3TableWidget {{ font-size: {body}px; }}")
        self._table.horizontalHeader().setStyleSheet(
            f"{self._head_qss}\nQHeaderView::section {{ font-size: {head}px; }}")
        font = self._table.font()
        font.setPixelSize(body)
        height = max(ds.space_lg + ds.space_xs,
                     self._lines * QFontMetrics(font).lineSpacing() + 2 * ds.space_xs)
        head_font = self._table.horizontalHeader().font()
        head_font.setPixelSize(head)
        # en-tête : hauteur de N lignes (libellés longs à la ligne) + marges haut/bas
        self._table.horizontalHeader().setFixedHeight(
            self._header_lines * QFontMetrics(head_font).lineSpacing() + 2 * ds.space_xs)
        vh = self._table.verticalHeader()
        vh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vh.setDefaultSectionSize(height)
