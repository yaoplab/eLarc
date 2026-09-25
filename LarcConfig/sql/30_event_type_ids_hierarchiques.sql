-- Renumérotation hiérarchique des IDs de larcauth_event_type_config.
-- ID = [langue][niv1][niv2][niv3][niv4 sur 2 chiffres]  (langue : 2 = FR, 1 = EN)
--   Absence FR = 210000 ; Absent de l'école = 211000 ; Maladie = 211100 ; Légère = 211101
-- Le contenu (code, label, parent, is_active…) ne change pas : seuls les IDs changent.
-- L'anglais reprend l'ordre du français, apparié par `code` (UNIQUE (code, fk_language)).
-- Références suivies : parent_id, student_event, staff_event (pas de cascade : UPDATE explicite).
-- À exécuter sur l'Intranet PUIS sur Supabase.

BEGIN;

-- 1. FKs différables : les contrôles sont faits au COMMIT
ALTER TABLE larcauth_event_type_config ALTER CONSTRAINT larcauth_event_type_config_parent_id_fkey DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE student_event ALTER CONSTRAINT student_event_event_type_config_id_fkey DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE staff_event   ALTER CONSTRAINT staff_event_event_type_config_id_fkey   DEFERRABLE INITIALLY IMMEDIATE;
SET CONSTRAINTS larcauth_event_type_config_parent_id_fkey, student_event_event_type_config_id_fkey,
                staff_event_event_type_config_id_fkey DEFERRED;

-- 2. Table de correspondance ancien -> nouvel ID
CREATE TEMP TABLE _evt_map ON COMMIT DROP AS
WITH RECURSIVE fr AS (
    SELECT id, code, 1 AS lvl,
           (row_number() OVER (ORDER BY id))::int * 10000 AS tree
    FROM larcauth_event_type_config WHERE fk_language = 2 AND parent_id IS NULL
  UNION ALL
    SELECT c.id, c.code, p.lvl + 1,
           p.tree + (row_number() OVER (PARTITION BY c.parent_id ORDER BY c.id))::int *
                    (CASE p.lvl WHEN 1 THEN 1000 WHEN 2 THEN 100 ELSE 1 END)
    FROM larcauth_event_type_config c JOIN fr p ON c.parent_id = p.id
    WHERE c.fk_language = 2
)
SELECT e.id AS old_id, e.fk_language * 100000 + fr.tree AS new_id
FROM larcauth_event_type_config e JOIN fr ON fr.code = e.code;

-- 3. Garde-fous : tout est couvert, aucun doublon
DO $$
BEGIN
    IF (SELECT count(*) FROM _evt_map) <> (SELECT count(*) FROM larcauth_event_type_config) THEN
        RAISE EXCEPTION 'correspondance incomplète';
    END IF;
    IF (SELECT count(DISTINCT new_id) FROM _evt_map) <> (SELECT count(*) FROM _evt_map) THEN
        RAISE EXCEPTION 'nouveaux IDs en doublon';
    END IF;
END $$;

-- 4. Application
UPDATE larcauth_event_type_config e SET parent_id = m.new_id
FROM _evt_map m WHERE e.parent_id = m.old_id;
UPDATE student_event s SET event_type_config_id = m.new_id
FROM _evt_map m WHERE s.event_type_config_id = m.old_id;
UPDATE staff_event s SET event_type_config_id = m.new_id
FROM _evt_map m WHERE s.event_type_config_id = m.old_id;
UPDATE larcauth_event_type_config e SET id = m.new_id
FROM _evt_map m WHERE e.id = m.old_id;

SELECT setval('larcauth_event_type_config_id_seq', (SELECT max(id) FROM larcauth_event_type_config));

COMMIT;

-- 5. Retour à l'état d'origine des contraintes (hors transaction)
ALTER TABLE larcauth_event_type_config ALTER CONSTRAINT larcauth_event_type_config_parent_id_fkey NOT DEFERRABLE;
ALTER TABLE student_event ALTER CONSTRAINT student_event_event_type_config_id_fkey NOT DEFERRABLE;
ALTER TABLE staff_event   ALTER CONSTRAINT staff_event_event_type_config_id_fkey   NOT DEFERRABLE;
