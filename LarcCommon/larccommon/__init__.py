from larccommon.app_config import AppConfig
from larccommon.auth import (  # noqa: F401
    AuthManager,
    OAuth2Manager,
    _deduce_role,
    _deduce_role_superviseur,
    _load_active_term,
    _sha256_hex,
)
from larccommon.bootstrap import init_app  # noqa: F401
from larccommon.config_loader import find_cfg
from larccommon.database import Database, DBMode
from larccommon.error_reporting import get_reporter  # noqa: F401
from larccommon.event_helpers import event_color, event_icon  # noqa: F401
from larccommon.l10n import Translator, _  # noqa: F401
from larccommon.logger import (  # noqa: F401
    get_log_path, log, log_error, set_log_filename, set_log_to_file,
)
from larccommon.network import NetworkMode, detect_network  # noqa: F401
from larccommon.photos import ensure_cached, get_photo_path, get_uncached_ids  # noqa: F401
from larccommon.session import AuthResult, ConnMode, Session, UserRole
from larccommon.theme import DesignTokens, FontScale, Palette, QssHelper, Theme, ThemeManager
from larccommon.widgets import (
    CARD_THEMES,
    DEFAULT_CONFIG,
    PHI_COMPACT,
    PHI_LARGE,
    PHI_MEDIUM,
    CardConfig,
    FilePanel,
    FileResolver,
    FileViewer,
    StudentCard,
    TableSettings,
    fill_cards_grid,
    make_avatar,
)

__all__ = [
    "Database",
    "DBMode",
    "OAuth2Manager",
    "_deduce_role_superviseur",
    "_load_active_term",
    "Session",
    "UserRole",
    "ConnMode",
    "AuthResult",
    "find_cfg",
    "AppConfig",
    "log",
    "log_error",
    "init_app",
    "get_reporter",
    "set_log_to_file",
    "get_log_path",
    "set_log_filename",
    "NetworkMode",
    "detect_network",
    "get_photo_path",
    "ensure_cached",
    "get_uncached_ids",
    "ThemeManager",
    "Theme",
    "Palette",
    "FontScale",
    "DesignTokens",
    "QssHelper",
    "event_icon",
    "event_color",
    "Translator",
    "_",
    "StudentCard",
    "CardConfig",
    "make_avatar",
    "fill_cards_grid",
    "PHI_COMPACT",
    "PHI_MEDIUM",
    "PHI_LARGE",
    "CARD_THEMES",
    "DEFAULT_CONFIG",
    "FileViewer",
    "FilePanel",
    "FileResolver",
    "TableSettings",
]
