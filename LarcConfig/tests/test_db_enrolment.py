"""Tests db_enrolment — diagnostic en lecture seule des inscriptions (Phase 0).

Les anomalies A1-A6 sont celles du plan 2026-09-19
(docs/superpowers/plans/2026-09-19-larcconfig-configuration-effectifs-plan.md).
"""
import inspect
import re
from unittest.mock import patch

import pytest

from LarcConfig.common import db_enrolment


class FakeCursor:
    def __init__(self):
        self.executed = []
        self.description = []
        self._next_fetchall = []
        self._next_fetchone = None
        self.rowcount = 0

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self._next_fetchall

    def fetchone(self):
        return self._next_fetchone


class FakeConn:
    def cursor(self):
        return self._cur


def _fake(rows, columns):
    cur = FakeCursor()
    cur._next_fetchall = rows
    cur.description = [(c,) for c in columns]
    conn = FakeConn()
    conn._cur = cur
    return conn, cur


class TestA1ActiveEnrolmentOnDisabledSubject:
    def test_joins_enabled_enrolment_to_disabled_classroom_subject(self):
        conn, cur = _fake([], ['id'])
        with patch.object(db_enrolment, "_conn", return_value=conn):
            db_enrolment.get_anomaly_a1(term_id=None)
        sql = cur.executed[0][0]
        assert "larcauth_learner_has_termsubject" in sql
        assert "larcauth_classroom_termsubject" in sql
        assert "lht.enabled = TRUE" in sql
        assert "cts.enabled = FALSE" in sql

    def test_scopes_to_term_when_given(self):
        conn, cur = _fake([], ['id'])
        with patch.object(db_enrolment, "_conn", return_value=conn):
            db_enrolment.get_anomaly_a1(term_id=1)
        sql, params = cur.executed[0]
        assert "cts.fk_term_id = %s" in sql
        assert params == (1,)


class TestA2ActiveEnrolmentOfDisabledStudent:
    def test_joins_enrolment_to_disabled_student(self):
        conn, cur = _fake([], ['id'])
        with patch.object(db_enrolment, "_conn", return_value=conn):
            db_enrolment.get_anomaly_a2(term_id=None)
        sql = cur.executed[0][0]
        assert "larcauth_student" in sql
        assert "lht.enabled = TRUE" in sql
        assert "s.enabled = FALSE" in sql


class TestA3ActiveSubjectWithoutStudent:
    def test_finds_enabled_subject_with_no_active_enrolment(self):
        conn, cur = _fake([], ['id'])
        with patch.object(db_enrolment, "_conn", return_value=conn):
            db_enrolment.get_anomaly_a3(term_id=None)
        sql = cur.executed[0][0]
        assert "cts.enabled = TRUE" in sql
        assert "NOT EXISTS" in sql


class TestA4LabelMismatch:
    def test_compares_classroom_subject_label_to_levelsubject_label(self):
        conn, cur = _fake([], ['id'])
        with patch.object(db_enrolment, "_conn", return_value=conn):
            db_enrolment.get_anomaly_a4(term_id=None)
        sql = cur.executed[0][0]
        assert "larcauth_levelsubject" in sql
        assert "cts.label" in sql and "ls.label" in sql


class TestA5NoRealTeacher:
    def test_flags_placeholder_teacher_1000(self):
        conn, cur = _fake([], ['id'])
        with patch.object(db_enrolment, "_conn", return_value=conn):
            db_enrolment.get_anomaly_a5(term_id=None)
        sql, params = cur.executed[0]
        assert "cts.fk_teacher_id = %s" in sql
        assert 1000 in params


class TestA6SubjectsDifferBetweenTerms:
    def test_compares_term1_and_term2_subject_sets_per_student(self):
        conn, cur = _fake([], ['aecuser_ptr_id'])
        with patch.object(db_enrolment, "_conn", return_value=conn):
            db_enrolment.get_anomaly_a6()
        sql = cur.executed[0][0]
        assert "fk_term_id = 1" in sql
        assert "fk_term_id = 2" in sql
        assert "IS DISTINCT FROM" in sql


def test_module_never_writes_insert_or_delete():
    source = inspect.getsource(db_enrolment)
    assert not re.search(r"\bINSERT\s+INTO\b", source, re.IGNORECASE)
    assert not re.search(r"\bDELETE\s+FROM\b", source, re.IGNORECASE)


# ===== Phase 1 — Onglet A : classes & matières de classe =====

