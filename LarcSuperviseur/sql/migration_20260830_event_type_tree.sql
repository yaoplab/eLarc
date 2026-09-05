-- ============================================================================
-- Migration 2026-08-30 — Types d'événements en arbre (LarcSuperviseur)
-- ============================================================================
-- Objectif :
--   1. larcauth_type_event devient un arbre auto-référencé (parent_id) avec
--      codes stables (code UNIQUE) — générique, profondeur illimitée.
--   2. student_event.event_type_id (FK) — sémantique portable pour les stats
--      (les chaînes event_type restent pour compatibilité legacy).
--   3. Verrou strict : un type référencé dans student_event est IMMUABLE
--      (trigger 23513 + checks Python côté appli).
--
-- Usage : psql -U postgres -d NewLarcDB -f migration_20260830_event_type_tree.sql
-- Idempotent : peut être relancé sans risque.
--
-- AVANT EXÉCUTION — vérifier l'unicité des IDs (sinon PK impossible) :
--   SELECT idtypeevent, count(*) FROM larcauth_type_event GROUP BY 1 HAVING count(*) > 1;
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION larc_slugify(label text) RETURNS text AS $$
    SELECT regexp_replace(
        regexp_replace(
        regexp_replace(
        regexp_replace(
        regexp_replace(
        regexp_replace(
        regexp_replace(
        regexp_replace(
            lower(COALESCE(label, '')),
            '[àâä]', 'a', 'g'),
            '[éèêë]', 'e', 'g'),
            '[îï]', 'i', 'g'),
            '[ôö]', 'o', 'g'),
            '[ùûü]', 'u', 'g'),
            'ç', 'c', 'g'),
            'ñ', 'n', 'g'),
        '[^a-z0-9]+', '-', 'g')
$$ LANGUAGE sql IMMUTABLE;

CREATE OR REPLACE FUNCTION larc_unique_code(base text) RETURNS text AS $$
DECLARE
    c text := COALESCE(NULLIF(base, ''), 'type');
    i int := 2;
BEGIN
    WHILE EXISTS (SELECT 1 FROM larcauth_type_event WHERE code = c) LOOP
        c := base || '-' || i;
        i := i + 1;
    END LOOP;
    RETURN c;
END $$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- A1. PRIMARY KEY + colonnes arbre + contraintes
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'larcauth_type_event_pkey') THEN
        ALTER TABLE larcauth_type_event ADD PRIMARY KEY (idtypeevent);
    END IF;
END $$;

-- fk_language existe en prod (ajout non documenté) ; garantie pour le script :
ALTER TABLE larcauth_type_event ADD COLUMN IF NOT EXISTS fk_language SMALLINT;

