from dataclasses import dataclass
from phibuilder.phi.scale import PhiScale, SpacingToken
from phibuilder.theme.color import M3ColorScheme
from phibuilder.theme.typo import M3Typography, TypeStyle
from phibuilder.theme.shape import M3Shape, BorderRadius
from phibuilder.theme.elevation import M3Elevation, Shadow

@dataclass
class ThemeConfig:
    seed_color: str = "#6750A4"
    is_dark: bool = False
    contrast_level: float = 0.0
    variant: str = "tonal_spot"
    spec_version: str = "2025"
    font_family: str = "Roboto"

class Theme:
    def __init__(self, config: ThemeConfig | None = None):
        self.config = config or ThemeConfig()
        self.colors = M3ColorScheme(
            hex_color=self.config.seed_color, is_dark=self.config.is_dark,
            contrast_level=self.config.contrast_level, variant=self.config.variant,
            spec_version=self.config.spec_version)
        self.typo = M3Typography(family=self.config.font_family)
        self.spacing = PhiScale(base_spacing=4)
        self.shape = M3Shape
        self.elevation = M3Elevation
    def rebuild(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self.config, k):
                setattr(self.config, k, v)
        self.colors = M3ColorScheme(
            hex_color=self.config.seed_color, is_dark=self.config.is_dark,
            contrast_level=self.config.contrast_level, variant=self.config.variant,
            spec_version=self.config.spec_version)
        self.typo = M3Typography(family=self.config.font_family)
    def to_qss_vars(self) -> str:
        return "\n".join(f"  --md-sys-color-{name}: {hex_val};"
                         for name, hex_val in self.colors.all_colors.items())

__all__ = ["Theme", "ThemeConfig", "M3ColorScheme", "M3Typography", "TypeStyle",
           "M3Shape", "BorderRadius", "M3Elevation", "Shadow", "SpacingToken"]