class TestGetPrograms:
    def test_filters_to_pei_myp_dpfr_dpen(self):
        conn, cur = _fake([], ['id'])
        with patch.object(db_enrolment, "_conn", return_value=conn):
            db_enrolment.get_programs()
        sql, params = cur.executed[0]
        assert "larcauth_program" in sql
        assert set(params) == {12, 13, 22, 23}


class TestGetClassrooms:
    def test_scopes_to_program_when_given(self):
        conn, cur = _fake([], ['id'])
        with patch.object(db_enrolment, "_conn", return_value=conn):
            db_enrolment.get_classrooms(program_id=22)
        sql, params = cur.executed[0]
        assert "larcauth_classroom" in sql
        assert "fk_program_id = %s" in sql
        assert 22 in params

    def test_without_program_still_scoped_to_the_four_programs(self):
        conn, cur = _fake([], ['id'])
        with patch.object(db_enrolment, "_conn", return_value=conn):
            db_enrolment.get_classrooms(program_id=None)
        sql, params = cur.executed[0]
        assert set(params) == {12, 13, 22, 23}


class TestGetClassroomSubjects:
    def test_scopes_to_classroom_and_term_and_joins_group_and_teacher(self):
        conn, cur = _fake([], ['id'])
        with patch.object(db_enrolment, "_conn", return_value=conn):
            db_enrolment.get_classroom_subjects(classroom_id=2311, term_id=1)
        sql, params = cur.executed[0]
        assert "cts.fk_classroom_id = %s" in sql
        assert "cts.fk_term_id = %s" in sql
        assert params == (2311, 1)
        assert "larcauth_subjectgroup" in sql
        assert "larcauth_teachadm" in sql or "larcauth_aecuser" in sql
        assert "learner_has_termsubject" in sql  # nb élèves inscrits
        assert "cts.cross_track" in sql


class TestSetClassroomLabel:
    def test_updates_label_and_timestamp_scoped_to_id(self):
        conn, cur = _fake([], [])
        cur.rowcount = 1
        with patch.object(db_enrolment, "_conn", return_value=conn), \
             patch("larccommon.audit_context.refresh"), \
             patch("larccommon.audit_context.attach"):
            ok = db_enrolment.set_classroom_label(2311, "DP-1Fr (renommé)")
        assert ok is True
        sql, params = cur.executed[-1]
        assert "UPDATE larcauth_classroom" in sql
        assert "updated = NOW()" in sql
        assert params == ("DP-1Fr (renommé)", 2311)


class TestSetClassroomEnabled:
    def test_updates_enabled_flag_scoped_to_id_no_cascade(self):
        conn, cur = _fake([], [])
        cur.rowcount = 1
        with patch.object(db_enrolment, "_conn", return_value=conn), \
             patch("larccommon.audit_context.refresh"), \
             patch("larccommon.audit_context.attach"):
            ok = db_enrolment.set_classroom_enabled(2312, True)
        assert ok is True
        sql, params = cur.executed[-1]
        assert "UPDATE larcauth_classroom" in sql
        assert "enabled" in sql
        assert params == (True, 2312)


class TestSetClassroomTermsubjectLabel:
    def test_updates_label_scoped_to_id(self):
        conn, cur = _fake([], [])
        cur.rowcount = 1
        with patch.object(db_enrolment, "_conn", return_value=conn), \
             patch("larccommon.audit_context.refresh"), \
             patch("larccommon.audit_context.attach"):
            ok = db_enrolment.set_classroom_termsubject_label(45678, "Économie NS")
        assert ok is True
        sql, params = cur.executed[-1]
        assert "UPDATE larcauth_classroom_termsubject" in sql
        assert "updated = NOW()" in sql
        assert params == ("Économie NS", 45678)


class TestSetClassroomTermsubjectCrossTrack:
    def test_updates_cross_track_scoped_to_id(self):
        conn, cur = _fake([], [])
        cur.rowcount = 1
        with patch.object(db_enrolment, "_conn", return_value=conn), \
             patch("larccommon.audit_context.refresh"), \
             patch("larccommon.audit_context.attach"):
            ok = db_enrolment.set_classroom_termsubject_cross_track(45678, True)
        assert ok is True
        sql, params = cur.executed[-1]
        assert "UPDATE larcauth_classroom_termsubject" in sql
        assert "cross_track" in sql
        assert "updated = NOW()" in sql
        assert params == (True, 45678)


