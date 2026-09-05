-- ============================================================
-- larcauth_config : Configuration centralisee (clef/valeur)
-- ============================================================
-- Table utilisee par LarcSuperviseur (preferences utilisateur :
-- theme, carte, langue) — main_window.py + dialogs/preferences.py
-- ============================================================

CREATE TABLE IF NOT EXISTS larcauth_config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    description TEXT,
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE larcauth_config IS
    'Configuration centralisee de l''application (chemins, defaults, feature flags)';

-- Seed valeurs par defaut
INSERT INTO larcauth_config (key, value, description) VALUES
    ('photos_dir', 'D:\projets\LarcSuperviseur\photos',
     'Repertoire des photos des eleves (PNG 500x500)'),
    ('photos_cache_dir', 'D:\projets\LarcSecretaire\photos\cache',
     'Cache local des photos telechargees depuis le cloud')
ON CONFLICT (key) DO NOTHING;
