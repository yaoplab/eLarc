"""Cœur de la synchronisation : comparer sync_version et pousser les mises à jour."""
import json
from datetime import datetime, timezone
from typing import Optional

from .config import load
from .logger import log
from . import db


def _version(conn, table: str, schema: str = 'public') -> int:
    """Retourne la version maximale d'une table (dernier élément de sync_listeMAJ)."""
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT COALESCE(
                    (SELECT sync_listeMAJ #>> '{{-1,v}}' FROM {schema}."{table}"
                     WHERE sync_listeMAJ IS NOT NULL AND sync_listeMAJ != '[]'::jsonb
                     ORDER BY (sync_listeMAJ #>> '{{-1,v}}')::int DESC LIMIT 1),
                    '0'
                )::int
            """)
            return cur.fetchone()[0]
    except Exception as e:
        log.warning(f"version({table}) : {e}")
        return 0


def _rows_modified_since(conn, table: str, from_version: int, schema: str = 'public') -> list[dict]:
    """Retourne les enregistrements dont la dernière version > from_version."""
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT *
                FROM {schema}."{table}"
                WHERE sync_listeMAJ IS NOT NULL
                  AND (sync_listeMAJ #>> '{{-1,v}}')::int > %s
                ORDER BY id
            """, (from_version,))
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        log.warning(f"rows_modified_since({table}) : {e}")
        return []


def _update_rows(dest_conn, table: str, rows: list[dict], schema: str = 'public') -> int:
    """Écrit les enregistrements dans la table destination."""
    if not rows:
        return 0
    count = 0
    try:
        with dest_conn.cursor() as cur:
            cols = [k for k in rows[0].keys() if k.lower() != 'id']
            col_names = ', '.join(f'"{c}"' for c in cols)
            placeholders = ', '.join(f'%({c})s' for c in cols)
            for row in rows:
                cur.execute(f"""
                    UPDATE {schema}."{table}"
                    SET ({col_names}) = ({placeholders})
                    WHERE id = %(id)s
                """, row)
                count += 1
    except Exception as e:
        log.error(f"update_rows({table}) : {e}")
    return count


def sync_table(table: str, freq_min: int) -> str:
    """Synchronise une table entre intranet et cloud.

    Compare la version max des deux côtés.
    Celui qui a la version la plus élevée est source → destination.
    Retourne un résumé.
    """
    try:
        intra = db.get_intranet()
        cloud = db.get_cloud()
    except Exception as e:
        return f"connexion impossible : {e}"

    v_intra = _version(intra, table)
    v_cloud = _version(cloud, table)

    if v_intra == v_cloud:
        return "à jour"

    if v_intra > v_cloud:
        rows = _rows_modified_since(intra, table, v_cloud)
        n = _update_rows(cloud, table, rows)
        log.info(f"{table} : intra v{v_intra} > cloud v{v_cloud} → {n} enregistrement(s) poussé(s)")
        return f"{n} enr. intranet → cloud"
    else:
        rows = _rows_modified_since(cloud, table, v_intra)
        n = _update_rows(intra, table, rows)
        log.info(f"{table} : cloud v{v_cloud} > intra v{v_intra} → {n} enregistrement(s) poussé(s)")
        return f"{n} enr. cloud → intranet"
