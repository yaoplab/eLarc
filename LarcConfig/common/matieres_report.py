"""Données d'impression / d'export du panneau « Matières par classe ».

Construit, pour UNE classe et UN trimestre, les trois pages de données du
panneau (Classes & matières, Élèves, Autres-matières) sous forme de tableaux de
texte neutres. Les trois sorties (PDF/impression, Excel, sauvegarde JSON) lisent
ce même modèle : elles ne relisent jamais l'écran, donc le tri ou le filtre en
cours à l'écran n'altère pas le document.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from LarcConfig.common import db_enrolment, db_othersubjects
from LarcConfig.common.enrolment_rules import Subject, dp_status, dp_status_reasons

SCHOOL_NAME = "Arc-en-Ciel"
BACKUP_FORMAT = "larcconfig-matieres-classe/1"


@dataclass
class Table:
    title: str
    columns: list[str]
    rows: list[list[str]]
    aligns: list[str] = field(default_factory=list)   # 'l' | 'c' par colonne
    flags: list[str] = field(default_factory=list)    # '' | 'warn' | 'muted' par ligne
    note: str = ""                                    # phrase affichée sous le tableau
    empty_text: str = "Aucune donnée."


@dataclass
class Section:
    title: str
    tables: list[Table]


@dataclass
class Report:
    classroom_label: str
    program_sigle: str
    term_no: int
    year_label: str
    generated: datetime.datetime
    sections: list[Section]
    backup: dict = field(default_factory=dict)

    @property
    def title(self) -> str:
        return f"Matières de classe — {self.classroom_label}"

    @property
    def subtitle(self) -> str:
        parts = [self.program_sigle, f"Trimestre {self.term_no}", self.year_label]
        return " · ".join(p for p in parts if p)

    @property
    def file_stem(self) -> str:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in self.classroom_label)
        return f"Matieres_{safe}_T{self.term_no}_{self.generated:%Y%m%d}"


def _person(last, first) -> str:
    # Le compte « en attente » a le même nom et prénom : ne pas le dupliquer.
    last, first = (last or "").strip(), (first or "").strip()
    return last if last == first else f"{last} {first}".strip()


def _classes_table(subjects: list[dict], is_dp: bool) -> Table:
    active = [s for s in subjects if s['enabled']]
    with_cross = any(s.get('cross_track') for s in active)   # colonne omise si jamais utilisée
    columns = (["Groupe", "Matière"] + (["Niveau"] if is_dp else []) + ["Enseignant", "Inscrits"]
               + (["Piste croisée"] if with_cross else []))
    aligns = ["l", "l"] + (["c"] if is_dp else []) + ["l", "c"] + (["c"] if with_cross else [])
    rows = []
    for s in active:
        row = [s['group_label'], s['label']]
        if is_dp:
            row.append("NS" if s['niv_sup'] else "NM")
        row += [_person(s.get('teacher_last_name'), s.get('teacher_first_name')), str(s['enrolled_count'])]
        if with_cross:
            row.append("Oui" if s.get('cross_track') else "")
        rows.append(row)
    inactive = len(subjects) - len(active)
    note = f"{len(active)} matière(s) active(s)."
    if inactive:
        note += f" {inactive} emplacement(s) inactif(s) non listé(s)."
    return Table("Matières de la classe", columns, rows, aligns, note=note,
                 empty_text="Aucune matière active pour ce trimestre.")


def _students_table(groups: list[dict], students: list[dict], enrolments: list[dict],
                    is_dp: bool) -> Table:
    by_cell: dict[tuple, list[dict]] = {}
    for e in enrolments:
        by_cell.setdefault((e['fk_student_id'], e['nr_group_in_pgm']), []).append(e)
    columns = ["Élève"] + [g['group_label'] for g in groups] + (["Statut DP"] if is_dp else [])
    rows, flags = [], []
    for st in students:
        sid = st['aecuser_ptr_id']
        row, subjects = [f"{st['last_name']} {st['first_name']}"], []
        for g in groups:
            cell = by_cell.get((sid, g['nr_group_in_pgm']), [])
            subjects += [Subject(group=g['nr_group_in_pgm'], niv_sup=bool(e.get('niv_sup'))) for e in cell]
            row.append("\n".join(
                e['label'] + (" (*)" if e.get('cross_track') else "") for e in cell))
        flag = ""
        if is_dp:
            status = dp_status(subjects)
            row.append("Conforme" if status.compliant
                       else "Non conforme — " + " ; ".join(dp_status_reasons(status)))
            flag = "" if status.compliant else "warn"
        rows.append(row)
        flags.append(flag)
    note = "* = piste croisée" + ("  ·  NS = niveau supérieur" if is_dp else "")
    aligns = ["l"] + ["c"] * len(groups) + (["l"] if is_dp else [])
    return Table("Inscriptions des élèves par groupe de matières", columns, rows,
                 aligns, flags, note=note, empty_text="Aucun élève actif dans cette classe.")


def _others_tables(slots: list[dict], students: list[dict], links: list[dict]) -> list[Table]:
    active = [s for s in slots if s['enabled']]
    slot_rows = [[s['label'],
                  _person(s.get('supervisor_last_name'), s.get('supervisor_first_name')),
                  str(s['enrolled_count'])] for s in active]
    slots_table = Table("Autres-matières de la classe", ["Matière", "Superviseur", "Inscrits"],
                        slot_rows, ["l", "l", "c"], note=f"{len(active)} slot(s) actif(s).",
                        empty_text="Aucune autre matière active pour ce trimestre.")
    if not active:
        return [slots_table]

    tutors = {(l['fk_student_id'], l['fk_termothersubject_id']): l['ref_teacher'] for l in links}
    teachers = {t['id']: _person(t['last_name'], t['first_name']) for t in db_othersubjects.get_supervisors()}
    rows = []
    for st in students:
        row = [f"{st['last_name']} {st['first_name']}"]
        for s in active:
            ref = tutors.get((st['aecuser_ptr_id'], s['id']))
            row.append(teachers.get(ref, f"ID {ref}") if db_othersubjects.is_enrolled(ref) else "")
        rows.append(row)
    columns = ["Élève"] + [s['label'] for s in active]
    grid = Table("Tuteurs des élèves par autre matière", columns, rows, ["l"] * len(columns),
                 note="La cellule indique le tuteur de l'élève ; vide = non inscrit.",
                 empty_text="Aucun élève actif dans cette classe.")
    return [slots_table, grid]


def build_report(classroom: dict, term_no: int, term_id: int, year_label: str = "") -> Report:
    """`classroom` = ligne de db_enrolment.get_classrooms (id, label, program_sigle…)."""
    cid = classroom['id']
    sigle = classroom.get('program_sigle') or ""
    is_dp = sigle.upper().startswith('DP')

    subjects = db_enrolment.get_classroom_subjects(cid, term_id)
    groups = db_enrolment.get_subject_groups(cid, term_id)
    students = db_enrolment.get_active_students(cid)
    enrolments = db_enrolment.get_student_enrolments(cid, term_id)
    slots = db_othersubjects.get_classroom_othersubjects(cid, term_id)
    links = db_othersubjects.get_othersubject_links(cid, term_id)

    sections = [
        Section("Classes & matières", [_classes_table(subjects, is_dp)]),
        Section("Élèves", [_students_table(groups, students, enrolments, is_dp)]),
        Section("Autres-matières", _others_tables(slots, students, links)),
    ]
    generated = datetime.datetime.now()
    backup = {
        "format": BACKUP_FORMAT,
        "generated": generated.isoformat(timespec="seconds"),
        "classroom": {"id": cid, "label": classroom['label'], "program": sigle},
        "term": {"number": term_no, "id": term_id},
        "year": year_label,
        "classroom_subjects": subjects,
        "students": students,
        "subject_enrolments": enrolments,
        "other_subject_slots": slots,
        "other_subject_links": links,
    }
    return Report(classroom['label'], sigle, term_no, year_label, generated, sections, backup)
