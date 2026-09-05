"""Shim vers larccommon.theme — ajoute btn_toggle_style pour LarcProf."""

from PySide6.QtGui import QFont

# Couleurs des zones sidebar/grille demandées par l'utilisateur (2026-08-18).
# Fixes par choix visuel : elles ne suivent pas le thème actif.
ZONE_F_COLOR = '#26A9E1'  # Formatives — bleu ciel
ZONE_S_COLOR = '#1E4394'  # Sommatives — bleu marine
ZONE_NEUTRAL = '#F0F0F0'  # Matière / Affichage colonnes — gris très clair
ZONE_TEXT_LIGHT = '#FFFFFF'  # Texte sur les panneaux F (bleu ciel) et S (bleu marine)
ZONE_BORDER = '#BDBDBD'    # Cadre des 4 sections du sidebar
ZONE_BTN_BG = '#F57C00'    # Boutons Pondération / Gérer — orange, texte blanc bold

from larccommon.design_system import ds
from larccommon.theme import (
    DesignTokens,
    FontScale,
    Palette,
    QssHelper,
    Theme,
    ThemeManager,
    theme_manager,
)


def btn_toggle_style(checked: bool, height: int = 22) -> str:
    """Style pour boutons toggle type OUI/NON (utilisé dans main_window).

    Cochés = bleu clair (primary_container) : consultation.
    Les actions de gestion (Gérer, Ponderation) restent en primary plein.
    """
    p = theme_manager.palette
    if checked:
        return (
            f"QPushButton {{ background: {p.primary_container}; color: {p.primary}; "
            f"border: 1px solid {p.primary}; border-radius: {ds.radius_xs}px; "
            f"font-weight: bold; padding: 0 8px; height: {height}px; }}"
        )
    return (
        f"QPushButton {{ background: transparent; color: {p.text_strong}; "
        f"border: 1px solid {p.outline_variant}; border-radius: {ds.radius_xs}px; "
        f"padding: 0 8px; height: {height}px; }}"
        f"QPushButton:hover {{ background: {p.surface_variant}; }}"
    )


def btn_toggle_style_dark(checked: bool, height: int = 22) -> str:
    """Variante pour panneau sombre (sommatives) : texte clair au décoché."""
    p = theme_manager.palette
    if checked:
        return (
            f"QPushButton {{ background: {p.primary_container}; color: {p.primary}; "
            f"border: 1px solid {p.primary}; border-radius: {ds.radius_xs}px; "
            f"font-weight: bold; padding: 0 8px; height: {height}px; }}"
        )
    return (
        f"QPushButton {{ background: transparent; color: {p.on_primary}; "
        f"border: 1px solid {p.outline_variant}; border-radius: {ds.radius_xs}px; "
        f"padding: 0 8px; height: {height}px; }}"
        f"QPushButton:hover {{ background: rgba(255,255,255,0.15); }}"
    )


class ThemeManagerWrapper:
    """Wrapper compatible avec l'API LarcProf existante."""

    def __init__(self):
        self._original = theme_manager

    @property
    def palette(self):
        return self._original.palette

    @property
    def fonts(self):
        return self._original.fonts

    @property
    def design(self):
        return self._original.design

    @property
    def theme(self):
        return self._original.theme

    @property
    def phi_theme(self):
        return self._original.phi_theme

    @property
    def active_name(self):
        return self._original.active_name

    @property
    def image(self):
        return self._original.image

    def set_active(self, name: str) -> bool:
        return self._original.set_active(name)

    def get_palette(self, name: str):
        """Palette d'un thème par clé (pour icônes de menu)."""
        return self._original.get_palette(name)

    def font_size(self, base: int) -> int:
        return self._original.font_size(base)

    def font(self, base: int, weight=QFont.Weight.Normal):
        return self._original.font(base, weight)

    def names(self):
        return self._original.names()

    def bind(self, app):
        self._original.bind(app)

    def btn_toggle_style(self, checked: bool, height: int = 22) -> str:
        return btn_toggle_style(checked, height)

    def btn_toggle_style_dark(self, checked: bool, height: int = 22) -> str:
        return btn_toggle_style_dark(checked, height)

    def btn_crit_style(self, checked: bool) -> str:
        p = self._original.palette
        if checked:
            return (
                f"QPushButton {{ background: {p.primary_container}; color: {p.primary}; "
                f"border: 1px solid {p.primary}; border-radius: {ds.radius_xs}px; "
                f"padding: 0 {ds.space_xs}px; height: 22px; font-weight: bold; }}"
            )
        return (
            f"QPushButton {{ background: transparent; color: {p.text_strong}; "
            f"border: 1px solid {p.outline_variant}; border-radius: {ds.radius_xs}px; "
            f"padding: 0 {ds.space_xs}px; height: 22px; }}"
            f"QPushButton:hover {{ background: {p.surface_variant}; }}"
        )

    def set_font_multiplier(self, mult: float):
        self._original._theme.fonts.multiplier = mult


theme_manager = ThemeManagerWrapper()
__all__ = [
    "theme_manager",
    "ThemeManager",
    "Theme",
    "Palette",
    "FontScale",
    "DesignTokens",
    "QssHelper",
    "btn_toggle_style",
    "btn_toggle_style_dark",
]