ALTER TABLE larcauth_type_event ADD COLUMN IF NOT EXISTS parent_id     SMALLINT;
ALTER TABLE larcauth_type_event ADD COLUMN IF NOT EXISTS code          VARCHAR(64);
ALTER TABLE larcauth_type_event ADD COLUMN IF NOT EXISTS label         VARCHAR(72);
ALTER TABLE larcauth_type_event ADD COLUMN IF NOT EXISTS sort_order    SMALLINT NOT NULL DEFAULT 0;
ALTER TABLE larcauth_type_event ADD COLUMN IF NOT EXISTS absence_scope VARCHAR(8);
ALTER TABLE larcauth_type_event ADD COLUMN IF NOT EXISTS context       VARCHAR(8);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_type_event_absence_scope') THEN
        ALTER TABLE larcauth_type_event ADD CONSTRAINT chk_type_event_absence_scope
            CHECK (absence_scope IN ('ecole', 'cours'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_type_event_context') THEN
        ALTER TABLE larcauth_type_event ADD CONSTRAINT chk_type_event_context
            CHECK (context IN ('cours', 'hors'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_type_event_parent') THEN
        ALTER TABLE larcauth_type_event ADD CONSTRAINT fk_type_event_parent
            FOREIGN KEY (parent_id) REFERENCES larcauth_type_event(idtypeevent);
    END IF;
END $$;

-- Unicité du code PAR LANGUE (nœuds FR/EN d'une même notion partagent le code)
UPDATE larcauth_type_event SET fk_language = 2 WHERE fk_language IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_type_event_code ON larcauth_type_event(fk_language, code);

-- student_event : FK vers le type (NULL = keyword legacy / non résolu)
ALTER TABLE student_event ADD COLUMN IF NOT EXISTS event_type_id SMALLINT;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_student_event_type') THEN
        ALTER TABLE student_event ADD CONSTRAINT fk_student_event_type
            FOREIGN KEY (event_type_id) REFERENCES larcauth_type_event(idtypeevent);
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_student_event_type ON student_event(event_type_id);

-- ---------------------------------------------------------------------------
-- A2. Nœuds structurels (IDs < 100, hors du re-seed DELETE >= 100)
--     type_event = NULL → invisibles pour les lecteurs legacy
--     (get_event_types_tree filtre type_event IS NOT NULL).
-- ---------------------------------------------------------------------------
INSERT INTO larcauth_type_event
    (idtypeevent, type_event, "Event_Niveau2", "Event_Niveau3", "Enabled", fk_language,
     parent_id, code, label, sort_order)
VALUES
    (1, NULL, NULL, NULL, TRUE, 2, NULL, 'evenement',    'Événement',          1),
    (2, NULL, NULL, NULL, TRUE, 2, NULL, 'absence',      'Absence',            2),
    (3, NULL, NULL, NULL, TRUE, 2, NULL, 'retard',       'Retard',             3),
    (4, NULL, NULL, NULL, TRUE, 2, 1,    'bureau-bi',    'Bureau BI',          1),
    (5, NULL, NULL, NULL, TRUE, 2, 1,    'medical',      'Médical',            2),
    (6, NULL, NULL, NULL, TRUE, 2, 1,    'sortie',       'Sortie',             3),
    (7, NULL, NULL, NULL, TRUE, 2, 1,    'suivi',        'Suivi',              4),
    (8, NULL, NULL, NULL, TRUE, 2, 2,    'absent-ecole', 'Absent de l''école', 1),
    (9, NULL, NULL, NULL, TRUE, 2, 2,    'absent-cours', 'Absent du cours',    2),
    -- Nœuds N2 intermédiaires du seed (IDs fixes, référencés par type_event_data.sql)
    (10, NULL, NULL, NULL, TRUE, 2, 4,   'bureau-bi-violence',    'Violence',    1),
    (11, NULL, NULL, NULL, TRUE, 2, 4,   'bureau-bi-harcelement', 'Harcèlement', 2),
    (12, NULL, NULL, NULL, TRUE, 2, 5,   'medical-accident',      'Accident',    1),
    (13, NULL, NULL, NULL, TRUE, 2, 6,   'sortie-perturbation',   'Perturbation', 1),
    (14, NULL, NULL, NULL, TRUE, 2, 6,   'sortie-exclusion',      'Exclusion',   2),
    -- Motifs d'absence école (sous absent-ecole) — la prod n'en a pas encore
    (15, NULL, NULL, NULL, TRUE, 2, 8,   'absence-ecole-maladie',       'Maladie',         1),
    (16, NULL, NULL, NULL, TRUE, 2, 8,   'absence-ecole-accident',      'Accident',        2),
    (17, NULL, NULL, NULL, TRUE, 2, 8,   'absence-ecole-vacances',      'Vacances',        3),
    (18, NULL, NULL, NULL, TRUE, 2, 8,   'absence-ecole-non-justifiee', 'Non justifiée',   4),
    (19, NULL, NULL, NULL, TRUE, 2, 8,   'absence-ecole-autre',         'Autre',           5),
    -- Nœuds EN (fk_language=1) — labels alignés sur la prod réelle
    (21, NULL, NULL, NULL, TRUE, 1, NULL, 'evenement',    'Event',            1),
    (22, NULL, NULL, NULL, TRUE, 1, NULL, 'absence',      'Absence',          2),
    (23, NULL, NULL, NULL, TRUE, 1, NULL, 'retard',       'Tardiness',        3),
    (24, NULL, NULL, NULL, TRUE, 1, 21,   'bureau-bi',    'BI Office',        1),
    (25, NULL, NULL, NULL, TRUE, 1, 21,   'medical',      'Medical',          2),
    (26, NULL, NULL, NULL, TRUE, 1, 21,   'sortie',       'Removal',          3),
    (27, NULL, NULL, NULL, TRUE, 1, 21,   'suivi',        'Follow-up',        4),
    (28, NULL, NULL, NULL, TRUE, 1, 22,   'absent-ecole', 'Absent from school', 1),
    (29, NULL, NULL, NULL, TRUE, 1, 22,   'absent-cours', 'Class absence',    2)
ON CONFLICT (idtypeevent) DO NOTHING;

-- ---------------------------------------------------------------------------
-- A2 (suite). Ré-parentage générique des lignes existantes (IDs >= 100)
--   - Suivi/Absence/*   → nœud 'absent-ecole' (8)      — nouvelle taxonomie
--   - Suivi/Retard      → racine 'retard' (3)          — héritage
--   - Suivi/Comportement, Suivi/Suivi pédagogique → 'suivi' (7)
--   - lignes N3 (cat/n2/n3) : nœud N2 intermédiaire créé sous la catégorie,
--     la ligne devient la feuille (label = N3)
--   - lignes N2 sans N3 : feuille directe sous la catégorie
--   Les lignes dont la catégorie n'a pas de nœud structurel (ex. langues EN
--   non couvertes) restent non ré-parentées — notice en fin de DO block.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    r RECORD;
    cat_node SMALLINT;
    n2_id SMALLINT;
    next_id SMALLINT;
    orphans INT := 0;
BEGIN
    FOR r IN
        SELECT idtypeevent, type_event AS cat, "Event_Niveau2" AS n2,
               "Event_Niveau3" AS n3, COALESCE(fk_language, 2) AS lang
        FROM larcauth_type_event
        WHERE idtypeevent NOT IN (1, 2, 3, 4, 5, 6, 7, 8, 9)
          AND type_event IS NOT NULL
        ORDER BY idtypeevent
    LOOP
        -- ---- Cas spéciaux (catégories absence + héritage Retard) ----
        IF r.cat = 'Suivi' AND r.n2 = 'Retard' THEN
            UPDATE larcauth_type_event SET parent_id = 3, label = 'Retard',
                   code = larc_unique_code('retard')
            WHERE idtypeevent = r.idtypeevent;
            CONTINUE;
        END IF;
        IF r.cat = 'Follow-up' AND r.n2 = 'Tardiness' THEN
            UPDATE larcauth_type_event SET parent_id = 23, label = 'Tardiness',
                   code = larc_unique_code('retard')
            WHERE idtypeevent = r.idtypeevent;
            CONTINUE;
        END IF;
        IF r.cat = 'Absence cours' THEN
            UPDATE larcauth_type_event SET parent_id = 9, label = BTRIM(r.n2),
                   code = larc_unique_code(larc_slugify('absent-cours-' || BTRIM(r.n2)))
            WHERE idtypeevent = r.idtypeevent;
            CONTINUE;
        END IF;
        IF r.cat = 'Class absence' THEN
            UPDATE larcauth_type_event SET parent_id = 29, label = BTRIM(r.n2),
                   code = larc_unique_code(larc_slugify('class-absence-' || BTRIM(r.n2)))
            WHERE idtypeevent = r.idtypeevent;
            CONTINUE;
        END IF;

        -- ---- Nœud catégorie structurel (même langue que la ligne) ----
        SELECT idtypeevent INTO cat_node FROM larcauth_type_event
        WHERE parent_id IS NOT NULL AND code IN
              ('bureau-bi', 'medical', 'sortie', 'suivi')
          AND BTRIM(label) = BTRIM(r.cat) AND COALESCE(fk_language, 2) = r.lang
        LIMIT 1;

        IF cat_node IS NULL THEN
            orphans := orphans + 1;
            CONTINUE;
        END IF;

        -- ---- Feuille N2 sans N3 : directe sous la catégorie ----
        IF r.n3 IS NULL OR NULLIF(r.n3, '') IS NULL THEN
            UPDATE larcauth_type_event SET parent_id = cat_node, label = BTRIM(r.n2),
                   code = larc_unique_code(larc_slugify(r.cat || '-' || BTRIM(r.n2)))
            WHERE idtypeevent = r.idtypeevent;
            CONTINUE;
        END IF;

        -- ---- Feuille N3 : nœud N2 intermédiaire si absent ----
        SELECT idtypeevent INTO n2_id FROM larcauth_type_event
        WHERE parent_id = cat_node AND BTRIM(label) = BTRIM(r.n2)
        LIMIT 1;
        IF n2_id IS NULL THEN
            -- ID fixe pour les N2 du seed (10-14) ; sinon max+1
            n2_id := NULL;
            IF r.cat = 'Bureau BI' AND BTRIM(r.n2) = 'Violence' THEN n2_id := 10;
            ELSIF r.cat = 'Bureau BI' AND BTRIM(r.n2) = 'Harcèlement' THEN n2_id := 11;
            ELSIF r.cat = 'Médical' AND BTRIM(r.n2) = 'Accident' THEN n2_id := 12;
            ELSIF r.cat = 'Sortie' AND BTRIM(r.n2) = 'Perturbation' THEN n2_id := 13;
            ELSIF r.cat = 'Sortie' AND BTRIM(r.n2) = 'Exclusion' THEN n2_id := 14;
            END IF;
            IF n2_id IS NULL OR NOT EXISTS (SELECT 1 FROM larcauth_type_event WHERE idtypeevent = n2_id) THEN
                SELECT COALESCE(MAX(idtypeevent), 0) + 1 INTO next_id FROM larcauth_type_event;
                n2_id := next_id;
            END IF;
            INSERT INTO larcauth_type_event
                (idtypeevent, type_event, "Enabled", fk_language, parent_id, code, label, sort_order)
            VALUES
                (n2_id, NULL, TRUE, r.lang, cat_node,
                 larc_unique_code(larc_slugify(r.cat || '-' || BTRIM(r.n2))), BTRIM(r.n2),
                 (SELECT COALESCE(MAX(sort_order), 0) + 1 FROM larcauth_type_event WHERE parent_id = cat_node));
        END IF;

        UPDATE larcauth_type_event SET parent_id = n2_id, label = BTRIM(r.n3),
               code = larc_unique_code(larc_slugify(r.cat || '-' || BTRIM(r.n2) || '-' || BTRIM(r.n3)))
        WHERE idtypeevent = r.idtypeevent;
    END LOOP;

    IF orphans > 0 THEN
        RAISE NOTICE 'Migration : % ligne(s) sans catégorie structurelle (non ré-parentées)', orphans;
    END IF;
END $$;

-- sort_order global par parent (déterministe)
UPDATE larcauth_type_event te SET sort_order = sub.rn
FROM (SELECT idtypeevent, ROW_NUMBER() OVER (PARTITION BY parent_id ORDER BY idtypeevent) AS rn
      FROM larcauth_type_event) sub
WHERE te.idtypeevent = sub.idtypeevent;

-- ---------------------------------------------------------------------------
-- A3. Backfill student_event.event_type_id (idempotent — ré-exécutable)
--   Étape 1 : correspondance exacte du chemin legacy stocké
--             ('Suivi > Absence > Maladie' = type_event || N2 || N3)
--   Étape 2 : motif 'Suivi > Absence > X' → nœud 'absent-ecole' (code
--             'absence-ecole-<x>'), fallback si l'étape 1 a raté (langues)
--   Étape 3 (Python) : chemins de la nouvelle taxonomie → sql/backfill_event_type_id.py
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION backfill_event_type_id() RETURNS integer AS $$
DECLARE
    n integer := 0;
    added integer := 0;
BEGIN
    -- 1. Exact-match legacy (1/2/3 niveaux)
    UPDATE student_event se SET event_type_id = te.idtypeevent
      FROM larcauth_type_event te
     WHERE se.event_type_id IS NULL
       AND se.event_type = te.type_event
           || COALESCE(' > ' || NULLIF(te."Event_Niveau2", ''), '')
           || COALESCE(' > ' || NULLIF(te."Event_Niveau3", ''), '')
       AND te."Enabled";
    GET DIAGNOSTICS n = ROW_COUNT;

    -- 2. Motifs 'Suivi > Absence > X' → nœud 'absent-ecole'
    UPDATE student_event se SET event_type_id = te.idtypeevent
      FROM larcauth_type_event te
     WHERE se.event_type_id IS NULL
       AND se.event_type LIKE 'Suivi > Absence > %'
       AND te.code = larc_slugify('absence-ecole-' || split_part(se.event_type, ' > ', 3))
       AND te."Enabled";
    GET DIAGNOSTICS added = ROW_COUNT;
    n := n + added;

    -- 3. 'Absence > X' → motif existant sous absent-ecole (8) / absent-cours (9)
    UPDATE student_event se SET event_type_id = te.idtypeevent
      FROM larcauth_type_event te
     WHERE se.event_type_id IS NULL
       AND se.event_type LIKE 'Absence > %'
       AND te.parent_id IN (8, 9)
       AND te.label = split_part(se.event_type, ' > ', 2)
       AND te."Enabled";
    GET DIAGNOSTICS added = ROW_COUNT;
    n := n + added;

    -- 4. 'Absence > Maladie/Accident/Vacances/Autre' → absent-ecole (8)
    UPDATE student_event se SET event_type_id = 8
     WHERE se.event_type_id IS NULL
       AND se.event_type LIKE 'Absence > %'
       AND lower(split_part(se.event_type, ' > ', 2)) IN
           ('maladie', 'accident', 'vacances', 'autre');
    GET DIAGNOSTICS added = ROW_COUNT;
    n := n + added;

    -- 5. 'Absence > justifié/infirmerie' → absent-cours (9)
    UPDATE student_event se SET event_type_id = 9
     WHERE se.event_type_id IS NULL
       AND se.event_type LIKE 'Absence > %'
       AND (lower(split_part(se.event_type, ' > ', 2)) LIKE '%justifi%'
            OR lower(split_part(se.event_type, ' > ', 2)) = 'infirmerie');
    GET DIAGNOSTICS added = ROW_COUNT;
    n := n + added;

    -- 6. 'Retard …' (héritage) → racine retard (3)
    UPDATE student_event se SET event_type_id = 3
     WHERE se.event_type_id IS NULL AND se.event_type LIKE 'Retard%';
    GET DIAGNOSTICS added = ROW_COUNT;
    n := n + added;

    RETURN n;
END $$ LANGUAGE plpgsql;

SELECT backfill_event_type_id() AS backfilled_event_type_ids;

-- ---------------------------------------------------------------------------
-- A4. Verrou strict — trigger sur larcauth_type_event
--   - UPDATE/DELETE d'un type référencé par student_event.event_type_id :
--     REFUSÉ (ERRCODE 23513 = exclusion_violation).
--   - Déplacement d'un nœud sous son propre descendant : REFUSÉ (anti-cycle).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION guard_type_event_used() RETURNS trigger AS $$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') AND EXISTS (
        SELECT 1 FROM student_event WHERE event_type_id = OLD.idtypeevent
    ) THEN
        RAISE EXCEPTION 'type_event % (%) : type déjà utilisé dans student_event — immuable',
            OLD.idtypeevent, OLD.label USING ERRCODE = '23513';
    END IF;

    IF TG_OP = 'UPDATE' AND NEW.parent_id IS NOT NULL
       AND NEW.parent_id IN (
           WITH RECURSIVE sub AS (
               SELECT idtypeevent FROM larcauth_type_event WHERE parent_id = OLD.idtypeevent
               UNION ALL
               SELECT t.idtypeevent FROM larcauth_type_event t
                   JOIN sub s ON t.parent_id = s.idtypeevent
           ) SELECT idtypeevent FROM sub)
    THEN
        RAISE EXCEPTION 'type_event % : déplacement sous un descendant interdit', OLD.idtypeevent
            USING ERRCODE = '23513';
    END IF;
    -- IMPORTANT : sur DELETE, NEW est NULL → RETURN NEW annulerait silencieusement
    -- tous les DELETE. Il faut retourner OLD pour autoriser la suppression.
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_guard_type_event_used ON larcauth_type_event;
CREATE TRIGGER trg_guard_type_event_used
    BEFORE UPDATE OR DELETE ON larcauth_type_event
    FOR EACH ROW EXECUTE FUNCTION guard_type_event_used();

-- ============================================================================
-- VÉRIFICATIONS (à lancer après exécution)
-- ============================================================================
-- 1. Racines :  SELECT code, label FROM larcauth_type_event WHERE parent_id IS NULL
--               → evenement, absence, retard
-- 2. Backfill : SELECT count(*) FROM student_event WHERE event_type_id IS NOT NULL;
-- 3. Trigger :  UPDATE larcauth_type_event SET label = label WHERE idtypeevent =
--               (SELECT event_type_id FROM student_event WHERE event_type_id IS NOT NULL LIMIT 1)
--               → exception 23513 attendue
-- 4. Codes :    SELECT count(*) FROM (SELECT code FROM larcauth_type_event
--               GROUP BY 1 HAVING count(*) > 1) x;  → 0
-- 5. Legacy :   get_event_types_tree() (appli) → même forme qu'avant migration
-- ============================================================================
