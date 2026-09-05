-- Audit trail RH (2026-08-16) : chaque table d'information purement RH
-- porte created_by / modified_by = id du larcauth_aecuser qui a créé/modifié.
-- Les tableaux informationnels affichent le NOM résolu (JOIN larcauth_aecuser).
ALTER TABLE staff_event           ADD COLUMN IF NOT EXISTS modified_by INTEGER;
ALTER TABLE staff_contract        ADD COLUMN IF NOT EXISTS modified_by INTEGER;
ALTER TABLE staff_todo            ADD COLUMN IF NOT EXISTS modified_by INTEGER;

ALTER TABLE staff_leave_request   ADD COLUMN IF NOT EXISTS created_by INTEGER;
ALTER TABLE staff_leave_request   ADD COLUMN IF NOT EXISTS modified_by INTEGER;
ALTER TABLE staff_leave_balance   ADD COLUMN IF NOT EXISTS created_by INTEGER;
ALTER TABLE staff_leave_balance   ADD COLUMN IF NOT EXISTS modified_by INTEGER;
ALTER TABLE staff_degree          ADD COLUMN IF NOT EXISTS created_by INTEGER;
ALTER TABLE staff_degree          ADD COLUMN IF NOT EXISTS modified_by INTEGER;
ALTER TABLE staff_language        ADD COLUMN IF NOT EXISTS created_by INTEGER;
ALTER TABLE staff_language        ADD COLUMN IF NOT EXISTS modified_by INTEGER;
ALTER TABLE staff_detail_category ADD COLUMN IF NOT EXISTS created_by INTEGER;
ALTER TABLE staff_detail_category ADD COLUMN IF NOT EXISTS modified_by INTEGER;
ALTER TABLE staff_document        ADD COLUMN IF NOT EXISTS created_by INTEGER;
ALTER TABLE staff_document        ADD COLUMN IF NOT EXISTS modified_by INTEGER;
ALTER TABLE staff_dossier_check   ADD COLUMN IF NOT EXISTS created_by INTEGER;
ALTER TABLE staff_dossier_check   ADD COLUMN IF NOT EXISTS modified_by INTEGER;
ALTER TABLE hr_generated_letter   ADD COLUMN IF NOT EXISTS created_by INTEGER;
ALTER TABLE hr_generated_letter   ADD COLUMN IF NOT EXISTS modified_by INTEGER;
