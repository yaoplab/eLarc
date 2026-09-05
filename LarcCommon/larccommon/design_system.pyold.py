"""
Design System — LarcCommon (Material Design V3 + Fibonacci).

RÈGLE ABSOLUE POUR TOUTE NOUVELLE CRÉATION UI : ZÉRO HARDCODING.
Toutes les tailles, espacements, couleurs doivent passer par ce module
ou leurs sources (theme_manager, phi.spacing, palette).

Usage :
    from larccommon.design_system import ds

    # Espacement — jamais setSpacing(12) ou setContentsMargins(6,6,6,6)
    layout.setSpacing(ds.space_sm)
    layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)

    # Hauteurs des composants — jamais setFixedHeight(52)
    field.setFixedHeight(ds.field_height)

    # Bordures — jamais border-radius: 8px; ou border: 1px solid #xxx
    field.setStyleSheet(ds.flat_input_qss())

    # Tableaux — harmonisés avec le formulaire
    table.setStyleSheet(ds.table_qss())

    # Couleurs — jamais #1565C0 ou #c0392b
    ds.p.primary, ds.p.surface, ds.p.error, ds.p.outline

    # Couleurs M3 — pour widgets phibuilder
    ds.c.primary, ds.c.on_surface, ds.c.outline_variant

    # Boutons — variants M3 standard
    M3Button("OK", theme=ds.phi, variant=ds.BTN_FILLED)

    # Fibonacci direct
    ds.sp(SpacingToken.XXL)   # 84 px

Valeurs INTERDITES en dur :
    - setSpacing(3), setSpacing(5), setSpacing(8), setSpacing(13)
    - setContentsMargins(6,6,6,6), setContentsMargins(13,13,13,13)
    - setFixedHeight(21), setFixedHeight(34), setFixedWidth(233)
    - padding: 6px; padding: 8px 16px; margin: 3px;
    - border-radius: 8px; font-size: 13px;

Exception : les valeurs 0 (zéro) pour collapse sont autorisées.
"""
from __future__ import annotations

from larccommon.theme import theme_manager
from phibuilder.phi.scale import SpacingToken
from phibuilder.widgets.button import ButtonVariant
from phibuilder.widgets.card import CardVariant


# =============================================================================
# Design System
# =============================================================================

