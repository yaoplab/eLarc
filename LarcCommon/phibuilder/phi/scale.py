from enum import IntEnum
from phibuilder.phi.constants import PHI
from phibuilder.phi.sequence import fibonacci

# Rayon des boutons — M3 standard 8px (shape-medium)
RADIUS_BTN = 8

class SpacingToken(IntEnum):
    NONE = 0
    XXS = 1
    XS = 2
    SM = 3
    MD = 5
    LG = 8
    XL = 13
    XXL = 21
    XXXL = 34
    HUGE = 55
    GIANT = 89
    COLOSSAL = 144

class TypeToken(IntEnum):
    LABEL_SM = 11
    LABEL_MD = 12
    LABEL_LG = 14
    BODY_SM = 12
    BODY_MD = 14
    BODY_LG = 16
    TITLE_SM = 14
    TITLE_MD = 16
    TITLE_LG = 22
    HEADLINE_SM = 24
    HEADLINE_MD = 28
    HEADLINE_LG = 32
    DISPLAY_SM = 36
    DISPLAY_MD = 44
    DISPLAY_LG = 52

class PhiScale:
    def __init__(self, base_spacing: int = 4, base_font: int = 14):
        self.base_spacing = base_spacing
        self.base_font = base_font
    @property
    def fibonacci_spacing(self) -> list[int]:
        return [fibonacci(i) * self.base_spacing for i in range(0, 13)]
    @property
    def phi_typography(self) -> list[int]:
        return [round(self.base_font * (PHI ** i)) for i in range(-2, 9)]
    def spacing(self, token: SpacingToken) -> int:
        return int(token) * self.base_spacing
    def type_size(self, token: TypeToken) -> int:
        return int(token)

PhiSpacing = PhiScale
PhiTypography = PhiScale
