"""
ThemedWidget — QWidget avec fond QSS activé par défaut.

Contourne le bug Qt où QWidget ignore le background des stylesheets parent.
Dans Qt, un QWidget standard ne peint PAS son fond même si un QSS parent
cible son objectName. Il faut impérativement WA_StyledBackground + AutoFill.

Usage:
    widget = ThemedWidget(object_name="group_page")
    # → WA_StyledBackground + AutoFillBackground déjà activés
    # → objectName déjà défini
    # → Plus besoin de guard palette manuellement

    widget = ThemedWidget(parent=self, object_name="sidebar",
                          allow_bg_color="#1E1E1E")
    # → Guard palette optionnel pour les cas où le QSS parent est lent à appliquer
"""

from typing import Optional

from PySide6.QtGui import QColor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget


class ThemedWidget(QWidget):
    """QWidget prêt pour le theming — WA_StyledBackground + AutoFill activés.

    Args:
        parent: widget parent optionnel
        object_name: objectName à définir (permet au QSS parent de cibler ce widget)
        allow_bg_color: couleur de fond hex (ex: "#1E1E1E") pour guard palette.
                        Redondant avec le QSS mais garantit le rendu.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        object_name: str = "",
        allow_bg_color: str = "",
    ):
        super().__init__(parent)
        # Nécessaire pour que QWidget peigne son background depuis le QSS
        self.setAttribute(Qt.WA_StyledBackground, True)
        # Nécessaire pour que le palette-based background soit peint
        self.setAutoFillBackground(True)
        if object_name:
            self.setObjectName(object_name)
        if allow_bg_color:
            pal = self.palette()
            pal.setColor(self.backgroundRole(), QColor(allow_bg_color))
            self.setPalette(pal)


class ThemedDialog(QDialog):
    """QDialog prêt pour le theming — WA_StyledBackground + AutoFill activés.

    Même pattern que ThemedWidget mais pour les dialogues.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        object_name: str = "",
        allow_bg_color: str = "",
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        if object_name:
            self.setObjectName(object_name)
        if allow_bg_color:
            pal = self.palette()
            pal.setColor(self.backgroundRole(), QColor(allow_bg_color))
            self.setPalette(pal)
