from dataclasses import dataclass
from enum import IntEnum

class FontWeight(IntEnum):
    THIN = 100; EXTRA_LIGHT = 200; LIGHT = 300; REGULAR = 400
    MEDIUM = 500; SEMI_BOLD = 600; BOLD = 700; EXTRA_BOLD = 800; BLACK = 900

@dataclass(frozen=True)
class TypeStyle:
    family: str = "Roboto"
    size: int = 14
    weight: FontWeight = FontWeight.REGULAR
    line_height: float = 1.5
    letter_spacing: float = 0.0

M3_TYPOGRAPHY = {
    "display_large":   TypeStyle(size=57, weight=FontWeight.REGULAR,  line_height=1.12, letter_spacing=-0.25),
    "display_medium":  TypeStyle(size=45, weight=FontWeight.REGULAR,  line_height=1.15, letter_spacing=0.0),
    "display_small":   TypeStyle(size=36, weight=FontWeight.REGULAR,  line_height=1.22, letter_spacing=0.0),
    "headline_large":  TypeStyle(size=32, weight=FontWeight.BOLD,     line_height=1.25, letter_spacing=0.0),
    "headline_medium": TypeStyle(size=28, weight=FontWeight.BOLD,     line_height=1.28, letter_spacing=0.0),
    "headline_small":  TypeStyle(size=24, weight=FontWeight.BOLD,     line_height=1.33, letter_spacing=0.0),
    "title_large":     TypeStyle(size=22, weight=FontWeight.BOLD,     line_height=1.27, letter_spacing=0.0),
    "title_medium":    TypeStyle(size=16, weight=FontWeight.MEDIUM,   line_height=1.50, letter_spacing=0.15),
    "title_small":     TypeStyle(size=14, weight=FontWeight.MEDIUM,   line_height=1.43, letter_spacing=0.1),
    "body_large":      TypeStyle(size=16, weight=FontWeight.REGULAR,  line_height=1.50, letter_spacing=0.5),
    "body_medium":     TypeStyle(size=14, weight=FontWeight.REGULAR,  line_height=1.43, letter_spacing=0.25),
    "body_small":      TypeStyle(size=12, weight=FontWeight.REGULAR,  line_height=1.33, letter_spacing=0.4),
    "label_large":     TypeStyle(size=14, weight=FontWeight.MEDIUM,   line_height=1.43, letter_spacing=0.1),
    "label_medium":    TypeStyle(size=12, weight=FontWeight.MEDIUM,   line_height=1.33, letter_spacing=0.5),
    "label_small":     TypeStyle(size=11, weight=FontWeight.MEDIUM,   line_height=1.45, letter_spacing=0.5),
}

class M3Typography:
    def __init__(self, family: str = "Roboto"):
        self.family = family
        self._styles = {name: TypeStyle(family=family, size=s.size, weight=s.weight,
                                        line_height=s.line_height, letter_spacing=s.letter_spacing)
                        for name, s in M3_TYPOGRAPHY.items()}
    def __getattr__(self, name: str) -> TypeStyle:
        key = name.replace("_", "_")
        if key in self._styles:
            return self._styles[key]
        raise AttributeError(f"No typography style '{name}'")
    @property
    def all(self) -> dict[str, TypeStyle]:
        return dict(self._styles)
    def qss_font(self, name: str) -> str:
        s = self._styles[name]
        return f"font-family: '{s.family}'; font-size: {s.size}px; font-weight: {s.weight}; letter-spacing: {s.letter_spacing}px;"
