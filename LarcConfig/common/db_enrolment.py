"""Diagnostic en lecture seule des inscriptions élèves × matières (Phase 0).

Reproduit les anomalies A1-A6 du plan 2026-09-19 (matières par classe et par
élève, PEI/DP). Aucune écriture dans ce module — les phases suivantes (1+)
ajouteront les fonctions d'UPDATE-only à côté, jamais ici en silence.
"""
from larccommon.database import db
from larccommon.logger import log_error
from LarcConfig.common.db_access import TEACHER_ID_MIN, TEACHER_ID_MAX


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


def get_anomaly_a1(term_id: int = None) -> list[dict]:
    """A1 : inscription active sur une matière-classe désactivée."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        sql = (
            "SELECT lht.id, lht.fk_student_id, cts.id AS classroom_termsubject_id, "
            "cts.label, cts.fk_term_id "
            "FROM larcauth_learner_has_termsubject lht "
            "JOIN larcauth_classroom_termsubject cts ON cts.id = lht.fk_classroom_termsubject_id "
            "WHERE lht.enabled = TRUE AND cts.enabled = FALSE"
        )
        params = ()
        if term_id is not None:
            sql += " AND cts.fk_term_id = %s"
            params = (term_id,)
        cur.execute(sql, params)
        return _rows(cur)
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_anomaly_a1: {e}")
        return []


def get_anomaly_a2(term_id: int = None) -> list[dict]:
    """A2 : inscription active d'un élève désactivé (résidu d'année précédente)."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        sql = (
            "SELECT lht.id, lht.fk_student_id, cts.fk_term_id "
            "FROM larcauth_learner_has_termsubject lht "
            "JOIN larcauth_classroom_termsubject cts ON cts.id = lht.fk_classroom_termsubject_id "
            "JOIN larcauth_student s ON s.aecuser_ptr_id = lht.fk_student_id "
            "WHERE lht.enabled = TRUE AND s.enabled = FALSE"
        )
        params = ()
        if term_id is not None:
            sql += " AND cts.fk_term_id = %s"
            params = (term_id,)
        cur.execute(sql, params)
        return _rows(cur)
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_anomaly_a2: {e}")
        return []


def get_anomaly_a3(term_id: int = None) -> list[dict]:
    """A3 : matière-classe active sans aucun élève inscrit."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        sql = (
            "SELECT cts.id, cts.fk_classroom_id, cts.label, cts.fk_term_id "
            "FROM larcauth_classroom_termsubject cts "
            "WHERE cts.enabled = TRUE AND NOT EXISTS ("
            "  SELECT 1 FROM larcauth_learner_has_termsubject lht "
            "  WHERE lht.fk_classroom_termsubject_id = cts.id AND lht.enabled = TRUE"
            ")"
        )
        params = ()
        if term_id is not None:
            sql += " AND cts.fk_term_id = %s"
            params = (term_id,)
        cur.execute(sql, params)
        return _rows(cur)
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_anomaly_a3: {e}")
        return []


def get_anomaly_a4(term_id: int = None) -> list[dict]:
    """A4 : matière-classe active dont le label diffère de celui de sa levelsubject."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        sql = (
            "SELECT cts.id, cts.label AS classroom_label, ls.label AS levelsubject_label, cts.fk_term_id "
            "FROM larcauth_classroom_termsubject cts "
            "JOIN larcauth_levelsubject ls ON ls.id = cts.fk_levelsubject_id "
            "WHERE cts.enabled = TRUE AND cts.label <> ls.label"
        )
        params = ()
        if term_id is not None:
            sql += " AND cts.fk_term_id = %s"
            params = (term_id,)
        cur.execute(sql, params)
        return _rows(cur)
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_anomaly_a4: {e}")
        return []


# fk_teacher_id = 1000 est le placeholder "enseignant en attente" (cf. plan 2026-09-19, A5).
PLACEHOLDER_TEACHER_ID = 1000


