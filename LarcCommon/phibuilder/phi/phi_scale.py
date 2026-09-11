"""PhiScale: Générateur master de tous les tokens via Fibonacci (φ = 1.618).

Chaque spacing, sizing, et section est issu de la séquence Fibonacci.
Base: 4px. Ratio: 1.618 (golden ratio).

Fibonacci sequence: 4, 8, 12, 20, 32, 52, 84, 136, 220, 356...
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class SpacingTokens:
    """Spacing tokens générés via Fibonacci."""
    xxs: int = 4
    xs: int = 8
    sm: int = 12
    md: int = 20
    lg: int = 32
    xl: int = 52
    xxl: int = 84
    xxxl: int = 136


@dataclass
class SizingTokens:
    """Component heights/widths générées via Fibonacci."""
    xs: int = 40          # 10×4 (minimal)
    sm: int = 48          # 12×4
    base: int = 52        # F(6) — touch target base
    md: int = 64          # 16×4
    lg: int = 84          # F(7)
    xl: int = 128         # 32×4
    xxl: int = 144        # F(7) golden card width
    xxxl: int = 233       # F(8) golden card height
    huge: int = 377       # F(9) rare use


@dataclass
class SectionTokens:
    """Golden sections pour layouts (φ-based widths)."""
    golden_1: float = None      # 6.5px
    golden_2: float = None      # 10.5px
    golden_3: float = None      # 17px
    golden_4: float = None      # 27.5px
    golden_5: float = None      # 44.5px ≈ 45px (Fibonacci-ish)
    golden_6: float = None      # 72px (sidebar compact)
    golden_7: float = None      # 116px
    golden_8: float = None      # 188px (detail panel)
    golden_9: float = None      # 304px (content area)

    def __post_init__(self):
        """Calcule les sections golden à partir de base 4px."""
        base = 4
        phi = 1.618
        self.golden_1 = int(base * phi)
        self.golden_2 = int(base * (phi ** 2))
        self.golden_3 = int(base * (phi ** 3))
        self.golden_4 = int(base * (phi ** 4))
        self.golden_5 = int(base * (phi ** 5))
        self.golden_6 = int(base * (phi ** 6))
        self.golden_7 = int(base * (phi ** 7))
        self.golden_8 = int(base * (phi ** 8))
        self.golden_9 = int(base * (phi ** 9))


class PhiScale:
    """Master generator: Fibonacci tokens pour le design system."""

    BASE = 4                    # Pixel minimum
    PHI = 1.618                 # Golden ratio

    def __init__(self):
        """Initialise tous les tokens Fibonacci."""
        self.spacing = self._create_spacing()
        self.sizing = self._create_sizing()
        self.sections = self._create_sections()

    def _create_spacing(self) -> SpacingTokens:
        """Crée spacing tokens : 4, 8, 12, 20, 32, 52, 84, 136."""
        return SpacingTokens(
            xxs=4,      # F(0) base
            xs=8,       # F(1)
            sm=12,      # ~Fib (exact: 8+4)
            md=20,      # F(3) + F(2) = 12+8
            lg=32,      # F(4) + F(3) = 20+12
            xl=52,      # F(5) + F(4) = 32+20
            xxl=84,     # F(6) + F(5) = 52+32
            xxxl=136,   # F(7) + F(6) = 84+52
        )

    def _create_sizing(self) -> SizingTokens:
        """Crée component sizing tokens."""
        return SizingTokens(
            xs=40,          # 10×4 minimal
            sm=48,          # 12×4
            base=52,        # Touch target base (F ≈)
            md=64,          # 16×4
            lg=84,          # F(7)
            xl=128,         # 32×4
            xxl=144,        # Golden card (12×12 = 144)
            xxxl=233,       # Golden card height (F(8))
            huge=377,       # F(9)
        )

    def _create_sections(self) -> SectionTokens:
        """Crée golden section tokens via φ puissances."""
        return SectionTokens()

    def get_spacing(self, key: str) -> int:
        """Accès rapide: ds.phi.get_spacing('md') → 20."""
        return getattr(self.spacing, key, None)

    def get_sizing(self, key: str) -> int:
        """Accès rapide: ds.phi.get_sizing('card_height') → 233."""
        return getattr(self.sizing, key, None)

    def get_section(self, key: str) -> float:
        """Accès rapide: ds.phi.get_section('golden_6') → 72."""
        return getattr(self.sections, key, None)

    def golden_proportion(self, width: float, position: str = 'content') -> float:
        """Calcule proportion golden d'une largeur.

        Args:
            width: Largeur totale du container
            position: 'sidebar' (1/φ) ou 'content' (φ/(φ+1))

        Returns:
            Largeur calculée via golden ratio
        """
        if position == 'sidebar':
            return width * (1 / self.PHI)
        else:  # 'content'
            return width * (self.PHI / (self.PHI + 1))

    def __repr__(self) -> str:
        return (
            f"PhiScale(\n"
            f"  spacing={self.spacing},\n"
            f"  sizing={self.sizing},\n"
            f"  sections={self.sections}\n"
            f")"
        )


# Singleton instance
_phi_scale_instance = None


def phi_scale() -> PhiScale:
    """Accès singleton à PhiScale."""
    global _phi_scale_instance
    if _phi_scale_instance is None:
        _phi_scale_instance = PhiScale()
    return _phi_scale_instance
