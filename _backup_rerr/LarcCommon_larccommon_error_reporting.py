"""ErrorReporter — enregistrement centralisé des erreurs (R1).

Transport asynchrone : file bornée + thread writer unique → PostgreSQL
error_log (flush par lot 5 s / 100) ; spool SQLite local en secours ;
JSONL en dernier recours ; compteur de pertes sinon.

Règles absolues :
- `report()` ne fait QUE `put_nowait` — aucun I/O, aucun raise (< 1 ms)
- le reporter ne lève JAMAIS ; en cas de doute, il avale
- cœur SANS Qt (testable sans QApplication)
"""
import atexit
import json
import os
import queue
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Callable, Optional

from .error_spool import ErrorSpool
from .logger import log as _log

_LEVEL_RANK = {'WARNING': 1, 'ERROR': 2, 'CRITICAL': 3}

_INSERT_SQL = """
INSERT INTO error_log (ts, app_name, app_version, user_id, user_name, role,
                       conn_mode, level, module, func, line, message,
                       traceback, context, spool_id)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (spool_id) DO NOTHING
"""


@dataclass
class ErrorEvent:
    ts: float
    level: str
    message: str
    traceback: str = ''
    module: str = ''
    func: str = ''
    line: int = 0
    context: dict = field(default_factory=dict)
    spool_id: Optional[int] = None


