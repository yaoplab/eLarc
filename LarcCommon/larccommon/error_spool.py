"""Spool SQLite local — tampon durable des erreurs quand PostgreSQL est injoignable.

Accès EXCLUSIVEMENT depuis le thread writer du reporter (pas de concurrence).
Ne lève jamais : en cas d'échec, retourne None / [] / 0.
"""
import os
import sqlite3
from datetime import datetime

_DDL = """
CREATE TABLE IF NOT EXISTS pending (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    payload    TEXT NOT NULL
);
"""


class ErrorSpool:
    def __init__(self, db_path: str, max_rows: int = 50_000) -> None:
        self._db_path = db_path
        self._max_rows = max_rows
        self._conn: sqlite3.Connection | None = None

    # -- interne --------------------------------------------------------
    def _connect(self) -> sqlite3.Connection | None:
        if self._conn is None:
            try:
                os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
                self._conn = sqlite3.connect(self._db_path, timeout=1)
                self._conn.execute("PRAGMA busy_timeout=1000")
                self._conn.executescript(_DDL)
            except Exception:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                self._conn = None
        return self._conn

    # -- API ------------------------------------------------------------
    def enqueue(self, payload: str) -> int | None:
        """Ajoute un événement ; retourne son id (None si échec)."""
        conn = self._connect()
        if conn is None:
            return None
        try:
            cur = conn.execute(
                "INSERT INTO pending (created_at, payload) VALUES (?, ?)",
                (datetime.now().isoformat(timespec='seconds'), payload))
            conn.commit()
            return cur.lastrowid
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return None

    def peek(self, limit: int) -> list[tuple[int, str]]:
        """Les plus anciens d'abord — [(id, payload), ...]."""
        conn = self._connect()
        if conn is None:
            return []
        try:
            cur = conn.execute(
                "SELECT id, payload FROM pending ORDER BY id ASC LIMIT ?", (limit,))
            return cur.fetchall()
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return []

    def mark_done(self, ids: list[int]) -> None:
        """Supprime les événements rejoués avec succès."""
        if not ids:
            return
        conn = self._connect()
        if conn is None:
            return
        try:
            conn.executemany("DELETE FROM pending WHERE id = ?", [(i,) for i in ids])
            conn.commit()
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass

    def prune(self) -> int:
        """Si > max_rows : purge le quart le plus ancien ; retourne le nombre purgé."""
        conn = self._connect()
        if conn is None:
            return 0
        try:
            total = conn.execute("SELECT count(*) FROM pending").fetchone()[0]
            if total <= self._max_rows:
                return 0
            drop = total - self._max_rows + self._max_rows // 4
            conn.execute(
                "DELETE FROM pending WHERE id IN "
                "(SELECT id FROM pending ORDER BY id ASC LIMIT ?)", (drop,))
            conn.commit()
            return drop
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return 0

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                pass
            self._conn = None