def get_anomaly_a5(term_id: int = None) -> list[dict]:
    """A5 : matière-classe active sans enseignant réel (fk_teacher_id = 1000)."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        sql = (
            "SELECT cts.id, cts.fk_classroom_id, cts.label, cts.fk_term_id "
            "FROM larcauth_classroom_termsubject cts "
            "WHERE cts.enabled = TRUE AND cts.fk_teacher_id = %s"
        )
        params = [PLACEHOLDER_TEACHER_ID]
        if term_id is not None:
            sql += " AND cts.fk_term_id = %s"
            params.append(term_id)
        cur.execute(sql, tuple(params))
        return _rows(cur)
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_anomaly_a5: {e}")
        return []


def get_anomaly_a6() -> list[dict]:
    """A6 : élèves actifs dont les matières inscrites diffèrent entre T1 et T2."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT s.aecuser_ptr_id "
            "FROM larcauth_student s "
            "WHERE s.enabled = TRUE AND ("
            "  SELECT array_agg(DISTINCT cts.fk_levelsubject_id ORDER BY cts.fk_levelsubject_id) "
            "  FROM larcauth_learner_has_termsubject lht "
            "  JOIN larcauth_classroom_termsubject cts ON cts.id = lht.fk_classroom_termsubject_id "
            "  WHERE lht.fk_student_id = s.aecuser_ptr_id AND lht.enabled = TRUE AND cts.fk_term_id = 1"
            ") IS DISTINCT FROM ("
            "  SELECT array_agg(DISTINCT cts.fk_levelsubject_id ORDER BY cts.fk_levelsubject_id) "
            "  FROM larcauth_learner_has_termsubject lht "
            "  JOIN larcauth_classroom_termsubject cts ON cts.id = lht.fk_classroom_termsubject_id "
            "  WHERE lht.fk_student_id = s.aecuser_ptr_id AND lht.enabled = TRUE AND cts.fk_term_id = 2"
            ")"
        )
        return _rows(cur)
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_anomaly_a6: {e}")
        return []


# ===== Phase 1 — Onglet A : classes & matières de classe =====

# Programmes dans le périmètre (D6 du plan 2026-09-19) : PEI, MYP, DPFr, DPEn.
# PP et PYP en sont exclus.
PROGRAM_IDS = (12, 13, 22, 23)

# Placeholder "enseignant en attente" — cf. PLACEHOLDER_TEACHER_ID (A5).


def get_programs() -> list[dict]:
    """Programmes du périmètre (PEI, MYP, DPFr, DPEn)."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT id, label, sigle FROM larcauth_program WHERE id IN (%s, %s, %s, %s) ORDER BY sigle",
            PROGRAM_IDS,
        )
        return _rows(cur)
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_programs: {e}")
        return []


def get_classrooms(program_id: int = None) -> list[dict]:
    """Classes du périmètre, avec niveau et programme — triées par programme puis niveau."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        sql = (
            "SELECT c.id, c.label, c.enabled, c.index_in_level, "
            "lv.label AS level_label, p.sigle AS program_sigle, p.id AS fk_program_id "
            "FROM larcauth_classroom c "
            "JOIN larcauth_level lv ON lv.id = c.fk_level_id "
            "JOIN larcauth_program p ON p.id = lv.fk_program_id "
            "WHERE lv.fk_program_id IN (%s, %s, %s, %s)"
        )
        params = list(PROGRAM_IDS)
        if program_id is not None:
            sql += " AND lv.fk_program_id = %s"
            params.append(program_id)
        sql += " ORDER BY p.sigle, lv.level_in_pgm, c.index_in_level"
        cur.execute(sql, tuple(params))
        return _rows(cur)
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_classrooms: {e}")
        return []


