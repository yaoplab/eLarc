-- LarcRH Phase 2 — Catégories dynamiques + métadonnées documents
-- Ajoute les tables pour les catégories de fiche détail et les métadonnées documentaires
-- À exécuter sur Intranet (127.0.0.1:5432) ET Supabase Cloud (6543)
-- Usage : psql -U postgres -d NewLarcDB -f migration_20260808_hr_phase2.sql

BEGIN;

-- ============================================================================
-- 1. Catégories de fiche détail (sidebar dynamique)
-- ============================================================================

CREATE TABLE IF NOT EXISTS staff_detail_category (
    id              SERIAL PRIMARY KEY,
    category_key    VARCHAR(30) NOT NULL UNIQUE,
    label_fr        VARCHAR(72) NOT NULL,
    label_en        VARCHAR(72),
    icon_name       VARCHAR(30) DEFAULT 'folder',
    sort_order      INTEGER DEFAULT 0,
    enabled         BOOLEAN DEFAULT true
);

-- Seed : 6 catégories par défaut
INSERT INTO staff_detail_category (category_key, label_fr, label_en, icon_name, sort_order)
VALUES
    ('personal',  'Fiche personnelle',  'Personal File',    'person',     0),
    ('degrees',   'Diplômes & Langues', 'Degrees & Languages', 'school',  1),
    ('contracts', 'Contrats',           'Contracts',         'assignment', 2),
    ('leave',     'Congés',             'Leave',             'event',      3),
    ('documents', 'Documents',          'Documents',         'folder',     4),
    ('events',    'Événements',         'Events',            'history',    5)
ON CONFLICT (category_key) DO NOTHING;

-- ============================================================================
-- 2. Métadonnées documentaires
-- ============================================================================

CREATE TABLE IF NOT EXISTS staff_document (
    id              SERIAL PRIMARY KEY,
    staff_id        INTEGER NOT NULL REFERENCES larcauth_aecuser(id),
    category_key    VARCHAR(30) NOT NULL,
    file_name       VARCHAR(255) NOT NULL,
    label           VARCHAR(150),
    description     TEXT,
    uploaded_at     TIMESTAMP DEFAULT NOW(),
    UNIQUE(staff_id, category_key, file_name)
);

-- Index
CREATE INDEX IF NOT EXISTS idx_staff_doc_staff ON staff_document(staff_id, category_key);

COMMIT;
