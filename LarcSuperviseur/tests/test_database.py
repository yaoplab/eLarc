"""Tests du module common/database.py — ré-export de larccommon.database.

Les tests DataLoader sont dans test_data_loader.py (renommé depuis
test_database.py le 2026-08-14 — le nom correspondait à une couverture
fictive pour ce module).
"""
from __future__ import annotations


def test_reexport_db_singleton():
    from LarcSuperviseur.common.database import Database, db

    assert isinstance(db, Database)


def test_dbmode_values():
    from LarcSuperviseur.common.database import DBMode

    assert {m.name for m in DBMode} == {"NONE", "INTRANET", "CLOUD"}
