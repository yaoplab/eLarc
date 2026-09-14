from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Signal, QObject

from phibuilder import PhiBuilder
from phibuilder.phi.scale import PhiScale
from phibuilder.theme import Theme as PhiTheme
from phibuilder.theme import ThemeConfig


class _LarcM3Colors:
    """Mappe Palette (LarcCommon) vers les propriétés M3 attendues par les widgets phibuilder."""

    def __init__(self, p: "Palette"):
        self.primary = p.primary
        self.on_primary = p.on_primary
        self.primary_container = p.primary_container
        self.on_primary_container = p.text_strong
        self.secondary = p.secondary
        self.on_secondary = p.on_secondary
        self.secondary_container = p.secondary_container
        self.on_secondary_container = p.text_strong
        self.tertiary = p.tertiary
        self.on_tertiary = p.on_tertiary
        self.tertiary_container = p.tertiary_container
        self.error = p.error
        self.on_error = p.on_error
        self.error_container = p.error_container
        self.surface = p.surface
        self.on_surface = p.text_strong
        self.surface_variant = p.surface_variant
        self.on_surface_variant = p.text_soft
        self.background = p.background
        self.on_background = p.text_strong
        self.outline = p.outline
        self.outline_variant = p.outline_variant
        self.surface_container = p.surface_container
        self.surface_container_highest = p.surface_container_highest
        self.surface_container_low = p.surface_container_low
        self.surface_container_high = p.surface_container_high
        self.accent = p.accent
        self.active = p.active
        self.inverse_surface = p.text_soft
        self.inverse_on_surface = p.surface
        self.inverse_primary = p.primary


# 4 thèmes d'origine — les 2 bleus du logo (#1F4494 + #24A9E1) intégrés
THEMES_CONFIG = [
    ("blue", "Bleu", "#1F4494", False),
    ("dark", "Dark", "#1F4494", True),
    ("sobre", "Sobre", "#1F4494", False),
    ("contrast", "Contrasté", "#1F4494", False),
]

_SEED_MAP = {k: s for k, _, s, _ in THEMES_CONFIG}
_IS_DARK_MAP = {k: d for k, _, _, d in THEMES_CONFIG}

_THEME_DESIGN = {
    "dark": dict(
        radius=6,
        radius_lg=10,
        radius_xl=14,
        field_pad_v=10,
        field_pad_h=14,
        btn_sm_pad_v=8,
        btn_sm_pad_h=18,
        btn_pad_v=10,
        btn_pad_h=22,
    ),
    "contrast": dict(
        radius=6,
        radius_lg=10,
        radius_xl=14,
        spacing=8,
        margin=20,
        field_pad_v=10,
        field_pad_h=16,
        label_pad_v=8,
        btn_pad_v=10,
        btn_pad_h=24,
        btn_sm_pad_v=8,
        btn_sm_pad_h=18,
        btn_border=2,
    ),
}


@dataclass
class Palette:
    """Palette marque (skill data-entry-ui) : #1F4494 / #24A9E1 / #EF4444."""
    primary: str = "#1F4494"
    on_primary: str = "#FFFFFF"
    primary_container: str = "#D6E4FF"
    secondary: str = "#475569"
    on_secondary: str = "#FFFFFF"
    secondary_container: str = "#E2E8F0"
    tertiary: str = "#0F766E"
    on_tertiary: str = "#FFFFFF"
    tertiary_container: str = "#CCFBF1"
    error: str = "#EF4444"
    on_error: str = "#FFFFFF"
    error_container: str = "#FEE2E2"
    surface: str = "#FFFFFF"
    surface_variant: str = "#F1F5F9"
    surface_container_low: str = "#F8FAFC"
    surface_container: str = "#EEF2F7"
    surface_container_high: str = "#E7ECF3"
    surface_container_highest: str = "#E0E6EF"
    background: str = "#F0F4F8"
    outline: str = "#CBD5E1"
    outline_variant: str = "#E2E8F0"
    text_strong: str = "#0F172A"
    text_soft: str = "#64748B"
    text_disabled: str = "#94A3B8"
    success: str = "#16A34A"
    active: str = "#24A9E1"
    accent: str = "#24A9E1"
    inactive: str = "#94A3B8"
    border: str = "#CBD5E1"
    border_light: str = "#E2E8F0"


@dataclass
class DesignTokens:
    radius: int = 4
    radius_lg: int = 8
    radius_xl: int = 12
    spacing: int = 8      # M3 ×8 grid standard (était 6 — n'appartenait à aucun système)
    margin: int = 16
    field_pad_v: int = 8
    field_pad_h: int = 12
    label_pad_v: int = 6
    label_pad_h: int = 0
    btn_pad_v: int = 8
    btn_pad_h: int = 20
    btn_sm_pad_v: int = 6
    btn_sm_pad_h: int = 16
    btn_border: int = 1


