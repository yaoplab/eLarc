-- LarcRH — Ajoute agenda_day_id + FKs sur staff_event (aligné sur student_event)
-- Usage : psql -U postgres -d NewLarcDB -f migration_20260809_staff_event_fk.sql

BEGIN;

-- 1. Colonne agenda_day_id
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='staff_event' AND column_name='agenda_day_id') THEN
        ALTER TABLE staff_event ADD COLUMN agenda_day_id INTEGER;
    END IF;
END $$;

-- 2. Index
CREATE INDEX IF NOT EXISTS idx_staff_event_agenda ON staff_event(agenda_day_id);

-- 3. FK vers larcauth_agenda
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                   WHERE table_name='staff_event' AND constraint_name='staff_event_agenda_fk') THEN
        ALTER TABLE staff_event
            ADD CONSTRAINT staff_event_agenda_fk FOREIGN KEY (agenda_day_id)
            REFERENCES larcauth_agenda(id);
    END IF;
END $$;

-- 4. FK event_type vers larcauth_type_event
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='staff_event' AND column_name='fk_typeevent_id') THEN
        ALTER TABLE staff_event ADD COLUMN fk_typeevent_id SMALLINT;
        ALTER TABLE staff_event
            ADD CONSTRAINT staff_event_type_fk FOREIGN KEY (fk_typeevent_id)
            REFERENCES larcauth_type_event(idtypeevent);
    END IF;
END $$;

-- 5. Trigger resolve_agenda_day (même que student_event)
DROP TRIGGER IF EXISTS trg_staff_resolve_agenda ON staff_event;
CREATE TRIGGER trg_staff_resolve_agenda
    BEFORE INSERT ON staff_event
    FOR EACH ROW
    EXECUTE FUNCTION resolve_agenda_day();

-- 6. Backfill agenda_day_id pour les lignes existantes
UPDATE staff_event
SET agenda_day_id = (SELECT id FROM larcauth_agenda WHERE date_all = event_at::date LIMIT 1)
WHERE agenda_day_id IS NULL AND event_at IS NOT NULL;

COMMIT;
