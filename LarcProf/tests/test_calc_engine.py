"""Tests unitaires pour CalcEngine."""
import os
import sys
import tempfile
import unittest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, 'LarcCommon'))


class TestCalcEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from LarcProf.common.database import db
        cls._tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        cls._tmp.close()
        db.connect_sqlite(cls._tmp.name)
        conn = db.local_conn
        # Tables minimales
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS larcauth_classroom_termsubject (
                id TEXT PRIMARY KEY, fk_classroom_id INTEGER, fk_levelsubject_id INTEGER,
                fk_term_id INTEGER, fk_teacher_id INTEGER, calc_formula TEXT);
            CREATE TABLE IF NOT EXISTS larcauth_classroom (id INTEGER PRIMARY KEY, label TEXT, fk_level_id INTEGER);
            CREATE TABLE IF NOT EXISTS larcauth_level (id INTEGER PRIMARY KEY, label TEXT, fk_program_id INTEGER);
            CREATE TABLE IF NOT EXISTS larcauth_program (id INTEGER PRIMARY KEY, sigle TEXT, label TEXT);
            CREATE TABLE IF NOT EXISTS larcauth_evaluation (
                id INTEGER PRIMARY KEY, type_evaluation TEXT, index_eval TEXT,
                crit_a TEXT, crit_b TEXT, crit_c TEXT, crit_d TEXT,
                fk_classroom_termsubject_id TEXT);
            CREATE TABLE IF NOT EXISTS larcauth_learner_has_termsubject (
                id INTEGER PRIMARY KEY, fk_student_id INTEGER, fk_classroom_termsubject_id TEXT);
            CREATE TABLE IF NOT EXISTS larcauth_learnerpei_has_termsubjectpei (
                id INTEGER PRIMARY KEY,
                learner_has_termsubject_ptr_id INTEGER,
                fk_student_id INTEGER,
                f01_note_a INTEGER, f01_note_c INTEGER,
                s01_note_a INTEGER, s01_note_b INTEGER, s01_note_c INTEGER, s01_note_d INTEGER,
                s02_note_a INTEGER, s02_note_b INTEGER, s02_note_c INTEGER, s02_note_d INTEGER);
            CREATE TABLE IF NOT EXISTS larcauth_learnerdp_has_termsubjectdp (
                id INTEGER PRIMARY KEY,
                learner_has_termsubject_ptr_id INTEGER,
                fk_student_id INTEGER,
                ei_note DOUBLE, f01_note DOUBLE, f02_note DOUBLE,
                s01_note DOUBLE, s02_note DOUBLE, s03_note DOUBLE);
            CREATE TABLE IF NOT EXISTS module_config (
                id INTEGER PRIMARY KEY, annee_scolaire TEXT, trimestre_courant INTEGER,
                nom_professeur TEXT, email_professeur TEXT);
        """)
        conn.execute("INSERT INTO module_config VALUES (1, '2026', 1, 'Prof', 'p@ecole.fr')")
        # Seed program
        conn.execute("INSERT OR REPLACE INTO larcauth_program VALUES (1, 'PEI', 'PEI')")
        conn.execute("INSERT OR REPLACE INTO larcauth_program VALUES (2, 'DP', 'DP')")
        conn.execute("INSERT OR REPLACE INTO larcauth_level VALUES (1, 'Niv1', 1)")
        conn.execute("INSERT OR REPLACE INTO larcauth_classroom VALUES (50, 'PEI5A', 1)")
        conn.execute("INSERT OR REPLACE INTO larcauth_classroom_termsubject VALUES ('100', 50, 1, 1, 1, NULL)")
        conn.execute("INSERT OR REPLACE INTO larcauth_learner_has_termsubject VALUES (1, 1, '100')")
        conn.execute("INSERT OR REPLACE INTO larcauth_learnerpei_has_termsubjectpei VALUES (1, 1, 1, 5, 6, 6, 5, 7, 4, 4, 3, 6, 5)")
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
        session.term_id = 1

    # ── Formula parsing ────────────────────────────────────────

    def test_get_formula_null_returns_default_pei(self):
        from LarcProf.common.calc_engine import CalcEngine
        formula = CalcEngine.get_formula(100)
        self.assertEqual(formula["type"], "PEI")
        self.assertEqual(formula["criteria"], ["A", "B", "C", "D"])

    def test_save_and_load_formula(self):
        from LarcProf.common.calc_engine import CalcEngine
        import json
        formula = {"type": "PEI", "criteria": ["A", "C"], "formative_weight": 0.3,
                    "summative_weight": 0.7, "conversion": {"method": "linear"}}
        CalcEngine.save_formula(100, formula)
        loaded = CalcEngine.get_formula(100)
        self.assertEqual(loaded["criteria"], ["A", "C"])
        self.assertEqual(loaded["conversion"]["method"], "linear")

    # ── Boundaries ─────────────────────────────────────────────

    def test_apply_boundaries(self):
        from LarcProf.common.calc_engine import CalcEngine
        boundaries = [
            {"min": 0, "max": 5, "note": 1},
            {"min": 6, "max": 9, "note": 2},
            {"min": 10, "max": 14, "note": 3},
            {"min": 15, "max": 18, "note": 4},
            {"min": 19, "max": 23, "note": 5},
            {"min": 24, "max": 27, "note": 6},
            {"min": 28, "max": 32, "note": 7},
        ]
        self.assertEqual(CalcEngine._apply_boundaries(3, boundaries), 1)
        self.assertEqual(CalcEngine._apply_boundaries(7, boundaries), 2)
        self.assertEqual(CalcEngine._apply_boundaries(12, boundaries), 3)
        self.assertEqual(CalcEngine._apply_boundaries(17, boundaries), 4)
        self.assertEqual(CalcEngine._apply_boundaries(21, boundaries), 5)
        self.assertEqual(CalcEngine._apply_boundaries(26, boundaries), 6)
        self.assertEqual(CalcEngine._apply_boundaries(30, boundaries), 7)

    def test_apply_boundaries_out_of_range(self):
        from LarcProf.common.calc_engine import CalcEngine
        boundaries = [{"min": 0, "max": 5, "note": 1}, {"min": 6, "max": 10, "note": 2}]
        self.assertEqual(CalcEngine._apply_boundaries(100, boundaries), 2)

    # ── Recalc boundaries ──────────────────────────────────────

    def test_recalc_boundaries_4_criteria(self):
        from LarcProf.common.calc_engine import _recalc_boundaries
        b = _recalc_boundaries(4)
        self.assertEqual(len(b), 7)
        self.assertEqual(b[-1]["max"], 32)
        self.assertEqual(b[0]["note"], 1)

    def test_recalc_boundaries_1_criterion(self):
        from LarcProf.common.calc_engine import _recalc_boundaries
        b = _recalc_boundaries(1)
        self.assertEqual(b[-1]["max"], 8)

    # ── Templates ──────────────────────────────────────────────

    def test_templates_pei(self):
        from LarcProf.common.calc_engine import CalcEngine
        templates = CalcEngine.get_templates_pei()
        self.assertIn("4c", templates)
        self.assertIn("1c", templates)
        self.assertEqual(templates["4c"]["criteria"], ["A", "B", "C", "D"])
        self.assertEqual(templates["1c"]["criteria"], ["A"])

    def test_templates_dp(self):
        from LarcProf.common.calc_engine import CalcEngine
        templates = CalcEngine.get_templates_dp()
        self.assertIn("standard", templates)
        self.assertIn("simple", templates)
        self.assertEqual(templates["standard"]["conversion"]["method"], "formula")
        self.assertEqual(templates["simple"]["conversion"]["method"], "simple_avg")

    # ── PEI Computation ────────────────────────────────────────

    def test_compute_pei_basic(self):
        from LarcProf.common.calc_engine import CalcEngine
        conn = self._conn()
        # Seed evaluations actives
        conn.execute("DELETE FROM larcauth_evaluation")
        conn.execute("INSERT INTO larcauth_evaluation VALUES "
                     "(1, 'F', '01', '1', '0', '1', '0', '100'),"   # F01: A,C actifs
                     "(2, 'S', '01', '1', '1', '1', '1', '100')")   # S01: A,B,C,D actifs
        conn.commit()

        # save formula
        CalcEngine.save_formula(100, {
            "type": "PEI", "criteria": ["A", "B", "C", "D"],
            "formative_weight": 0.4, "summative_weight": 0.6,
            "conversion": {"method": "linear"},
        })

        note = CalcEngine.compute_note(1, 100)
        self.assertIsNotNone(note)

    def test_compute_pei_no_learner(self):
        from LarcProf.common.calc_engine import CalcEngine
        note = CalcEngine.compute_note(999, 100)
        self.assertIsNone(note)

    # ── Helpers ────────────────────────────────────────────────

    def _conn(self):
        from LarcProf.common.database import db
        return db.local_conn
