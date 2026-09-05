-- Trigger générique : incrémente sync_version et ajoute l'entrée dans sync_listeMAJ
-- Exécuter sur Intranet ET Cloud (identique).

CREATE OR REPLACE FUNCTION track_sync_update()
RETURNS TRIGGER AS $$
DECLARE
    diff JSONB;
    entry JSONB;
    uid INT;
    src TEXT;
BEGIN
    -- Ne pas tracker si le trigger est appelé par le daemon lui-même
    IF current_setting('app.sync_source', TRUE) = 'daemon' THEN
        RETURN NEW;
    END IF;

    -- Calculer les colonnes modifiées
    SELECT jsonb_object_agg(k, v)
    INTO diff
    FROM (
        SELECT k, v
        FROM jsonb_each(to_jsonb(NEW)) n
        WHERE to_jsonb(OLD) ? k
          AND (to_jsonb(OLD) ->> k) IS DISTINCT FROM (to_jsonb(NEW) ->> k)
          AND k NOT IN ('sync_version', 'sync_listeMAJ')
    ) changed
    WHERE v IS NOT NULL;

    IF diff IS NULL OR diff = '{}'::jsonb THEN
        RETURN NEW;
    END IF;

    -- Déterminer l'utilisateur et la source
    BEGIN
        uid := current_setting('app.current_user_id')::int;
    EXCEPTION WHEN OTHERS THEN
        uid := 0;
    END;
    BEGIN
        src := current_setting('app.sync_source');
    EXCEPTION WHEN OTHERS THEN
        src := 'local';
    END;

    -- Incrémenter la version
    NEW.sync_version := COALESCE(NEW.sync_version, 0) + 1;

    -- Construire l'entrée de journal
    entry := jsonb_build_object(
        'v',     NEW.sync_version,
        'user',  uid,
        'at',    NOW(),
        'src',   src,
        'fields', diff
    );

    -- Ajouter à sync_listeMAJ (garder les 50 dernières entrées max)
    IF NEW.sync_listeMAJ IS NULL OR NEW.sync_listeMAJ = '[]'::jsonb THEN
        NEW.sync_listeMAJ := jsonb_build_array(entry);
    ELSE
        NEW.sync_listeMAJ := NEW.sync_listeMAJ || entry;
        IF jsonb_array_length(NEW.sync_listeMAJ) > 50 THEN
            NEW.sync_listeMAJ := (SELECT jsonb_agg(e) FROM (
                SELECT e FROM jsonb_array_elements(NEW.sync_listeMAJ) e
                ORDER BY (e ->> 'v')::int DESC
                LIMIT 50
            ) sub);
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- Application du trigger sur toutes les tables métier
DO $$
DECLARE
    tables TEXT[] := ARRAY[
        'larcauth_learnerdp_has_termsubjectdp',
        'larcauth_learnerpei_has_termsubjectpei',
        'larcauth_evaluation',
        'larcauth_learner_has_termsubject',
        'larcauth_learner_has_termothersubject',
        'larcauth_student_has_dayevents',
        'larcauth_termsubject_has_homework',
        'larcauth_aecuser',
        'larcauth_classroom_has_timeperiod',
        'larcauth_classroom_termothersubject',
        'larcauth_classroom_termsubject',
        'larcauth_edt_classe',
        'larcauth_learner_has_subjectgroup',
        'larcauth_learner_has_term',
        'larcauth_student',
        'larcauth_teachadm',
        'larcauth_academicyear',
        'larcauth_agenda',
        'larcauth_campus',
        'larcauth_classroom',
        'larcauth_concept',
        'larcauth_criteria_of_levelsubject',
        'larcauth_district',
        'larcauth_gender',
        'larcauth_globalcontext',
        'larcauth_language',
        'larcauth_level',
        'larcauth_levelsubject',
        'larcauth_lieu',
        'larcauth_natureparentutor',
        'larcauth_program',
        'larcauth_subjectgroup',
        'larcauth_term',
        'larcauth_timeperiod',
        'larcauth_type_event',
        'larcauth_unit'
    ];
    t TEXT;
BEGIN
    FOREACH t IN ARRAY tables
    LOOP
        EXECUTE format('
            DROP TRIGGER IF EXISTS trg_sync_%I ON public.%I
        ', t, t);
        EXECUTE format('
            CREATE TRIGGER trg_sync_%I
                BEFORE UPDATE ON public.%I
                FOR EACH ROW
                EXECUTE FUNCTION track_sync_update()
        ', t, t);
    END LOOP;
END $$;