def get_classroom_subjects(classroom_id: int, term_id: int) -> list[dict]:
    """Slots de matières d'une classe pour un trimestre, groupés par groupe de matières."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT cts.id, cts.label, cts.enabled, cts.niv_sup, cts.cross_track, cts.fk_teacher_id, cts.couleur, "
            "sg.nr_group_in_pgm, sg.label AS group_label, ls.label AS levelsubject_label, "
            "ta.first_name AS teacher_first_name, ta.last_name AS teacher_last_name, "
            "COALESCE(enr.n, 0) AS enrolled_count "
            "FROM larcauth_classroom_termsubject cts "
            "JOIN larcauth_levelsubject ls ON ls.id = cts.fk_levelsubject_id "
            "JOIN larcauth_subjectgroup sg ON sg.id = ls.fk_subjectgroup_id "
            "LEFT JOIN larcauth_aecuser ta ON ta.id = cts.fk_teacher_id "
            "LEFT JOIN ("
            "  SELECT fk_classroom_termsubject_id, COUNT(*) AS n "
            "  FROM larcauth_learner_has_termsubject WHERE enabled = TRUE "
            "  GROUP BY fk_classroom_termsubject_id"
            ") enr ON enr.fk_classroom_termsubject_id = cts.id "
            "WHERE cts.fk_classroom_id = %s AND cts.fk_term_id = %s "
            # cts.cross_track d'abord : la langue de la classe avant la piste
            # croisée (ex. « Sciences (En) » dans une classe PEI francophone).
            "ORDER BY sg.nr_group_in_pgm, cts.cross_track, cts.label",
            (classroom_id, term_id),
        )
        return _rows(cur)
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_classroom_subjects: {e}")
        return []


def get_teachers() -> list[dict]:
    """Enseignants actifs du périmètre (collège/lycée, mêmes bornes que
    db_access.TEACHER_ID_MIN/MAX) pour peupler la combobox d'affectation.

    Source = `larcauth_teachadm` (enabled + is_teacher), pas `aecuser` :
    `aecuser.is_active` est à false pour la plupart des enseignants
    réellement affectés, et `type_teacher` est trop large (vérifié 2026-09-24)."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT a.id, a.first_name, a.last_name "
            "FROM larcauth_teachadm t "
            "JOIN larcauth_aecuser a ON a.id = t.aecuser_ptr_id "
            "WHERE t.enabled AND t.is_teacher AND a.id BETWEEN %s AND %s "
            "ORDER BY a.last_name, a.first_name",
            (TEACHER_ID_MIN, TEACHER_ID_MAX),
        )
        return _rows(cur)
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_teachers: {e}")
        return []


def set_classroom_label(classroom_id: int, label: str) -> bool:
    """Renomme une classe (jamais de création/suppression — principe gabarit)."""
    c = _conn()
    if not c:
        return False
    try:
        from larccommon.audit_context import attach, refresh
        refresh()
        cur = c.cursor()
        attach(c)
        cur.execute(
            "UPDATE larcauth_classroom SET label = %s, updated = NOW() WHERE id = %s",
            (label, classroom_id),
        )
        return cur.rowcount > 0
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"set_classroom_label: {e}")
        return False


def set_classroom_enabled(classroom_id: int, enabled: bool) -> bool:
    """Active/désactive une classe. Pas de cascade automatique : les autres
    applications filtrent déjà sur `classroom.enabled` (D5/section 3 du plan)."""
    c = _conn()
    if not c:
        return False
    try:
        from larccommon.audit_context import attach, refresh
        refresh()
        cur = c.cursor()
        attach(c)
        cur.execute(
            "UPDATE larcauth_classroom SET enabled = %s, updated = NOW() WHERE id = %s",
            (enabled, classroom_id),
        )
        return cur.rowcount > 0
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"set_classroom_enabled: {e}")
        return False


def set_classroom_termsubject_label(cts_id: int, label: str) -> bool:
    """Renomme un slot de matière-classe."""
    c = _conn()
    if not c:
        return False
    try:
        from larccommon.audit_context import attach, refresh
        refresh()
        cur = c.cursor()
        attach(c)
        cur.execute(
            "UPDATE larcauth_classroom_termsubject SET label = %s, updated = NOW() WHERE id = %s",
            (label, cts_id),
        )
        return cur.rowcount > 0
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"set_classroom_termsubject_label: {e}")
        return False


