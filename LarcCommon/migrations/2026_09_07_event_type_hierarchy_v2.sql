-- Migration: 2026-09-07_event_type_hierarchy_v2
-- Hiérarchie 4 niveaux : distingue Absence / Sortie, ajoute motifs détaillés,
-- supprime la redondance "Incident", relie student_event/staff_event au nœud exact choisi.
-- Additive uniquement : aucun DELETE, aucune suppression de code existant (principe gabarit).

-- ----------------------------------------------------------------------------
-- 0. Élargir la contrainte de catégorie pour accueillir 'sortie'
-- ----------------------------------------------------------------------------
ALTER TABLE larcauth_event_type_config DROP CONSTRAINT IF EXISTS check_category;
ALTER TABLE larcauth_event_type_config ADD CONSTRAINT check_category
    CHECK (category IN ('absence', 'retard', 'evenement', 'sortie', 'custom'));

-- ----------------------------------------------------------------------------
-- 1. Colonnes de liaison event_type_config_id (additives, nullable)
-- ----------------------------------------------------------------------------
ALTER TABLE IF EXISTS student_event
    ADD COLUMN IF NOT EXISTS event_type_config_id INTEGER
    REFERENCES larcauth_event_type_config(id);
CREATE INDEX IF NOT EXISTS idx_student_event_type_config
    ON student_event(event_type_config_id);

ALTER TABLE IF EXISTS staff_event
    ADD COLUMN IF NOT EXISTS event_type_config_id INTEGER
    REFERENCES larcauth_event_type_config(id);
CREATE INDEX IF NOT EXISTS idx_staff_event_type_config
    ON staff_event(event_type_config_id);

-- ----------------------------------------------------------------------------
-- 2. ABSENCE — nouveaux motifs sous absence_school (Maladie déjà existant)
-- ----------------------------------------------------------------------------
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'absence_school_sick_mild', 'Légère (rhume, fièvre)', 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school_sick'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_sick_mild');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'absence_school_sick_severe', 'Grave / Hospitalisation', 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school_sick'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_sick_severe');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'absence_school_sick_chronic', 'Chronique (suivi médical)', 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school_sick'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_sick_chronic');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'absence_school_sick_other', 'Autre', 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school_sick'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_sick_other');

