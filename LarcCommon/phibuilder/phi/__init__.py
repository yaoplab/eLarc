from phibuilder.phi.constants import PHI, PHI_INV, PHI_SQUARED, SQRT5, Angle
from phibuilder.phi.sequence import fibonacci, fibonacci_sequence, is_fibonacci, nearest_fibonacci
from phibuilder.phi.scale import PhiScale, PhiSpacing, PhiTypography

class Phi:
    PHI = PHI
    PHI_INV = PHI_INV
    PHI_SQUARED = PHI_SQUARED
    fibonacci = staticmethod(fibonacci)
    fibonacci_sequence = staticmethod(fibonacci_sequence)
    is_fibonacci = staticmethod(is_fibonacci)
    nearest_fibonacci = staticmethod(nearest_fibonacci)
    Scale = PhiScale
    Spacing = PhiSpacing
    Typography = PhiTypography
    Angle = Angle

__all__ = [
    "Phi", "PHI", "PHI_INV", "PHI_SQUARED",
    "fibonacci", "fibonacci_sequence", "is_fibonacci", "nearest_fibonacci",
    "PhiScale", "PhiSpacing", "PhiTypography", "Angle",
]
