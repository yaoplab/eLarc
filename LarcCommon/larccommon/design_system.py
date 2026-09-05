from __future__ import annotations
from typing import Optional

from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect
from PySide6.QtCore import QMargins, QObject, Signal

from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from phibuilder.phi.scale import SpacingToken
from phibuilder.widgets.button import ButtonVariant
from phibuilder.widgets.card import CardVariant

class _DesignSystem(QObject):
    """
    Design System — LarcCommon (Material Design V3 + Fibonacci + Ratio d'Or).
    
    RÈGLE ABSOLUE POUR TOUTE NOUVELLE CRÉATION UI : ZÉRO HARDCODING.
    Toutes les tailles, espacements, couleurs et polices doivent passer par ce module.
    """
    theme_changed = Signal()

    def __init__(self):
        super().__init__()
        self._tm = theme_manager
        
        # Constantes fondamentales
        self.GOLDEN = 1.618033988749895
        self.border_width = 1
        # Shapes M3 (voir Sous-système C du skill design-system-larc)
        # Skill data-entry-ui : cartes/champs = angles droits (0), boutons 5px (F₅)
        self.radius_none = 0      # shape-none — DataTable, ListItem
        self.radius_xs = 0         # shape-extra-small — TextField (angles droits)
        self.radius_sm = 0         # shape-small — Card (angles droits)
        self.radius_btn = 5        # boutons — Fibonacci F₅ (skill data-entry-ui)
        self.radius_md = 12        # shape-medium — Dialog, Drawer
        self.radius_lg = 16        # shape-large — Filled Button, FAB (NOT pill)
        self.radius_xl = 28        # shape-extra-large — Pill, BottomNav

        # Variants M3 (raccourcis pour les widgets phibuilder)
        self.BTN_FILLED   = ButtonVariant.FILLED
        self.BTN_TONAL    = ButtonVariant.TONAL
        self.BTN_OUTLINED = ButtonVariant.OUTLINED
        self.BTN_TEXT     = ButtonVariant.TEXT

        self.CARD_ELEVATED = CardVariant.ELEVATED
        self.CARD_FILLED   = CardVariant.FILLED
        self.CARD_OUTLINED = CardVariant.OUTLINED

        # Relayer theme_changed de theme_manager vers ds
        self._tm.theme_changed.connect(self._relay_theme_changed)

    @safe_slot("_DesignSystem.relay_theme_changed")
    def _relay_theme_changed(self):
        self.theme_changed.emit()

    def switch_theme(self, name: str) -> bool:
        """Change le thème (ds.theme_changed émis via relay theme_manager)."""
        return self._tm.set_active(name)

    # =========================================================================
    # 1. ARCHITECTURE DYNAMIQUE (Couleurs & Thème)
    # =========================================================================
    @property
    def theme_manager(self): return self._tm

    @property
    def p(self): return self._tm.palette

    @property
    def phi(self): return self._tm.phi_theme

    @property
    def c(self): return self.phi.colors

    # =========================================================================
    # 2. MICRO-PROPORTIONS : ESPACEMENTS FIBONACCI (px)
    # =========================================================================
    def sp(self, token: SpacingToken) -> int:
        return self.phi.spacing.spacing(token)

    @property
    def space_xxs(self) -> int: return self.sp(SpacingToken.XXS)
    @property
    def space_xs(self)  -> int: return self.sp(SpacingToken.XS)
    @property
    def space_sm(self)  -> int: return self.sp(SpacingToken.SM)
    @property
    def space_md(self)  -> int: return self.sp(SpacingToken.MD)
    @property
    def space_lg(self)  -> int: return self.sp(SpacingToken.LG)
    @property
    def space_xl(self)  -> int: return self.sp(SpacingToken.XL)
    @property
    def space_xxl(self) -> int: return self.sp(SpacingToken.XXL)
    @property
    def space_xxxl(self) -> int: return self.sp(SpacingToken.XXXL)
    @property
    def space_m3(self) -> int:
        """16px — M3 card/dialog/field padding.
        Valeur M3 ×8 pure (non-Fibonacci) pour compatibilité."""
        return 16

    # =========================================================================
    # 3. MACRO-PROPORTIONS : RATIO D'OR (Phi ≈ 1.618)
    # =========================================================================
    def golden_width(self, height: int) -> int:
        """Retourne la largeur idéale pour une hauteur donnée."""
        return int(height * self.GOLDEN)

    def golden_height(self, width: int) -> int:
        """Retourne la hauteur idéale pour une largeur donnée."""
        return int(width / self.GOLDEN)

    def golden_split(self, total_size: int) -> tuple[int, int]:
        """
        Divise un espace total (ex: largeur écran) en deux parties (A et B)
        telles que A/B = Phi. Idéal pour un QSplitter (Menu latéral + Contenu).
        Retourne (partie_principale, partie_secondaire).
        """
        small_part = int(total_size / (self.GOLDEN + 1))
        large_part = total_size - small_part
        return large_part, small_part

    # =========================================================================
    # 4. HELPERS DE MARGES ET LAYOUTS (Slots)
    # =========================================================================
    def margins(self, all: Optional[SpacingToken] = None, 
                top: Optional[SpacingToken] = None, 
                right: Optional[SpacingToken] = None, 
                bottom: Optional[SpacingToken] = None, 
                left: Optional[SpacingToken] = None) -> QMargins:
        """Retourne un QMargins strict basé sur Fibonacci."""
        if all is not None:
            v = self.sp(all)
            return QMargins(v, v, v, v)
        return QMargins(
            self.sp(left) if left else 0,
            self.sp(top) if top else 0,
            self.sp(right) if right else 0,
            self.sp(bottom) if bottom else 0
        )

    def v_layout(self, spacing: SpacingToken = SpacingToken.SM, 
                 margins: Optional[SpacingToken] = None) -> QVBoxLayout:
        """Génère un layout vertical M3 prêt à l'emploi."""
        layout = QVBoxLayout()
        layout.setSpacing(self.sp(spacing))
        layout.setContentsMargins(self.margins(all=margins) if margins else QMargins(0,0,0,0))
        return layout

    def h_layout(self, spacing: SpacingToken = SpacingToken.SM, 
                 margins: Optional[SpacingToken] = None) -> QHBoxLayout:
        """Génère un layout horizontal M3 prêt à l'emploi."""
        layout = QHBoxLayout()
        layout.setSpacing(self.sp(spacing))
        layout.setContentsMargins(self.margins(all=margins) if margins else QMargins(0,0,0,0))
        return layout

    # =========================================================================
    # 5. TYPOGRAPHIE DYNAMIQUE (Objets QFont M3)
    # =========================================================================
    @property
    def font_h1(self) -> int:
        return self._tm.typography.headline_medium.size   # 28

    @property
    def font_h2(self) -> int:
        return self._tm.typography.title_large.size       # 22

    @property
    def font_title(self) -> int:
        return self._tm.typography.title_medium.size      # 16

    @property
    def font_body(self) -> int:
        return self._tm.typography.body_medium.size        # 14

    @property
    def font_small(self) -> int:
        return self._tm.typography.body_small.size         # 12
        
    # Versions px pour QSS (échelle M3 complète)
    @property
    def font_label_sm(self) -> int: return 11     # label-small — badges, metadata
    @property
    def font_body_sm(self) -> int: return 12      # body-small — légendes
    @property
    def font_label_lg(self) -> int: return 13     # label-large — boutons, list items
    @property
    def font_body_md(self) -> int: return 14      # body-medium — TEXTE STANDARD
    @property
    def font_title_md(self) -> int: return 16     # title-medium — titres section
    @property
    def font_title_lg(self) -> int: return 18     # title-large — titres page
    @property
    def font_headline_sm(self) -> int: return 22  # headline-small — héros
    @property
    def font_headline_md(self) -> int: return 28  # headline-medium — KPIs
    @property
    def font_headline_lg(self) -> int: return 36  # headline-large — grands chiffres
    @property
    def font_display_sm(self) -> int: return 45   # display-small — très grand
    @property
    def font_display_lg(self) -> int: return 57   # display-large — hero

    # Aliases pour compatibilité ascendante (gardent les valeurs historiques)
    @property
    def font_px_sm(self) -> int: return self.font_label_sm      # 11px (inchangé)
    @property
    def font_px_md(self) -> int: return self.font_label_lg      # 13px (inchangé)
    @property
    def font_px_lg(self) -> int: return self.font_body_md       # 14px (inchangé)
    @property
    def font_px_title(self) -> int: return 21                   # 21px (inchangé — gardé pour login_qss)
    @property
    def font_size_sm(self) -> int: return self.font_label_sm    # 11px (inchangé)
    @property
    def font_size_md(self) -> int: return self.font_label_lg    # 13px (inchangé)
    @property
    def font_size_lg(self) -> int: return self.font_body_md     # 14px (inchangé)
    @property
    def font_size_title(self) -> int: return 21                 # 21px (inchangé)

    # =========================================================================
    # 6. ÉLÉVATION & OMBRES (Shadows M3)
    # =========================================================================
    def elevation(self, level: int) -> QGraphicsDropShadowEffect:
        """Génère une ombre M3 (niveau 1 à 5). S'adapte au mode Dark/Light."""
        effect = QGraphicsDropShadowEffect()
        blur_tokens = [SpacingToken.XXS, SpacingToken.XS, SpacingToken.SM, SpacingToken.MD, SpacingToken.LG]
        safe_level = max(1, min(level, 5)) - 1
        
        effect.setBlurRadius(self.sp(blur_tokens[safe_level]))
        effect.setOffset(0, safe_level + 1)
        
        shadow_color = QColor(self.p.shadow)
        # Transparence plus marquée en mode sombre pour rester lisible
        shadow_color.setAlpha(40 if getattr(self._tm, 'is_dark_mode', False) else 20) 
        effect.setColor(shadow_color)
        
        return effect

    # =========================================================================
    # 7. COMPOSANTS SPÉCIFIQUES & QSS DYNAMIQUE
    # =========================================================================
    @property
    def field_height(self)  -> int: return self.space_lg    # 32px
    @property
    def button_height(self) -> int: return self.space_xl    # 52px
    @property
    def header_height(self) -> int: return self.space_xl    # 52px
    @property
    def field_max_width(self) -> int: return 360             # largeur max champ/combo/date (input-ergonomics IE6)
    @property
    def form_max_width(self) -> int: return 720              # largeur max contenu popup/dialogue uniquement (IE6)
    @property
    def icon_md(self)         -> int: return self.space_lg    # 32px
    @property
    def table_row_min(self)   -> int: return 21               # font_size_md(13) × φ(1.618) ≈ 21
    @property
    def table_min_section(self) -> int: return 18             # hauteur min ligne tableau

    # Tailles d'icônes
    @property
    def icon_sm(self) -> int: return 18                       # petite icône (toolbar)
    # Tailles héritées d'ImageScale (valeurs préservées — tokens ds.*)
    @property
    def logo_small(self) -> int: return 55                    # hauteur bouton logo (ImageScale.logo_small)
    @property
    def avatar(self) -> int: return 150                       # largeur filtre avatar
    @property
    def add_btn(self) -> int: return 100                      # bouton ajout carré (ImageScale.add_btn)

    # Tailles de cartes KPIs
    @property
    def kpi_card_height(self) -> int: return 80
    @property
    def kpi_card_min_width(self) -> int: return 160  # largeur minimale KPI

    # Tailles de fenêtres et panels
    @property
    def sidebar_width(self) -> int: return 233
    @property
    def workspace_sidebar_width(self) -> int: return 300  # sidebar verticale LarcProf (4 blocs empilés)
    @property
    def jugements_width(self) -> int: return 144
    @property
    def scroll_max_height(self) -> int: return 144
    @property
    def workspace_min_height(self) -> int: return 144
    @property
    def idx_label_width(self) -> int: return 34
    @property
    def nature_label_width(self) -> int: return 150  # nature tronquée à 20 chars ≈ 135px à fonts.small
    @property
    def crit_letter_width(self) -> int: return 16  # colonne fixe par lettre de critère (A/B/C/D alignés)
    @property
    def icon_btn_size(self) -> int: return 32   # Fibonacci LG (was 30)
    @property
    def font_btn_width(self) -> int: return 32   # Fibonacci LG (was 36)
    @property
    def font_btn_height(self) -> int: return 32   # Fibonacci LG (was 30)
    @property
    def window_width(self) -> int: return 1200
    @property
    def window_height(self) -> int: return 800

    def flat_input_qss(self) -> str:
        """QSS avec gestion des états pseudo-classes (:hover, :focus, :disabled)."""
        return f"""
            QLineEdit {{
                background: transparent;
                border: {self.border_width}px solid {self.p.outline};
                border-radius: {self.space_xxs}px;
                padding: {self.sp(SpacingToken.XXS)}px {self.sp(SpacingToken.XS)}px;
                color: {self.p.text_strong};
            }}
            QLineEdit:hover {{
                background: {self.p.surface_variant};
            }}
            QLineEdit:focus {{
                border: 2px solid {self.p.primary};
                outline: none;
            }}
            QLineEdit:disabled {{
                color: {self.p.text_disabled};
                border-color: {self.p.outline_variant};
            }}
        """

    def panel_qss(self) -> str:
        """QSS de base pour un panneau (QFrame)."""
        return f"""
            QFrame {{
                background: {self.p.surface};
                border: {self.border_width}px solid {self.p.border};
                border-radius: {self.space_xs}px;
            }}
        """

    def table_qss(self) -> str:
        """QSS pour un tableau sans bordures arrondies, harmonisé formulaire."""
        return f"""
            M3TableWidget {{ 
                background-color: {self.p.surface}; 
                border: {self.border_width}px solid {self.p.outline}; 
                border-radius: 0px; 
                gridline-color: {self.p.outline_variant}; 
                outline: none; 
                color: {self.p.text_strong}; 
            }}
            M3TableWidget::item {{ 
                padding: {self.space_xxs}px; 
                border-bottom: {self.border_width}px solid {self.p.outline_variant}; 
            }}
            M3TableWidget::item:selected {{ 
                background-color: {self.p.primary_container}; 
                color: {self.p.text_strong}; 
            }}
            M3TableWidget::item:hover {{ 
                background-color: {self.p.surface_variant}; 
            }}
            QHeaderView::section {{ 
                background-color: {self.p.surface}; 
                color: {self.p.text_strong}; 
                padding: {self.space_xs}px; 
                height: {self.table_row_min}px;
                border: none; 
                border-bottom: 2px solid {self.p.outline}; 
                font-weight: bold; 
            }}
        """

# Singleton global
ds = _DesignSystem()