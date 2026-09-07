-- Migration: 2026-09-07_event_type_language_gabarit
-- fk_language sur larcauth_event_type_config (pattern larcauth_program : arbre dupliqué par
-- langue, is_active indépendant par langue) + gabarit de slots potentiels réutilisables.
-- Additive uniquement (principe gabarit) : les 105 lignes existantes deviennent la variante
-- FR (fk_language=2), dupliquées en EN (fk_language=1, texte à corriger dans LarcConfig).

-- ----------------------------------------------------------------------------
-- 1. Colonne fk_language — les 105 lignes existantes sont la variante française
-- ----------------------------------------------------------------------------
ALTER TABLE larcauth_event_type_config
    ADD COLUMN IF NOT EXISTS fk_language INT REFERENCES larcauth_language(id);

UPDATE larcauth_event_type_config SET fk_language = 2 WHERE fk_language IS NULL;

ALTER TABLE larcauth_event_type_config ALTER COLUMN fk_language SET NOT NULL;

ALTER TABLE larcauth_event_type_config
    DROP CONSTRAINT IF EXISTS larcauth_event_type_config_code_key;

DO $$ BEGIN
    ALTER TABLE larcauth_event_type_config
        ADD CONSTRAINT larcauth_event_type_config_code_fklang_key UNIQUE (code, fk_language);
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL;
END $$;

-- ----------------------------------------------------------------------------
-- 2. Duplication FR (fk_language=2) -> EN (fk_language=1)
--    4 passes identiques (profondeur max = 4 niveaux) : chaque passe résout le parent EN
--    via le code du parent FR déjà dupliqué par la passe précédente (les racines n'ont pas
--    besoin de parent résolu, elles passent dès la 1re passe).
-- ----------------------------------------------------------------------------
INSERT INTO larcauth_event_type_config
    (code, label, category, icon_code, parent_id, applicable_to, requires_validation,
     requires_lieu, requires_subject, is_active, fk_language)
SELECT fr.code, fr.label, fr.category, fr.icon_code, en_parent.id,
       fr.applicable_to, fr.requires_validation, fr.requires_lieu, fr.requires_subject,
       fr.is_active, 1
FROM larcauth_event_type_config fr
LEFT JOIN larcauth_event_type_config fr_parent ON fr_parent.id = fr.parent_id
LEFT JOIN larcauth_event_type_config en_parent
       ON en_parent.code = fr_parent.code AND en_parent.fk_language = 1
WHERE fr.fk_language = 2
  AND NOT EXISTS (
      SELECT 1 FROM larcauth_event_type_config x WHERE x.code = fr.code AND x.fk_language = 1
  )
  AND (fr.parent_id IS NULL OR en_parent.id IS NOT NULL);

-- Passe 2 (résout les enfants de racines, désormais dupliquées par la passe 1)
INSERT INTO larcauth_event_type_config
    (code, label, category, icon_code, parent_id, applicable_to, requires_validation,
     requires_lieu, requires_subject, is_active, fk_language)
SELECT fr.code, fr.label, fr.category, fr.icon_code, en_parent.id,
       fr.applicable_to, fr.requires_validation, fr.requires_lieu, fr.requires_subject,
       fr.is_active, 1
FROM larcauth_event_type_config fr
LEFT JOIN larcauth_event_type_config fr_parent ON fr_parent.id = fr.parent_id
LEFT JOIN larcauth_event_type_config en_parent
       ON en_parent.code = fr_parent.code AND en_parent.fk_language = 1
WHERE fr.fk_language = 2
  AND NOT EXISTS (
      SELECT 1 FROM larcauth_event_type_config x WHERE x.code = fr.code AND x.fk_language = 1
  )
  AND (fr.parent_id IS NULL OR en_parent.id IS NOT NULL);

-- Passe 3
INSERT INTO larcauth_event_type_config
    (code, label, category, icon_code, parent_id, applicable_to, requires_validation,
     requires_lieu, requires_subject, is_active, fk_language)
