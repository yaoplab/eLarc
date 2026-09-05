from materialyoucolor.hct import Hct
from materialyoucolor.dynamiccolor.material_dynamic_colors import MaterialDynamicColors
from materialyoucolor.dynamiccolor.color_spec import COLOR_NAMES
from materialyoucolor.scheme.scheme_tonal_spot import SchemeTonalSpot
from materialyoucolor.scheme.scheme_expressive import SchemeExpressive
from materialyoucolor.scheme.scheme_fidelity import SchemeFidelity
from materialyoucolor.scheme.scheme_monochrome import SchemeMonochrome
from materialyoucolor.scheme.scheme_neutral import SchemeNeutral
from materialyoucolor.scheme.scheme_vibrant import SchemeVibrant
from materialyoucolor.scheme.scheme_rainbow import SchemeRainbow
from materialyoucolor.scheme.scheme_fruit_salad import SchemeFruitSalad
from materialyoucolor.scheme.scheme_content import SchemeContent

_VARIANT_MAP = {
    "tonal_spot": SchemeTonalSpot, "expressive": SchemeExpressive,
    "fidelity": SchemeFidelity, "monochrome": SchemeMonochrome,
    "neutral": SchemeNeutral, "vibrant": SchemeVibrant,
    "rainbow": SchemeRainbow, "fruit_salad": SchemeFruitSalad, "content": SchemeContent,
}

class M3ColorScheme:
    def __init__(self, hex_color: str = "#6750A4", is_dark: bool = False,
                 contrast_level: float = 0.0, variant: str = "tonal_spot",
                 spec_version: str = "2025"):
        argb = _hex_to_argb(hex_color)
        self.source_hct = Hct.from_int(argb)
        self.is_dark = is_dark
        self.contrast_level = contrast_level
        self.variant = variant
        self.spec_version = spec_version
        self._scheme = self._build()
        self._mdc = MaterialDynamicColors(spec=spec_version)
    def _build(self):
        scheme_cls = _VARIANT_MAP.get(self.variant, SchemeTonalSpot)
        return scheme_cls(source_color_hct=self.source_hct, is_dark=self.is_dark,
                          contrast_level=self.contrast_level, spec_version=self.spec_version)
    def rebuild(self, **kwargs):
        for k, v in kwargs.items():
            if k == "hex_color":
                self.source_hct = Hct.from_int(_hex_to_argb(v))
            else:
                setattr(self, k, v)
        self._scheme = self._build()
    def get_hex(self, color_name: str) -> str:
        dc = getattr(self._mdc, color_name, None)
        if not dc:
            return "#000000"
        hexv = dc.get_hex(self._scheme)
        # materialyoucolor renvoie "#RRGGBBAA" (alpha en dernier), mais Qt QSS
        # attend "#AARRGGBB" (alpha en premier). Un 8-chiffres RRGGBBAA est donc
        # mal interprété : le premier octet devient l'OPACITÉ (ex. #2F323AFF →
        # alpha 18 %, texte bleu translucide illisible sur les dialogues).
        # Les couleurs étant opaques, on renvoie le 6-chiffres #RRGGBB.
        return hexv[:7] if len(hexv) >= 7 else hexv
    def get_argb(self, color_name: str) -> int:
        dc = getattr(self._mdc, color_name, None)
        return dc.get_argb(self._scheme) if dc else 0
    def get_rgba(self, color_name: str) -> list:
        dc = getattr(self._mdc, color_name, None)
        return dc.get_rgba(self._scheme) if dc else [0, 0, 0, 255]
    @property
    def all_colors(self) -> dict[str, str]:
        return {name: self.get_hex(name) for name in COLOR_NAMES}
    def __getattr__(self, name: str) -> str:
        m3_name = name[0] + "".join(p.capitalize() for p in name.split("_")[1:]) if "_" in name else name
        try:
            return self.get_hex(m3_name)
        except (AttributeError, KeyError):
            raise AttributeError(f"'M3ColorScheme' has no attribute '{name}'")
    @property
    def primary(self): return self.get_hex("primary")
    @property
    def on_primary(self): return self.get_hex("onPrimary")
    @property
    def primary_container(self): return self.get_hex("primaryContainer")
    @property
    def on_primary_container(self): return self.get_hex("onPrimaryContainer")
    @property
    def secondary(self): return self.get_hex("secondary")
    @property
    def on_secondary(self): return self.get_hex("onSecondary")
    @property
    def secondary_container(self): return self.get_hex("secondaryContainer")
    @property
    def surface(self): return self.get_hex("surface")
    @property
    def on_surface(self): return self.get_hex("onSurface")
    @property
    def surface_variant(self): return self.get_hex("surfaceVariant")
    @property
    def on_surface_variant(self): return self.get_hex("onSurfaceVariant")
    @property
    def background(self): return self.get_hex("background")
    @property
    def on_background(self): return self.get_hex("onBackground")
    @property
    def error(self): return self.get_hex("error")
    @property
    def on_error(self): return self.get_hex("onError")
    @property
    def error_container(self): return self.get_hex("errorContainer")
    @property
    def outline(self): return self.get_hex("outline")
    @property
    def outline_variant(self): return self.get_hex("outlineVariant")
    @property
    def surface_container_highest(self): return self.get_hex("surfaceContainerHighest")
    @property
    def surface_container(self): return self.get_hex("surfaceContainer")
    @property
    def surface_container_low(self): return self.get_hex("surfaceContainerLow")
    @property
    def inverse_surface(self): return self.get_hex("inverseSurface")
    @property
    def inverse_on_surface(self): return self.get_hex("inverseOnSurface")
    @property
    def inverse_primary(self): return self.get_hex("inversePrimary")

def _hex_to_argb(hex_color: str) -> int:
    return int("ff" + hex_color.lstrip("#"), 16)
