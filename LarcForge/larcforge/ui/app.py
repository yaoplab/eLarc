"""Point d'entrée de l'IHM LarcForge (PySide6, importé paresseusement)."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from larccommon.theme import theme_manager

from .main_window import MainWindow
from .profiles import ProfilesStore


def main(root, timeout: int = 300) -> int:
    """Lance la fenêtre LarcForge et entre dans la boucle d'événements.

    Pas d'init_app() : LarcForge surveille error_log — il ne doit pas
    s'y écrire lui-même. L'IHM démarre même sans base (c'est depuis
    Configuration qu'on répare l'accès DB).
    """
    app = QApplication(sys.argv)
    app.setApplicationName("LarcForge")
    app.setOrganizationName("Arc-en-Ciel")
    app.setStyle("Fusion")
    theme_manager.bind(app)  # réactivité thème (skill theme-reactivity)

    store = ProfilesStore()
    config = store.load()
    win = MainWindow(root=root, timeout=timeout, store=store, config=config)
    win.showMaximized()
    return app.exec()
