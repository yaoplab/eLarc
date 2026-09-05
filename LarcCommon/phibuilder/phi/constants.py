import math
from enum import IntEnum

SQRT5 = math.sqrt(5)
PHI = (1 + SQRT5) / 2
PHI_INV = 1 / PHI
PHI_SQUARED = PHI * PHI

class Angle(IntEnum):
    ZERO = 0
    PHI_DEG = 137
    PHI_DEG_COMPLEMENT = 222
    QUARTER_CIRCLE = 90
    HALF_CIRCLE = 180
    FULL_CIRCLE = 360
    @property
    def radians(self) -> float:
        return math.radians(self.value)
