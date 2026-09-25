"""Autres-matières (TDC, Mémoire/EE, CAS, Projet personnel...) — lien direct
élève ↔ slot, sans passage par un groupe de matières (cf. skill graphify,
discussion 2026-09-23) : `larcauth_learner_has_termothersubject.enabled`
toggle directement l'inscription, une ligne par (élève, slot) préexistante
(principe gabarit — jamais d'INSERT/DELETE ici).
"""
from larccommon.database import db
from larccommon.logger import log_error

from LarcConfig.common import db_enrolment


def _conn():
    if not db.is_server_connected:
        return
    c = db.server_conn
    if not c:
        db.connect_intranet()
        c = db.server_conn
    return c


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_supervisors() -> list[dict]:
    """Superviseurs proposables : mêmes enseignants que la combo Enseignant
    (teachadm enabled + is_teacher, collège/lycée) — tous les superviseurs
    actuellement affectés y figurent (vérifié 2026-09-24). Ni `aecuser.is_active`
    (false pour des superviseurs réels) ni « tout teachadm actif » (inclut des
    comptes de test et le primaire) ne conviennent."""
    return db_enrolment.get_teachers()


def get_classroom_othersubjects(classroom_id: int, term_id: int) -> list[dict]:
    """Slots « autre-matière » d'une classe/trimestre, avec superviseur et
    nombre d'élèves actuellement inscrits."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT cts.id, cts.label, cts.enabled, cts.fk_supervisor_id, "
            "a.first_name AS supervisor_first_name, a.last_name AS supervisor_last_name, "
            "COALESCE(enr.n, 0) AS enrolled_count "
            "FROM larcauth_classroom_termothersubject cts "
            "LEFT JOIN larcauth_aecuser a ON a.id = cts.fk_supervisor_id "
            "LEFT JOIN ("
            "  SELECT fk_termothersubject_id, COUNT(*) AS n "
            "  FROM larcauth_learner_has_termothersubject WHERE enabled = TRUE "
            "  GROUP BY fk_termothersubject_id"
            ") enr ON enr.fk_termothersubject_id = cts.id "
            "WHERE cts.fk_classroom_id = %s AND cts.fk_term_id = %s "
            "ORDER BY cts.label",
            (classroom_id, term_id),
        )
        return _rows(cur)
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_classroom_othersubjects: {e}")
        return []


def set_othersubject_label(cts_id: int, label: str) -> bool:
    c = _conn()
    if not c:
        return False
    try:
        from larccommon.audit_context import attach, refresh
        refresh()
        cur = c.cursor()
        attach(c)
        cur.execute(
            "UPDATE larcauth_classroom_termothersubject SET label = %s, updated = NOW() WHERE id = %s",
            (label, cts_id),
        )
        return cur.rowcount > 0
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"set_othersubject_label: {e}")
        return False


def set_othersubject_supervisor(cts_id: int, supervisor_id: int) -> bool:
    c = _conn()
    if not c:
        return False
    try:
        from larccommon.audit_context import attach, refresh
        refresh()
        cur = c.cursor()
        attach(c)
        cur.execute(
            "UPDATE larcauth_classroom_termothersubject SET fk_supervisor_id = %s, updated = NOW() WHERE id = %s",
            (supervisor_id, cts_id),
        )
        return cur.rowcount > 0
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"set_othersubject_supervisor: {e}")
        return False


def count_othersubject_enrolment(cts_id: int) -> int:
    c = _conn()
    if not c:
        return 0
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM larcauth_learner_has_termothersubject "
            "WHERE fk_termothersubject_id = %s AND enabled = TRUE",
            (cts_id,),
        )
        return cur.fetchone()[0]
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"count_othersubject_enrolment: {e}")
        return 0


def set_othersubject_enabled(cts_id: int, enabled: bool, cascade: bool = False) -> dict:
    """Désactive un slot — cascade optionnelle pour désinscrire les élèves
    (même garde-fou que `db_enrolment.set_classroom_termsubject_enabled`)."""
    c = _conn()
    if not c:
        return {'subject_updated': False, 'enrolment_disabled': 0}
    try:
        from larccommon.audit_context import attach, refresh
        refresh()
        cur = c.cursor()
        attach(c)
        n_disabled = 0
        if not enabled and cascade:
            cur.execute(
                "UPDATE larcauth_learner_has_termothersubject "
                "SET enabled = FALSE, ref_teacher = %s, updated = NOW() "
                "WHERE fk_termothersubject_id = %s AND enabled = TRUE",
                (db_enrolment.PLACEHOLDER_TEACHER_ID, cts_id),
            )
            n_disabled = cur.rowcount
        cur.execute(
            "UPDATE larcauth_classroom_termothersubject SET enabled = %s, updated = NOW() WHERE id = %s",
            (enabled, cts_id),
        )
        return {'subject_updated': cur.rowcount > 0, 'enrolment_disabled': n_disabled}
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"set_othersubject_enabled: {e}")
        return {'subject_updated': False, 'enrolment_disabled': 0}


def get_othersubject_links(classroom_id: int, term_id: int) -> list[dict]:
    """Toutes les lignes élève × slot (actives ou non) pour cette classe/trimestre
    — une ligne préexiste déjà pour chaque (élève, slot), jamais d'INSERT ici."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT lht.fk_student_id, lht.fk_termothersubject_id, lht.enabled, lht.ref_teacher "
            "FROM larcauth_learner_has_termothersubject lht "
            "JOIN larcauth_classroom_termothersubject cts ON cts.id = lht.fk_termothersubject_id "
            "WHERE cts.fk_classroom_id = %s AND cts.fk_term_id = %s",
            (classroom_id, term_id),
        )
        return _rows(cur)
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_othersubject_links: {e}")
        return []


