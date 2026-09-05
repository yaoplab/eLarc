"""Test de démarrage — bootstrap.init_app (télémétrie).

Garde-fou contre le scénario « tests verts, app morte » : tout chemin de
démarrage cassé (imports locaux shadowés, hooks, lock, reporter) doit
échouer ICI, dans pytest — pas au lancement de l'app.

Rappel (2026-08-30) : le patch RERR avait inséré 17 imports locaux
`from larccommon.error_reporting import get_reporter` dans les handlers
de bootstrap.py — chaque import local rendait `get_reporter` local à sa
fonction → UnboundLocalError dans init_app au démarrage de LarcSuperviseur.
Aucun test n'exécutait init_app → 195 tests verts, app morte.
"""

import pytest

from larccommon import bootstrap


def test_init_app_execute_sans_exception():
    """Le chemin réel du démarrage (défauts identiques à main.py) ne lève pas."""
    rep = bootstrap.init_app("test")  # qt=True, check_updates=True (défauts)
    assert rep is not None


def test_init_app_idempotent():
    """Deux appels successifs ne lèvent pas (init_app est idempotent)."""
    bootstrap.init_app("test")
    bootstrap.init_app("test")


def test_init_app_qt_false():
    """Variante sans Qt (scripts, tests headless)."""
    bootstrap.init_app("test", qt=False, check_updates=False)


def test_get_reporter_global_jamais_none():
    """Le reporter global est toujours disponible après init_app."""
    from larccommon.error_reporting import get_reporter
    rep = get_reporter()
    assert rep is not None
    assert hasattr(rep, "report_exception")
