-- LarcRH Phase 1 — Migration socle RH minimal
-- Ajoute les colonnes et tables pour la gestion RH enrichie
-- À exécuter sur Intranet (127.0.0.1:5432) ET Supabase Cloud (6543)
-- Usage : psql -U postgres -d NewLarcDB -f migration_20260808_hr_phase1.sql

BEGIN;

-- ============================================================================
-- 1. Nouvelles colonnes sur larcauth_aecuser
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='civility') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN civility VARCHAR(8);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='nationality') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN nationality VARCHAR(72);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='marital_status') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN marital_status VARCHAR(20);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='children_count') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN children_count INTEGER DEFAULT 0;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='emergency_contact_name') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN emergency_contact_name VARCHAR(150);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='emergency_contact_phone') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN emergency_contact_phone VARCHAR(20);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='blood_type') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN blood_type VARCHAR(4);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='cnss_number') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN cnss_number VARCHAR(30);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='tax_id') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN tax_id VARCHAR(30);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='id_document_type') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN id_document_type VARCHAR(30);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='id_document_number') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN id_document_number VARCHAR(50);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='id_document_expiry') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN id_document_expiry DATE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='matricule') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN matricule VARCHAR(30);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='professional_category') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN professional_category VARCHAR(30);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='emp_status') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN emp_status VARCHAR(20) DEFAULT 'actif';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='departure_date') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN departure_date DATE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='departure_reason') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN departure_reason TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='fk_campus_id') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN fk_campus_id INTEGER REFERENCES larcauth_campus(id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_aecuser' AND column_name='fk_supervisor_id') THEN
        ALTER TABLE larcauth_aecuser ADD COLUMN fk_supervisor_id INTEGER REFERENCES larcauth_aecuser(id);
    END IF;
END $$;

-- ============================================================================
-- 2. Table des contrats
-- ============================================================================

CREATE TABLE IF NOT EXISTS staff_contract (
    id              SERIAL PRIMARY KEY,
    staff_id        INTEGER NOT NULL REFERENCES larcauth_aecuser(id),
    contract_type   VARCHAR(30) NOT NULL DEFAULT 'cdi',
    date_debut      DATE NOT NULL,
    date_fin        DATE,
    periode_essai   INTEGER,
    periode_essai_fin DATE,
    salaire_brut    NUMERIC(12,2),
    volume_horaire  NUMERIC(5,1),
    classification  VARCHAR(30),
    echelon         INTEGER,
    statut          VARCHAR(20) NOT NULL DEFAULT 'actif',
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    created_by      INTEGER,
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- 3. Soldes de congés
-- ============================================================================

CREATE TABLE IF NOT EXISTS staff_leave_balance (
    id              SERIAL PRIMARY KEY,
    staff_id        INTEGER NOT NULL REFERENCES larcauth_aecuser(id),
    year            INTEGER NOT NULL,
    leave_type      VARCHAR(10) NOT NULL,
    total_days      NUMERIC(5,1) DEFAULT 0,
    used_days       NUMERIC(5,1) DEFAULT 0,
    notes           TEXT,
    UNIQUE(staff_id, year, leave_type)
);

-- ============================================================================
-- 4. Demandes de congés
-- ============================================================================

CREATE TABLE IF NOT EXISTS staff_leave_request (
    id              SERIAL PRIMARY KEY,
    staff_id        INTEGER NOT NULL REFERENCES larcauth_aecuser(id),
    leave_type      VARCHAR(10) NOT NULL,
    date_debut      DATE NOT NULL,
    date_fin        DATE NOT NULL,
    nb_days         NUMERIC(4,1) NOT NULL,
    motif           TEXT,
    attachment_path TEXT,
    status          VARCHAR(15) DEFAULT 'en_attente',
    requested_at    TIMESTAMP DEFAULT NOW(),
    validated_by    INTEGER REFERENCES larcauth_aecuser(id),
    validated_at    TIMESTAMP,
    validation_note TEXT
);

-- ============================================================================
-- 5. Diplômes employé
-- ============================================================================

CREATE TABLE IF NOT EXISTS staff_degree (
    id              SERIAL PRIMARY KEY,
    staff_id        INTEGER NOT NULL REFERENCES larcauth_aecuser(id),
    degree_type     VARCHAR(72) NOT NULL,
    institution     VARCHAR(150),
    year_obtained   INTEGER,
    country         VARCHAR(72),
    field_of_study  VARCHAR(150)
);

-- ============================================================================
-- 6. Langues parlées
-- ============================================================================

CREATE TABLE IF NOT EXISTS staff_language (
    id              SERIAL PRIMARY KEY,
    staff_id        INTEGER NOT NULL REFERENCES larcauth_aecuser(id),
    language        VARCHAR(50) NOT NULL,
    proficiency     VARCHAR(20) DEFAULT 'B1',
    UNIQUE(staff_id, language)
);

-- ============================================================================
-- 7. Index
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_staff_contract_staff ON staff_contract(staff_id);
CREATE INDEX IF NOT EXISTS idx_staff_contract_status ON staff_contract(statut);
CREATE INDEX IF NOT EXISTS idx_staff_contract_fin
    ON staff_contract(date_fin) WHERE statut = 'actif' AND date_fin IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_staff_leave_bal ON staff_leave_balance(staff_id, year);
CREATE INDEX IF NOT EXISTS idx_staff_leave_req ON staff_leave_request(staff_id);
CREATE INDEX IF NOT EXISTS idx_staff_leave_req_status ON staff_leave_request(status);
CREATE INDEX IF NOT EXISTS idx_staff_degree_staff ON staff_degree(staff_id);
CREATE INDEX IF NOT EXISTS idx_staff_lang_staff ON staff_language(staff_id);
CREATE INDEX IF NOT EXISTS idx_aec_campus ON larcauth_aecuser(fk_campus_id);
CREATE INDEX IF NOT EXISTS idx_aec_supervisor ON larcauth_aecuser(fk_supervisor_id);
CREATE INDEX IF NOT EXISTS idx_aec_emp_status ON larcauth_aecuser(emp_status);

COMMIT;