_THEME_PALETTES = {
    # 4 thèmes d'origine — les 2 bleus du logo (primary #1F4494 + accent #24A9E1)
    # présents partout ; variantes distinctes par fonds/contraste.
    "blue": Palette(
        primary="#1F4494",
        on_primary="#FFFFFF",
        primary_container="#D6E4FF",
        secondary="#475569",
        on_secondary="#FFFFFF",
        secondary_container="#E2E8F0",
        tertiary="#0F766E",
        on_tertiary="#FFFFFF",
        tertiary_container="#CCFBF1",
        error="#EF4444",
        on_error="#FFFFFF",
        error_container="#FEE2E2",
        success="#16A34A",
        surface="#FFFFFF",
        surface_container_low="#FAFBFD",
        surface_container="#F5F7FA",
        surface_container_high="#EEF1F5",
        surface_container_highest="#E7ECF3",
        surface_variant="#F1F5F9",
        background="#F0F4F8",
        outline="#CBD5E1",
        outline_variant="#E2E8F0",
        text_strong="#0F172A",
        text_soft="#5B6778",
        text_disabled="#94A3B8",
        active="#24A9E1",
        accent="#24A9E1",
        inactive="#94A3B8",
        border="#CBD5E1",
        border_light="#E2E8F0",
    ),
    "dark": Palette(
        primary="#1F4494",
        on_primary="#FFFFFF",
        primary_container="#1E3A8A",
        secondary="#64748B",
        on_secondary="#FFFFFF",
        secondary_container="#475569",
        tertiary="#38BDF8",
        on_tertiary="#082F49",
        tertiary_container="#0C4A6E",
        error="#EF4444",
        on_error="#FFFFFF",
        error_container="#7F1D1D",
        success="#22C55E",
        surface="#1E293B",
        surface_container_low="#243044",
        surface_container="#28344A",
        surface_container_high="#2D3A52",
        surface_container_highest="#37476A",
        surface_variant="#334155",
        background="#0F172A",
        outline="#334155",
        outline_variant="#475569",
        text_strong="#F1F5F9",
        text_soft="#CBD5E1",
        text_disabled="#94A3B8",
        active="#24A9E1",
        accent="#24A9E1",
        inactive="#94A3B8",
        border="#475569",
        border_light="#64748B",
    ),
    "sobre": Palette(
        primary="#1F4494",
        on_primary="#FFFFFF",
        primary_container="#E8EEF9",
        secondary="#64748B",
        on_secondary="#FFFFFF",
        secondary_container="#EEF1F6",
        tertiary="#0F766E",
        on_tertiary="#FFFFFF",
        tertiary_container="#E6F4F2",
        error="#EF4444",
        on_error="#FFFFFF",
        error_container="#FEF2F2",
        success="#16A34A",
        surface="#FBFCFE",
        surface_container_low="#F7F9FB",
        surface_container="#F2F5F8",
        surface_container_high="#ECF0F4",
        surface_container_highest="#E5E9EF",
        surface_variant="#EDF0F5",
        background="#F5F7FA",
        outline="#C9D2DE",
        outline_variant="#DDE3EC",
        text_strong="#1B2433",
        text_soft="#5B6778",
        text_disabled="#8B96A6",
        active="#24A9E1",
        accent="#24A9E1",
        inactive="#9AA5B5",
        border="#C9D2DE",
        border_light="#DDE3EC",
    ),
    "contrast": Palette(
        primary="#1F4494",
        on_primary="#FFFFFF",
        primary_container="#D6E4FF",
        secondary="#1F4494",
        on_secondary="#FFFFFF",
        secondary_container="#E2E8F0",
        tertiary="#0F766E",
        on_tertiary="#FFFFFF",
        tertiary_container="#CCFBF1",
        error="#EF4444",
        on_error="#FFFFFF",
        error_container="#FEE2E2",
        success="#16A34A",
        surface="#FFFFFF",
        surface_container_low="#F7F7F7",
        surface_container="#EFEFEF",
        surface_container_high="#E5E5E5",
        surface_container_highest="#D9D9D9",
        surface_variant="#F1F5F9",
        background="#FFFFFF",
        outline="#000000",
        outline_variant="#333333",
        text_strong="#000000",
        text_soft="#1A1A1A",
        text_disabled="#555555",
        active="#24A9E1",
        accent="#24A9E1",
        inactive="#666666",
        border="#000000",
        border_light="#333333",
    ),
}


@dataclass
class FontScale:
    base: int = 12
    small: int = 10
    title: int = 14
    header: int = 16
    button: int = 12
    multiplier: float = 1.0


@dataclass
class ImageScale:
    """Tailles standard des images, logos, icônes (Fibonacci + usage)."""

    logo: int = 89  # SpacingToken.GIANT
    logo_small: int = 55  # SpacingToken.HUGE
    avatar: int = 150
    photo: int = 150
    add_btn: int = 100
    icon_btn: int = 18
    icon_menu: int = 18
    icon_large: int = 32
    profile_btn: int = 34
    theme_btn: int = 34
    refresh_btn: int = 34
    field_height: int = 56  # M3TextField par défaut


@dataclass
class Theme:
    name: str
    label: str
    palette: Palette = field(default_factory=Palette)
    fonts: FontScale = field(default_factory=FontScale)
    design: DesignTokens = field(default_factory=DesignTokens)


_BUILTIN_THEMES: dict[str, Theme] = {}


def _init_themes():
    if _BUILTIN_THEMES:
        return
    for key, label, seed, is_dark in THEMES_CONFIG:
        pal = _THEME_PALETTES[key]
        dt_kwargs = _THEME_DESIGN.get(key, {})
        dt = DesignTokens(**dt_kwargs)
        _BUILTIN_THEMES[key] = Theme(key, label, pal, design=dt)


