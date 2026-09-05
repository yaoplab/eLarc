-- =============================================================
-- 01_larc_issue.sql — Registre central des issues de qualité (LarcForge, étape 1)
-- signature UNIQUE = dédoublonnage ; statut open/resolved/regressed
-- Exécuter : python -m larcforge init-db   (ou run_ddl.py [--cloud])
-- Style : CREATE TABLE IF NOT EXISTS + index + vue (pattern 01_error_log.sql)
-- =============================================================

CREATE TABLE IF NOT EXISTS public.larc_issue (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    signature      TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'open',
    occurrences    INTEGER NOT NULL DEFAULT 1,
    first_seen     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen      TIMESTAMPTZ NOT NULL DEFAULT now(),
    first_seen_run BIGINT,
    last_seen_run  BIGINT,
    source         TEXT NOT NULL,   -- 'linter:R|D|V|C|S|FS|DB|AUTH|COV|REACT' | 'pytest' | 'errorlog'
    app_name       TEXT NOT NULL,   -- repo (linters/tests) ou app_name (error_log)
    module         TEXT,            -- chemin relatif à la racine, séparateur '/'
    func           TEXT,            -- nom de test / fonction / règle
    line           INTEGER,
    level          TEXT NOT NULL DEFAULT 'ERROR',
    rule           TEXT,            -- R1, D1, C1..C13, V1..., nom de test
    message        TEXT NOT NULL,   -- message brut (1re occurrence)
    traceback      TEXT,            -- échantillon (errorlog uniquement)
    context        JSONB NOT NULL DEFAULT '{}'::jsonb,
    larc_version   TEXT,            -- version LarcCommon au moment du bug
    resolution_note TEXT,
    resolved_at    TIMESTAMPTZ,
    resolved_run   BIGINT,
    regressed_count    INTEGER NOT NULL DEFAULT 0,
    first_regressed_at TIMESTAMPTZ,
    CONSTRAINT ck_larc_issue_status CHECK (status IN ('open', 'resolved', 'regressed'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_larc_issue_signature ON public.larc_issue (signature);
CREATE INDEX IF NOT EXISTS idx_larc_issue_status  ON public.larc_issue (status, last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_larc_issue_app     ON public.larc_issue (app_name, status);
CREATE INDEX IF NOT EXISTS idx_larc_issue_module  ON public.larc_issue (app_name, module);
CREATE INDEX IF NOT EXISTS idx_larc_issue_run     ON public.larc_issue (last_seen_run);

-- Un enregistrement par invocation CLI (run/lints/tests/errorlog) — historique des audits
CREATE TABLE IF NOT EXISTS public.larc_run (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ,
    command      TEXT NOT NULL,    -- 'run' | 'lints' | 'tests' | 'errorlog'
    status       TEXT NOT NULL DEFAULT 'running',  -- running | ok | issues | error
    scope        JSONB NOT NULL DEFAULT '{}'::jsonb,
    nb_issues    INTEGER NOT NULL DEFAULT 0,
    nb_new       INTEGER NOT NULL DEFAULT 0,
    nb_regressed INTEGER NOT NULL DEFAULT 0,
    nb_resolved  INTEGER NOT NULL DEFAULT 0,
    nb_errors    INTEGER NOT NULL DEFAULT 0,
    python       TEXT,
    larc_version TEXT,
    root         TEXT
);

-- Snapshot des fichiers .py scannés PAR RUN (substitut git — aucun repo n'a de .git)
CREATE TABLE IF NOT EXISTS public.larc_run_module (
    run_id    BIGINT NOT NULL,
    app_name  TEXT NOT NULL,
    module    TEXT NOT NULL,       -- relatif à la racine, '/'
    mtime_ns  BIGINT,
    size      BIGINT,
    PRIMARY KEY (run_id, app_name, module)
);

-- Vue des issues : regressed/open d'abord, puis dernières vues
CREATE OR REPLACE VIEW public.v_larc_issues AS
SELECT id, signature, status, occurrences, first_seen, last_seen,
       source, app_name, module, func, line, level, rule, message,
       larc_version, resolution_note, resolved_at, regressed_count, first_regressed_at
FROM public.larc_issue
ORDER BY (status IN ('open', 'regressed')) DESC, last_seen DESC;
