-- État du dossier PRÉ-CALCULÉ pour le dashboard (2026-08-16).
-- Mis à jour par set_dossier_check() à chaque cochage — le dashboard lit
-- cette table en 1 SELECT (pas de recalcul par refresh), comme la balance
-- pré-calculée de la scolarité (compta_parent_balance).
CREATE TABLE IF NOT EXISTS staff_dossier_status (
    staff_id        INTEGER PRIMARY KEY REFERENCES larcauth_aecuser(id) ON DELETE CASCADE,
    validated_count INTEGER NOT NULL DEFAULT 0,
    total_items     INTEGER NOT NULL DEFAULT 8,
    complete        BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- Backfill depuis les checks existants
INSERT INTO staff_dossier_status (staff_id, validated_count, total_items, complete)
SELECT dc.staff_id,
       COUNT(*) FILTER (WHERE dc.validated = TRUE),
       8,
       (COUNT(*) FILTER (WHERE dc.validated = TRUE) = 8)
FROM staff_dossier_check dc
GROUP BY dc.staff_id
ON CONFLICT (staff_id) DO UPDATE SET
    validated_count = EXCLUDED.validated_count,
    total_items     = EXCLUDED.total_items,
    complete        = EXCLUDED.complete,
    updated_at      = NOW();