class ThemeManager(QObject):
    theme_changed = Signal()

    def __init__(self):
        super().__init__()
        _init_themes()
        self._themes = _BUILTIN_THEMES
        self._active: str = "blue"
        self._theme: Theme = self._themes[self._active]
        self._app: Optional[QApplication] = None
        self._phibuilder: Optional[PhiBuilder] = None
        self._phi_theme: Optional[PhiTheme] = None
        self._image_scale = ImageScale()

    @property
    def theme(self) -> Theme:
        return self._theme

    @property
    def phibuilder(self) -> Optional[PhiBuilder]:
        return self._phibuilder

    @property
    def palette(self) -> Palette:
        return self._theme.palette

    @property
    def phi_theme(self) -> PhiTheme:
        """Thème phibuilder unifié avec les couleurs de la palette LarcCommon active."""
        if self._phi_theme is None:
            cfg = ThemeConfig(
                seed_color=_SEED_MAP.get(self._active, "#1565C0"),
                is_dark=_IS_DARK_MAP.get(self._active, False),
                font_family="Segoe UI",
            )
            self._phi_theme = PhiTheme(cfg)
            self._phi_theme.spacing = PhiScale(base_spacing=4)
        self._phi_theme.colors = _LarcM3Colors(self._theme.palette)
        return self._phi_theme

    @property
    def typography(self):
        """Typographie M3 depuis le thème phibuilder actif."""
        return self.phi_theme.typo

    @property
    def fonts(self) -> FontScale:
        return self._theme.fonts

    @property
    def design(self) -> DesignTokens:
        return self._theme.design

    @property
    def image(self) -> ImageScale:
        return self._image_scale

    @property
    def active_name(self) -> str:
        return self._active

    def names(self) -> list[tuple[str, str]]:
        return [(k, v.label) for k, v in self._themes.items()]

    def get_palette(self, name: str) -> Optional[Palette]:
        t = self._themes.get(name)
        return t.palette if t else None

    def set_active(self, name: str) -> bool:
        if name in self._themes:
            self._active = name
            self._theme = self._themes[name]
            self._phi_theme = None
            self._sync_phibuilder()
            self._apply_palette()
            self._reapply()
            self.theme_changed.emit()
            return True
        return False

    def font_size(self, base: int) -> int:
        return max(7, int(base * self._theme.fonts.multiplier))

    def font(self, base: int, weight=QFont.Weight.Normal, family="Segoe UI") -> QFont:
        return QFont(family, self.font_size(base), int(weight))

    def font_px(self, base: int, weight=QFont.Weight.Normal,
                family="Segoe UI") -> QFont:
        """QFont en PIXELS — contrairement à font() qui passe par
        QFont(famille, int) : ce constructeur crée des POINTS (12 pt ≈ 16 px,
        +33 %). Les graphiques QPainter doivent aligner leurs tailles sur
        les QSS (px réels) — utiliser cette méthode."""
        f = QFont(family)
        f.setPixelSize(self.font_size(base))
        f.setWeight(QFont.Weight(weight))
        return f

    def bind(self, app: QApplication) -> None:
        self._app = app
        # Fusion : rendu identique sur toutes les machines (le style natif
        # Windows peint certains widgets — ex. QDateEdit — avec des couleurs
        # système hors thème, bleu illisible sur fond clair).
        app.setStyle("Fusion")
        self._phibuilder = PhiBuilder(
            seed_color=_SEED_MAP.get(self._active, "#1565C0"),
            is_dark=_IS_DARK_MAP.get(self._active, False),
        )
        self._apply_palette()
        self._reapply()

    def _sync_phibuilder(self):
        if self._phibuilder is None:
            return
        self._phibuilder.set_seed_color(_SEED_MAP.get(self._active, "#1565C0"))
        self._phibuilder.set_dark_mode(_IS_DARK_MAP.get(self._active, False))

    def _apply_palette(self):
        """Aligne la palette Qt sur la palette du thème actif (sections QDateEdit,
        calendrier, sélections, ET dialogues natifs : QMessageBox/QDialog sans
        WA_StyledBackground ne peignent pas le QSS de fond et retombent sur
        QPalette.Window — gris Fusion illisible en thème dark)."""
        if self._app is None:
            return
        pal = self._app.palette()
        p = self.palette
        pal.setColor(QPalette.Text, p.text_strong)
        pal.setColor(QPalette.ButtonText, p.text_strong)
        pal.setColor(QPalette.WindowText, p.text_strong)
        # Marqueur de section des QDateEdit : bande sombre + texte blanc
        # (le défaut était un bleu vif sur fond clair, illisible).
        pal.setColor(QPalette.Highlight, p.text_strong)
        pal.setColor(QPalette.HighlightedText, p.on_primary)
        # Fond des fenêtres natives (QMessageBox, QDialog « plain ») —
        # sans ces rôles, le fond reste le gris Fusion par défaut.
        pal.setColor(QPalette.Window, p.surface)
        pal.setColor(QPalette.Base, p.surface)
        pal.setColor(QPalette.AlternateBase, p.surface_variant)
        pal.setColor(QPalette.Button, p.surface_variant)
        pal.setColor(QPalette.ToolTipBase, p.surface_variant)
        pal.setColor(QPalette.ToolTipText, p.text_strong)
        pal.setColor(QPalette.PlaceholderText, p.text_soft)
        pal.setColor(QPalette.Link, p.primary)
        pal.setColor(QPalette.LinkVisited, p.primary)
        self._app.setPalette(pal)

    def _reapply(self):
        if self._app is None:
            return
        combined = ""
        if self._phibuilder is not None:
            combined += self._phibuilder.qss + "\n"
        combined += self._generate_global_qss()
        self._app.setStyleSheet(combined)

    def _generate_global_qss(self) -> str:
        _ds = _get_ds()
        p = self._theme.palette
        f = self._theme.fonts
        s = self.font_size
        d = self._theme.design
        return f"""
            QToolTip {{
                background: {p.surface_variant}; color: {p.text_strong};
                border: 1px solid {p.outline}; padding: {_ds.space_xxs}px;  /* 4px Fibo padding */
                font-size: {s(f.small)}px;
            }}
            QMessageBox, QDialog {{
                background-color: {p.surface};
            }}
            QMessageBox QLabel {{
                color: {p.text_strong}; background: transparent;
            }}
            QDialogButtonBox QPushButton {{
                height: {_ds.field_height}px; padding: 0 {_ds.space_md}px;
            }}
            QMenu {{
                background: {p.surface}; color: {p.text_strong};
                border: 1px solid {p.outline};
                font-size: {s(f.base)}px;
            }}
            QMenu::item:selected {{
                background: {p.primary_container}; color: {p.text_strong};
            }}
            QScrollBar:vertical {{
                background: {p.surface_variant}; width: 8px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {p.outline}; border-radius: {_ds.radius_xs}px; min-height: {_ds.space_lg - _ds.space_xxs // 2}px;  /* 30px */
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            {QssHelper.table(p, d, s)}

            /* Dialogues standards : le QSS phibuilder colore le texte de tous
               les QPushButton en on_primary (blanc) — sur QMessageBox,
               QColorDialog, QFileDialog le fond clair rendait les boutons
               invisibles (blanc sur blanc). Boutons primaires explicites. */
            QMessageBox, QColorDialog, QFileDialog, QInputDialog {{
                background: {p.surface};
            }}
            QMessageBox QPushButton, QColorDialog QPushButton,
            QFileDialog QPushButton, QInputDialog QPushButton {{
                background-color: {p.primary}; color: {p.on_primary};
                border: none; border-radius: {_ds.radius_sm}px;
                padding: {_ds.space_xs}px {_ds.space_md}px;
                font-size: {s(13)}px;
            }}
            QMessageBox QPushButton:hover, QColorDialog QPushButton:hover,
            QFileDialog QPushButton:hover, QInputDialog QPushButton:hover {{
                background-color: {p.primary_container}; color: {p.text_strong};
            }}
            QMessageBox QLabel, QColorDialog QLabel {{
                color: {p.text_strong};
            }}
        """