def set_classroom_termsubject_cross_track(cts_id: int, cross_track: bool) -> bool:
    """Marque/démarque un slot comme enseigné dans l'autre langue que celle
    du programme de la classe (colonne dédiée — cf. migration_20260922_cross_track.sql,
    plus fiable que le texte libre du libellé)."""
    c = _conn()
    if not c:
        return False
    try:
        from larccommon.audit_context import attach, refresh
        refresh()
        cur = c.cursor()
        attach(c)
        cur.execute(
            "UPDATE larcauth_classroom_termsubject SET cross_track = %s, updated = NOW() WHERE id = %s",
            (cross_track, cts_id),
        )
        return cur.rowcount > 0
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"set_classroom_termsubject_cross_track: {e}")
        return False


def set_classroom_termsubject_teacher(cts_id: int, teacher_id: int) -> bool:
    """Affecte un enseignant à un slot de matière-classe."""
    c = _conn()
    if not c:
        return False
    try:
        from larccommon.audit_context import attach, refresh
        refresh()
        cur = c.cursor()
        attach(c)
        cur.execute(
            "UPDATE larcauth_classroom_termsubject SET fk_teacher_id = %s, updated = NOW() WHERE id = %s",
            (teacher_id, cts_id),
        )
        return cur.rowcount > 0
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"set_classroom_termsubject_teacher: {e}")
        return False


# ===== Phase 2 — Onglet B : grille élèves × groupes de matières =====

def get_subject_groups(classroom_id: int, term_id: int) -> list[dict]:
    """Groupes de matières ayant au moins un slot activé dans cette classe/trimestre
    — ce sont les colonnes de la grille."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT DISTINCT sg.nr_group_in_pgm, sg.label AS group_label "
            "FROM larcauth_classroom_termsubject cts "
            "JOIN larcauth_levelsubject ls ON ls.id = cts.fk_levelsubject_id "
            "JOIN larcauth_subjectgroup sg ON sg.id = ls.fk_subjectgroup_id "
            "WHERE cts.fk_classroom_id = %s AND cts.fk_term_id = %s "
            "AND (cts.enabled = TRUE OR EXISTS ("
            "  SELECT 1 FROM larcauth_learner_has_termsubject lht "
            "  WHERE lht.fk_classroom_termsubject_id = cts.id AND lht.enabled = TRUE"
            ")) "
            "ORDER BY sg.nr_group_in_pgm",
            (classroom_id, term_id),
        )
        return _rows(cur)
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_subject_groups: {e}")
        return []


def get_group_choices(classroom_id: int, term_id: int, nr_group_in_pgm: int) -> list[dict]:
    """Slots activés d'un groupe donné — options proposées au sélecteur de cellule."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT cts.id, cts.label, cts.niv_sup, cts.cross_track, cts.couleur "
            "FROM larcauth_classroom_termsubject cts "
            "JOIN larcauth_levelsubject ls ON ls.id = cts.fk_levelsubject_id "
            "JOIN larcauth_subjectgroup sg ON sg.id = ls.fk_subjectgroup_id "
            "WHERE cts.fk_classroom_id = %s AND cts.fk_term_id = %s "
            "AND sg.nr_group_in_pgm = %s AND cts.enabled = TRUE "
            "ORDER BY cts.label",
            (classroom_id, term_id, nr_group_in_pgm),
        )
        return _rows(cur)
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_group_choices: {e}")
        return []


def get_active_students(classroom_id: int) -> list[dict]:
    """Élèves actifs de la classe — lignes de la grille."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT s.aecuser_ptr_id, a.first_name, a.last_name "
            "FROM larcauth_student s "
            "JOIN larcauth_aecuser a ON a.id = s.aecuser_ptr_id "
            "WHERE s.s_classroom_id = %s AND s.enabled = TRUE "
            "ORDER BY a.last_name, a.first_name",
            (classroom_id,),
        )
        return _rows(cur)
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_active_students: {e}")
        return []


def get_student_enrolments(classroom_id: int, term_id: int) -> list[dict]:
    """Inscriptions actives de tous les élèves de la classe, pour ce trimestre
    — l'appelant construit la grille (élève × groupe) à partir de cette liste plate."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT lht.fk_student_id, cts.id AS cts_id, cts.label, cts.niv_sup, "
            "cts.cross_track, cts.couleur, sg.nr_group_in_pgm "
            "FROM larcauth_learner_has_termsubject lht "
            "JOIN larcauth_classroom_termsubject cts ON cts.id = lht.fk_classroom_termsubject_id "
            "JOIN larcauth_levelsubject ls ON ls.id = cts.fk_levelsubject_id "
            "JOIN larcauth_subjectgroup sg ON sg.id = ls.fk_subjectgroup_id "
            "WHERE cts.fk_classroom_id = %s AND cts.fk_term_id = %s AND lht.enabled = TRUE",
            (classroom_id, term_id),
        )
        return _rows(cur)
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_student_enrolments: {e}")
        return []


