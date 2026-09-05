"""Pont de session LarcProf → larccommon.

Ré-exporte les types et le singleton session depuis larccommon,
avec les extensions spécifiques à LarcProf (load_role_flags, role_display).
"""
from __future__ import annotations
from types import MethodType

from larccommon.session import (
    UserRole,
    ConnMode,
    AuthResult,
    Session,
    session,
)


def load_role_flags(self) -> dict[str, bool]:
    """Charge les flags de rôle depuis PostgreSQL/SQLite.

    Retourne un dict: {'Professeur': True, 'Coordinateur': False, ...}
    """
    from .database import db
    flags = {}
    conn = db.server_conn if db.is_server_connected else None
    if conn is not None:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT type_teacher, type_coordonator, type_supervisor, "
                    "type_secretary, type_director "
                    "FROM larcauth_aecuser WHERE id = %s",
                    (self.user_id,)
                )
                row = cur.fetchone()
                if row:
                    flags = {
                        'Professeur': bool(row[0]),
                        'Coordinateur': bool(row[1]),
                        'Superviseur': bool(row[2]),
                        'Secretaire': bool(row[3]),
                        'Directeur': bool(row[4]),
                    }
                    self.role_flags = flags
                    return flags
        except Exception:
            pass
    sqlite = db.local_conn
    if sqlite is not None:
        try:
            row = sqlite.execute(
                "SELECT type_teacher, type_coordonator, type_supervisor, "
                "type_secretary, type_director "
                "FROM larcauth_aecuser WHERE id = ?",
                (self.user_id,)
            ).fetchone()
            if row:
                flags = {
                    'Professeur': bool(row[0]),
                    'Coordinateur': bool(row[1]),
                    'Superviseur': bool(row[2]),
                    'Secretaire': bool(row[3]),
                    'Directeur': bool(row[4]),
                }
                self.role_flags = flags
                return flags
        except Exception:
            pass
    return flags


def _get_active_role_labels(self) -> list[str]:
    """Retourne la liste des rôles actifs pour affichage."""
    if not self.role_flags:
        load_role_flags(self)
    return [label for label, active in self.role_flags.items() if active]


def _get_role_display(self) -> str:
    """Retourne les rôles actifs séparés par ' | ' pour affichage."""
    labels = _get_active_role_labels(self)
    return ' | '.join(labels) if labels else self.role.value


# Attacher les méthodes au singleton session
session.load_role_flags = MethodType(load_role_flags, session)

# Injecter les propriétés via la classe (un seul singleton, pas d'impact)
Session.active_role_labels = property(_get_active_role_labels)
Session.role_display = property(_get_role_display)
