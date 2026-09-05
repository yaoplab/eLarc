-- =============================================================
-- 01_error_log.sql — Enregistrement centralisé des erreurs (R1)
-- Tous les programmes LARC → error_log (via larccommon/error_reporting.py)
-- spool_id UNIQUE : rejeu idempotent du spool local (ON CONFLICT DO NOTHING)
-- Exécuter sur Intranet ET Cloud : python sql/run_ddl.py [--cloud]
-- =============================================================

CREATE TABLE IF NOT EXISTS public.error_log (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    app_name    TEXT NOT NULL,
    app_version TEXT,
    user_id     INTEGER,
    user_name   TEXT,
    role        TEXT,
    conn_mode   TEXT,
    level       TEXT NOT NULL DEFAULT 'ERROR',
    module      TEXT,
    func        TEXT,
    line        INTEGER,
    message     TEXT NOT NULL,
    traceback   TEXT,
    context     JSONB,
    spool_id    BIGINT UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_error_log_ts   ON public.error_log (ts DESC);
CREATE INDEX IF NOT EXISTS idx_error_log_app  ON public.error_log (app_name, ts DESC);
CREATE INDEX IF NOT EXISTS idx_error_log_user ON public.error_log (user_id);

-- Vue simple pour la consultation (LarcConfig panel_logs)
CREATE OR REPLACE VIEW public.v_errors AS
SELECT id, ts, app_name, app_version, user_id, user_name, role, conn_mode,
       level, module, func, line, message, traceback, context
FROM public.error_log
ORDER BY ts DESC;
