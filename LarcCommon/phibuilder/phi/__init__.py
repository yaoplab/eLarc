"""Phi & Fibonacci: Fondation du design system LARC.

Modules:
- phi_scale.py: Générateur de tokens (spacing, sizing, sections)
- phi_grid.py: Layouts basés golden ratio
- m3_phi_bridge.py: Material Design 3 + Phi fusion
"""

# New Phi system (v2)
from phibuilder.phi.phi_scale import PhiScale, phi_scale
from phibuilder.phi.phi_grid import PhiGrid, GridLayout, SplitLayout
from phibuilder.phi.m3_phi_bridge import M3PhiBridge, M3ColorScheme, ColorGenerator

__all__ = [
    'PhiScale',
    'phi_scale',
    'PhiGrid',
    'GridLayout',
    'SplitLayout',
    'M3PhiBridge',
    'M3ColorScheme',
    'ColorGenerator',
]
