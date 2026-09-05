-- Key SQL queries used in eLarcProfPy
-- Reference file for quick resumption

-- Load evaluations for a CTS (evaluation_panel.py:713)
SELECT id, index_eval,
       crit_a, crit_b, crit_c, crit_d,
       label, nature, source
FROM larcauth_evaluation
WHERE fk_classroom_termsubject_id = ?
  AND type_evaluation = ?
  AND CAST(index_eval AS INTEGER) BETWEEN 1 AND 12
ORDER BY CAST(index_eval AS INTEGER)

-- Load criteria legend (evaluation_panel.py:201-214)
SELECT fk_levelsubject_id FROM larcauth_classroom_termsubject WHERE id = ?
-- then:
SELECT criteria_letter, criteria_label
FROM larcauth_criteria_of_levelsubject
WHERE fk_levelsubject_id = ?
  AND criteria_letter IN ('A','B','C','D')
ORDER BY criteria_letter

-- Save evaluation criteria (evaluation_panel.py:668-682)
UPDATE larcauth_evaluation
SET label=?, nature=?, source=?,
    crit_a=?, crit_b=?, crit_c=?, crit_d=?
WHERE id=?

-- Load CTS list (main_window.py)
-- (build from module_config + larcauth_classroom_termsubject + related tables)
SELECT cts.id AS termsubject_id,
       s.label AS matiere_label,
       cl.label AS class_label,
       cts.fk_level_id AS level_id
FROM larcauth_classroom_termsubject cts
JOIN larcauth_subject s ON s.id = cts.fk_subject_id
JOIN larcauth_classroom cl ON cl.id = cts.fk_classroom_id
WHERE ... filter by teacher_id and term_id

-- Save session (sqlite_init.py)
INSERT OR REPLACE INTO session_cache (...)

-- Module config (sqlite_init.py)
INSERT OR REPLACE INTO module_config (...)

-- Key DDL for larcauth_evaluation (sqlite_init.py:43-76)
CREATE TABLE IF NOT EXISTS larcauth_evaluation (
    id INTEGER PRIMARY KEY,
    label TEXT, nature TEXT, baremeNoteDP TEXT,
    type_evaluation TEXT, index_eval TEXT,
    crit_a TEXT, crit_b TEXT, crit_c TEXT, crit_d TEXT,
    crit_e TEXT, crit_f TEXT,
    aspect_a1..a7, aspect_b1..b7, aspect_c1..c7, aspect_d1..d7,
    aspect_e1..e7, aspect_f1..f7,
    created TEXT, updated TEXT,
    fk_classroom_termsubject_id TEXT,
    baremeNoteCritere TEXT,
    sync_version TEXT, synced_at TEXT, synced_by TEXT,
    last_modified_at TEXT, sync_revision TEXT,
    source TEXT
);

-- Naming conventions for note columns in learner tables:
-- formatives:  f01_note_a..f12_note_d, f13_note_a..f15_note_f (reserved)
-- sommatives:  s01_note_a..s12_note_d, s13_note_a..s15_note_f (reserved)
-- synthèse:    note_on_7 (PEI) or moy_on_20 (DP)
-- observation: fXX_observation, sXX_observation
-- jugement:    jgt_a..jgt_d
-- Bug server:  S09_note_f (uppercase S) vs s09_note_f
