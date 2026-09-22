"""Tests db_enrolment — Phase 2 : grille élèves × groupes de matières (Onglet B)."""
from unittest.mock import patch

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


def _fake(rows=None, columns=None, fetchone=None):
    cur = FakeCursor()
    cur._next_fetchall = rows or []
    cur.description = [(c,) for c in (columns or [])]
    cur._next_fetchone = fetchone
    conn = FakeConn()
    conn._cur = cur
    return conn, cur


class TestGetSubjectGroups:
    def test_scopes_to_classroom_and_term(self):
        conn, cur = _fake([], ['nr_group_in_pgm'])
        with patch.object(db_enrolment, "_conn", return_value=conn):
            db_enrolment.get_subject_groups(classroom_id=2211, term_id=1)
        sql, params = cur.executed[0]
        assert "cts.fk_classroom_id = %s" in sql
        assert "cts.fk_term_id = %s" in sql
        assert params == (2211, 1)

    def test_includes_enabled_slots_or_slots_with_an_active_anomalous_enrolment(self):
        # A1 (Phase 0) : une inscription active peut pointer vers un slot
        # depuis désactivé. La colonne du groupe ne doit pas disparaître pour
        # autant, sinon ces inscriptions deviennent invisibles dans la grille.
        conn, cur = _fake([], ['nr_group_in_pgm'])
        with patch.object(db_enrolment, "_conn", return_value=conn):
            db_enrolment.get_subject_groups(classroom_id=2211, term_id=1)
        sql = cur.executed[0][0]
        assert "cts.enabled = TRUE" in sql
        assert "lht.enabled = TRUE" in sql
        assert "OR" in sql


class TestGetGroupChoices:
    def test_scopes_to_classroom_term_and_group_only_enabled(self):
        conn, cur = _fake([], ['id'])
        with patch.object(db_enrolment, "_conn", return_value=conn):
            db_enrolment.get_group_choices(classroom_id=2211, term_id=1, nr_group_in_pgm=3)
        sql, params = cur.executed[0]
        assert "cts.fk_classroom_id = %s" in sql
        assert "cts.fk_term_id = %s" in sql
        assert "sg.nr_group_in_pgm = %s" in sql
        assert "cts.enabled = TRUE" in sql
        assert params == (2211, 1, 3)


class TestGetActiveStudents:
    def test_scopes_to_classroom_and_only_enabled_students(self):
        conn, cur = _fake([], ['aecuser_ptr_id'])
        with patch.object(db_enrolment, "_conn", return_value=conn):
            db_enrolment.get_active_students(classroom_id=2211)
        sql, params = cur.executed[0]
        assert "s.s_classroom_id = %s" in sql
        assert "s.enabled = TRUE" in sql
        assert params == (2211,)


class TestGetStudentEnrolments:
    def test_scopes_to_classroom_term_and_active_enrolment(self):
        conn, cur = _fake([], ['fk_student_id'])
        with patch.object(db_enrolment, "_conn", return_value=conn):
            db_enrolment.get_student_enrolments(classroom_id=2211, term_id=1)
        sql, params = cur.executed[0]
        assert "cts.fk_classroom_id = %s" in sql
        assert "cts.fk_term_id = %s" in sql
        assert "lht.enabled = TRUE" in sql
        assert params == (2211, 1)


class TestSetStudentSubject:
    def test_enrols_student_scoped_to_classroom_and_term(self):
        conn, cur = _fake()
        cur.rowcount = 1
        with patch.object(db_enrolment, "_conn", return_value=conn), \
             patch("larccommon.audit_context.refresh"), \
             patch("larccommon.audit_context.attach"):
            ok = db_enrolment.set_student_subject(
                student_id=231101, cts_id=45678, classroom_id=2311, term_id=1, enabled=True)
        assert ok is True
        sql, params = cur.executed[-1]
        assert "UPDATE larcauth_learner_has_termsubject" in sql
        assert "cts.fk_classroom_id = %s" in sql
        assert "cts.fk_term_id = %s" in sql
        assert "updated = NOW()" in sql
        assert params[0] is True
        assert 231101 in params and 45678 in params and 2311 in params and 1 in params

    def test_returns_false_when_no_matching_row_in_scope(self):
        conn, cur = _fake()
        cur.rowcount = 0
        with patch.object(db_enrolment, "_conn", return_value=conn), \
             patch("larccommon.audit_context.refresh"), \
             patch("larccommon.audit_context.attach"):
            ok = db_enrolment.set_student_subject(
                student_id=231101, cts_id=99999, classroom_id=2311, term_id=1, enabled=True)
        assert ok is False


class TestCountClassSubjectPreview:
    def test_counts_active_students_and_already_enrolled(self):
        conn, cur = _fake(fetchone=(17, 2))
        with patch.object(db_enrolment, "_conn", return_value=conn):
            preview = db_enrolment.count_class_subject_preview(classroom_id=2211, cts_id=45678)
        assert preview == {'total_active_students': 17, 'already_matching': 2}
        sql, params = cur.executed[0]
        assert "s.s_classroom_id = %s" in sql
        assert set(params) == {2211, 45678}


class TestSetClassSubject:
    def test_enables_for_every_active_student_of_the_classroom_scoped_to_term(self):
        conn, cur = _fake()
        cur.rowcount = 17
        with patch.object(db_enrolment, "_conn", return_value=conn), \
             patch("larccommon.audit_context.refresh"), \
             patch("larccommon.audit_context.attach"):
            n = db_enrolment.set_class_subject(classroom_id=2211, term_id=1, cts_id=45678, enabled=True)
        assert n == 17
        sql, params = cur.executed[-1]
        assert "UPDATE larcauth_learner_has_termsubject" in sql
        assert "s.s_classroom_id = %s" in sql
        assert "cts.fk_term_id = %s" in sql
        assert params[0] is True

    def test_disabling_scoped_the_same_way(self):
        conn, cur = _fake()
        cur.rowcount = 5
        with patch.object(db_enrolment, "_conn", return_value=conn), \
             patch("larccommon.audit_context.refresh"), \
             patch("larccommon.audit_context.attach"):
            n = db_enrolment.set_class_subject(classroom_id=2211, term_id=1, cts_id=45678, enabled=False)
        assert n == 5
        sql, params = cur.executed[-1]
        assert params[0] is False
