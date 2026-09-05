-- Vérification du dossier « Vérifié et Validé » — port Blado (2026-08-16)
-- Validation 100 % manuelle : le RH coche chaque item indispensable.
CREATE TABLE IF NOT EXISTS staff_dossier_check (
    id              SERIAL PRIMARY KEY,
    staff_id        INTEGER NOT NULL REFERENCES larcauth_aecuser(id) ON DELETE CASCADE,
    item_key        VARCHAR(40) NOT NULL,   -- matricule, cnss, piece_identite, urgence_nom, urgence_tel
    validated       BOOLEAN NOT NULL DEFAULT FALSE,
    validated_by    VARCHAR(150),
    validated_at    TIMESTAMP,
    UNIQUE (staff_id, item_key)
);
