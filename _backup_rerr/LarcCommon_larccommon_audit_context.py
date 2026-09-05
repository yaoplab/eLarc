"""Contexte d'audit — « qui fait quoi », fixé au niveau SESSION.

⚠ Toutes les connexions LARC sont autocommit=True : un `SET LOCAL` ne survit
pas à sa propre transaction implicite (no-op silencieux). On utilise donc
`set_config(..., false)` = niveau SESSION, appliqué à chaque connexion et
rafraîchi aux points de login (refresh()).
"""
from typing import Optional

_user_id: Optional[int] = None
_user_name: str = ''
_sync_source: str = 'local'


def refresh() -> None:
    """Re-lit larccommon.session.session — à appeler au login / après connect."""
    global _user_id, _user_name, _sync_source
    try:
        from .session import session
        _user_id = getattr(session, 'user_id', None) or None
        _user_name = getattr(session, 'full_name', None) or ''
        mode = getattr(session, 'conn_mode', None)
        value = getattr(mode, 'value', None) if mode is not None else None
        _sync_source = (value or 'local').lower()
    except Exception:
        pass


def attach(conn) -> None:
    """Applique le contexte courant sur une connexion — jamais de raise."""
    if conn is None:
        return
    try:
        cur = conn.cursor()
        cur.execute("SELECT set_config('app.modified_by', %s, false)",
                    (str(_user_id or ''),))
        cur.execute("SELECT set_config('app.modified_by_name', %s, false)",
                    (_user_name or '',))
        cur.execute("SELECT set_config('app.current_user_id', %s, false)",
                    (str(_user_id or ''),))
        cur.execute("SELECT set_config('app.sync_source', %s, false)",
                    (_sync_source or 'local',))
    except Exception:
        pass


def current_user_id() -> Optional[int]:
    return _user_id


def current_user_name() -> str:
    return _user_name
