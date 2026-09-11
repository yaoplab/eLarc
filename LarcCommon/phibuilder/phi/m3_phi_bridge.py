"""M3PhiBridge: Fusion Material Design 3 colors + Phi structure.

Material Design 3 fournit les couleurs (Light/Dark/HighContrast).
Phi fournit les proportions et le rhythm (espacement, sizing).
"""

from dataclasses import dataclass
from typing import Dict, Any
from phibuilder.phi.phi_scale import phi_scale


@dataclass
class M3ColorScheme:
    """Material Design 3 color scheme (un thème)."""
    # Primary colors
    primary: str
    on_primary: str
    primary_container: str
    on_primary_container: str

    # Secondary colors
    secondary: str
    on_secondary: str
    secondary_container: str
    on_secondary_container: str

    # Tertiary colors
    tertiary: str
    on_tertiary: str
    tertiary_container: str
    on_tertiary_container: str

    # Neutral colors
    surface: str
    on_surface: str
    surface_dim: str
    surface_bright: str
    surface_container_lowest: str
    surface_container_low: str
    surface_container: str
    surface_container_high: str
    surface_container_highest: str

    # Background
    background: str
    on_background: str

    # Error colors
    error: str
    on_error: str
    error_container: str
    on_error_container: str

    # Outline colors
    outline: str
    outline_variant: str
    inverse_on_surface: str
    inverse_surface: str
    inverse_primary: str

    # Status/utility (non M3 standard mais utile)
    success: str = "#4CAF50"
    warning: str = "#FFC107"
    info: str = "#2196F3"


class ColorGenerator:
    """Génère Material Design 3 palettes Light/Dark/HighContrast."""

    PHI = 1.618

    @staticmethod
    def lighten(hex_color: str, percent: float) -> str:
        """Éclaircit une couleur hex."""
        # Simplifié: convertit hex → RGB, augmente luminance
        r, g, b = ColorGenerator._hex_to_rgb(hex_color)
        factor = 1 + (percent / 100)
        r = min(255, int(r * factor))
        g = min(255, int(g * factor))
        b = min(255, int(b * factor))
        return ColorGenerator._rgb_to_hex(r, g, b)

    @staticmethod
    def darken(hex_color: str, percent: float) -> str:
        """Assombrit une couleur hex."""
        r, g, b = ColorGenerator._hex_to_rgb(hex_color)
        factor = 1 - (percent / 100)
        r = max(0, int(r * factor))
        g = max(0, int(g * factor))
        b = max(0, int(b * factor))
        return ColorGenerator._rgb_to_hex(r, g, b)

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple:
        """Convertit #RRGGBB → (R, G, B)."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    @staticmethod
    def _rgb_to_hex(r: int, g: int, b: int) -> str:
        """Convertit (R, G, B) → #RRGGBB."""
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def generate_light_palette(brand_color: str) -> M3ColorScheme:
        """Génère palette Light theme à partir d'une couleur brand."""
        return M3ColorScheme(
            # Primary (brand color)
            primary=brand_color,
            on_primary="#FFFFFF",
            primary_container=ColorGenerator.lighten(brand_color, 40),
            on_primary_container=ColorGenerator.darken(brand_color, 80),

            # Secondary (derived)
            secondary=ColorGenerator.lighten(brand_color, 30),
            on_secondary="#FFFFFF",
            secondary_container=ColorGenerator.lighten(brand_color, 50),
            on_secondary_container=ColorGenerator.darken(brand_color, 70),

            # Tertiary
            tertiary=ColorGenerator.darken(brand_color, 20),
            on_tertiary="#FFFFFF",
            tertiary_container=ColorGenerator.lighten(brand_color, 60),
            on_tertiary_container=ColorGenerator.darken(brand_color, 90),

            # Neutral/Surface (Light)
            surface="#FFFBFE",
            on_surface="#1C1B1F",
            surface_dim="#DDD6DE",
            surface_bright="#FFFBFE",
            surface_container_lowest="#FFFFFF",
            surface_container_low="#F7F2F6",
            surface_container="#F3EEF1",
            surface_container_high="#ECE6F0",
            surface_container_highest="#E6E0E9",

            # Background
            background="#FFFBFE",
            on_background="#1C1B1F",

            # Error
            error="#B3261E",
            on_error="#FFFFFF",
            error_container="#F9DEDC",
            on_error_container="#410E0B",

            # Outline
            outline="#79747E",
            outline_variant="#CAC7D0",
            inverse_on_surface="#F4EFF4",
            inverse_surface="#313033",
            inverse_primary=ColorGenerator.lighten(brand_color, 80),
        )

    @staticmethod
    def generate_dark_palette(brand_color: str) -> M3ColorScheme:
        """Génère palette Dark theme à partir d'une couleur brand."""
        return M3ColorScheme(
            # Primary (more vibrant in dark)
            primary=ColorGenerator.lighten(brand_color, 60),
            on_primary="#000000",
            primary_container=ColorGenerator.darken(brand_color, 60),
            on_primary_container=ColorGenerator.lighten(brand_color, 90),

            # Secondary
            secondary=ColorGenerator.lighten(brand_color, 50),
            on_secondary="#000000",
            secondary_container=ColorGenerator.darken(brand_color, 50),
            on_secondary_container=ColorGenerator.lighten(brand_color, 80),

            # Tertiary
            tertiary=ColorGenerator.lighten(brand_color, 40),
            on_tertiary="#000000",
            tertiary_container=ColorGenerator.darken(brand_color, 40),
            on_tertiary_container=ColorGenerator.lighten(brand_color, 70),

            # Neutral/Surface (Dark)
            surface="#1C1B1F",
            on_surface="#E6E0E9",
            surface_dim="#0F0E12",
            surface_bright="#2B2930",
            surface_container_lowest="#0F0E12",
            surface_container_low="#1A1822",
            surface_container="#1E192B",
            surface_container_high="#48454E",
            surface_container_highest="#49454E",

            # Background
            background="#1C1B1F",
            on_background="#E6E0E9",

            # Error
            error="#F2B8B5",
            on_error="#601410",
            error_container="#8C1D18",
            on_error_container="#F9DEDC",

            # Outline
            outline="#99989D",
            outline_variant="#49454E",
            inverse_on_surface="#1C1B1F",
            inverse_surface="#E6E0E9",
            inverse_primary=ColorGenerator.darken(brand_color, 50),
        )

    @staticmethod
    def generate_hc_palette(brand_color: str) -> M3ColorScheme:
        """Génère palette High Contrast (WCAG AAA optimized)."""
        return M3ColorScheme(
            # Contrast max: black/white primary
            primary="#000000",
            on_primary="#FFFFFF",
            primary_container="#000000",
            on_primary_container="#FFFFFF",

            # Secondary
            secondary="#000000",
            on_secondary="#FFFFFF",
            secondary_container="#000000",
            on_secondary_container="#FFFFFF",

            # Tertiary
            tertiary="#000000",
            on_tertiary="#FFFFFF",
            tertiary_container="#000000",
            on_tertiary_container="#FFFFFF",

            # Neutral (pure contrast)
            surface="#FFFFFF",
            on_surface="#000000",
            surface_dim="#FFFFFF",
            surface_bright="#FFFFFF",
            surface_container_lowest="#FFFFFF",
            surface_container_low="#FFFFFF",
            surface_container="#FFFFFF",
            surface_container_high="#F0F0F0",
            surface_container_highest="#E8E8E8",

            # Background
            background="#FFFFFF",
            on_background="#000000",

            # Error (high contrast red)
            error="#CC0000",
            on_error="#FFFFFF",
            error_container="#CC0000",
            on_error_container="#FFFFFF",

            # Outline
            outline="#000000",
            outline_variant="#000000",
            inverse_on_surface="#FFFFFF",
            inverse_surface="#000000",
            inverse_primary="#FFFFFF",
        )


