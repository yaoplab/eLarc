"""Fixtures de test Phase 1 — LarcSuperviseur.

Mock complet de larccommon.database.db + larccommon.session.session
pour exécuter les tests sans PostgreSQL.

Usage :
    pytest tests/ -v -m "not integration"
"""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest


def _rebind_from_import(attr: str, mock: MagicMock):
    """Re-lie `attr` (db/session) vers le vrai objet dans tous les modules
    qui référencent encore le mock (bindings `from X import db` capturés
    pendant un import sous patch)."""
    import sys

    if attr == "db":
        from larccommon.database import db as real_obj
    else:
        from larccommon.session import session as real_obj

    for mod in list(sys.modules.values()):
        try:
            if getattr(mod, attr, None) is mock:
                setattr(mod, attr, real_obj)
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass


# ---------------------------------------------------------------------------
# Doublures de session
# ---------------------------------------------------------------------------

class _FakeUserRole:
    SUPERVISEUR = "SUPERVISEUR"
    PROF = "PROF"
    COORD = "COORD"
    SECR = "SECR"
    ADMIN = "ADMIN"


class _FakeConnMode:
    INTRANET = "Intranet"
    CLOUD = "Cloud"
    OFFLINE = "Hors connexion"


@pytest.fixture
def mock_session():
    """Remplace la session par un mock avec valeurs par défaut.

    ATTENTION : on patch le MÊME mock à plusieurs niveaux d'import, car
    `from X import session` binde la référence à l'import. Les modules
    déjà chargés (ex. event_actions importé par le fixture mock_db)
    gardent l'ancienne référence si on ne patch que la source.
    """
    mock = MagicMock()
    mock.user_id = 1
    mock.email = "test@arc-en-ciel.org"
    mock.full_name = "Test User"
    mock.role = MagicMock()
    mock.role.value = _FakeUserRole.SUPERVISEUR
    mock.conn_mode = _FakeConnMode.INTRANET
    mock.is_authenticated = True
    mock.term_id = 1
    mock.term_label = "Trimestre 1"
    mock.fk_language = 2
    mock.theme_pref = "blue"
    mock.card_theme = "medium"
    targets = [
        "LarcSuperviseur.common.session.session",
        "LarcSuperviseur.views.core.event_actions.session",
        "LarcSuperviseur.views.core.data_loader.session",
        "LarcSuperviseur.views.main_events.session",
        "LarcSuperviseur.views.main_group.session",
        "LarcSuperviseur.views.main_students.session",
    ]
    with ExitStack() as stack:
        for t in targets:
            stack.enter_context(patch(t, mock))
        yield mock
    _rebind_from_import("session", mock)


# ---------------------------------------------------------------------------
# Doublure de Database
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Remplace db par un MagicMock complet, patché à tous les niveaux d'import.

    ATTENTION : on patch TROIS cibles avec le MÊME objet mock, car Python
    crée une COPIE de la référence au moment du `from X import db` dans
    chaque module. Si on ne patch qu'un niveau, les modules déjà chargés
    dans sys.modules gardent l'ancienne référence.

    Cibles patchées :
    1. LarcSuperviseur.common.database.db       — source (re-export)
    2. LarcSuperviseur.views.core.data_loader.db — cache import (DataLoader)
    3. larccommon.database.db                    — racine (larccommon)

    Le mock expose :
    - db.server_conn          → MagicMock avec cursor()
    - db.mode                 → DBMode.INTRANET
    - db.server_mode          → DBMode.INTRANET
    - db.is_server_connected  → True
    - db.connect_intranet()   → True
    - db.connect_cloud()      → True
    """
    mock = MagicMock()

    # Configuration du mock
    fake_conn = MagicMock()
    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = None
    fake_cursor.fetchall.return_value = []
    fake_conn.cursor.return_value = fake_cursor
    fake_conn.closed = False
    fake_conn.commit = MagicMock()
    fake_conn.rollback = MagicMock()
    mock.server_conn = fake_conn

    mock.DBMode = type("DBMode", (), {"INTRANET": 1, "CLOUD": 2, "NONE": 0})()
    mock.mode = mock.DBMode.INTRANET
    mock.server_mode = mock.DBMode.INTRANET
    mock.is_server_connected = True
    mock.connect_intranet.return_value = True
    mock.connect_cloud.return_value = True
    mock.disconnect_all.return_value = None

    # Patcher les 3 niveaux d'import avec le MÊME mock
    targets = [
        "LarcSuperviseur.common.database.db",
        "LarcSuperviseur.views.core.data_loader.db",
        "LarcSuperviseur.views.core.event_actions.db",
        "LarcSuperviseur.views.main_events.db",
        "LarcSuperviseur.views.main_group.db",
        "LarcSuperviseur.views.main_students.db",
        "larccommon.database.db",
    ]
    with ExitStack() as stack:
        for t in targets:
            stack.enter_context(patch(t, mock))
        yield mock
    # Réparer les bindings from-import pollués : les modules importés PENDANT
    # le patch ont bindé le mock (`from X import db`) ; patch() restaure
    # l'attribut source mais pas ces bindings. On re-lie tous les modules
    # qui référencent encore ce mock vers le vrai db (tests d'intégration
    # real_db et tests suivants avec un nouveau mock).
    _rebind_from_import("db", mock)


# ---------------------------------------------------------------------------
# Doublure de theme_manager
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_theme():
    """Mock léger de LarcSuperviseur.common.theme.theme_manager — évite PySide6/Qt.

    ATTENTION : on patch le re-export LarcSuperviseur.common.theme.theme_manager,
    PAS larccommon.theme.theme_manager.
    """
    with patch("LarcSuperviseur.common.theme.theme_manager") as mock:
        mock.palette = MagicMock()
        mock.palette.primary = "#1976d2"
        mock.palette.on_primary = "#ffffff"
        mock.palette.primary_container = "#bbdefb"
        mock.palette.secondary = "#455A64"
        mock.palette.error = "#d32f2f"
        mock.palette.surface = "#fafafa"
        mock.palette.surface_variant = "#e0e0e0"
        mock.palette.background = "#f5f5f5"
        mock.palette.text_strong = "#212121"
        mock.palette.text_soft = "#757575"
        mock.palette.text_disabled = "#bdbdbd"
        mock.palette.success = "#388e3c"
        mock.palette.active = "#1565c0"
        mock.palette.outline_variant = "#c8c8c8"

        mock.design = MagicMock()
        mock.design.radius = 8
        mock.design.radius_lg = 12
        mock.design.spacing = 8

        mock.image = MagicMock()
        mock.image.logo = 89
        mock.image.theme_btn = 40
        mock.image.icon_btn = 18
        mock.image.icon_menu = 20
        mock.image.field_height = 40
        mock.image.profile_btn = 60

        mock.font_size = MagicMock()
        mock.font_size.return_value = 14

        mock.set_active.return_value = None

        yield mock
