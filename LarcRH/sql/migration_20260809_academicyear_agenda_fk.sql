-- Ajoute agenda_start_id + agenda_end_id sur larcauth_academicyear
BEGIN;
ALTER TABLE larcauth_academicyear ADD COLUMN IF NOT EXISTS agenda_start_id INTEGER REFERENCES larcauth_agenda(id);
ALTER TABLE larcauth_academicyear ADD COLUMN IF NOT EXISTS agenda_end_id INTEGER REFERENCES larcauth_agenda(id);
UPDATE larcauth_academicyear
SET agenda_start_id = to_char(start_date, 'YYYYMMDD')::INTEGER,
    agenda_end_id   = to_char(end_date, 'YYYYMMDD')::INTEGER
WHERE agenda_start_id IS NULL;
COMMIT;
