-- Phase A — rôles du personnel : larcauth_teachadm devient la source unique.
-- Idempotent. À exécuter sur l'Intranet PUIS sur Supabase. Aucune colonne supprimée ici.
-- Principe gabarit : aucune suppression ; INSERT limité aux comptes personnel sans ligne teachadm.
BEGIN;

-- 1. Colonnes de rôle manquantes (supervisor et director n'existaient que dans aecuser ; is_non_teaching est nouveau)
ALTER TABLE larcauth_teachadm ADD COLUMN IF NOT EXISTS is_supervisor BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE larcauth_teachadm ADD COLUMN IF NOT EXISTS is_director   BOOLEAN NOT NULL DEFAULT FALSE;
-- is_non_teaching : personnel non enseignant (aucun équivalent historique, donc aucun rapatriement)
ALTER TABLE larcauth_teachadm ADD COLUMN IF NOT EXISTS is_non_teaching BOOLEAN NOT NULL DEFAULT FALSE;

-- 2. Comptes personnel (ID 1 à 4000) sans ligne teachadm : on la crée (rares exceptions au gabarit)
INSERT INTO larcauth_teachadm (aecuser_ptr_id, enabled, is_teacher, is_adm, is_coordonator, is_secretary)
SELECT a.id, a.is_active, FALSE, FALSE, FALSE, FALSE
FROM larcauth_aecuser a
WHERE a.id BETWEEN 1 AND 4000
  AND NOT EXISTS (SELECT 1 FROM larcauth_teachadm t WHERE t.aecuser_ptr_id = a.id);

-- 3. Rapatriement des rôles depuis aecuser (réunion : on ne retire jamais un rôle existant)
UPDATE larcauth_teachadm t SET
    is_teacher     = COALESCE(t.is_teacher, FALSE)     OR COALESCE(a.type_teacher, FALSE),
    is_coordonator = COALESCE(t.is_coordonator, FALSE) OR COALESCE(a.type_coordonator, FALSE),
    is_secretary   = COALESCE(t.is_secretary, FALSE)   OR COALESCE(a.type_secretary, FALSE),
    is_supervisor  = COALESCE(t.is_supervisor, FALSE)  OR COALESCE(a.type_supervisor, FALSE),
    is_director    = COALESCE(t.is_director, FALSE)    OR COALESCE(a.type_director, FALSE)
FROM larcauth_aecuser a
WHERE a.id = t.aecuser_ptr_id;
-- is_adm est laissé tel quel : il diverge de type_director dans les deux sens (à arbitrer).

COMMIT;
