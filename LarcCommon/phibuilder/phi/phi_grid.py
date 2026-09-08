"""PhiGrid: Layouts basés sur proportions Fibonacci (golden sections).

Utilise PhiScale pour calculer dimensions et proportions
qui respectent le golden ratio (φ = 1.618).
"""

from dataclasses import dataclass
from typing import Tuple
from phibuilder.phi.phi_scale import phi_scale


@dataclass
class GridLayout:
    """Description d'un layout calculé."""
    cols: int
    card_width: int
    card_height: int
    gap: int
    margin: int


@dataclass
class SplitLayout:
    """Description d'un split sidebar/content."""
    sidebar_width: float
    content_width: float


class PhiGrid:
    """Calcule layouts adaptatifs via proportions Fibonacci."""

    PHI = 1.618

    @staticmethod
    def sidebar_content_split(total_width: float) -> SplitLayout:
        """Split container en sidebar + content via golden ratio.

        Sidebar = (φ-1)/φ = 1 - 1/φ ≈ 0.382 (38.2%)
        Content = 1/φ ≈ 0.618 (61.8%)
        Total = 1.0

        Args:
            total_width: Largeur totale du container

        Returns:
            SplitLayout avec dimensions calculées
        """
        # 1/φ ≈ 0.618 (proportion dorée)
        phi_inv = 1 / PhiGrid.PHI  # ≈ 0.618
        sidebar = total_width * (1 - phi_inv)  # ≈ 0.382
        content = total_width * phi_inv  # ≈ 0.618
        return SplitLayout(sidebar_width=sidebar, content_width=content)

    @staticmethod
    def card_grid_fibonacci(
        container_width: float,
        base_card_width: int = 144,
        gap: int = 20,
    ) -> GridLayout:
        """Grille de cards adaptative Fibonacci.

        Utilise 144px (F(7)) comme largeur de card de base.
        Ajuste nombre de colonnes selon container_width.

        Args:
            container_width: Largeur du container
            base_card_width: Largeur de base d'une card (défaut: 144px = F(7))
            gap: Espacement entre cards (défaut: 20px = Fibonacci)

        Returns:
            GridLayout avec cols, card_width, hauteur calculées
        """
        phi = phi_scale()
        card_height = 233  # F(8)

        # Calcule nombre de colonnes possibles
        available_width = container_width - 40  # Margin gauche/droit (2×20px)

        if available_width >= (3 * base_card_width + 2 * gap):
            cols = 3
            card_w = 144
        elif available_width >= (2 * base_card_width + gap):
            cols = 2
            card_w = 144
        else:
            cols = 1
            card_w = min(base_card_width, int(available_width))

        return GridLayout(
            cols=cols,
            card_width=card_w,
            card_height=card_height,
            gap=gap,
            margin=20,  # Fibonacci margin
        )

    @staticmethod
    def detail_panel_golden_width(window_width: float) -> float:
        """Calcule largeur de detail panel en golden section droite.

        Utilise le ratio φ/(φ+1) pour la largeur du panel de détail.

        Args:
            window_width: Largeur totale de la fenêtre

        Returns:
            Largeur calculée pour le detail panel
        """
        # Detail panel = ~38.2% de content area (1/φ)
        # Content area = 61.8% de total (φ/(φ+1))
        # → Detail = 61.8% × 61.8% ≈ 38% du total
        return window_width * (1 / PhiGrid.PHI) * (PhiGrid.PHI / (PhiGrid.PHI + 1))

    @staticmethod
    def sidebar_compact_expanded() -> Tuple[int, int]:
        """Retourne largeurs compact et expanded du sidebar.

        Returns:
            (compact_width, expanded_width) en pixels Fibonacci
        """
        phi = phi_scale()
        # Compact: golden_5 ≈ 45px
        # Expanded: golden_6 ≈ 72px
        return (
            int(phi.sections.golden_5),
            int(phi.sections.golden_6),
        )

    @staticmethod
    def modal_golden_size(base_width: int = 500) -> Tuple[int, int]:
        """Taille d'une modale/dialog en proportions golden.

        Args:
            base_width: Largeur de base (défaut: 500px)

        Returns:
            (width, height) calculées via golden ratio
        """
        phi = PhiGrid.PHI
        width = base_width
        height = int(width / phi)  # Hauteur = largeur/φ
        return (width, height)

    @staticmethod
    def three_column_layout(total_width: float) -> dict:
        """Layout 3 colonnes avec sections Fibonacci.

        Colonne gauche (sidebar): 1/φ
        Colonne centre (content): φ/(2φ+1) ≈ 0.382 aussi
        Colonne droite (detail): 1/φ

        Args:
            total_width: Largeur totale

        Returns:
            Dict avec 'left', 'center', 'right' widths
        """
        left = total_width * (1 / PhiGrid.PHI)
        right = left
        center = total_width - left - right
        return {
            'left': left,
            'center': center,
            'right': right,
        }
