-- ============================================================
-- MIGRATION 2026-07-04 : Rattrapage DB Intranet
-- Appliquer sur NewLarcDB (Intranet PostgreSQL 127.0.0.1:5432)
-- ============================================================

BEGIN;

-- 1. Ajouter fk_language sur aecuser (LarcSuperviseur en a besoin)
ALTER TABLE larcauth_aecuser
  ADD COLUMN IF NOT EXISTS fk_language INTEGER REFERENCES larcauth_language(id);

COMMENT ON COLUMN larcauth_aecuser.fk_language IS
  'Langue préférée de l''utilisateur (1=En, 2=Fr)';

-- Initialiser tous les utilisateurs existants en Français (2) par défaut
UPDATE larcauth_aecuser SET fk_language = 2 WHERE fk_language IS NULL;

-- 2. Supprimer l'ancien CHECK restrictif sur student_event.event_type
--    (bloque les nouveaux types hiérarchiques comme 'Suivi > Absence')
DO $$
DECLARE cons_name text;
BEGIN
    SELECT con.conname INTO cons_name
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    WHERE rel.relname = 'student_event' AND con.contype = 'c'
      AND pg_get_constraintdef(con.oid) ILIKE '%event_type%';
    IF cons_name IS NOT NULL THEN
        EXECUTE 'ALTER TABLE student_event DROP CONSTRAINT ' || cons_name;
    END IF;
END $$;

-- 3. audit_trail (traçabilité LarcSecretaire)
CREATE TABLE IF NOT EXISTS audit_trail (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    secretary_id INTEGER,
    secretary_name TEXT,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id INTEGER,
    detail TEXT,
    source TEXT DEFAULT 'intranet',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_trail_action ON audit_trail (action);
CREATE INDEX IF NOT EXISTS idx_audit_trail_secretary ON audit_trail (secretary_id);
CREATE INDEX IF NOT EXISTS idx_audit_trail_created ON audit_trail (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_trail_target ON audit_trail (target_type, target_id);

COMMIT;
