"""Connexion PostgreSQL autonome : psycopg2 si disponible, sinon psycopg (v3).

Lit le config.ini master (LarcCommon/config.ini, sections IntranetDatabase /
SupabaseDatabase) — jamais de port hardcodé (le port réel peut être 55515).
"""

from __future__ import annotations

import configparser
from pathlib import Path

try:
    import psycopg2  # type: ignore
    _DRIVER = "psycopg2"
except ImportError:
    try:
        import psycopg  # type: ignore  # v3
        _DRIVER = "psycopg3"
    except ImportError:
        _DRIVER = None


class DBUnavailable(ConnectionError):
    """Connexion à la base impossible (service down, driver manquant, timeout)."""


def find_config(root: Path | str) -> Path:
    """Config.ini master (priorité LarcCommon/), sinon ./config.ini (comme find_cfg()).

    Accepte str ou Path (l'IHM passe le chemin de racine en str).
    """
    root = Path(root)
    master = root / "LarcCommon" / "config.ini"
    if master.is_file():
        return master
    local = root / "config.ini"
    if local.is_file():
        return local
    return master  # inexistant → pg_params utilise les defaults


def pg_params(section: str, config_path: Path) -> dict:
    """Paramètres de connexion pour une section du config.ini."""
    defaults = {
        "host": "127.0.0.1",
        "port": "5432",
        "dbname": "NewLarcDB",
        "user": "postgres",
        "password": "postgres",
    }
    cp = configparser.ConfigParser()
    try:
        cp.read(str(config_path), encoding="utf-8")
    except Exception:
        return defaults
    if cp.has_section(section):
        keymap = {"Host": "host", "Port": "port", "DB": "dbname",
                  "User": "user", "Pass": "password"}
        for ini_key, kw in keymap.items():
            if cp.has_option(section, ini_key):
                defaults[kw] = cp.get(section, ini_key)
    return defaults


def connect(section: str = "IntranetDatabase", root: Path | None = None,
            params: dict | None = None) -> object:
    """Ouvre une connexion PostgreSQL (autocommit). Lève DBUnavailable si impossible.

    params explicites (host/port/dbname/user/password) court-circuitent la
    lecture du config.ini — utilisé par l'IHM pour les profils de connexion.
    """
    from .config import find_root

    root = Path(root) if root else find_root()
    params = params or pg_params(section, find_config(root))
    if _DRIVER == "psycopg2":
        conn = psycopg2.connect(connect_timeout=5, **params)  # noqa: F821
        conn.autocommit = True
        return conn
    if _DRIVER == "psycopg3":
        return psycopg.connect(connect_timeout=5, autocommit=True, **params)  # noqa: F821
    raise DBUnavailable(
        "Aucun driver PostgreSQL installé (psycopg2 ou psycopg).\n"
        "Installez : pip install psycopg2-binary  (ou : pip install 'psycopg[binary]')"
    )
