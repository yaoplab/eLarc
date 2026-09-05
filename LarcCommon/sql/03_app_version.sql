-- =============================================================
-- 03_app_version.sql — Registre des versions (R3 mise à jour douce)
-- Version distante publiée par app/channel ; comparée à la version
-- locale (D:\projets\VERSION, fallback config.ini [App] Version)
-- =============================================================

CREATE TABLE IF NOT EXISTS public.app_version (
    app_name     TEXT PRIMARY KEY,
    version      TEXT NOT NULL,
    channel      TEXT NOT NULL DEFAULT 'stable',
    notes        TEXT,
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by   TEXT
);

-- Seed : les 7 apps en 1.0 (ne touche pas aux versions déjà publiées)
INSERT INTO public.app_version (app_name, version, channel, notes, updated_by)
VALUES
    ('LarcSuperviseur', '1.0', 'stable', 'Version initiale', 'seed'),
    ('LarcSecretaire',  '1.0', 'stable', 'Version initiale', 'seed'),
    ('LarcHub',         '1.0', 'stable', 'Version initiale', 'seed'),
    ('LarcProf',        '1.0', 'stable', 'Version initiale', 'seed'),
    ('LarcConfig',      '1.0', 'stable', 'Version initiale', 'seed'),
    ('LarcRH',          '1.0', 'stable', 'Version initiale', 'seed'),
    ('LarcCompta',      '1.0', 'stable', 'Version initiale', 'seed')
ON CONFLICT (app_name) DO NOTHING;
