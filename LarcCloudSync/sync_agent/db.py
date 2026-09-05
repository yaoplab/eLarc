"""Connexions PostgreSQL (intranet + cloud)."""
import psycopg2
from .config import load

_intranet = None
_cloud = None


def connect_intranet() -> psycopg2.extensions.connection:
    global _intranet
    cfg = load()['db']['intranet']
    _intranet = psycopg2.connect(**cfg, connect_timeout=5)
    _intranet.autocommit = True
    return _intranet


def connect_cloud() -> psycopg2.extensions.connection:
    global _cloud
    cfg = load()['db']['cloud']
    _cloud = psycopg2.connect(**cfg, connect_timeout=10)
    _cloud.autocommit = True
    return _cloud


def get_intranet():
    return _intranet or connect_intranet()


def get_cloud():
    return _cloud or connect_cloud()


def close_all():
    for conn in (_intranet, _cloud):
        if conn:
            try:
                conn.close()
            except Exception:
                pass
