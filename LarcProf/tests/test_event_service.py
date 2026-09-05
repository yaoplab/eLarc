"""Tests unitaires pour EventService — evenements eleves."""
import os
import sys
import tempfile
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, 'LarcCommon'))


class TestEventService(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from LarcProf.common.database import db
        from LarcProf.common.sqlite_init import sqlite_init, _DDL, BUSINESS_TABLES

        cls._tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        cls._tmp.close()
        db.connect_sqlite(cls._tmp.name)
        conn = db.local_conn
        # Tables minimales pour les tests
        conn.execute("CREATE TABLE IF NOT EXISTS larcauth_student (aecuser_ptr_id INTEGER PRIMARY KEY, s_classroom_id INTEGER, enabled INTEGER DEFAULT 1)")
        conn.execute("CREATE TABLE IF NOT EXISTS larcauth_aecuser (id INTEGER PRIMARY KEY, last_name TEXT, first_name TEXT, email TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS larcauth_classroom (id INTEGER PRIMARY KEY, label TEXT, fk_level_id INTEGER, enabled INTEGER DEFAULT 1)")
        conn.execute("CREATE TABLE IF NOT EXISTS larcauth_classroom_termsubject (id INTEGER PRIMARY KEY, label TEXT, fk_classroom_id INTEGER, fk_levelsubject_id INTEGER, fk_term_id INTEGER, fk_teacher_id INTEGER, enabled INTEGER DEFAULT 1)")
        conn.execute("CREATE TABLE IF NOT EXISTS larcauth_level (id INTEGER PRIMARY KEY, label TEXT, fk_program_id INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS larcauth_program (id INTEGER PRIMARY KEY, sigle TEXT, label TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS module_config (id INTEGER PRIMARY KEY, annee_scolaire TEXT, trimestre_courant INTEGER, nom_professeur TEXT, email_professeur TEXT, date_creation_module TEXT, derniere_synchronisation TEXT)")
        # student_event tables
        conn.execute("""CREATE TABLE IF NOT EXISTS student_event (
            event_id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL,
            agenda_day_id INTEGER, event_type TEXT NOT NULL, event_at TEXT NOT NULL,
            note TEXT, source TEXT DEFAULT 'intranet', created_by INTEGER NOT NULL,
            validated_by INTEGER, created_at TEXT, lieu_label TEXT, subject_label TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS student_event_ref (
            event_id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL,
            agenda_day_id INTEGER, event_type TEXT NOT NULL, event_at TEXT NOT NULL,
            note TEXT, source TEXT DEFAULT 'intranet', created_by INTEGER NOT NULL,
            validated_by INTEGER, created_at TEXT, lieu_label TEXT, subject_label TEXT)""")
        # Seed test data
        conn.execute("INSERT OR REPLACE INTO larcauth_aecuser VALUES (1, 'Dupont', 'Jean', 'jean@ecole.fr')")
        conn.execute("INSERT OR REPLACE INTO larcauth_aecuser VALUES (2, 'Martin', 'Marie', 'marie@ecole.fr')")
        conn.execute("INSERT OR REPLACE INTO larcauth_student VALUES (1, 50, 1)")
        conn.execute("INSERT OR REPLACE INTO larcauth_student VALUES (2, 50, 1)")
        conn.execute("INSERT OR REPLACE INTO larcauth_classroom VALUES (50, 'PEI 5A', 1, 1)")
        conn.execute("INSERT OR REPLACE INTO module_config VALUES (1, '2025-2026', 1, 'Prof Test', 'prof@ecole.fr', datetime('now'), datetime('now'))")
        conn.commit()

    @classmethod
    def tearDownClass(cls):
        from LarcProf.common.database import db
        db.disconnect_all()
        os.unlink(cls._tmp.name)

    def setUp(self):
        from LarcProf.common.database import db
        from LarcProf.common.session import session
        db.connect_sqlite(self._tmp.name)
        session.user_id = 100
        # Nettoyer les events entre chaque test
        conn = db.local_conn
        conn.execute("DELETE FROM student_event")
        conn.execute("DELETE FROM student_event_ref")
        conn.commit()

    # ------------------------------------------------------------------
    def test_insert_event_creates_row(self):
        from LarcProf.common.event_service import EventService
        eid = EventService.insert_event(student_id=1, event_type='absence', created_by=100)
        self.assertLess(eid, 0)  # ID local negatif

        events = EventService.fetch_events_for_student(1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['event_type'], 'absence')
        self.assertEqual(events[0]['student_id'], 1)
        self.assertEqual(events[0]['created_by'], 100)

    def test_insert_event_with_note(self):
        from LarcProf.common.event_service import EventService
        EventService.insert_event(student_id=1, event_type='late', created_by=100, note='Embouteillage')
        events = EventService.fetch_events_for_student(1)
        self.assertEqual(events[0]['note'], 'Embouteillage')

    def test_insert_event_invalid_type_accepted(self):
        from LarcProf.common.event_service import EventService
        eid = EventService.insert_event(student_id=1, event_type='bizarre', created_by=100)
        self.assertLess(eid, 0)

    def test_fetch_events_for_student_ordering(self):
        from LarcProf.common.event_service import EventService
        from datetime import datetime, timedelta
        yesterday = datetime.now() - timedelta(days=1)
        EventService.insert_event(student_id=1, event_type='exit', created_by=100, event_at=yesterday)
        EventService.insert_event(student_id=1, event_type='absence', created_by=100)
        events = EventService.fetch_events_for_student(1)
        self.assertGreaterEqual(len(events), 2)
        self.assertEqual(events[0]['event_type'], 'absence')

    def test_fetch_events_for_student_empty(self):
        from LarcProf.common.event_service import EventService
        events = EventService.fetch_events_for_student(999)
        self.assertEqual(len(events), 0)

    def test_fetch_events_for_class(self):
        from LarcProf.common.event_service import EventService
        EventService.insert_event(student_id=1, event_type='absence', created_by=100)
        EventService.insert_event(student_id=2, event_type='late', created_by=100)
        events = EventService.fetch_events_for_class(50)
        self.assertEqual(len(events), 2)

    def test_fetch_absents_today(self):
        from LarcProf.common.event_service import EventService
        EventService.insert_event(student_id=1, event_type='absence', created_by=100)
        absents = EventService.fetch_absents_today(50)
        self.assertEqual(len(absents), 1)
        self.assertIn('Dupont', absents[0]['student_name'])

    def test_fetch_event_stats(self):
        from LarcProf.common.event_service import EventService
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        EventService.insert_event(student_id=1, event_type='exit', created_by=100)
        EventService.insert_event(student_id=1, event_type='absence', created_by=100)
        EventService.insert_event(student_id=2, event_type='late', created_by=100)

        stats = EventService.fetch_event_stats_for_students([1, 2], '2020-01-01', today)
        self.assertIn(1, stats)
        self.assertIn(2, stats)
        self.assertEqual(stats[1]['exit_count'], 1)
        self.assertEqual(stats[1]['total_events'], 2)
        self.assertEqual(stats[2]['total_events'], 1)

    def test_fetch_event_stats_empty_ids(self):
        from LarcProf.common.event_service import EventService
        stats = EventService.fetch_event_stats_for_students([], '2020-01-01', '2020-12-31')
        self.assertEqual(stats, {})

    def test_event_types_constant(self):
        from LarcProf.common.event_service import EventService
        self.assertIn('absence', EventService.EVENT_TYPES)
        self.assertIn('late', EventService.EVENT_TYPES)
        self.assertIn('exit', EventService.EVENT_TYPES)
        self.assertEqual(EventService.EVENT_TYPES['absence'], 'Absence')
        self.assertEqual(EventService.EVENT_TYPES['late'], 'Retard')


if __name__ == '__main__':
    unittest.main()
