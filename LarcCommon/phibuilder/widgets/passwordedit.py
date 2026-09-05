"""PasswordLineEdit — champ mot de passe avec œil (skill data-entry-ui).

L'icône de l'œil est fournie par l'appelant (ex. `md3_icon` de larccommon) —
phibuilder reste indépendant du système d'icônes. Sans icône, le champ est
un simple mot de passe (sans action œil).
"""
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLineEdit

from phibuilder.theme import Theme
from phibuilder.widgets.textfield import M3TextField
from larccommon.safe_slot import safe_slot


class PasswordLineEdit(M3TextField):
    def __init__(self, text: str = "", theme: Theme | None = None,
                 placeholder: str = "",
                 eye_icon: QIcon | None = None,
                 eye_hidden_icon: QIcon | None = None,
                 parent=None):
        super().__init__(text, theme=theme, placeholder=placeholder,
                         parent=parent)
        self.setEchoMode(QLineEdit.EchoMode.Password)
        self._visible = False
        self._eye_icon = eye_icon
        self._eye_hidden_icon = eye_hidden_icon
        self._eye_action = None
        if eye_icon is not None:
            self._eye_action = self.addAction(
                eye_icon, QLineEdit.ActionPosition.TrailingPosition)
            self._eye_action.setToolTip("Afficher / Masquer")
            self._eye_action.triggered.connect(self._toggle_visibility)

    @safe_slot("PasswordLineEdit._toggle_visibility")
    def _toggle_visibility(self):
        self._visible = not self._visible
        self.setEchoMode(QLineEdit.EchoMode.Normal
                         if self._visible else QLineEdit.EchoMode.Password)
        if self._eye_action is not None:
            self._eye_action.setIcon(
                self._eye_hidden_icon if self._visible else self._eye_icon)