SELECT fr.code, fr.label, fr.category, fr.icon_code, en_parent.id,
       fr.applicable_to, fr.requires_validation, fr.requires_lieu, fr.requires_subject,
       fr.is_active, 1
FROM larcauth_event_type_config fr
LEFT JOIN larcauth_event_type_config fr_parent ON fr_parent.id = fr.parent_id
LEFT JOIN larcauth_event_type_config en_parent
       ON en_parent.code = fr_parent.code AND en_parent.fk_language = 1
WHERE fr.fk_language = 2
  AND NOT EXISTS (
      SELECT 1 FROM larcauth_event_type_config x WHERE x.code = fr.code AND x.fk_language = 1
  )
  AND (fr.parent_id IS NULL OR en_parent.id IS NOT NULL);

-- Passe 4 (feuilles)
INSERT INTO larcauth_event_type_config
    (code, label, category, icon_code, parent_id, applicable_to, requires_validation,
     requires_lieu, requires_subject, is_active, fk_language)
SELECT fr.code, fr.label, fr.category, fr.icon_code, en_parent.id,
       fr.applicable_to, fr.requires_validation, fr.requires_lieu, fr.requires_subject,
       fr.is_active, 1
FROM larcauth_event_type_config fr
LEFT JOIN larcauth_event_type_config fr_parent ON fr_parent.id = fr.parent_id
LEFT JOIN larcauth_event_type_config en_parent
       ON en_parent.code = fr_parent.code AND en_parent.fk_language = 1
WHERE fr.fk_language = 2
  AND NOT EXISTS (
      SELECT 1 FROM larcauth_event_type_config x WHERE x.code = fr.code AND x.fk_language = 1
  )
  AND (fr.parent_id IS NULL OR en_parent.id IS NOT NULL);

-- ----------------------------------------------------------------------------
-- 3. Gabarit potentiel — niveau 1 (racines) : +2 par langue, catégorie 'custom', sans parent
-- ----------------------------------------------------------------------------
INSERT INTO larcauth_event_type_config
    (code, label, category, parent_id, applicable_to, requires_validation, requires_lieu,
     requires_subject, is_active, fk_language)
SELECT 'type_niv1_' || lpad(n::text, 2, '0'),
       'Type_Niv1_' || lpad(n::text, 2, '0'),
       'custom', NULL, 'student,staff', TRUE, FALSE, FALSE, FALSE, lang.id
FROM generate_series(1, 2) AS n
CROSS JOIN larcauth_language lang
ON CONFLICT (code, fk_language) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 4. Gabarit potentiel — niveaux 2-4 : +2 par parent réel ACTIF, par langue
--    (aucun slot potentiel niveau 2 sous une racine potentielle — is_active=TRUE filtre ça)
-- ----------------------------------------------------------------------------
WITH RECURSIVE depths AS (
    SELECT id, code, category, applicable_to, fk_language, 1 AS depth
    FROM larcauth_event_type_config WHERE parent_id IS NULL AND is_active = TRUE
    UNION ALL
    SELECT c.id, c.code, c.category, c.applicable_to, c.fk_language, d.depth + 1
    FROM larcauth_event_type_config c
    JOIN depths d ON c.parent_id = d.id
    WHERE c.is_active = TRUE
)
INSERT INTO larcauth_event_type_config
    (code, label, category, parent_id, applicable_to, requires_validation, requires_lieu,
     requires_subject, is_active, fk_language)
SELECT 'type_niv' || (d.depth + 1) || '_' || d.code || '_' || lpad(n::text, 2, '0'),
       'Type_Niv' || (d.depth + 1) || '_' || lpad(n::text, 2, '0'),
       d.category, d.id, d.applicable_to, TRUE, FALSE, FALSE, FALSE, d.fk_language
FROM depths d
CROSS JOIN generate_series(1, 2) AS n
WHERE d.depth < 4
ON CONFLICT (code, fk_language) DO NOTHING;