# ─── Sous-système P : Couleurs des programmes (PEI, MYP, DP, DPEn) ────────
# Les valeurs sont des noms de RÔLES (pas des couleurs) qui sont résolus
# dynamiquement depuis la palette active au moment de l'utilisation.
# Usage : PROGRAM_STYLES["PEI"] → ("primary", "primary_container", "on_primary")
# Chaque tuple = (rôle_fg, rôle_bg, rôle_on_fg)
PROGRAM_STYLES: dict[str, tuple[str, str, str]] = {
    "PYP":  ("primary",              "primary_container",         "on_primary"),
    "PP":   ("secondary",            "secondary_container",       "on_secondary"),
    "PEI":  ("primary",              "primary_container",         "on_primary"),
    "MYP":  ("secondary",            "secondary_container",       "on_secondary"),
    "DPFr": ("error",                "error_container",           "on_error"),
    "DPEn": ("tertiary",             "tertiary_container",        "on_tertiary"),
}

# ── Code couleur des types d'employés ────────────────────────────────
# 6 teintes Material distinctes, en DEUX DÉCLINAISONS par type :
#   "light" — thèmes clairs (blue, sobre, contrast) : badge mid-tone,
#             texte blanc, conteneur pastel
#   "dark"  — thème sombre : badge clair (tonalité 300), texte foncé,
#             conteneur sombre — même logique que les palettes du thème
# Chaque tuple = (badge, conteneur doux, texte sur badge).
# Clés alignées sur les flags larcauth_aecuser (type_director, etc.).
# Utilisé par LarcSuperviseur, LarcProf, LarcConfig, LarcSecretaire.
STAFF_TYPE_COLORS: dict[str, dict[str, tuple[str, str, str]]] = {
    "administrateur": {  # bleu — type_director
        "light": ("#1565C0", "#D1E4FF", "#FFFFFF"),
        "dark":  ("#64B5F6", "#1E3A5F", "#0D2137"),
    },
    "coordonnateur": {   # violet — type_coordonator
        "light": ("#7B1FA2", "#E1BEE7", "#FFFFFF"),
        "dark":  ("#CE93D8", "#4A148C", "#1A1A1A"),
    },
    "superviseur": {     # orange — type_supervisor
        "light": ("#EF6C00", "#FFE0B2", "#FFFFFF"),
        "dark":  ("#FFB74D", "#5C4300", "#3E2C00"),
    },
    "secretaire": {      # magenta — type_secretary
        "light": ("#AD1457", "#F8BBD0", "#FFFFFF"),
        "dark":  ("#F48FB1", "#5C1A45", "#2A0A1E"),
    },
    "professeur": {      # vert — type_teacher
        "light": ("#2E7D32", "#C8E6C9", "#FFFFFF"),
        "dark":  ("#81C784", "#2E5C2E", "#1B3A1B"),
    },
    "staff": {           # bleu turquoise foncé — non enseignant (aucun flag type_*)
        "light": ("#058B8C", "#B2DFDB", "#FFFFFF"),
        "dark":  ("#4DB6AC", "#004D40", "#00251F"),
    },
}

