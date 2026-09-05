"""Interface graphique de contrôle LarcForge (dashboard PySide6).

AUCUN import PySide6 au niveau module : la CLI reste fonctionnelle sans
l'extra « gui ». L'import paresseux est fait dans run_ui() / app.main().
"""

from __future__ import annotations

__all__ = ["run_ui"]


def run_ui(root, timeout: int = 300) -> int:
    """Point d'entrée de l'IHM (appelé par la CLI). PySide6 importé ici."""
    from .app import main

    return main(root, timeout)
