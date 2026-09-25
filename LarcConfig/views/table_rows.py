"""Hauteur de ligne fixe pour les tableaux du panneau « Classes & matières ».

Sans ça, chaque ligne prenait la hauteur de son contenu (`resizeRowsToContents`,
combobox en cellule, texte renvoyé à la ligne) : les tableaux sautaient d'une
classe à l'autre et les lignes n'avaient jamais la même hauteur.
"""
from larccommon.design_system import ds
from PySide6.QtWidgets import QHeaderView, QTableWidget


def fix_row_height(table: QTableWidget, height: int | None = None, lines: int = 1) -> None:
    """Fixe la hauteur de TOUTES les lignes (présentes et futures) du tableau.

    Par défaut `ds.space_lg + ds.space_xs` (32 + 8 = 40 px, jetons de la grille
    phi) : loge une combobox de cellule (`cell_combo_height()`, 32 px) avec 4 px
    d'air. `lines` > 1 réserve la place de N lignes de texte (cellules
    multi-matières)."""
    if height is None:
        height = ds.space_lg + ds.space_xs
        if lines > 1:
            height = max(height, lines * table.fontMetrics().lineSpacing() + 2 * ds.space_xs)
    vh = table.verticalHeader()
    vh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
    vh.setDefaultSectionSize(height)


def cell_combo_height() -> int:
    """Hauteur d'une combobox placée dans une cellule (`ds.field_height`, 32 px) —
    M3ComboBox impose 40 px par défaut, trop haut pour une ligne de tableau."""
    return ds.field_height
