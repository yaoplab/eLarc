"""M3ProfileButton — QPushButton simple pour bouton profil (initiales, pas de style M3)."""
from PySide6.QtWidgets import QPushButton
from phibuilder.theme import Theme


class M3ProfileButton(QPushButton):
    """Bouton circulaire pour initiales / avatar, sans surcharge M3.
    Le style est défini entièrement par l'appelant via setStyleSheet()."""
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