class M3PhiBridge:
    """Fusion Material Design 3 colors + Phi structure."""

    def __init__(self, brand_color: str):
        """Initialise bridge avec couleur brand.

        Args:
            brand_color: Couleur primaire en hex (ex: "#0066CC")
        """
        self.brand_color = brand_color
        self.phi = phi_scale()

        # Génère palettes M3
        self.colors_light = ColorGenerator.generate_light_palette(brand_color)
        self.colors_dark = ColorGenerator.generate_dark_palette(brand_color)
        self.colors_hc = ColorGenerator.generate_hc_palette(brand_color)

    def generate_theme(self, mode: str = 'light') -> Dict[str, Any]:
        """Combine couleurs M3 + tokens Phi.

        Args:
            mode: 'light', 'dark', ou 'hc' (high_contrast)

        Returns:
            Dict complet du thème (colors + tokens)
        """
        if mode == 'light':
            colors = self.colors_light
        elif mode == 'dark':
            colors = self.colors_dark
        elif mode in ['hc', 'high_contrast']:
            colors = self.colors_hc
        else:
            raise ValueError(f"Mode inconnu: {mode}")

        return {
            'mode': mode,
            'colors': colors,
            'spacing': self.phi.spacing,
            'sizing': self.phi.sizing,
            'sections': self.phi.sections,
        }

    def get_all_themes(self) -> Dict[str, Dict[str, Any]]:
        """Génère tous les thèmes (Light, Dark, HighContrast)."""
        return {
            'light': self.generate_theme('light'),
            'dark': self.generate_theme('dark'),
            'high_contrast': self.generate_theme('hc'),
        }
