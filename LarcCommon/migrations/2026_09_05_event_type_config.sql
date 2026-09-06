-- Migration: 2026-09-05_event_type_config
-- Refactor: Types d'événements configurables en DB + marqueur d'origine sync

-- Table de configuration hiérarchique des types d'événements
CREATE TABLE IF NOT EXISTS larcauth_event_type_config (
    id SERIAL PRIMARY KEY,
    code VARCHAR(64) UNIQUE NOT NULL,
    label VARCHAR(128) NOT NULL,
    category VARCHAR(32) NOT NULL,
    icon_code VARCHAR(32),
    parent_id INT REFERENCES larcauth_event_type_config(id),

    -- Conditions de visibilité/applicabilité
    applicable_to VARCHAR(64) NOT NULL DEFAULT 'student,staff',
    requires_validation BOOLEAN DEFAULT TRUE,
    requires_lieu BOOLEAN DEFAULT FALSE,
    requires_subject BOOLEAN DEFAULT FALSE,

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_category CHECK (category IN ('absence', 'retard', 'evenement', 'custom'))
);

CREATE INDEX IF NOT EXISTS idx_event_type_config_parent ON larcauth_event_type_config(parent_id);
CREATE INDEX IF NOT EXISTS idx_event_type_config_category ON larcauth_event_type_config(category);
CREATE INDEX IF NOT EXISTS idx_event_type_config_code ON larcauth_event_type_config(code);
CREATE INDEX IF NOT EXISTS idx_event_type_config_active ON larcauth_event_type_config(is_active);

-- Seed initial depuis larcauth_type_event (hiérarchie existante)
-- Suppression d'abord (au cas où migration rejouée)
DELETE FROM larcauth_event_type_config WHERE id > 0;

-- Insérer les racines (absence, retard, evenement)
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
VALUES
('absence', 'Absence', 'absence', NULL, 'student,staff', TRUE, FALSE, FALSE, TRUE),
('retard', 'Retard', 'retard', NULL, 'student,staff', TRUE, FALSE, FALSE, TRUE),
('evenement', 'Événement', 'evenement', NULL, 'student', TRUE, TRUE, TRUE, TRUE);

-- Insérer la hiérarchie Absence
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT
    'absence_school',
    'Absent de l''école',
    'absence',
    (SELECT id FROM larcauth_event_type_config WHERE code = 'absence'),
    'student,staff',
    TRUE,
    FALSE,
    FALSE,
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT
    'absence_class',
    'Absent du cours',
    'absence',
    (SELECT id FROM larcauth_event_type_config WHERE code = 'absence'),
    'student',
    TRUE,
    FALSE,
    TRUE,
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_class');

-- Motifs d'absence (enfants de absence_school)
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT
    'absence_school_sick',
    'Maladie',
    'absence',
    (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school'),
    'student,staff',
    TRUE,
    FALSE,
    FALSE,
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_sick');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT
    'absence_school_justified',
    'Justifiée',
    'absence',
    (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school'),
    'student,staff',
    TRUE,
    FALSE,
    FALSE,
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_justified');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT
    'absence_school_unjustified',
    'Injustifiée',
    'absence',
    (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_school'),
    'student,staff',
    TRUE,
    FALSE,
    FALSE,
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_school_unjustified');

-- Motifs d'absence du cours (enfants de absence_class)
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT
    'absence_class_sick',
    'Maladie',
    'absence',
    (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_class'),
    'student',
    TRUE,
    FALSE,
    TRUE,
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_class_sick');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT
    'absence_class_justified',
    'Justifiée',
    'absence',
    (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_class'),
    'student',
    TRUE,
    FALSE,
    TRUE,
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_class_justified');

INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
SELECT
    'absence_class_unjustified',
    'Injustifiée',
    'absence',
    (SELECT id FROM larcauth_event_type_config WHERE code = 'absence_class'),
    'student',
    TRUE,
    FALSE,
    TRUE,
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM larcauth_event_type_config WHERE code = 'absence_class_unjustified');

-- Hiérarchie Retard
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
VALUES
('retard_5min', 'Retard 5 min', 'retard', (SELECT id FROM larcauth_event_type_config WHERE code = 'retard'), 'student', TRUE, FALSE, FALSE, TRUE),
('retard_15min', 'Retard 15 min', 'retard', (SELECT id FROM larcauth_event_type_config WHERE code = 'retard'), 'student', TRUE, FALSE, FALSE, TRUE),
('retard_30min', 'Retard 30 min', 'retard', (SELECT id FROM larcauth_event_type_config WHERE code = 'retard'), 'student', TRUE, FALSE, FALSE, TRUE)
ON CONFLICT (code) DO NOTHING;

-- Hiérarchie Événement (racine simple avec enfants)
INSERT INTO larcauth_event_type_config
(code, label, category, parent_id, applicable_to, requires_validation, requires_lieu, requires_subject, is_active)
VALUES
('event_behavior', 'Comportement', 'evenement', (SELECT id FROM larcauth_event_type_config WHERE code = 'evenement'), 'student', TRUE, TRUE, TRUE, TRUE),
('event_health', 'Santé', 'evenement', (SELECT id FROM larcauth_event_type_config WHERE code = 'evenement'), 'student', TRUE, TRUE, TRUE, TRUE),
('event_incident', 'Incident', 'evenement', (SELECT id FROM larcauth_event_type_config WHERE code = 'evenement'), 'student', TRUE, TRUE, FALSE, TRUE)
ON CONFLICT (code) DO NOTHING;

-- Ajouter colonne created_location à student_event
ALTER TABLE IF EXISTS student_event
ADD COLUMN IF NOT EXISTS created_location VARCHAR(16) DEFAULT 'intranet'
CHECK (created_location IN ('intranet', 'cloud'));

-- Ajouter colonne created_location à staff_event
ALTER TABLE IF EXISTS staff_event
ADD COLUMN IF NOT EXISTS created_location VARCHAR(16) DEFAULT 'intranet'
CHECK (created_location IN ('intranet', 'cloud'));

-- Index pour sync (recherche par created_location)
CREATE INDEX IF NOT EXISTS idx_student_event_created_location ON student_event(created_location);
CREATE INDEX IF NOT EXISTS idx_staff_event_created_location ON staff_event(created_location);
