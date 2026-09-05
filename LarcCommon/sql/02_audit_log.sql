-- =============================================================
-- 02_audit_log.sql — Journal d'audit « qui a fait quoi, quand » (R2)
-- Triggers AFTER INSERT/UPDATE/DELETE sur les tables métier → audit_log
-- Attribution : current_setting('app.modified_by', true) fixée au niveau
-- SESSION par larccommon/audit_context.py (set_config(..., false)).
-- ⚠ Ne JAMAIS utiliser SET LOCAL sous autocommit (no-op silencieux).
-- =============================================================

CREATE TABLE IF NOT EXISTS public.audit_log (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ts         TIMESTAMPTZ NOT NULL DEFAULT now(),
    app_name   TEXT,
    user_id    INTEGER,
    user_name  TEXT,
    source     TEXT NOT NULL DEFAULT 'local',   -- intranet | cloud | local | app | daemon(exclu)
    table_name TEXT NOT NULL,
    operation  TEXT NOT NULL,                   -- INSERT | UPDATE | DELETE | EVENT
    row_id     TEXT,                            -- TEXT : la PK peut être TEXT (larcauth_evaluation)
    field      TEXT,                            -- '*' pour INSERT/DELETE/EVENT
    old_value  TEXT,
    new_value  TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_log_ts   ON public.audit_log (ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON public.audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_tbl  ON public.audit_log (table_name, ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_row  ON public.audit_log (table_name, row_id);

-- Append-only : l'écriture est réservée aux triggers (SECURITY DEFINER)
REVOKE INSERT, UPDATE, DELETE ON public.audit_log FROM PUBLIC;
GRANT SELECT ON public.audit_log TO PUBLIC;

-- -------------------------------------------------------------
-- Fonction partagée d'audit
-- -------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.fn_audit_row()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    k     TEXT;
    uid   INTEGER;
    uname TEXT;
    src   TEXT;
    app   TEXT;
    pk    TEXT;
    rid   TEXT;
BEGIN
    -- Changements venus du daemon de sync : déjà audités à l'origine
    IF current_setting('app.sync_source', TRUE) = 'daemon' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    uid   := NULLIF(current_setting('app.modified_by', TRUE), '')::INTEGER;
    uname := NULLIF(current_setting('app.modified_by_name', TRUE), '');
    src   := COALESCE(NULLIF(current_setting('app.sync_source', TRUE), ''), 'local');
    app   := NULLIF(current_setting('application_name', TRUE), '');

    -- Clé primaire RÉELLE de la table (ex. larcauth_academicyear → s_id).
    -- L'ancien code supposait NEW.id partout et faisait échouer tout
    -- UPDATE réel sur les tables sans colonne « id ».
    SELECT a.attname INTO pk
    FROM pg_index i
    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
    WHERE i.indrelid = TG_RELID AND i.indisprimary
    ORDER BY a.attnum
    LIMIT 1;
    pk := COALESCE(pk, 'id');

    IF TG_OP = 'INSERT' THEN
        EXECUTE format('SELECT ($1).%I::text', pk) INTO rid USING NEW;
        INSERT INTO public.audit_log (app_name, user_id, user_name, source,
                                      table_name, operation, row_id, field, new_value)
        VALUES (app, uid, uname, src, TG_TABLE_NAME, 'INSERT',
                rid, '*', to_jsonb(NEW)::TEXT);
        RETURN NEW;

    ELSIF TG_OP = 'DELETE' THEN
        EXECUTE format('SELECT ($1).%I::text', pk) INTO rid USING OLD;
        INSERT INTO public.audit_log (app_name, user_id, user_name, source,
                                      table_name, operation, row_id, field, old_value)
        VALUES (app, uid, uname, src, TG_TABLE_NAME, 'DELETE',
                rid, '*', to_jsonb(OLD)::TEXT);
        RETURN OLD;

    ELSE
        -- UPDATE : une ligne par champ réellement modifié (colonnes internes exclues)
        FOR k IN
            SELECT key FROM jsonb_each(to_jsonb(NEW))
            WHERE to_jsonb(OLD) ? key
              AND to_jsonb(OLD) ->> key IS DISTINCT FROM to_jsonb(NEW) ->> key
              AND key NOT IN ('sync_version', 'sync_listeMAJ', 'synced_at', 'synced_by',
                              'sync_revision', 'last_modified_at', 'last_sync_at')
        LOOP
            EXECUTE format('SELECT ($1).%I::text', pk) INTO rid USING NEW;
            INSERT INTO public.audit_log (app_name, user_id, user_name, source,
                                          table_name, operation, row_id, field,
                                          old_value, new_value)
            VALUES (app, uid, uname, src, TG_TABLE_NAME, 'UPDATE', rid, k,
                    to_jsonb(OLD) ->> k, to_jsonb(NEW) ->> k);
        END LOOP;
        RETURN NEW;
    END IF;
END;
$$;

-- -------------------------------------------------------------
-- Application des triggers sur les tables métier
-- (to_regclass : table absente → notice, pas d'abort)
-- -------------------------------------------------------------
DO $$
DECLARE
    tables TEXT[] := ARRAY[
        -- Noyau élèves / personnel
        'larcauth_student', 'larcauth_parent', 'larcauth_aecuser', 'larcauth_teachadm',
        'larcauth_program',
        -- Évaluations et liens élèves
        'larcauth_evaluation',
        'larcauth_learner_has_termsubject', 'larcauth_learner_has_termothersubject',
        'larcauth_learner_has_subjectgroup', 'larcauth_learner_has_term',
        'larcauth_learnerpei_has_termsubjectpei', 'larcauth_learnerdp_has_termsubjectdp',
        -- Classes et programmes
        'larcauth_classroom', 'larcauth_classroom_termsubject',
        'larcauth_classroom_termothersubject', 'larcauth_classroom_has_timeperiod',
        'larcauth_termsubject_has_homework',
        -- Référentiels métier (configurés par l'admin)
        'larcauth_criteria_of_levelsubject', 'larcauth_level', 'larcauth_levelsubject',
        'larcauth_subjectgroup', 'larcauth_term', 'larcauth_academicyear', 'larcauth_agenda',
        -- Événements élèves
        'larcauth_student_has_dayevents', 'larcauth_student_has_events',
        'larcauth_student_has_termevents', 'larcauth_student_has_weekevents',
        'student_event',
        -- LarcCompta
        'compta_student_fee', 'compta_payment', 'compta_payment_document',
        'compta_fee_level', 'compta_payment_schedule', 'compta_parent_milestone',
        'compta_reminder'
    ];
    t TEXT;
BEGIN
    FOREACH t IN ARRAY tables
    LOOP
        IF to_regclass(format('public.%I', t)) IS NULL THEN
            RAISE NOTICE 'audit: table % absente — trigger ignoré', t;
            CONTINUE;
        END IF;
        EXECUTE format('DROP TRIGGER IF EXISTS trg_audit_%I ON public.%I', t, t);
        EXECUTE format(
            'CREATE TRIGGER trg_audit_%I AFTER INSERT OR UPDATE OR DELETE
             ON public.%I FOR EACH ROW EXECUTE FUNCTION public.fn_audit_row()',
            t, t);
    END LOOP;
END;
$$;

-- Interrupteur si une table devient trop chaude :
-- ALTER TABLE public.<table> DISABLE TRIGGER trg_audit_<table>;
