"""UpdateManager — mise à jour douce des apps (R3). Cœur SANS Qt.

Registre : table DB app_version (version distante par app/channel) vs
D:\\projets\\VERSION (version locale, lue par bootstrap.current_app_version).
Ne lève jamais ; offline → check() retourne None.
"""
import json
import os
from dataclasses import dataclass
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
LARCCOMMON_ROOT = os.path.normpath(os.path.join(_HERE, '..'))
RUNTIME_DIR = os.path.join(LARCCOMMON_ROOT, 'runtime')
PENDING_FILE = os.path.join(RUNTIME_DIR, 'pending_update.json')


@dataclass
class UpdateInfo:
    app_name: str
    current: str
    target: str
    channel: str = 'stable'
    notes: str = ''
    published_at: str = ''


def _version_tuple(v: str) -> tuple:
    parts = []
    for p in (v or '').split('.'):
        try:
            parts.append(int(p))
        except ValueError:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            parts.append(0)
    return tuple(parts)


class UpdateManager:
    def __init__(self, app_name: str, current_version: str,
                 config: Optional[dict] = None) -> None:
        self._app_name = app_name
        self._current = current_version
        self._cfg = config or {}
        self._enabled = str(self._cfg.get('Enabled', 'false')).lower() == 'true'
        self._silent = str(self._cfg.get('Silent', 'false')).lower() == 'true'
        self._channel = str(self._cfg.get('Channel', 'stable'))

    # -- lecture --------------------------------------------------------
    def check(self) -> Optional[UpdateInfo]:
        """Version distante (app_version) vs locale — offline → None."""
        if not self._enabled:
            return None
        try:
            from .database import db
            conn = db.server_conn
            if conn is None:
                return None
            cur = conn.cursor()
            cur.execute(
                "SELECT version, channel, notes, published_at FROM app_version "
                "WHERE app_name = %s AND channel = %s",
                (self._app_name, self._channel))
            row = cur.fetchone()
            if not row:
                return None
            target = row[0] or ''
            if not target or _version_tuple(target) <= _version_tuple(self._current):
                return None
            return UpdateInfo(self._app_name, self._current, target,
                              row[1] or self._channel, row[2] or '',
                              str(row[3]) if row[3] else '')
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return None

    def silent(self) -> bool:
        return self._silent

    def enabled(self) -> bool:
        return self._enabled

    def check_interval_min(self) -> int:
        try:
            return max(10, int(str(self._cfg.get('CheckIntervalMin', '60'))))
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return 60

    # -- persistance ----------------------------------------------------
    def apply(self, info: UpdateInfo, main_path: str, argv: list) -> bool:
        """Persiste l'update en attente (state JSON). Retourne False si échec."""
        try:
            os.makedirs(RUNTIME_DIR, exist_ok=True)
            with open(PENDING_FILE, 'w', encoding='utf-8') as f:
                json.dump({'app_name': info.app_name, 'target': info.target,
                           'main': main_path, 'argv': argv,
                           'channel': info.channel}, f, ensure_ascii=False)
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return False

    def pending(self) -> Optional[dict]:
        try:
            with open(PENDING_FILE, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return None

    def clear_pending(self) -> None:
        try:
            os.remove(PENDING_FILE)
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass

    # -- décisions ------------------------------------------------------
    def should_apply_on_quit(self) -> bool:
        """Mode silencieux : appliquer au quit (ou re-tenter un échec précédent)."""
        if not self._enabled:
            return False
        if self.pending() is not None:
            return True
        return self._silent and self.check() is not None
