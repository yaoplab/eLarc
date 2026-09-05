"""Service CRUD pour student_event — evenements eleves (absences, retards, sorties...).

Portee : seuls les eleves des classes du prof sont concernes.
Operations : insertion locale SQLite, lecture, listing des absents du jour.
La synchronisation serveur est geree par SyncManager (table dans BUSINESS_TABLES).
"""
from datetime import datetime, timezone
from typing import Optional

from .database import db
from .session import session
from .logger import log as _log


class EventService:
    """CRUD pour la table student_event (SQLite locale)."""

    # Types d'evenement accessibles au professeur
    EVENT_TYPES = {
        'absence': 'Absence',
        'late': 'Retard',
        'exit': 'Sortie anticipee',
        'justified': 'Absence justifiee',
        'departure': 'Depart',
        'arrival': 'Arrivee',
    }

    @classmethod
    def _conn(cls):
        c = db.local_conn
        if c is None:
            raise RuntimeError("Aucune connexion SQLite locale")
        return c

    # ------------------------------------------------------------------
    # Insertion
    # ------------------------------------------------------------------
    @classmethod
    def insert_event(
        cls,
        student_id: int,
        event_type: str,
        created_by: int,
        *,
        note: str = '',
        lieu_label: str = '',
        subject_label: str = '',
        event_at: Optional[datetime] = None,
    ) -> int:
        """Cree un evenement dans la table locale. Retourne l'event_id genere.

        L'event_id est genere localement (max + 1). Cote serveur, le trigger
        trg_resolve_agenda_day resoudra agenda_day_id automatiquement.
        """
        conn = cls._conn()
        cur = conn.cursor()

        # Generer un event_id local (negatif pour eviter collisions avec le serveur)
        # Les ids serveur commencent a 1, les ids locaux seront < 0
        row = cur.execute('SELECT COALESCE(MIN(event_id), -1) FROM student_event').fetchone()
        next_id = min(row[0] - 1, -1) if row else -1

        ts = (event_at or datetime.now()).isoformat()

        cur.execute(
            """INSERT INTO student_event
               (event_id, student_id, event_type, event_at, note, source, created_by,
                lieu_label, subject_label)
               VALUES (?, ?, ?, ?, ?, 'intranet', ?, ?, ?)""",
            (next_id, student_id, event_type, ts, note, created_by,
             lieu_label, subject_label),
        )
        conn.commit()
        _log(f"EventService: event {next_id} cree — {event_type} pour student {student_id}")
        return next_id

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------
    @classmethod
    def fetch_events_for_student(
        cls, student_id: int, limit: int = 50
    ) -> list[dict]:
        """Retourne les evenements d'un eleve, du plus recent au plus ancien."""
        rows = cls._conn().execute(
            """SELECT event_id, student_id, event_type, event_at, note,
                      lieu_label, subject_label, created_by, validated_by, source
               FROM student_event
               WHERE student_id = ?
               ORDER BY event_at DESC
               LIMIT ?""",
            (student_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def fetch_events_for_class(
        cls, class_id: int, date_from: Optional[str] = None, date_to: Optional[str] = None
    ) -> list[dict]:
        """Retourne les evenements pour tous les eleves d'une classe.

        Jointure avec larcauth_student pour filtrer par classe.
        """
        sql = """SELECT se.event_id, se.student_id, se.event_type, se.event_at,
                        se.note, se.lieu_label, se.subject_label,
                        se.created_by, se.validated_by,
                        aec.last_name || ' ' || aec.first_name AS student_name
                 FROM student_event se
                 JOIN larcauth_student s ON s.aecuser_ptr_id = se.student_id
                 JOIN larcauth_aecuser aec ON aec.id = se.student_id
                 WHERE s.s_classroom_id = ?"""
        params: list = [class_id]

        if date_from:
            sql += ' AND DATE(se.event_at) >= ?'
            params.append(date_from)
        if date_to:
            sql += ' AND DATE(se.event_at) <= ?'
            params.append(date_to)

        sql += ' ORDER BY se.event_at DESC LIMIT 200'

        rows = cls._conn().execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def fetch_absents_today(cls, class_id: int) -> list[dict]:
        """Retourne les eleves absents aujourd'hui (absence non justifiee)."""
        today = datetime.now().strftime('%Y-%m-%d')
        rows = cls._conn().execute(
            """SELECT se.student_id,
                      aec.last_name || ' ' || aec.first_name AS student_name,
                      se.event_type, se.note
               FROM student_event se
               JOIN larcauth_student s ON s.aecuser_ptr_id = se.student_id
               JOIN larcauth_aecuser aec ON aec.id = se.student_id
               WHERE s.s_classroom_id = ?
                 AND (se.event_type = 'absence'
                      OR se.event_type LIKE 'Suivi > Absence%')
                 AND DATE(se.event_at) = ?
                 AND se.validated_by IS NULL
               ORDER BY aec.last_name""",
            (class_id, today),
        ).fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def fetch_event_stats_for_students(
        cls, student_ids: list[int], date_from: str, date_to: str
    ) -> dict[int, dict]:
        """Stats agregees par eleve : nb exits, nb events, presence du jour.

        Meme logique que LarcSuperviseur DataLoader.get_student_event_stats.
        """
        if not student_ids:
            return {}
        ids_str = ','.join(str(sid) for sid in student_ids)
        today = datetime.now().strftime('%Y-%m-%d')

        conn = cls._conn()
        rows = conn.execute(
            f"""SELECT se.student_id,
                       SUM(CASE WHEN se.event_type = 'exit'
                           OR se.event_type LIKE 'Sortie%'
                           OR se.event_type LIKE '%Fuite%' THEN 1 ELSE 0 END) AS exit_count,
                       COUNT(*) AS total_events,
                       CASE WHEN SUM(CASE WHEN (se.event_type = 'absence'
                               OR se.event_type LIKE 'Suivi > Absence%')
                           AND se.validated_by IS NULL
                           AND DATE(se.event_at) = '{today}'
                           THEN 1 ELSE 0 END) > 0 THEN 'Absent' ELSE 'Present' END AS presence
                FROM student_event se
                WHERE se.student_id IN ({ids_str})
                  AND DATE(se.event_at) BETWEEN '{date_from}' AND '{date_to}'
                GROUP BY se.student_id"""
        ).fetchall()

        result = {}
        for r in rows:
            result[r['student_id']] = {
                'exit_count': r['exit_count'],
                'total_events': r['total_events'],
                'presence': r['presence'],
            }
        return result
