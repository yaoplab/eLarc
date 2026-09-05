import os
import configparser
import sqlite3
from enum import Enum, auto
from typing import Optional

try:
    import psycopg2
    _PG_OK = True
except ImportError:
    from larccommon.error_reporting import get_reporter
    get_reporter().report_exception()
    _PG_OK = False

try:
    from larccommon.config_loader import find_cfg
except ImportError:
    from larccommon.error_reporting import get_reporter
    get_reporter().report_exception()
    from .logger import log as _log
    def find_cfg() -> str:
        here = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(here, '..', 'config.ini'),
            os.path.join(here, '..', '..', 'eLarcProf', 'config.ini'),
        ]
        for p in candidates:
            p = os.path.normpath(p)
            if os.path.isfile(p):
                return p
        _log("AVERTISSEMENT : config.ini introuvable. Utilisation des valeurs par défaut.")
        print("AVERTISSEMENT : config.ini introuvable. Utilisation des valeurs par défaut.")
        return os.path.normpath(candidates[0])

from .logger import log as _log


class DBMode(Enum):
    NONE     = auto()
    INTRANET = auto()
    CLOUD    = auto()
    SQLITE   = auto()


class Database:
    def __init__(self) -> None:
        self._intranet: Optional[object] = None
        self._cloud:    Optional[object] = None
        self._sqlite:   Optional[sqlite3.Connection] = None
        self._mode = DBMode.NONE
        self._server_mode = DBMode.NONE

    def _pg_params(self, section: str) -> dict:
        cfg = configparser.ConfigParser()
        cfg.read(find_cfg())
        default_db = 'NewLarcDB' if section == 'IntranetDatabase' else 'postgres'
        return {
            'host':             cfg.get(section, 'Host', fallback='127.0.0.1'),
            'port':             cfg.getint(section, 'Port', fallback=5432),
            'dbname':           cfg.get(section, 'DB',   fallback=default_db),
            'user':             cfg.get(section, 'User', fallback='postgres'),
            'password':         cfg.get(section, 'Pass', fallback=''),
            'application_name': 'eLarcProf',
            'connect_timeout':  5,
        }

    def _sync_server_to_larccommon(self) -> None:
        """Sync server conn state to larccommon.database.db so AuthManager sees it."""
        from larccommon.database import db as lc_db, DBMode as LcDBMode
        if self._server_mode == DBMode.INTRANET:
            lc_db._intranet = self._intranet
            lc_db._server_mode = LcDBMode.INTRANET
        elif self._server_mode == DBMode.CLOUD:
            lc_db._cloud = self._cloud
            lc_db._server_mode = LcDBMode.CLOUD

    def sync_from_larccommon(self) -> None:
        """Copie les connexions depuis larccommon.database.db vers ce Database.

        Utilisé par LarcHub quand il a déjà établi les connexions PostgreSQL.
        LarcProf hérite des connexions existantes plutôt que de reconnecter.
        """
        from larccommon.database import db as lc_db, DBMode as LcDBMode
        lc_mode = lc_db.server_mode
        if lc_mode == LcDBMode.INTRANET and lc_db._intranet is not None:
            self._intranet = lc_db._intranet
            self._server_mode = DBMode.INTRANET
            self._mode = DBMode.INTRANET
        elif lc_mode == LcDBMode.CLOUD and lc_db._cloud is not None:
            self._cloud = lc_db._cloud
            self._server_mode = DBMode.CLOUD
            self._mode = DBMode.CLOUD

    def connect_intranet(self) -> bool:
        if not _PG_OK:
            _log("connect_intranet: psycopg2 non installé")
            return False
        try:
            if self._intranet:
                self._intranet.close()
            params = self._pg_params('IntranetDatabase')
            self._intranet = psycopg2.connect(**params)
            self._intranet.autocommit = True
            self._mode = DBMode.INTRANET
            self._server_mode = DBMode.INTRANET
            self._sync_server_to_larccommon()
            _log("connect_intranet: connexion réussie")
            return True
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            _log(f"connect_intranet: échec : {e}")
            self._mode = DBMode.NONE
            self._server_mode = DBMode.NONE
            return False

    def connect_cloud(self) -> bool:
        if not _PG_OK:
            _log("connect_cloud: psycopg2 non installé")
            return False
        try:
            if self._cloud:
                self._cloud.close()
            params = self._pg_params('SupabaseDatabase')
            params['sslmode'] = 'require'
            self._cloud = psycopg2.connect(**params)
            self._cloud.autocommit = True
            self._mode = DBMode.CLOUD
            self._server_mode = DBMode.CLOUD
            self._sync_server_to_larccommon()
            _log("connect_cloud: connexion réussie")
            return True
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            _log(f"connect_cloud: échec : {e}")
            self._mode = DBMode.NONE
            self._server_mode = DBMode.NONE
            return False

    def connect_sqlite(self, db_path: str = '') -> bool:
        if not db_path:
            db_path = os.path.normpath(os.path.join(
                os.path.dirname(os.path.abspath(__file__)), '..', 'elarc.db'
            ))
        try:
            if self._sqlite:
                self._sqlite.close()
            self._sqlite = sqlite3.connect(db_path, check_same_thread=False)
            self._sqlite.row_factory = sqlite3.Row
            self._sqlite.execute('PRAGMA journal_mode=WAL')
            self._mode = DBMode.SQLITE
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self._mode = DBMode.NONE
            return False

    def disconnect_all(self) -> None:
        try:
            from larccommon.database import db as lc_db, DBMode as LcDBMode
            for attr in ('_intranet', '_cloud'):
                setattr(lc_db, attr, None)
            lc_db._server_mode = LcDBMode.NONE
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass
        for attr in ('_intranet', '_cloud'):
            conn = getattr(self, attr, None)
            if conn:
                try:
                    conn.close()
                except Exception:
                    from larccommon.error_reporting import get_reporter
                    get_reporter().report_exception()
                    pass
                setattr(self, attr, None)
        if self._sqlite:
            try:
                self._sqlite.close()
            except Exception:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                pass
            self._sqlite = None
        self._mode = DBMode.NONE
        self._server_mode = DBMode.NONE

    def before_update(self, user_id: int) -> None:
        conn = self.server_conn
        if conn is None:
            return
        # Niveau SESSION (set_config, false) — SET LOCAL serait un no-op
        # sous autocommit (chaque instruction = sa propre transaction).
        from larccommon.audit_context import attach, refresh
        refresh()
        attach(conn)

    @property
    def server_conn(self):
        if self._server_mode == DBMode.INTRANET:
            return self._intranet
        if self._server_mode == DBMode.CLOUD:
            return self._cloud
        return None

    @property
    def local_conn(self) -> Optional[sqlite3.Connection]:
        return self._sqlite

    @property
    def mode(self) -> DBMode:
        return self._mode

    @property
    def server_mode(self) -> DBMode:
        return self._server_mode

    @property
    def is_server_connected(self) -> bool:
        return self.server_conn is not None

    def get_sqlalchemy_url(self, section: str = 'IntranetDatabase') -> str:
        params = self._pg_params(section)
        return (f"postgresql+psycopg2://{params['user']}:{params['password']}"
                f"@{params['host']}:{params['port']}/{params['dbname']}")

    def __del__(self) -> None:
        try:
            self.disconnect_all()
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass


db = Database()
_find_cfg = find_cfg  # compatibilité
