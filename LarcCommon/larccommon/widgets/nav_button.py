"""
NavButton — Bouton de navigation standardisé (Dashboard, Recherche, Parents, etc.)

Conforme au Sous-système K du skill design-system-larc pour les boutons de
navigation latérale. Utilise M3Button(variant=TONAL) avec une icône standardisée.

Usage:
    from larccommon.widgets.nav_button import NavButton

    nav = NavButton(
        text=_("sec_main.dashboard"),
        icon_name="dashboard",
        on_click=lambda: self._set_scope('school'),
    )
    sidebar_layout.addWidget(nav)
"""

from typing import Callable, Optional

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWidget

from larccommon.icons import icon as md3_icon
from larccommon.theme import theme_manager
from phibuilder.widgets.button import ButtonVariant, M3Button


class NavButton(M3Button):
    """Bouton de navigation avec icone standardisee.

    Herite de M3Button et ajoute :
    - Icone Material Design avec taille et couleur standardisees
    - Curseur 'main' par defaut (via M3Button)
    - API concise : text + icon_name + on_click
    - Variant parametrable (defaut: TONAL)
    """

    def __init__(
        self,
        text: str = "",
        icon_name: str = "",
        on_click: Optional[Callable] = None,
        variant: ButtonVariant = ButtonVariant.TONAL,
        parent: Optional[QWidget] = None,
    ):
        # K26 (sidebar-spec) : avec icône, texte aligné à gauche → icône calée
        # au padding et gap icône↔texte natif Qt = ds.space_xs (8px).
        super().__init__(
            text, variant=variant, parent=parent,
            text_align="left" if icon_name else "center",
        )
        self._icon_name = icon_name
        self._icon_size = ds.icon_sm

        if icon_name:
            self._apply_icon()

        if on_click:
            self.clicked.connect(on_click)

    def _apply_icon(self):
        """Recrée l'icône avec les couleurs du thème actif."""
        self.setIcon(
            md3_icon(self._icon_name,
                     color=theme_manager.palette.text_soft,
                     size=self._icon_size))
        self.setIconSize(QSize(self._icon_size, self._icon_size))
        self._apply_text_align()

    def _apply_text_align(self):
        """K26 (sidebar-spec) : icône calée à gauche, gap icône↔texte natif Qt
        (8px = ds.space_xs). Le QSS widget fusionne avec le QSS global de
        l'app — sans lui, Qt centre le groupe icône+texte et l'icône dérive
        selon la longueur du libellé (NavButton est souvent créé sans theme)."""
        if not self._icon_name:
            return
        base = self.styleSheet()
        if "text-align" not in base:
            self.setStyleSheet(base + "\nM3Button { text-align: left; }")

    def restyle(self):
        """Met à jour l'icône après un changement de thème."""
        if self._icon_name:
            self._apply_icon()
