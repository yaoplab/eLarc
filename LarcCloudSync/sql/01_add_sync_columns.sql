-- Ajout des colonnes sync_listeMAJ sur toutes les tables métier
-- Exécuter sur Intranet EN PREMIER, puis sur Cloud.

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
            ALTER TABLE public.%I
                ADD COLUMN IF NOT EXISTS sync_version INT DEFAULT 0,
                ADD COLUMN IF NOT EXISTS sync_listeMAJ JSONB DEFAULT ''[]''::jsonb
        ', t);
    END LOOP;
END $$;