def set_student_subject(student_id: int, cts_id: int, classroom_id: int, term_id: int,
                         enabled: bool) -> bool:
    """Inscrit/désinscrit UN élève sur UN slot — `classroom_id`/`term_id` sont
    revérifiés côté serveur (pas seulement dans l'UI) via `classroom_termsubject`."""
    c = _conn()
    if not c:
        return False
    try:
        from larccommon.audit_context import attach, refresh
        refresh()
        cur = c.cursor()
        attach(c)
        cur.execute(
            "UPDATE larcauth_learner_has_termsubject lht "
            "SET enabled = %s, updated = NOW() "
            "FROM larcauth_classroom_termsubject cts "
            "WHERE lht.fk_classroom_termsubject_id = cts.id "
            "AND lht.fk_student_id = %s AND lht.fk_classroom_termsubject_id = %s "
            "AND cts.fk_classroom_id = %s AND cts.fk_term_id = %s",
            (enabled, student_id, cts_id, classroom_id, term_id),
        )
        return cur.rowcount > 0
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"set_student_subject: {e}")
        return False


def count_class_subject_preview(classroom_id: int, cts_id: int) -> dict:
    """Aperçu avant application en masse : combien d'élèves actifs de la
    classe, et combien sont déjà inscrits sur ce slot."""
    c = _conn()
    if not c:
        return {'total_active_students': 0, 'already_matching': 0}
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT COUNT(*) AS total, "
            "COUNT(*) FILTER (WHERE lht.enabled) AS already "
            "FROM larcauth_student s "
            "LEFT JOIN larcauth_learner_has_termsubject lht "
            "  ON lht.fk_student_id = s.aecuser_ptr_id AND lht.fk_classroom_termsubject_id = %s "
            "WHERE s.s_classroom_id = %s AND s.enabled = TRUE",
            (cts_id, classroom_id),
        )
        row = cur.fetchone()
        if not row:
            return {'total_active_students': 0, 'already_matching': 0}
        return {'total_active_students': row[0], 'already_matching': row[1]}
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"count_class_subject_preview: {e}")
        return {'total_active_students': 0, 'already_matching': 0}


def count_group_overflow(classroom_id: int, term_id: int, nr_group_in_pgm: int, cts_id: int) -> int:
    """Garde-fou avant application en masse (« Toute la classe ») : combien
    d'élèves actifs ont déjà MAX_SUBJECTS_PER_GROUP matières *autres* que
    `cts_id` dans ce groupe — activer `cts_id` pour eux dépasserait la règle
    « jamais plus de 2 par groupe » (enrolment_rules.MAX_SUBJECTS_PER_GROUP)."""
    from LarcConfig.common.enrolment_rules import MAX_SUBJECTS_PER_GROUP
    c = _conn()
    if not c:
        return 0
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM ("
            "  SELECT s.aecuser_ptr_id, "
            "  COUNT(*) FILTER (WHERE lht.enabled AND cts.id != %s) AS other_count, "
            "  BOOL_OR(lht.enabled AND cts.id = %s) AS already_has_target "
            "  FROM larcauth_student s "
            "  JOIN larcauth_learner_has_termsubject lht ON lht.fk_student_id = s.aecuser_ptr_id "
            "  JOIN larcauth_classroom_termsubject cts ON cts.id = lht.fk_classroom_termsubject_id "
            "  JOIN larcauth_levelsubject ls ON ls.id = cts.fk_levelsubject_id "
            "  JOIN larcauth_subjectgroup sg ON sg.id = ls.fk_subjectgroup_id "
            "  WHERE s.s_classroom_id = %s AND s.enabled = TRUE "
            "  AND cts.fk_classroom_id = %s AND cts.fk_term_id = %s AND sg.nr_group_in_pgm = %s "
            "  GROUP BY s.aecuser_ptr_id"
            ") sub WHERE NOT already_has_target AND other_count >= %s",
            (cts_id, cts_id, classroom_id, classroom_id, term_id, nr_group_in_pgm, MAX_SUBJECTS_PER_GROUP),
        )
        row = cur.fetchone()
        return row[0] if row else 0
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"count_group_overflow: {e}")
        return 0


