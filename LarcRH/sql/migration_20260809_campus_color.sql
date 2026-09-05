BEGIN;
ALTER TABLE larcauth_campus ADD COLUMN IF NOT EXISTS color VARCHAR(20) DEFAULT '#64748B';
UPDATE larcauth_campus SET color = '#FF8F00' WHERE s_id = 1;  -- Maternelle / Kindergarten → Orange
UPDATE larcauth_campus SET color = '#2E7D32' WHERE s_id = 2;  -- Primaire / Primary → Vert
UPDATE larcauth_campus SET color = '#1565C0' WHERE s_id = 3;  -- College-Lycee / High School → Bleu
COMMIT;
