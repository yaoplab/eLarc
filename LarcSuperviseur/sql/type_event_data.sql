-- larcauth_type_event — seed de référence (nouveau format arbre, 2026-08-30)
-- ============================================================================
-- Nœuds structurels (IDs 1-14) + 27 lignes legacy (IDs 100-406).
-- Prérequis : migration_20260830_event_type_tree.sql appliquée (colonnes
-- parent_id/code/label/sort_order + PK + trigger).
--
-- ATTENTION : le DELETE ci-dessous est BLOQUÉ (exception 23513) pour toute
-- ligne référencée par student_event.event_type_id — comportement VOULU
-- (verrou strict : un type utilisé est immuable). Le re-seed ne réinitialise
-- donc que les types non utilisés.
-- ============================================================================

-- Nœuds structurels (jamais supprimés par le re-seed, IDs < 100)
INSERT INTO larcauth_type_event
    (idtypeevent, type_event, "Event_Niveau2", "Event_Niveau3", "Enabled", fk_language,
     parent_id, code, label, sort_order)
VALUES
    (1, NULL, NULL, NULL, TRUE, 2, NULL, 'evenement',    'Événement',          1),
    (2, NULL, NULL, NULL, TRUE, 2, NULL, 'absence',      'Absence',            2),
    (3, NULL, NULL, NULL, TRUE, 2, NULL, 'retard',       'Retard',             3),
    (4, NULL, NULL, NULL, TRUE, 2, 1,    'bureau-bi',    'Bureau BI',          1),
    (5, NULL, NULL, NULL, TRUE, 2, 1,    'medical',      'Médical',            2),
    (6, NULL, NULL, NULL, TRUE, 2, 1,    'sortie',       'Sortie',             3),
    (7, NULL, NULL, NULL, TRUE, 2, 1,    'suivi',        'Suivi',              4),
    (8, NULL, NULL, NULL, TRUE, 2, 2,    'absent-ecole', 'Absent de l''école', 1),
    (9, NULL, NULL, NULL, TRUE, 2, 2,    'absent-cours', 'Absent du cours',    2),
    (10, NULL, NULL, NULL, TRUE, 2, 4,   'bureau-bi-violence',    'Violence',    1),
    (11, NULL, NULL, NULL, TRUE, 2, 4,   'bureau-bi-harcelement', 'Harcèlement', 2),
    (12, NULL, NULL, NULL, TRUE, 2, 5,   'medical-accident',      'Accident',    1),
    (13, NULL, NULL, NULL, TRUE, 2, 6,   'sortie-perturbation',   'Perturbation', 1),
    (14, NULL, NULL, NULL, TRUE, 2, 6,   'sortie-exclusion',      'Exclusion',   2),
    -- Nœuds EN (fk_language=1) — mêmes codes (unicité par langue)
    (21, NULL, NULL, NULL, TRUE, 1, NULL, 'evenement',    'Event',               1),
    (22, NULL, NULL, NULL, TRUE, 1, NULL, 'absence',      'Absence',             2),
    (23, NULL, NULL, NULL, TRUE, 1, NULL, 'retard',       'Tardiness',           3),
    (24, NULL, NULL, NULL, TRUE, 1, 21,   'bureau-bi',    'Bureau BI',           1),
    (25, NULL, NULL, NULL, TRUE, 1, 21,   'medical',      'Medical',             2),
    (26, NULL, NULL, NULL, TRUE, 1, 21,   'sortie',       'Exit',                3),
    (27, NULL, NULL, NULL, TRUE, 1, 21,   'suivi',        'Follow-up',           4),
    (28, NULL, NULL, NULL, TRUE, 1, 22,   'absent-ecole', 'Absent from school',  1),
    (29, NULL, NULL, NULL, TRUE, 1, 22,   'absent-cours', 'Absent from class',   2),
    (30, NULL, NULL, NULL, TRUE, 1, 24,   'bureau-bi-violence',    'Violence',    1),
    (31, NULL, NULL, NULL, TRUE, 1, 24,   'bureau-bi-harcelement', 'Bullying',    2),
    (32, NULL, NULL, NULL, TRUE, 1, 25,   'medical-accident',      'Accident',    1),
    (33, NULL, NULL, NULL, TRUE, 1, 26,   'sortie-perturbation',   'Disruption',  1),
    (34, NULL, NULL, NULL, TRUE, 1, 26,   'sortie-exclusion',      'Exclusion',   2)
ON CONFLICT (idtypeevent) DO NOTHING;