def is_enrolled(ref_teacher) -> bool:
    """Un élève est inscrit à un autre-matière ssi un vrai tuteur est renseigné
    (NULL ou placeholder « en attente » = non inscrit)."""
    return ref_teacher is not None and ref_teacher != db_enrolment.PLACEHOLDER_TEACHER_ID


def set_learner_othersubject_tutor(student_id: int, cts_id: int, tutor_id: int | None) -> bool:
    """Affecte un tuteur à un élève sur un slot : `enabled` suit `ref_teacher`
    (tuteur réel → inscrit ; aucun → non inscrit, ref_teacher = placeholder)."""
    c = _conn()
    if not c:
        return False
    try:
        from larccommon.audit_context import attach, refresh
        refresh()
        cur = c.cursor()
        attach(c)
        ref = tutor_id if is_enrolled(tutor_id) else db_enrolment.PLACEHOLDER_TEACHER_ID
        cur.execute(
            "UPDATE larcauth_learner_has_termothersubject "
            "SET enabled = %s, ref_teacher = %s, updated = NOW() "
            "WHERE fk_student_id = %s AND fk_termothersubject_id = %s",
            (is_enrolled(tutor_id), ref, student_id, cts_id),
        )
        return cur.rowcount > 0
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"set_learner_othersubject_tutor: {e}")
        return False


def count_class_active_students(classroom_id: int) -> int:
    c = _conn()
    if not c:
        return 0
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM larcauth_student WHERE s_classroom_id = %s AND enabled = TRUE",
            (classroom_id,),
        )
        return cur.fetchone()[0]
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"count_class_active_students: {e}")
        return 0


def set_class_othersubject_tutor(classroom_id: int, cts_id: int, tutor_id: int | None) -> int:
    """Affecte un tuteur (ou personne) à tous les élèves actifs de la classe
    sur ce slot — UPDATE-only. Retourne le nombre de lignes modifiées."""
    c = _conn()
    if not c:
        return 0
    try:
        from larccommon.audit_context import attach, refresh
        refresh()
        cur = c.cursor()
        attach(c)
        ref = tutor_id if is_enrolled(tutor_id) else db_enrolment.PLACEHOLDER_TEACHER_ID
        cur.execute(
            "UPDATE larcauth_learner_has_termothersubject lht "
            "SET enabled = %s, ref_teacher = %s, updated = NOW() "
            "FROM larcauth_student s "
            "WHERE s.aecuser_ptr_id = lht.fk_student_id AND s.s_classroom_id = %s AND s.enabled = TRUE "
            "AND lht.fk_termothersubject_id = %s",
            (is_enrolled(tutor_id), ref, classroom_id, cts_id),
        )
        return cur.rowcount
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"set_class_othersubject_tutor: {e}")
        return 0
