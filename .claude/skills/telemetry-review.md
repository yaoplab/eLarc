---
name: telemetry-review
description: Audit des 3 capacités télémétrie LARC — erreurs centralisées (R1), journal d'audit (R2), mise à jour douce (R3)
category: quality
trigger: audit télémétrie, audit erreurs, audit error_log, audit audit_log, audit mise à jour, revue télémetry, revue telemetry, check erreurs
---

# Telemetry Review — Audit R1 + R2 + R3

Vérifier l'enregistrement centralisé des erreurs, le journal d'audit et la mise à jour douce.

## Procédure

1. Lancer les linters :
```bash
python D:/projets/scripts/lint_safe_slot.py
python D:/projets/scripts/lint_file_size.py --stats
python D:/projets/scripts/lint_db_checker.py --json
python D:/projets/scripts/lint_qss_hardcoding.py
```

2. Vérifier le schéma déployé :
```bash
python -c "from larccommon.database import db; db.connect_intranet(); c=db.server_conn.cursor(); \
c.execute('SELECT count(*) FROM error_log'); print('error_log', c.fetchone()[0]); \
c.execute('SELECT count(*) FROM audit_log'); print('audit_log', c.fetchone()[0]); \
c.execute('SELECT count(*) FROM app_version'); print('app_version', c.fetchone()[0])"
```

3. Tester le reporter en réel :
```bash
python -c "from larccommon.error_reporting import get_reporter; r=get_reporter(); \
r and r.report('ERROR', 'test telemetry-review', context={'probe': True})"
```

## Checklist R1 — Erreurs centralisées
- [ ] `report()` = `put_nowait` uniquement — aucun I/O, aucun raise sur le thread appelant
- [ ] Chaîne de dégradation complète : PG → spool SQLite → JSONL → compteur dropped
- [ ] Rejeu spool idempotent (`spool_id UNIQUE` + `ON CONFLICT DO NOTHING`)
- [ ] Flush par lot actif (5 s OU 100 événements), une seule INSERT multi-VALUES
- [ ] Connexion PG dédiée au reporter (pas de `db.server_conn` partagé entre threads)
- [ ] `sys.excepthook` + `threading.excepthook` installés par bootstrap
- [ ] `qInstallMessageHandler` : Fatal re-call l'ancien handler (jamais d'abort avalé)
- [ ] `@safe_slot` reporte (contexte `slot_label`), `log_error` alias fonctionnel
- [ ] Rotation fichier plat > 5 Mo (`.1/.2/.3`)
- [ ] `init_app` présent dans les 7 main.py, avant QApplication
- [ ] `stop()` via atexit + aboutToQuit, flush ≤ 2 s
- [ ] Tests Phase 1 (mock) verts : `pytest LarcCommon/tests/test_error_reporting.py test_error_spool.py -v`

## Checklist R2 — Journal d'audit
- [ ] **Aucun `SET LOCAL`** sous autocommit (no-op silencieux) — `set_config(..., false)` partout
- [ ] `audit_context.attach(conn)` dans `connect_intranet` ET `connect_cloud`
- [ ] `refresh()` appelé aux points de login (LarcSecretaire, LarcProf)
- [ ] UPDATE : 1 ligne par champ modifié, champs inchangés ignorés, colonnes `sync_*` exclues
- [ ] `sync_source = 'daemon'` → aucune ligne d'audit
- [ ] INSERT/DELETE → `field = '*'` avec JSON complet
- [ ] `REVOKE INSERT, UPDATE, DELETE ON audit_log FROM PUBLIC` appliqué
- [ ] Index : `(ts DESC)`, `(user_id)`, `(table_name, ts DESC)`, `(table_name, row_id)`
- [ ] `row_id TEXT` (PK TEXT possible — `larcauth_evaluation`)
- [ ] `audit_trail` intact en archive ; `LarcSecretaire/common/audit.py` → `audit_log` (EVENT)
- [ ] Test intégration (si `LARC_PG_TEST=1`) : UPDATE avec `set_config('app.modified_by')` → lignes attendues

## Checklist R3 — Mise à jour douce
- [ ] `check()` ne lève jamais (offline → None), channel filtré
- [ ] `--ff-only` partout ; retry ×3 ; worktree sale → refus propre
- [ ] Verrous `runtime/locks/<app>.pid` créés/supprimés (init_app/atexit)
- [ ] Mode silencieux : update au quit, aucun dialogue
- [ ] Mode informé : dialogue seulement si aucun modal ouvert
- [ ] Résultat (succès ET échec) journalisé dans `error_log`
- [ ] `pending_update.json` persistant → re-tentative au prochain démarrage
- [ ] Relance avec argv d'origine préservé

## Skills de référence

- `error-reporting` — R1, `audit-log` — R2, `soft-update` — R3
- `sync` — sync/daemon exclus de l'audit ; `database-operations` — connexions DB
