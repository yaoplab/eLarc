-- LarcCompta v2 : gestion des frais de scolarite (parent-based)
-- A executer sur Intranet (127.0.0.1:5432) ET Supabase Cloud (6543)

-- 1. Echeancier global (% cumule attendu par mois)
DROP TABLE IF EXISTS compta_payment_schedule CASCADE;
CREATE TABLE compta_payment_schedule (
    id                  SERIAL PRIMARY KEY,
    academic_year       VARCHAR(9) NOT NULL,
    month_number        INTEGER NOT NULL CHECK (month_number BETWEEN 1 AND 12),
    percentage_expected DECIMAL(5,2) NOT NULL,
    UNIQUE (academic_year, month_number)
);

-- 2. Bareme des frais par niveau
DROP TABLE IF EXISTS compta_fee_structure CASCADE;
DROP TABLE IF EXISTS compta_fee_level CASCADE;
CREATE TABLE compta_fee_level (
    id              SERIAL PRIMARY KEY,
    level_id        INTEGER NOT NULL,
    academic_year   VARCHAR(9) NOT NULL,
    annual_fee      INTEGER NOT NULL,
    monthly_amount  INTEGER,
    UNIQUE (level_id, academic_year)
);

-- 3. Frais par eleve (copie du bareme, modifiable individuellement)
CREATE TABLE IF NOT EXISTS compta_student_fee (
    id              SERIAL PRIMARY KEY,
    student_id      INTEGER NOT NULL,
    academic_year   VARCHAR(9) NOT NULL,
    level_id        INTEGER NOT NULL,
    annual_fee      INTEGER NOT NULL,
    payment_mode    VARCHAR(20),
    created_at      TIMESTAMP,
    UNIQUE (student_id, academic_year)
);

-- 4. Paiements lies au PARENT (pas a l'eleve)
DROP TABLE IF EXISTS compta_payment CASCADE;
CREATE TABLE compta_payment (
    id              SERIAL PRIMARY KEY,
    parent_id       INTEGER NOT NULL,
    amount          INTEGER NOT NULL,
    payment_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    payment_method  VARCHAR(30) DEFAULT 'especes',
    reference       VARCHAR(100),
    received_by     INTEGER,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 5. Documents joints au dossier parent
CREATE TABLE IF NOT EXISTS compta_payment_document (
    id              SERIAL PRIMARY KEY,
    payment_id      INTEGER,
    parent_id       INTEGER NOT NULL,
    file_path       TEXT,
    title           VARCHAR(200),
    amount          INTEGER,
    document_date   DATE DEFAULT CURRENT_DATE,
    created_by      INTEGER,
    created_at      TIMESTAMP DEFAULT NOW(),
    notes           TEXT
);

-- 6. Echeancier personnalise parent (remplace le global si present)
CREATE TABLE IF NOT EXISTS compta_parent_milestone (
    id              SERIAL PRIMARY KEY,
    parent_id       INTEGER NOT NULL,
    due_date        DATE NOT NULL,
    amount_expected INTEGER NOT NULL,
    agreed_by       INTEGER,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 7. Rappels envoyes aux parents
DROP TABLE IF EXISTS compta_reminder CASCADE;
CREATE TABLE compta_reminder (
    id              SERIAL PRIMARY KEY,
    parent_id       INTEGER NOT NULL,
    reminder_type   VARCHAR(20) DEFAULT 'email',
    sent_at         TIMESTAMP DEFAULT NOW(),
    status          VARCHAR(20) DEFAULT 'envoye',
    message         TEXT,
    created_by      INTEGER
);

-- 8. Colonne payeur sur larcauth_parent
ALTER TABLE larcauth_parent ADD COLUMN IF NOT EXISTS is_payer BOOLEAN DEFAULT FALSE;

-- 9. Echeancier global par defaut
INSERT INTO compta_payment_schedule (academic_year, month_number, percentage_expected) VALUES
    ('2026-2027', 1, 10.0), ('2026-2027', 2, 20.0), ('2026-2027', 3, 30.0),
    ('2026-2027', 4, 40.0), ('2026-2027', 5, 50.0), ('2026-2027', 6, 60.0),
    ('2026-2027', 7, 70.0), ('2026-2027', 8, 80.0), ('2026-2027', 9, 90.0),
    ('2026-2027', 10, 100.0)
ON CONFLICT DO NOTHING;

-- 10. Baremes par defaut (par programme -> tous les niveaux)
INSERT INTO compta_fee_level (level_id, academic_year, annual_fee, monthly_amount)
SELECT l.id, '2026-2027',
    CASE WHEN l.fk_program_id IN (13,23) THEN 3000000 ELSE 2500000 END,
    CASE WHEN l.fk_program_id IN (13,23) THEN 300000 ELSE 250000 END
FROM larcauth_level l
WHERE l.fk_program_id IN (11,12,13,21,22,23)
ON CONFLICT DO NOTHING;
