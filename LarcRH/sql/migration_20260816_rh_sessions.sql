-- Présence RH (2026-08-16) : qui est connecté en ce moment.
-- Heartbeat : l'app met à jour last_seen toutes les 60 s tant qu'elle est
-- authentifiée ; logout/timeout d'inactivité → DELETE.
-- « En ligne » = last_seen < 10 min (même fenêtre que l'IdleGuard).
CREATE TABLE IF NOT EXISTS rh_user_sessions (
    user_id      INTEGER PRIMARY KEY,
    app          VARCHAR(20),
    logged_in_at TIMESTAMP DEFAULT NOW(),
    last_seen    TIMESTAMP DEFAULT NOW()
);