class _DesignSystem:
    """Tokens de design unifiés — liés à theme_manager et Fibonacci.

    Propriétés dynamiques :
        ds.p       → palette active (couleurs)
        ds.phi     → PhiTheme (spacing + couleurs M3)
        ds.sp(x)   → raccourci : sp(SpacingToken.X) en px

    Tokens dynamiques (Fibonacci × base_spacing=4) :
        ds.space_xxs =  4 px    ds.space_xs  =  8 px    ds.space_sm  = 12 px
        ds.space_md  = 20 px    ds.space_lg  = 32 px    ds.space_xl  = 52 px
        ds.space_xxl = 84 px    ds.space_xxxl=136 px

    Tous calculés via ds.sp(SpacingToken.XXX) — zéro hardcoding.
    Si le base_spacing change, tout s'adapte.
    """

    def __init__(self):
        self._tm = theme_manager

    # ---- Palette active (couleurs) ----
    @property
    def p(self):
        return self._tm.palette

    @property
    def phi(self):
        return self._tm.phi_theme

    def sp(self, token: SpacingToken) -> int:
        return self.phi.spacing.spacing(token)

    @property
    def c(self):
        """Couleurs M3 (primary, surface, error, outline, etc.)."""
        return self.phi.colors

    # =========================================================================
    # Espacements Fibonacci (px) — dynamiques depuis PhiScale(base_spacing=4)
    # =========================================================================
    @property
    def space_xxs(self) -> int: return self.sp(SpacingToken.XXS)    #  4 px
    @property
    def space_xs(self)  -> int: return self.sp(SpacingToken.XS)     #  8 px
    @property
    def space_sm(self)  -> int: return self.sp(SpacingToken.SM)     # 12 px
    @property
    def space_md(self)  -> int: return self.sp(SpacingToken.MD)     # 20 px
    @property
    def space_lg(self)  -> int: return self.sp(SpacingToken.LG)     # 32 px
    @property
    def space_xl(self)  -> int: return self.sp(SpacingToken.XL)     # 52 px
    @property
    def space_xxl(self) -> int: return self.sp(SpacingToken.XXL)    # 84 px
    @property
    def space_xxxl(self)-> int: return self.sp(SpacingToken.XXXL)   #136 px

    # =========================================================================
    # Hauteurs des composants (px) — dérivées de Fibonacci
    # =========================================================================
    @property
    def field_height(self)  -> int: return self.space_lg    # 32 — M3TextField / M3ComboBox / M3DateEdit
    @property
    def button_height(self) -> int: return self.space_xl    # 52 — hauteur bouton standard
    @property
    def header_height(self) -> int: return self.space_xl    # 52 — hauteur header top-bar
    @property
    def table_row_min(self) -> int: return self.space_lg    # 32 — hauteur ligne tableau

    # =========================================================================
    # Icônes / boutons carrés (px)
    # =========================================================================
    @property
    def icon_sm(self) -> int: return self.space_md          # 20
    @property
    def icon_md(self) -> int: return self.space_lg          # 32
    @property
    def icon_lg(self) -> int: return self.space_xl          # 52

    # =========================================================================
    # Bordures (px) — dérivées de Fibonacci
    # =========================================================================
    radius_none = 0
    @property
    def radius_xs(self)  -> int: return self.space_xxs      # 4
    @property
    def radius_sm(self)  -> int: return self.space_xs       # 8
    @property
    def radius_md(self)  -> int: return self.space_sm       # 12
    @property
    def radius_lg(self)  -> int: return self.space_md       # 20
    border_width = 1

    # =========================================================================
    # Typographie
    # =========================================================================
    font_family = "Segoe UI"
    font_title  = 14            # titre fenêtre (QFont.Bold)
    font_body   = 13            # corps de texte standard
    font_small  = 11            # métadonnées / info secondaire
    font_tiny   = 10            # badges / tooltips
    font_h1     = 22            # titre de section
    font_h2     = 16            # sous-titre

    # =========================================================================
    # Ratio d'or (φ ≈ 1.618)
    # Consecutive SpacingToken values follow Fibonacci: XXS/XS=2/1, XS/SM=3/2,
    # SM/MD=5/3, MD/LG=8/5, LG/XL=13/8, XL/XXL=21/13... → each ratio ≈ φ.
    # Avec base_spacing=4, les pixels suivent la même progression :
    # 4/8=0.5, 8/12=0.667, 12/20=0.6, 20/32=0.625, 32/52=0.615, 52/84=0.619
    # Plus la séquence avance, plus le ratio tend vers 1/φ ≈ 0.618.
    # =========================================================================
    GOLDEN = 1.618033988749895

    def golden_width(self, height: int) -> int:
        return int(height * self.GOLDEN)

    def golden_height(self, width: int) -> int:
        return int(width * self.GOLDEN)

    # =========================================================================
    # Variants M3 (raccourcis pour les widgets phibuilder)
    # =========================================================================
    BTN_FILLED   = ButtonVariant.FILLED
    BTN_TONAL    = ButtonVariant.TONAL
    BTN_OUTLINED = ButtonVariant.OUTLINED
    BTN_TEXT     = ButtonVariant.TEXT

    CARD_ELEVATED = CardVariant.ELEVATED
    CARD_FILLED   = CardVariant.FILLED
    CARD_OUTLINED = CardVariant.OUTLINED

    # =========================================================================
    # Helpers
    # =========================================================================
    def flat_input_qss(self) -> str:
        """QSS pour un champ de saisie plat (coins 4px, bordure outline, padding 20px)."""
        return (
            f"background: transparent; "
            f"border: {self.border_width}px solid {self.p.outline}; "
            f"border-radius: {self.radius_xs}px; "
            f"padding: {self.sp(SpacingToken.MD)}px; "
            f"color: {self.p.text_strong}; "
            f"font-size: {self.font_body}px;"
        )

    def panel_qss(self) -> str:
        """QSS de base pour un panneau (QFrame.panel)."""
        return (
            f"background: {self.p.surface}; "
            f"border: {self.border_width}px solid {self.p.border}; "
            f"border-radius: {self.radius_sm}px;"
        )

    def table_qss(self) -> str:
        """QSS pour un tableau sans bordures arrondies, harmonisé formulaire."""
        return (
            f"M3TableWidget {{ background-color: {self.p.surface}; "
            f"border: {self.border_width}px solid {self.p.outline}; border-radius: 0px; "
            f"gridline-color: {self.p.outline_variant}; outline: none; "
            f"font-size: {self.font_body}px; color: {self.p.text_strong}; }}"
            f"M3TableWidget::item {{ padding: {self.space_md}px; "
            f"border-bottom: {self.border_width}px solid {self.p.outline_variant}; }}"
            f"M3TableWidget::item:selected {{ background-color: {self.p.primary_container}; "
            f"color: {self.p.text_strong}; }}"
            f"QHeaderView::section {{ background-color: {self.p.surface}; "
            f"color: {self.p.text_strong}; padding: {self.space_xs}px; "
            f"border: none; border-bottom: 2px solid {self.p.outline}; "
            f"font-size: {self.theme_manager.font_size(12)}px; font-weight: bold; }}"
        )

    def label_qss(self) -> str:
        """QSS pour un label de section (titre de card)."""
        return f"font-size: {self.font_body}px; font-weight: bold; color: {self.p.text_strong};"

    @property
    def theme_manager(self):
        return self._tm


# Singleton global
ds = _DesignSystem()