class TestCountClassroomTermsubjectEnrolment:
    def test_counts_active_enrolments_for_the_slot(self):
        conn, cur = _fake([], ['n'])
        cur._next_fetchone = (7,)
        with patch.object(db_enrolment, "_conn", return_value=conn):
            n = db_enrolment.count_classroom_termsubject_enrolment(45678)
        assert n == 7
        sql, params = cur.executed[0]
        assert "fk_classroom_termsubject_id = %s" in sql
        assert "enabled = TRUE" in sql
        assert params == (45678,)


class TestSetClassroomTermsubjectEnabled:
    def test_enabling_does_not_touch_enrolment(self):
        conn, cur = _fake([], [])
        cur.rowcount = 1
        with patch.object(db_enrolment, "_conn", return_value=conn), \
             patch("larccommon.audit_context.refresh"), \
             patch("larccommon.audit_context.attach"):
            result = db_enrolment.set_classroom_termsubject_enabled(45678, True)
        assert result['subject_updated'] is True
        assert result['enrolment_disabled'] == 0
        assert len(cur.executed) == 1  # un seul UPDATE (le slot)

    def test_disabling_without_cascade_leaves_enrolment_untouched(self):
        conn, cur = _fake([], [])
        cur.rowcount = 1
        with patch.object(db_enrolment, "_conn", return_value=conn), \
             patch("larccommon.audit_context.refresh"), \
             patch("larccommon.audit_context.attach"):
            result = db_enrolment.set_classroom_termsubject_enabled(45678, False, cascade=False)
        assert result['subject_updated'] is True
        assert result['enrolment_disabled'] == 0
        assert len(cur.executed) == 1

    def test_disabling_with_cascade_also_disables_enrolment_first(self):
        conn, cur = _fake([], [])
        cur.rowcount = 3
        with patch.object(db_enrolment, "_conn", return_value=conn), \
             patch("larccommon.audit_context.refresh"), \
             patch("larccommon.audit_context.attach"):
            result = db_enrolment.set_classroom_termsubject_enabled(45678, False, cascade=True)
        assert result['subject_updated'] is True
        assert result['enrolment_disabled'] == 3
        assert len(cur.executed) == 2
        enrolment_sql = cur.executed[0][0]
        subject_sql = cur.executed[1][0]
        assert "larcauth_learner_has_termsubject" in enrolment_sql
        assert "larcauth_classroom_termsubject" in subject_sql


def test_write_functions_never_use_insert_or_delete():
    # Redondant avec test_module_never_writes_insert_or_delete mais nommé
    # explicitement pour les nouvelles fonctions d'écriture Phase 1.
    source = inspect.getsource(db_enrolment)
    assert "INSERT INTO" not in source.upper().replace("\n", " ")
    assert "DELETE FROM" not in source.upper().replace("\n", " ")


class TestLiveDatabaseCounts:
    """Intégration lecture seule contre la vraie base — ignorée si indisponible.

    Les comptes ne sont PAS gelés sur les valeurs du plan 2026-09-19 : ce sont
    des mesures d'un instant sur une base de production vivante (ex. la
    cascade de rentrée fait grossir A2 au fil des désinscriptions), pas des
    invariants. On vérifie seulement que chaque requête s'exécute et renvoie
    des lignes bien formées.
    """

    @pytest.fixture(autouse=True)
    def _require_db(self):
        from larccommon.database import db
        if not db.connect_intranet():
            pytest.skip("base intranet indisponible")

    @pytest.mark.parametrize("fn, expects_term_scope", [
        (db_enrolment.get_anomaly_a1, True),
        (db_enrolment.get_anomaly_a2, True),
        (db_enrolment.get_anomaly_a3, True),
        (db_enrolment.get_anomaly_a4, True),
        (db_enrolment.get_anomaly_a5, True),
    ])
    def test_anomaly_runs_and_returns_dict_rows(self, fn, expects_term_scope):
        rows = fn(term_id=None)
        assert isinstance(rows, list)
        assert all(isinstance(r, dict) for r in rows)

    def test_a6_runs_and_returns_dict_rows(self):
        rows = db_enrolment.get_anomaly_a6()
        assert isinstance(rows, list)
        assert all(isinstance(r, dict) for r in rows)

    def test_a1_matches_plan_baseline_unaffected_by_rentree_cascade(self):
        # A1 ne dépend que de classroom_termsubject (jamais touché par la
        # cascade de rentrée du 2026-09-22) : seule anomalie dont le compte
        # du plan 2026-09-19 reste valide tel quel.
        assert len(db_enrolment.get_anomaly_a1(term_id=None)) == 280