# Flags larcauth_aecuser → clé de type (ordre = hiérarchie)
ROLE_KEY_BY_FLAG: dict[str, str] = {
    "type_director": "administrateur",
    "type_coordonator": "coordonnateur",
    "type_supervisor": "superviseur",
    "type_secretary": "secretaire",
    "type_teacher": "professeur",
}


def staff_type_color(role_key: str) -> tuple[str, str, str]:
    """(badge, conteneur, texte) du type d'employé, DÉCLINÉ selon le thème actif.

    Thèmes clairs (blue, sobre, contrast) → variante "light" ;
    thème sombre (dark) → variante "dark". Résolu à l'appel — un badge
    relu au paint/restyle suit automatiquement le changement de thème.
    Clé inconnue → « staff » (rose).
    """
    variants = STAFF_TYPE_COLORS.get(role_key, STAFF_TYPE_COLORS["staff"])
    decl = "dark" if _IS_DARK_MAP.get(theme_manager.active_name, False) else "light"
    return variants[decl]


def staff_type_from_flags(flags: dict) -> str:
    """Déduit la clé de type depuis les flags larcauth_aecuser (type_director, …)."""
    for flag, key in ROLE_KEY_BY_FLAG.items():
        if flags.get(flag):
            return key
    return "staff"

# ── Code couleur des types d'erreur (LarcForge) ──────────────────────
# 10 catégories thématiques, même structure que STAFF_TYPE_COLORS :
#   "light" — badge mid-tone, texte blanc, conteneur pastel
#   "dark"  — badge clair (tonalité 300), texte foncé, conteneur sombre
# Chaque tuple = (badge, conteneur doux, texte sur badge).
# Clés alignées sur la taxonomie de larcforge/taxonomy.py (category_for()).
ERROR_CATEGORY_COLORS: dict[str, dict[str, tuple[str, str, str]]] = {
    "theme": {          # violet — R, D, REACT (QSS/couleurs/réactivité)
        "light": ("#7B1FA2", "#E1BEE7", "#FFFFFF"),
        "dark":  ("#CE93D8", "#4A148C", "#1A1A1A"),
    },
    "ui": {             # cyan — V (finitions visuelles)
        "light": ("#00838F", "#B2EBF2", "#FFFFFF"),
        "dark":  ("#4DD0E1", "#0B3B4A", "#062A36"),
    },
    "qt": {             # orange — S (anti-patterns PySide6)
        "light": ("#EF6C00", "#FFE0B2", "#FFFFFF"),
        "dark":  ("#FFB74D", "#5C4300", "#3E2C00"),
    },
    "checklist": {      # rouge — C (pré-soumission)
        "light": ("#C62828", "#FFCDD2", "#FFFFFF"),
        "dark":  ("#EF9A9A", "#7F1D1D", "#2A0A0A"),
    },
    "filesize": {       # brun — FS (taille / refactoring)
        "light": ("#6D4C41", "#D7CCC8", "#FFFFFF"),
        "dark":  ("#BCAAA4", "#3E2723", "#1A1A1A"),
    },
    "data": {           # bleu — DB (base de données)
        "light": ("#1565C0", "#D1E4FF", "#FFFFFF"),
        "dark":  ("#64B5F6", "#1E3A5F", "#0D2137"),
    },
    "auth": {           # indigo — AUTH (authentification)
        "light": ("#283593", "#C5CAE9", "#FFFFFF"),
        "dark":  ("#9FA8DA", "#1A237E", "#1A1A1A"),
    },
    "tests": {          # vert — COV / pytest (tests & couverture)
        "light": ("#2E7D32", "#C8E6C9", "#FFFFFF"),
        "dark":  ("#81C784", "#2E5C2E", "#1B3A1B"),
    },
    "runtime": {        # magenta — errorlog (erreurs d'application)
        "light": ("#AD1457", "#F8BBD0", "#FFFFFF"),
        "dark":  ("#F48FB1", "#5C1A45", "#2A0A1E"),
    },
    "build": {          # gris ardoise — larcforge:build (packaging)
        "light": ("#455A64", "#CFD8DC", "#FFFFFF"),
        "dark":  ("#90A4AE", "#37474F", "#1A1A1A"),
    },
}

_DEFAULT_ERROR_CATEGORY = "ui"


def error_category_color(cat: str) -> tuple[str, str, str]:
    """(badge, conteneur, texte) d'une catégorie d'erreur, décliné selon le thème.

    Même logique que staff_type_color() : résolu à l'appel, un badge relu au
    paint/restyle suit automatiquement le changement de thème. Catégorie
    inconnue → « ui ».
    """
    variants = ERROR_CATEGORY_COLORS.get(cat, ERROR_CATEGORY_COLORS[_DEFAULT_ERROR_CATEGORY])
    decl = "dark" if _IS_DARK_MAP.get(theme_manager.active_name, False) else "light"
    return variants[decl]


