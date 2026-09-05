-- Academicyear 2026-2027 + FK agenda sur larcauth_unit
-- Usage: psql -U postgres -d NewLarcDB -f migration_20260809_academicyear_unit.sql

BEGIN;

-- ============================================================================
-- 1. Ajouter l'année scolaire 2026-2027
-- ============================================================================

INSERT INTO larcauth_academicyear (s_id, label, start_date, end_date,
    current_term_number, "Current_unit_number", auto_calc, debug_mode, synchro_allowed, created, updated)
VALUES (2, '2026-2027', '2026-09-01', '2027-06-18', 1, 1, TRUE, FALSE, TRUE, NOW(), NOW())
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 2. Ajouter FK agenda_start_id + agenda_end_id sur larcauth_unit
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_unit' AND column_name='agenda_start_id') THEN
        ALTER TABLE larcauth_unit ADD COLUMN agenda_start_id INTEGER
            REFERENCES larcauth_agenda(id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='larcauth_unit' AND column_name='agenda_end_id') THEN
        ALTER TABLE larcauth_unit ADD COLUMN agenda_end_id INTEGER
            REFERENCES larcauth_agenda(id);
    END IF;
END $$;

COMMIT;
