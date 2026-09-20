-- Phase B — supprime de aecuser les types devenus inutiles. NE PAS EXÉCUTER
-- avant que TOUTES les applications lisent teachadm (voir l'inventaire des lecteurs).
-- Le type se déduit de la sous-table : teachadm = personnel, student = élève.
-- type_parentutor est conservé : il n'existe aucune sous-table « parent ».
BEGIN;
ALTER TABLE larcauth_aecuser
    DROP COLUMN IF EXISTS type_teacher,
    DROP COLUMN IF EXISTS type_student,
    DROP COLUMN IF EXISTS type_coordonator,
    DROP COLUMN IF EXISTS type_supervisor,
    DROP COLUMN IF EXISTS type_secretary,
    DROP COLUMN IF EXISTS type_director;
COMMIT;