-- Motif familial (nouveau, sous absence_school)
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'absence_school_family', 'Motif familial', 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_family');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school_family'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
FROM (VALUES
    ('absence_school_family_death', 'Décès'),
    ('absence_school_family_event', 'Événement familial'),
    ('absence_school_family_travel', 'Déplacement'),
    ('absence_school_family_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

-- Rendez-vous médical (nouveau, sous absence_school)
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'absence_school_appointment', 'Rendez-vous médical', 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_appointment');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school_appointment'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
FROM (VALUES
    ('absence_school_appointment_gp', 'Généraliste'),
    ('absence_school_appointment_specialist', 'Spécialiste'),
    ('absence_school_appointment_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

-- Motif administratif (nouveau, sous absence_school)
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'absence_school_admin', 'Motif administratif', 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_admin');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school_admin'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
FROM (VALUES
    ('absence_school_admin_process', 'Démarches'),
    ('absence_school_admin_summons', 'Convocation externe'),
    ('absence_school_admin_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

-- "Autre" direct sous absence_school (absence_school_justified/unjustified existent déjà)
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'absence_school_other', 'Autre', 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_other');

UPDATE larcauth_event_type_config SET label = 'Justifiée (sans détail)'
WHERE code = 'absence_school_justified';

-- absence_class : nouveaux motifs (Convoqué / Activité scolaire / Autre), désactivation des anciens
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'absence',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_class'),
       'student', TRUE, FALSE, TRUE, TRUE
FROM (VALUES
    ('absence_class_summoned', 'Convoqué (direction/administration)'),
    ('absence_class_school_activity', 'Activité scolaire (sport, sortie pédagogique, compétition)'),
    ('absence_class_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

UPDATE larcauth_event_type_config SET is_active = FALSE
WHERE code IN ('absence_class_sick', 'absence_class_justified', 'absence_class_unjustified');

-- ----------------------------------------------------------------------------
-- 3. SORTIE — nouvelle racine (élève présent puis retiré, distinct de Absence)
-- ----------------------------------------------------------------------------
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'sortie', 'Sortie', 'sortie', NULL, 'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'sortie');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'sortie_class', 'Sortie du cours', 'sortie',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'sortie'),
       'student,staff', TRUE, FALSE, TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'sortie_class');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'sortie',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'sortie_class'),
       'student,staff', TRUE, v.requires_lieu, TRUE, TRUE
FROM (VALUES
    ('sortie_class_toilets', 'Toilettes', FALSE),
    ('sortie_class_infirmary', 'Infirmerie', TRUE),
    ('sortie_class_office', 'Bureau direction/vie scolaire', TRUE),
    ('sortie_class_forgot_material', 'Matériel oublié', FALSE),
    ('sortie_class_other', 'Autre', FALSE)
) AS v(code, label, requires_lieu)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

-- Mauvais comportement : student uniquement (le staff n'est pas "sorti" pour ce motif)
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'sortie_class_misbehavior', 'Mauvais comportement', 'sortie',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'sortie_class'),
       'student', TRUE, FALSE, TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'sortie_class_misbehavior');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'sortie',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'sortie_class_misbehavior'),
       'student', TRUE, FALSE, TRUE, TRUE
FROM (VALUES
    ('sortie_class_misbehavior_minor', 'Indiscipline légère'),
    ('sortie_class_misbehavior_insolence', 'Insolence'),
    ('sortie_class_misbehavior_verbal', 'Violence verbale'),
    ('sortie_class_misbehavior_physical', 'Violence physique'),
    ('sortie_class_misbehavior_fraud', 'Fraude'),
    ('sortie_class_misbehavior_theft', 'Vol'),
    ('sortie_class_misbehavior_damage', 'Dégradation matériel'),
    ('sortie_class_misbehavior_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'sortie_school', 'Sortie de l''école', 'sortie',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'sortie'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'sortie_school');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'sortie',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'sortie_school'),
       'student,staff', TRUE, FALSE, FALSE, TRUE
FROM (VALUES
    ('sortie_school_parent', 'Récupéré par parent/tuteur'),
    ('sortie_school_appointment', 'Rendez-vous médical'),
    ('sortie_school_illness', 'Malaise/renvoyé'),
    ('sortie_school_exception', 'Autorisation exceptionnelle'),
    ('sortie_school_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

-- ----------------------------------------------------------------------------
-- 4. RETARD — restructuration à 4 niveaux (École / Cours × durée × motif)
-- ----------------------------------------------------------------------------
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'retard_school', 'Retard à l''école', 'retard',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'retard'),
       'student', TRUE, FALSE, FALSE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'retard_school');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'retard_class', 'Retard au cours', 'retard',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'retard'),
       'student', TRUE, FALSE, TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'retard_class');

-- Reparenter les durées existantes (retard_5min/15min/30min) sous retard_school
UPDATE larcauth_event_type_config SET
    parent_id = (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_school'),
    label = '5 min'
WHERE code = 'retard_5min';

UPDATE larcauth_event_type_config SET
    parent_id = (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_school'),
    label = '15 min'
WHERE code = 'retard_15min';

UPDATE larcauth_event_type_config SET
    parent_id = (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_school'),
    label = '30 min et +'
WHERE code = 'retard_30min';

-- Motifs sous chaque durée "école" (retard_5min/15min/30min) + nouvelles durées "cours"
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'retard', v.parent_id, 'student', TRUE, FALSE, v.requires_subject, TRUE
FROM (
    SELECT 'retard_5min_' || m.suffix AS code, m.label,
           (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_5min') AS parent_id,
           FALSE AS requires_subject
    FROM (VALUES ('transport','Transport'), ('family','Familial'),
                 ('oversleep','Oubli-réveil'), ('other','Autre')) AS m(suffix, label)
    UNION ALL
    SELECT 'retard_15min_' || m.suffix, m.label,
           (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_15min'), FALSE
    FROM (VALUES ('transport','Transport'), ('family','Familial'),
                 ('oversleep','Oubli-réveil'), ('other','Autre')) AS m(suffix, label)
    UNION ALL
    SELECT 'retard_30min_' || m.suffix, m.label,
           (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_30min'), FALSE
    FROM (VALUES ('transport','Transport'), ('family','Familial'),
                 ('oversleep','Oubli-réveil'), ('other','Autre')) AS m(suffix, label)
) AS v
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'retard',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_class'),
       'student', TRUE, FALSE, TRUE, TRUE
FROM (VALUES
    ('retard_class_5', '5 min'),
    ('retard_class_15plus', '15 min et +')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'retard', v.parent_id, 'student', TRUE, FALSE, TRUE, TRUE
FROM (
    SELECT 'retard_class_5_' || m.suffix AS code, m.label,
           (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_class_5') AS parent_id
    FROM (VALUES ('transport','Transport'), ('family','Familial'),
                 ('oversleep','Oubli-réveil'), ('other','Autre')) AS m(suffix, label)
    UNION ALL
    SELECT 'retard_class_15plus_' || m.suffix, m.label,
           (SELECT id FROM larcauth_event_type_config WHERE code = 'retard_class_15plus')
    FROM (VALUES ('transport','Transport'), ('family','Familial'),
                 ('oversleep','Oubli-réveil'), ('other','Autre')) AS m(suffix, label)
) AS v
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

-- ----------------------------------------------------------------------------
-- 5. ÉVÉNEMENT — Comportement (Positif/Négatif/Matériel oublié/Manque de travail), Santé
--    "Incident" supprimé (redondant avec Comportement > Négatif)
-- ----------------------------------------------------------------------------
UPDATE larcauth_event_type_config SET is_active = FALSE WHERE code = 'event_incident';

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'event_behavior_positive', 'Positif', 'evenement',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'event_behavior'),
       'student', TRUE, TRUE, TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'event_behavior_positive');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'evenement',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'event_behavior_positive'),
       'student', TRUE, TRUE, TRUE, TRUE
FROM (VALUES
    ('event_behavior_positive_merit', 'Mérite/Encouragement'),
    ('event_behavior_positive_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'event_behavior_negative', 'Négatif', 'evenement',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'event_behavior'),
       'student', TRUE, TRUE, TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'event_behavior_negative');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'evenement',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'event_behavior_negative'),
       'student', TRUE, TRUE, TRUE, TRUE
FROM (VALUES
    ('event_behavior_negative_minor', 'Indiscipline légère'),
    ('event_behavior_negative_insolence', 'Insolence'),
    ('event_behavior_negative_verbal', 'Violence verbale'),
    ('event_behavior_negative_physical', 'Violence physique'),
    ('event_behavior_negative_fraud', 'Fraude'),
    ('event_behavior_negative_theft', 'Vol'),
    ('event_behavior_negative_damage', 'Dégradation matériel'),
    ('event_behavior_negative_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'event_behavior_forgot_material', 'Matériel oublié (élève continue de travailler)', 'evenement',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'event_behavior'),
       'student', TRUE, TRUE, TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'event_behavior_forgot_material');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT 'event_behavior_lack_of_work', 'Manque de travail', 'evenement',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'event_behavior'),
       'student', TRUE, TRUE, TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'event_behavior_lack_of_work');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'evenement',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'event_behavior_lack_of_work'),
       'student', TRUE, TRUE, TRUE, TRUE
FROM (VALUES
    ('event_behavior_lack_of_work_homework', 'Devoirs non faits'),
    ('event_behavior_lack_of_work_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT v.code, v.label, 'evenement',
       (SELECT id FROM larcauth_event_type_config WHERE code = 'event_health'),
       'student', TRUE, TRUE, TRUE, TRUE
FROM (VALUES
    ('event_health_illness', 'Malaise'),
    ('event_health_injury', 'Blessure'),
    ('event_health_emergency', 'Urgence médicale'),
    ('event_health_pai', 'Suivi PAI'),
    ('event_health_other', 'Autre')
) AS v(code, label)
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = v.code);
