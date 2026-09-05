-- compta_parent_balance : balance comptable par parent
CREATE TABLE IF NOT EXISTS compta_parent_balance (
    id              SERIAL PRIMARY KEY,
    parent_id       INTEGER NOT NULL,
    academic_year   VARCHAR(9) NOT NULL,
    total_due       INTEGER DEFAULT 0,
    total_paid      INTEGER DEFAULT 0,
    remaining       INTEGER DEFAULT 0,
    inscription_paid INTEGER DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'en_retard',
    status_override BOOLEAN DEFAULT FALSE,
    status_set_by   INTEGER,
    change_history  JSONB DEFAULT '[]'::jsonb,
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (parent_id, academic_year)
);

-- Colonnes pour les preuves de paiement
ALTER TABLE compta_payment ADD COLUMN IF NOT EXISTS file_url TEXT;
ALTER TABLE compta_payment ADD COLUMN IF NOT EXISTS cloud_url TEXT;