def set_class_subject(classroom_id: int, term_id: int, cts_id: int, enabled: bool) -> int:
    """Applique un slot à TOUS les élèves actifs de la classe (ligne « Toute la
    classe »). Un seul `UPDATE`, scopé classe+trimestre côté serveur. Retourne
    le nombre de lignes réellement modifiées."""
    c = _conn()
    if not c:
        return 0
    try:
        from larccommon.audit_context import attach, refresh
        refresh()
        cur = c.cursor()
        attach(c)
        cur.execute(
            "UPDATE larcauth_learner_has_termsubject lht "
            "SET enabled = %s, updated = NOW() "
            "FROM larcauth_classroom_termsubject cts, larcauth_student s "
            "WHERE lht.fk_classroom_termsubject_id = cts.id "
            "AND lht.fk_student_id = s.aecuser_ptr_id "
            "AND lht.fk_classroom_termsubject_id = %s "
            "AND cts.fk_term_id = %s "
            "AND s.s_classroom_id = %s AND s.enabled = TRUE "
            "AND lht.enabled IS DISTINCT FROM %s",
            (enabled, cts_id, term_id, classroom_id, enabled),
        )
        return cur.rowcount
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"set_class_subject: {e}")
        return 0


def count_classroom_termsubject_enrolment(cts_id: int) -> int:
    """Nombre d'élèves actuellement inscrits (actifs) sur ce slot — pour
    décider s'il faut proposer la cascade avant une désactivation."""
    c = _conn()
    if not c:
        return 0
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM larcauth_learner_has_termsubject "
            "WHERE fk_classroom_termsubject_id = %s AND enabled = TRUE",
            (cts_id,),
        )
        row = cur.fetchone()
        return row[0] if row else 0
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"count_classroom_termsubject_enrolment: {e}")
        return 0


def set_classroom_termsubject_enabled(cts_id: int, enabled: bool, cascade: bool = False) -> dict:
    """Active/désactive un slot de matière-classe.

    Si `enabled=False` et `cascade=True`, désinscrit d'abord (UPDATE-only, même
    précaution qu'`activate_event_type` : on écrit dans l'ordre qui minimise le
    risque d'état à moitié appliqué, connexions en autocommit=True) les élèves
    actifs sur ce slot, avant de désactiver le slot lui-même. Retourne le
    nombre de lignes réellement modifiées de chaque côté (jamais un booléen
    seul — l'appelant doit pouvoir afficher « N désinscrits »).
    """
    c = _conn()
    if not c:
        return {'subject_updated': False, 'enrolment_disabled': 0}
    try:
        from larccommon.audit_context import attach, refresh
        refresh()
        cur = c.cursor()
        attach(c)
        enrolment_disabled = 0
        if not enabled and cascade:
            cur.execute(
                "UPDATE larcauth_learner_has_termsubject SET enabled = FALSE, updated = NOW() "
                "WHERE fk_classroom_termsubject_id = %s AND enabled = TRUE",
                (cts_id,),
            )
            enrolment_disabled = cur.rowcount
        cur.execute(
            "UPDATE larcauth_classroom_termsubject SET enabled = %s, updated = NOW() WHERE id = %s",
            (enabled, cts_id),
        )
        return {'subject_updated': cur.rowcount > 0, 'enrolment_disabled': enrolment_disabled}
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"set_classroom_termsubject_enabled: {e}")
        return {'subject_updated': False, 'enrolment_disabled': 0}