# Cache lazy pour ds (évite l'import circulaire theme.py ↔ design_system.py)
_ds_cache = None
def _get_ds():
    global _ds_cache
    if _ds_cache is None:
        from larccommon.design_system import ds
        _ds_cache = ds
    return _ds_cache


class QssHelper:
    """Shared QSS fragment generators — single source of truth for both apps.

    Usage: p = theme_manager.palette; d = theme_manager.design; s = theme_manager.font_size
    Note: radius tokens uses ds.radius_* (M3 shapes), spacing uses ds.space_* (Fibo+M3)
    """

    @staticmethod
    def top_bar(p, d) -> str:
        _ds = _get_ds()
        return (
            f"QFrame#top_bar {{ background: {p.surface}; color: {p.text_strong}; "
            f"border: 1px solid {p.outline_variant}; "
            f"border-radius: {_ds.radius_sm}px; }}"  # shape-small (8px) — Card-like
            # Boutons icône-only : pas de padding global (icône centrée)
            f"QPushButton#theme_btn, QPushButton#profile_btn, "
            f"QPushButton#refresh_btn {{ padding: 0; }}"
        )

    @staticmethod
    def panel(p, d) -> str:
        _ds = _get_ds()
        return (
            f"QFrame#panel {{ background: {p.surface}; color: {p.text_strong}; "
            f"border: 1px solid {p.outline_variant}; "
            f"border-radius: {_ds.radius_sm}px; }}"  # shape-small (8px) — Card
        )

    @staticmethod
    def panel_title(p, s, fs) -> str:
        return (
            f"QLabel#panel_title {{ color: {p.text_strong}; "
            f"font-size: {s(fs)}px; font-weight: bold; }}"
        )

    @staticmethod
    def push_button(p, d, s) -> str:
        _ds = _get_ds()
        return (
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: {_ds.radius_lg}px; padding: {d.btn_pad_v}px {d.btn_pad_h}px; "  # shape-large (16px) — Filled Button
            f"font-size: {s(13)}px; }}"  # label-large (13px) — M3
            f"QPushButton:hover {{ background: {p.primary_container}; border-color: {p.primary}; }}"
            f"QPushButton:pressed {{ background: {p.primary}; color: {p.on_primary}; }}"
        )

    @staticmethod
    def table(p, d, s) -> str:
        _ds = _get_ds()
        return (
            f"QTableWidget {{ background: {p.surface}; color: {p.text_strong}; "
            f"border: none; gridline-color: {p.outline_variant}; "
            f"font-size: {s(12)}px; }}"
            f"QTableWidget::item {{ "
            f"background: {p.surface}; "  # Force le fond des cellules (contre le QSS phibuilder)
            f"color: {p.text_strong}; "
            f"padding: {d.btn_sm_pad_v}px {_ds.space_xs}px; "
            f"border-bottom: 1px solid {p.outline_variant}; }}"  # Row separator + text color + bg
            f"QTableWidget::item:selected {{ "
            f"background: {p.primary_container}; color: {p.text_strong}; }}"  # Selected row
            f"QTableWidget::item:hover {{ "
            f"background: {p.primary_container}; }}"  # Hover row
            f"QHeaderView::section {{ "
            f"background: {p.surface_variant}; color: {p.text_strong}; "
            f"padding: {d.btn_sm_pad_v}px {_ds.space_xs}px; "
            f"font-weight: bold; border: none; "
            f"border-bottom: 2px solid {p.outline}; }}"  # Header separator
        )

    @staticmethod
    def combobox(p, d) -> str:
        _ds = _get_ds()
        return (
            f"QComboBox {{ background: {p.surface}; color: {p.text_strong}; "
            f"border: 1px solid {p.outline_variant}; border-radius: {_ds.radius_xs}px; "  # shape-extra-small (4px) — input-like
            f"padding: {d.field_pad_v}px {d.field_pad_h}px; }}"
            f"QComboBox:hover {{ border-color: {p.primary}; }}"
            f"QComboBox::drop-down {{ border: none; width: 20px; }}"
        )

    @staticmethod
    def period_btn(p, d) -> str:
        _ds = _get_ds()
        return (
            f"QPushButton#period_btn {{ min-width: {theme_manager.image.logo}px; max-width: {theme_manager.image.logo}px; height: {theme_manager.image.theme_btn}px; "
            f"font-size: {theme_manager.font_size(13)}px; font-weight: normal; "
            f"border: {d.btn_border * 2}px solid transparent; border-radius: {_ds.radius_lg}px; "  # shape-large (16px) — button
            f"padding: 0; background: {p.surface_variant}; color: {p.text_strong}; }}"
            f"QPushButton#period_btn:hover {{ background: {p.primary_container}; "
            f"border-color: {p.primary}; }}"
            f"QPushButton#period_btn:checked {{ background: {p.primary}; color: {p.on_primary}; "
            f"border: {d.btn_border * 2}px solid {p.primary}; font-weight: bold; }}"
            f"QPushButton#period_btn:focus {{ outline: 2px solid {p.primary}; outline-offset: 2px; }}"
        )

    @staticmethod
    def input_field(p, d) -> str:
        _ds = _get_ds()
        return (
            f"QLineEdit, QTextEdit, QPlainTextEdit {{ background: {p.surface}; "
            f"color: {p.text_strong}; border: 1px solid {p.outline_variant}; "
            f"border-radius: {_ds.radius_xs}px; padding: {d.field_pad_v}px {d.field_pad_h}px; }}"  # shape-extra-small (4px) — TextField
            f"QLineEdit:focus, QTextEdit:focus {{ border-color: {p.primary}; }}"
        )

    @staticmethod
    def kpi_common(p, d, s) -> str:
        _ds = _get_ds()
        return (
            f"QFrame#kpi_card {{ background: {p.surface}; border: 1px solid {p.outline_variant}; "
            f"border-radius: {_ds.radius_sm}px; padding: {_ds.space_xs}px; }}"  # shape-small (8px) — Card with border
            f"QLabel#kpi_value {{ font-size: {s(24)}px; font-weight: bold; color: {p.text_strong}; }}"
            f"QLabel#kpi_label {{ font-size: {s(10)}px; color: {p.text_strong}; }}"  # text_strong = lisibilité garantie dark comme light
            f"QFrame#kpi_small {{ background: {p.surface}; border: 1px solid {p.outline_variant}; "
            f"border-radius: {_ds.radius_sm}px; padding: {_ds.space_xxs}px; }}"  # Card with border
        )

    @staticmethod
    def sidebar_frame(p, d) -> str:
        return (
            f"QFrame#sidebar {{ background: {p.surface}; border: none; "
            f"border-right: 1px solid {p.outline_variant}; }}"
        )

    @staticmethod
    def phi_btn(p, d) -> str:
        _ds = _get_ds()
        return (
            f"QPushButton#phi_btn {{ font-size: {theme_manager.font_size(18)}px; border: 1px solid {p.outline_variant}; "
            f"border-radius: {_ds.radius_lg}px; background: {p.surface_variant}; color: {p.text_strong}; }}"  # shape-large (16px) — button
            f"QPushButton#phi_btn:checked {{ background: {p.primary}; color: {p.on_primary}; "
            f"border: {d.btn_border * 2}px solid {p.primary}; }}"
            f"QPushButton#phi_btn:focus {{ outline: 2px solid {p.primary}; outline-offset: 2px; }}"
        )

    @staticmethod
    def section_btn(p, d, s) -> str:
        """Alias vers sidebar_section_header (même style flat divider)."""
        return QssHelper.sidebar_section_header(p, d, s)

    @staticmethod
    def class_btn(p, d, s) -> str:
        _ds = _get_ds()
        return (
            f"QPushButton#class_btn {{ border: none; border-radius: {_ds.radius_sm}px; "  # shape-small (8px) — compact button
            f"text-align: left; padding: {_ds.space_xxs}px {d.field_pad_h}px; "  # 4px vertical padding
            f"font-size: {s(10)}px; }}"
            f"QPushButton#class_btn:hover {{ background: {p.primary_container}; }}"
            f"QPushButton#class_btn:checked {{ font-weight: bold; }}"
            f"QPushButton#class_btn:focus {{ outline: 2px solid {p.primary}; outline-offset: 2px; }}"
        )

    @staticmethod
    def sidebar_section_header(p, d, s) -> str:
        """QSS avec sélecteur #sidebar_sec_hdr — pour usage dans _STYLE (parent).
        Fond surface_variant pour se démarquer du fond surface du sidebar."""
        _ds = _get_ds()
        return (
            f"#sidebar_sec_hdr {{ background: {p.surface_variant}; border: none; "
            f"border-bottom: 2px solid {p.outline_variant}; font-weight: bold; "
            f"font-size: {s(12)}px; color: {p.text_strong}; text-align: center; "
            f"padding: {_ds.space_xxs}px {_ds.space_xxs // 2}px; }}"
            f"#sidebar_sec_hdr:hover {{ color: {p.primary}; "
            f"border-bottom: 2px solid {p.primary}; }}"
        )

    @staticmethod
    def sidebar_section_header_inline(p, s) -> str:
        """QSS sans sélecteur — pour setStyleSheet() DIRECT sur le widget.
        Fond surface_variant pour se démarquer du fond surface du sidebar."""
        _ds = _get_ds()
        return (
            f"background: {p.surface_variant}; border: none; "
            f"border-bottom: 2px solid {p.outline_variant}; font-weight: bold; "
            f"font-size: {s(12)}px; color: {p.text_strong}; text-align: center; "
            f"padding: {_ds.space_xxs}px {_ds.space_xxs // 2}px;"
        )

    @staticmethod
    def sidebar_program_header(p, d, s, fg: str, bg: str, on_fg: str) -> str:
        """QSS avec sélecteur #sidebar_prog_hdr — pour usage dans _STYLE (parent)."""
        _ds = _get_ds()
        return (
            f"#sidebar_prog_hdr {{ background: {fg}; color: {on_fg}; border: none; "
            f"border-radius: {_ds.radius_sm}px; font-weight: bold; "
            f"font-size: {s(11)}px; padding: {_ds.space_xxs - _ds.space_xxs // 4}px; }}"
            f"#sidebar_prog_hdr:hover {{ background: {bg}; color: {fg}; }}"
        )

    @staticmethod
    def sidebar_program_header_inline(p, s, fg: str, on_fg: str) -> str:
        """QSS sans sélecteur — pour setStyleSheet() DIRECT sur le widget."""
        _ds = _get_ds()
        return (
            f"background: {fg}; color: {on_fg}; border: none; "
            f"border-radius: {_ds.radius_sm}px; font-weight: bold; "
            f"font-size: {s(11)}px; padding: {_ds.space_xxs - _ds.space_xxs // 4}px;"
        )

    @staticmethod
    def sidebar_class_button(p, d, s, bg: str, fg: str) -> str:
        """QSS avec sélecteur #sidebar_class_btn — pour usage dans _STYLE (parent)."""
        _ds = _get_ds()
        return (
            f"#sidebar_class_btn {{ background: {bg}; color: {fg}; border: none; "
            f"border-radius: {_ds.radius_sm}px; font-size: {s(11)}px; padding: {_ds.space_xxs // 2}px {_ds.space_xxs}px; }}"
            f"#sidebar_class_btn:hover {{ background: {fg}; color: {bg}; }}"
            f"#sidebar_class_btn:checked {{ background: {fg}; color: {bg}; "
            f"border: 2px solid {fg}; }}"
        )

    @staticmethod
    def sidebar_class_button_inline(p, s, bg: str, fg: str) -> str:
        """QSS sans sélecteur — pour setStyleSheet() DIRECT sur le widget."""
        _ds = _get_ds()
        return (
            f"background: {bg}; color: {fg}; border: none; "
            f"border-radius: {_ds.radius_sm}px; font-size: {s(11)}px; padding: {_ds.space_xxs // 2}px {_ds.space_xxs}px;"
        )

    @staticmethod
    def sidebar_all_button(p, d, s) -> str:
        """QSS avec sélecteur #sidebar_all_btn — pour usage dans _STYLE (parent)."""
        _ds = _get_ds()
        return (
            f"#sidebar_all_btn {{ background: {p.primary}; color: {p.on_primary}; "
            f"border: none; border-radius: {_ds.radius_lg}px; font-weight: bold; "
            f"font-size: {s(11)}px; padding: {_ds.space_xs}px; }}"
            f"#sidebar_all_btn:hover {{ background: {p.active}; }}"
        )

    @staticmethod
    def sidebar_all_button_inline(p, s) -> str:
        """QSS sans sélecteur — pour setStyleSheet() DIRECT sur le widget."""
        _ds = _get_ds()
        return (
            f"background: {p.primary}; color: {p.on_primary}; "
            f"border: none; border-radius: {_ds.radius_lg}px; font-weight: bold; "
            f"font-size: {s(11)}px; padding: {_ds.space_xs}px;"
        )

    @staticmethod
    def sidebar_container(p) -> str:
        """Conteneur du sidebar (frame ou scrollarea)."""
        return (
            f"QWidget#sidebar {{ background: {p.surface}; border: none; "
            f"border-right: 1px solid {p.outline_variant}; }}"
        )

    @staticmethod
    def login_qss(p) -> str:
        _ds = _get_ds()
        return f"""
            QWidget#root {{ background: {p.background}; }}
            QLabel {{ font-size: {theme_manager.font_size(13)}px; color: {p.text_strong}; background: transparent; }}
            QTabWidget::pane {{
                border: 1px solid {p.outline_variant}; background: {p.surface};
                border-radius: {_ds.radius_sm}px;
            }}
            QTabBar::tab          {{ padding: {_ds.space_xs}px {_ds.space_sm}px; font-size: {theme_manager.font_size(13)}px; }}
            QTabBar::tab:selected {{
                background: {p.surface}; border-bottom: 2px solid {p.primary};
                color: {p.text_strong}; font-weight: bold;
            }}
            QTabBar::tab:!selected {{ background: {p.surface_variant}; color: {p.text_strong}; }}
            QLineEdit {{
                padding: {_ds.space_xs}px {_ds.space_xs}px; border: 1px solid {p.outline_variant};
                border-radius: {_ds.radius_sm}px; font-size: {theme_manager.font_size(13)}px; background: {p.surface};
                color: {p.text_strong};
            }}
            QLineEdit:focus {{ border-color: {p.primary}; }}
            QPushButton {{
                padding: {_ds.space_xs}px {_ds.space_sm}px; border: none; border-radius: {_ds.radius_sm}px;
                font-size: {theme_manager.font_size(13)}px; font-weight: bold; color: white;
            }}
            QPushButton#btnIntra  {{ background: {p.primary}; }}
            QPushButton#btnIntra:hover  {{ background: {p.active}; }}
            QPushButton#btnIntra:disabled  {{ background: {p.inactive}; }}
            QPushButton#btnGoogle {{ background: #DB4437; }}
            QPushButton#btnGoogle:hover {{ background: #C53929; }}
            QPushButton#btnGoogle:disabled {{ background: {p.inactive}; }}
            QPushButton#btnCloud {{ background: {p.primary}; }}
            QPushButton#btnCloud:hover {{ background: {p.active}; }}
            QLabel#errLabel {{ color: {p.error}; font-size: {theme_manager.font_size(13)}px; }}
            QLabel#hdrTitle {{ color: {p.text_strong}; font-size: {theme_manager.font_size(21)}px; font-weight: bold; }}
            QLabel#hdrSub   {{ color: {p.text_soft}; font-size: {theme_manager.font_size(13)}px; }}
            QLabel#infoLbl  {{ color: {p.text_soft}; font-size: {theme_manager.font_size(13)}px; }}
            QLabel#formLbl {{ color: {p.text_strong}; font-size: {theme_manager.font_size(13)}px; }}
        """


theme_manager = ThemeManager()
