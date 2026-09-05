-- LarcRH — Support personnalisation des modèles de lettres (body_text + source_code)
-- À exécuter sur Intranet (127.0.0.1:5432) ET Supabase Cloud (6543)
-- Usage : psql -U postgres -d NewLarcDB -f migration_20260809_letter_body_custom.sql

BEGIN;

-- Colonne pour le corps personnalisé (NULL = utiliser la fonction _body_* intégrée)
ALTER TABLE hr_letter_template
    ADD COLUMN IF NOT EXISTS body_text TEXT;

-- Colonne pour tracer le code source lors d'une duplication depuis le catalogue
ALTER TABLE hr_letter_template
    ADD COLUMN IF NOT EXISTS source_code VARCHAR(8);

-- Backfill : les copies existantes portent leur origine dans "[De A01] …" de la description
UPDATE hr_letter_template
   SET source_code = substring(description from '^\[De ([A-J][0-9]{2})\]')
 WHERE source_code IS NULL
   AND is_builtin = FALSE
   AND description ~ '^\[De [A-J][0-9]{2}\]';

COMMIT;