-- Lignes legacy (IDs 100-406) — parent_id/label/code dans la NOUVELLE taxonomie.
-- Les colonnes type_event/"Event_Niveau2"/"Event_Niveau3" restent (snapshot legacy).
DELETE FROM larcauth_type_event WHERE idtypeevent >= 100;

INSERT INTO larcauth_type_event
    (idtypeevent, type_event, "Event_Niveau2", "Event_Niveau3", "Enabled", fk_language,
     parent_id, code, label, sort_order)
VALUES
-- Bureau BI (100-107)
(100, 'Bureau BI', 'Violence',     'Auteur',      TRUE, 2, 10, 'bureau-bi-violence-auteur',    'Auteur',     1),
(101, 'Bureau BI', 'Violence',     'Victime',     TRUE, 2, 10, 'bureau-bi-violence-victime',   'Victime',    2),
(102, 'Bureau BI', 'Violence',     'Témoin',      TRUE, 2, 10, 'bureau-bi-violence-temoin',    'Témoin',     3),
(103, 'Bureau BI', 'Harcèlement',  'Auteur',      TRUE, 2, 11, 'bureau-bi-harcelement-auteur', 'Auteur',     1),
(104, 'Bureau BI', 'Harcèlement',  'Victime',     TRUE, 2, 11, 'bureau-bi-harcelement-victime','Victime',    2),
(105, 'Bureau BI', 'Harcèlement',  'Témoin',      TRUE, 2, 11, 'bureau-bi-harcelement-temoin', 'Témoin',     3),
(106, 'Bureau BI', 'Fugue',        NULL,          TRUE, 2, 4,  'bureau-bi-fugue',              'Fugue',      4),
(107, 'Bureau BI', 'Entretien',    NULL,          TRUE, 2, 4,  'bureau-bi-entretien',          'Entretien',  5),
-- Médical (200-204)
(200, 'Médical', 'Maladie',       NULL,          TRUE, 2, 5,  'medical-maladie',              'Maladie',    1),
(201, 'Médical', 'Accident',      'Scolaire',    TRUE, 2, 12, 'medical-accident-scolaire',    'Scolaire',   1),
(202, 'Médical', 'Accident',      'Sportif',     TRUE, 2, 12, 'medical-accident-sportif',     'Sportif',    2),
(203, 'Médical', 'Infirmerie',    NULL,          TRUE, 2, 5,  'medical-infirmerie',           'Infirmerie', 2),
(204, 'Médical', 'Hospitalisation', NULL,        TRUE, 2, 5,  'medical-hospitalisation',      'Hospitalisation', 3),
-- Sortie (300-306)
(300, 'Sortie', 'Perturbation',   'Bavardage',   TRUE, 2, 13, 'sortie-perturbation-bavardage','Bavardage', 1),
(301, 'Sortie', 'Perturbation',   'Agitation',   TRUE, 2, 13, 'sortie-perturbation-agitation','Agitation', 2),
(302, 'Sortie', 'Perturbation',   'Insolence',   TRUE, 2, 13, 'sortie-perturbation-insolence','Insolence', 3),
(303, 'Sortie', 'Exclusion',      'Interne',     TRUE, 2, 14, 'sortie-exclusion-interne',     'Interne',    1),
(304, 'Sortie', 'Exclusion',      'Externe',     TRUE, 2, 14, 'sortie-exclusion-externe',     'Externe',    2),
(305, 'Sortie', 'Renvoi',         NULL,          TRUE, 2, 6,  'sortie-renvoi',                'Renvoi',     3),
(306, 'Sortie', 'Demande',        NULL,          TRUE, 2, 6,  'sortie-demande',               'Demande',    4),
-- Suivi (400-406) — les 400-403 migrent dans la branche ABSENCE
(400, 'Suivi', 'Absence',         'Maladie',     TRUE, 2, 8,  'absence-ecole-maladie',        'Maladie',    1),
(401, 'Suivi', 'Absence',         'Accident',    TRUE, 2, 8,  'absence-ecole-accident',       'Accident',   2),
(402, 'Suivi', 'Absence',         'Vacances',    TRUE, 2, 8,  'absence-ecole-vacances',       'Vacances',   3),
(403, 'Suivi', 'Absence',         'Non justifiée', TRUE, 2, 8, 'absence-ecole-non-justifiee', 'Non justifiée', 4),
(404, 'Suivi', 'Retard',          NULL,          TRUE, 2, 3,  'retard-2',                     'Retard',     1),
(405, 'Suivi', 'Comportement',    NULL,          TRUE, 2, 7,  'suivi-comportement',           'Comportement', 1),
(406, 'Suivi', 'Suivi pédagogique', NULL,        TRUE, 2, 7,  'suivi-suivi-pedagogique',      'Suivi pédagogique', 2);
