"""
TableSettings — sauvegarde/restauration des largeurs de colonnes.
Utilise QSettings pour persister entre sessions.
"""

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QTableView, QTableWidget

_SETTINGS = QSettings("Larc", "LarcCommon")


class TableSettings:
    """Sauvegarde/restauration des largeurs de colonnes via QSettings.

    Usage:
        table = QTableWidget()
        TableSettings.restore(table, "dossier_panel/table_medicale")
        # ... l'utilisateur redimensionne les colonnes ...
        TableSettings.save(table, "dossier_panel/table_medicale")
    """

    @staticmethod
    def save(table: QTableWidget | QTableView, key: str):
        """Sauvegarde l'état des colonnes sous la clé donnée."""
        hdr = (
            table.horizontalHeader()
            if isinstance(table, QTableWidget)
            else table.horizontalHeader()
        )
        if hdr:
            _SETTINGS.setValue(f"table/{key}/columns", hdr.saveState())

    @staticmethod
    def restore(table: QTableWidget | QTableView, key: str):
        """Restaure les largeurs de colonnes depuis la clé donnée."""
        hdr = (
            table.horizontalHeader()
            if isinstance(table, QTableWidget)
            else table.horizontalHeader()
        )
        if not hdr:
            return
        state = _SETTINGS.value(f"table/{key}/columns")
        if state:
            hdr.restoreState(state)

    @staticmethod
    def reset(key: str):
        """Supprime la configuration sauvegardée pour la clé donnée."""
        _SETTINGS.remove(f"table/{key}/columns")