class ErrorReporter:
    def __init__(self, app_name: str, app_version: str = '',
                 config: Optional[dict] = None,
                 pg_conn_provider: Optional[Callable[[], object]] = None,
                 spool_dir: Optional[str] = None) -> None:
        self._app_name = app_name
        self._app_version = app_version
        self._cfg = config or {}
        self._pg_conn_provider = pg_conn_provider

        self._enabled = self._cfg_str('Enabled', 'true').lower() == 'true'
        self._flush_interval = self._cfg_float('FlushIntervalSec', 5.0)
        self._batch_size = self._cfg_int('FlushBatchSize', 100)
        self._queue_max = self._cfg_int('QueueMax', 1000)
        self._spool_max_rows = self._cfg_int('SpoolMaxRows', 50000)
        self._retry_backoff = self._cfg_float('RetryBackoffSec', 10.0)
        min_level = self._cfg_str('MinLevel', 'ERROR').upper()
        self._min_rank = _LEVEL_RANK.get(min_level, 2)

        spool_dir = spool_dir or self._default_spool_dir()
        self._spool = ErrorSpool(os.path.join(spool_dir, 'error_spool.db'),
                                 max_rows=self._spool_max_rows)
        self._jsonl_path = os.path.join(spool_dir, 'error_spool.jsonl')

        self._queue: queue.Queue = queue.Queue(maxsize=self._queue_max)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._pg_conn = None
        self._backoff_until = 0.0
        self._backoff = self._retry_backoff
        self._dropped = 0
        self._atexit_done = False

    # -- config ---------------------------------------------------------
    def _cfg_str(self, key: str, default: str) -> str:
        try:
            return str(self._cfg.get(key, default))
        except Exception:
            return default

    def _cfg_int(self, key: str, default: int) -> int:
        try:
            return int(self._cfg_str(key, str(default)))
        except Exception:
            return default

    def _cfg_float(self, key: str, default: float) -> float:
        try:
            return float(self._cfg_str(key, str(default)))
        except Exception:
            return default

    def _default_spool_dir(self) -> str:
        try:
            from .session import session
            inst = getattr(session, 'instance_dir', None)
            if inst and os.path.isdir(str(inst)):
                return os.path.join(str(inst), '.error_spool')
        except Exception:
            pass
        return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '..', '.error_spool')

    # -- cycle de vie ---------------------------------------------------
    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name='error-reporter',
                                        daemon=True)
        self._thread.start()
        if not self._atexit_done:
            self._atexit_done = True
            atexit.register(self.stop)

    def stop(self) -> None:
        if self._thread is not None:
            self._stop_event.set()
            self._thread.join(timeout=2.0)
            self._thread = None
        self.flush(timeout=1.0)
        self._spool.close()
        if self._pg_conn is not None:
            try:
                self._pg_conn.close()
            except Exception:
                pass
            self._pg_conn = None

    def flush(self, timeout: float = 2.0) -> None:
        """Vidage synchrone de la file (tests + shutdown)."""
        deadline = time.monotonic() + timeout
        items: list[ErrorEvent] = []
        while time.monotonic() < deadline:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if items:
            self._flush_batch(items)

    # -- API ------------------------------------------------------------
    def report(self, level: str, message: str, traceback: str = '',
               module: str = '', func: str = '', line: int = 0,
               context: Optional[dict] = None) -> None:
        """Enregistre un événement — fire-and-forget, jamais de raise."""
        if not self._enabled:
            return
        if _LEVEL_RANK.get(level, 0) < self._min_rank:
            return
        ctx = self._auto_context()
        if context:
            ctx.update(context)
        ev = ErrorEvent(ts=time.time(), level=level, message=str(message),
                        traceback=traceback, module=module, func=func,
                        line=line, context=ctx)
        try:
            self._queue.put_nowait(ev)
        except queue.Full:
            self._dropped += 1  # perte silencieuse — jamais de blocage

    def report_exception(self, exc: Optional[BaseException] = None,
                         tb=None, context: Optional[dict] = None) -> None:
        """Enregistre une exception avec traceback complet et position du code."""
        if exc is None:
            try:
                exc, tb = sys.exc_info()[1:3]
            except Exception:
                return
        if exc is None:
            return
        try:
            module, func, line = self._locate(tb or exc.__traceback__)
        except Exception:
            module = func = ''
            line = 0
        try:
            tb_str = ''.join(traceback.format_exception(
                type(exc), exc, tb or exc.__traceback__))
        except Exception:
            tb_str = ''
        self.report('ERROR', f"{type(exc).__name__}: {exc}",
                    traceback=tb_str, module=module, func=func, line=line,
                    context=context)

    # -- interne --------------------------------------------------------
    def _auto_context(self) -> dict:
        ctx = {'app_name': self._app_name,
               'app_version': self._app_version}
        try:
            from .session import session
            ctx['user_id'] = getattr(session, 'user_id', None)
            ctx['user_name'] = getattr(session, 'full_name', None)
            role = getattr(session, 'role', None)
            ctx['role'] = getattr(role, 'value', None) if role is not None else None
            mode = getattr(session, 'conn_mode', None)
            ctx['conn_mode'] = getattr(mode, 'value', None) if mode is not None else None
        except Exception:
            pass
        return ctx

    @staticmethod
    def _locate(tb) -> tuple[str, str, int]:
        frames = traceback.extract_tb(tb)
        if not frames:
            return '', '', 0
        frame = frames[-1]
        return (os.path.basename(frame.filename), frame.name, frame.lineno)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=self._flush_interval)
                items = [item]
                for _i in range(self._batch_size - 1):
                    try:
                        items.append(self._queue.get_nowait())
                    except queue.Empty:
                        break
                self._flush_batch(items)
            except queue.Empty:
                self._flush_batch([])  # tick : rejeu du spool si PG dispo
            except Exception:
                try:
                    _log('ErrorReporter._run: erreur interne ignorée')
                except Exception:
                    pass

    def _flush_batch(self, items: list[ErrorEvent]) -> None:
        if not items:
            if self._enabled and time.monotonic() >= self._backoff_until:
                self._replay_spool()
            return
        payloads = [self._serialize(e) for e in items]
        if self._enabled and time.monotonic() >= self._backoff_until:
            if self._try_insert(payloads, items):
                self._backoff = self._retry_backoff
                self._backoff_until = 0.0
                self._replay_spool()
                return
        # PG indisponible → spool, puis JSONL, puis compteur
        self._to_spool(payloads)

    def _try_insert(self, payloads: list[str], items: list[ErrorEvent]) -> bool:
        try:
            conn = self._pg_conn
            if conn is None:
                conn = self._get_pg_conn()
                if conn is None:
                    raise ConnectionError('connexion PG indisponible')
            rows = [self._row_from_dict(json.loads(p)) for p in payloads]
            if self._dropped:
                rows.append(self._synthetic_dropped_row())
                self._dropped = 0
            with conn.cursor() as cur:
                cur.executemany(_INSERT_SQL, rows)
            return True
        except Exception as e:
            self._pg_conn = None
            self._backoff = min(self._backoff * 2, 300.0)
            self._backoff_until = time.monotonic() + self._backoff
            try:
                _log(f"ErrorReporter: PG indisponible ({e})")
            except Exception:
                pass
            return False

    def _to_spool(self, payloads: list[str]) -> None:
        for payload in payloads:
            sid = self._spool.enqueue(payload)
            if sid is not None:
                continue
            if not self._jsonl_append(payload):
                self._dropped += 1
        self._spool.prune()

    def _replay_spool(self) -> None:
        """Rejoue le spool vers PG — idempotent grâce à spool_id (ON CONFLICT)."""
        if not self._enabled:
            return
        try:
            rows = self._spool.peek(self._batch_size)
            if not rows:
                return
            conn = self._pg_conn
            if conn is None:
                conn = self._get_pg_conn()
                if conn is None:
                    raise ConnectionError('connexion PG indisponible')
            insert_rows = []
            for sid, payload in rows:
                data = json.loads(payload)
                data['spool_id'] = sid
                insert_rows.append(self._row_from_dict(data))
            with conn.cursor() as cur:
                cur.executemany(_INSERT_SQL, insert_rows)
            self._spool.mark_done([sid for sid, _ in rows])
            self._backoff = self._retry_backoff
            self._backoff_until = 0.0
        except Exception as e:
            self._pg_conn = None
            self._backoff = min(self._backoff * 2, 300.0)
            self._backoff_until = time.monotonic() + self._backoff
            try:
                _log(f"ErrorReporter: rejeu spool impossible ({e})")
            except Exception:
                pass

    def _get_pg_conn(self):
        if self._pg_conn_provider is not None:
            return self._pg_conn_provider()
        try:
            from .database import db
            mode = getattr(db, 'server_mode', None)
            section = ('SupabaseDatabase' if mode is not None
                       and getattr(mode, 'name', '') == 'CLOUD'
                       else 'IntranetDatabase')
            import psycopg2
            params = db._pg_params(section)
            params['application_name'] = f"{self._app_name}_reporter"
            self._pg_conn = psycopg2.connect(**params)
            self._pg_conn.autocommit = True
            return self._pg_conn
        except Exception:
            return None

    def _serialize(self, ev: ErrorEvent) -> str:
        data = {'ts': time.strftime('%Y-%m-%dT%H:%M:%S',
                                    time.localtime(ev.ts)),
                'level': ev.level, 'message': ev.message,
                'traceback': ev.traceback, 'module': ev.module,
                'func': ev.func, 'line': ev.line, 'context': ev.context,
                'app_name': self._app_name, 'app_version': self._app_version,
                'user_id': None, 'user_name': None, 'role': None,
                'conn_mode': None}
        data.update(self._auto_context())
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def _row_from_dict(d: dict) -> tuple:
        return (d.get('ts'), d.get('app_name'), d.get('app_version'),
                d.get('user_id'), d.get('user_name'), d.get('role'),
                d.get('conn_mode'), d.get('level'), d.get('module'),
                d.get('func'), d.get('line'), d.get('message'),
                d.get('traceback'),
                json.dumps(d.get('context') or {}, ensure_ascii=False)
                if d.get('context') else None,
                d.get('spool_id'))

    def _synthetic_dropped_row(self) -> tuple:
        ctx = self._auto_context()
        return (time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime()),
                self._app_name, self._app_version, ctx.get('user_id'),
                ctx.get('user_name'), ctx.get('role'), ctx.get('conn_mode'),
                'ERROR', 'error_reporting', '_to_spool', 0,
                'Événements perdus (spool et JSONL indisponibles)',
                '', json.dumps({'dropped': True}), None)

    def _jsonl_append(self, payload: str) -> bool:
        try:
            os.makedirs(os.path.dirname(self._jsonl_path), exist_ok=True)
            with open(self._jsonl_path, 'a', encoding='utf-8') as f:
                f.write(payload + '\n')
            return True
        except Exception:
            return False


# -- singleton ---------------------------------------------------------
reporter: Optional[ErrorReporter] = None


class _NullReporter:
    """Dernier filet : ne lève jamais, ne fait rien (si le reporter par
    défaut ne peut même pas être construit)."""

    def report(self, *args, **kwargs) -> None:
        return None

    def report_exception(self, *args, **kwargs) -> None:
        return None


def get_reporter() -> ErrorReporter:
    """Retourne le reporter global — JAMAIS None (initialisation paresseuse).

    Si `init_app` n'a pas encore posé le reporter (tests, scripts, modules
    chargés tôt), un reporter par défaut est créé à la première demande : il
    spoule en SQLite/JSONL sans bloquer, et `init_app` le remplacera par le
    vrai reporter de l'app.
    """
    global reporter
    if reporter is None:
        try:
            reporter = ErrorReporter(app_name="default")
        except Exception:
            reporter = _NullReporter()
    return reporter


def _set_reporter(rep: Optional[ErrorReporter]) -> None:
    global reporter
    reporter = rep
