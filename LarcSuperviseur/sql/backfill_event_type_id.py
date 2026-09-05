"""Backfill student_event.event_type_id — chemins de la nouvelle taxonomie.

Usage : python LarcSuperviseur/sql/backfill_event_type_id.py
Prérequis : migration_20260830_event_type_tree.sql appliquée (le backfill SQL
y couvre les chemins legacy ; ce script couvre les chemins de la nouvelle
taxonomie et logge les lignes non résolues).

Règle gabarit : UPDATE uniquement (jamais d'INSERT/DELETE).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from LarcSuperviseur.common.database import db
from LarcSuperviseur.common.logger import log
from LarcSuperviseur.views.core.event_type_repo import EventTypeRepo

BATCH = 500


def main() -> int:
    if db.server_conn is None:
        db.connect_intranet()
    loader = EventTypeRepo()
    cur = db.server_conn.cursor()

    cur.execute("SELECT event_id, event_type FROM student_event WHERE event_type_id IS NULL")
    rows = cur.fetchall()
    n, unresolved = 0, []

    for i in range(0, len(rows), BATCH):
        for event_id, event_type in rows[i : i + BATCH]:
            type_id = loader.resolve_event_type_id(event_type)
            if type_id:
                cur.execute(
                    "UPDATE student_event SET event_type_id = %s WHERE event_id = %s",
                    (type_id, event_id),
                )
                n += 1
            else:
                unresolved.append((event_id, event_type))
        db.server_conn.commit()
        log(f"backfill_event_type_id: lot {i // BATCH + 1} traité")

    print(f"backfill: {n} résolue(s), {len(unresolved)} non résolue(s)")
    for event_id, event_type in unresolved[:50]:
        print(f"  non résolu : #{event_id} '{event_type}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
