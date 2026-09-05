---
name: error-reporting
description: Enregistrement centralisé des erreurs LARC — ErrorReporter, spool SQLite, excepthook, capture non-bloquante vers error_log PostgreSQL
category: infrastructure
trigger: erreur, erreurs, log d'erreur, error_log, excepthook, reporter, spool, télémétrie, crash, traceback
---

# Error Reporting — Erreurs centralisées (R1)

Tous les messages d'erreur des apps LARC → PostgreSQL `error_log`, **sans nuire à la charge**
(asynchrone), **sans jamais lever** (le reporter est transparent), **tout est prévu** (dégradation complète).

## Transport — `larccommon/error_reporting.py`

- Thread writer **unique** + `queue.Queue` bornée ; `report()` = `put_nowait` uniquement (< 1 ms, aucun I/O sur le thread appelant, jamais de raise)
- Flush par lot : **5 s OU 100 événements**, une seule `INSERT ... VALUES (...),(...)`
- Connexion PG **dédiée au reporter** (jamais `db.server_conn` partagé — psycopg2 non thread-safe), `application_name = "<app>_reporter"`
- Cœur **sans Qt** (testable sans QApplication) ; le bridge Qt vit dans `bootstrap.py`

## Chaîne de dégradation (toujours descendre, jamais bloquer)

```
PG injoignable ─→ spool SQLite (<app>/.error_spool/*.db) ─→ JSONL (error_spool.jsonl) ─→ compteur dropped
                                                   ↑ replay auto au retour PG (idempotent : spool_id UNIQUE, ON CONFLICT DO NOTHING)
```
- Backoff ×2 plafonné à 300 s sur PG ; le spool (local) est tenté même pendant le backoff
- Spool plein (`SpoolMaxRows`) → prune ¼ le plus ancien ; pertes comptées + ligne synthétique au prochain flush
- `stop()` : flush borné 2 s (atexit + `aboutToQuit`) ; démarrage hors-ligne = aucun échec (spool seul chemin actif)

## Points de capture (tous branchés, transparents)

| Point | Fichier | Comportement |
|---|---|---|
| `sys.excepthook` + `threading.excepthook` | `larccommon/bootstrap.py` | report puis `traceback.print_exception` stderr — jamais de raise |
| `qInstallMessageHandler` | `bootstrap.py` | Critical/Fatal → report ; Warning/Info → fichier plat ; **Fatal → re-call ancien handler** (ne jamais avaler un crash fatal) |
| `@safe_slot` (325 sites) | `larccommon/safe_slot.py` (except :59-61) | conserve le log fichier + `reporter.report_exception(e, context={"slot_label": label})` |
| `log(msg, level="ERROR")` / `log_error(msg, exc)` | `larccommon/logger.py` | rétro-compatible (signature `log(msg)` inchangée) ; ERROR/CRITICAL → report fire-and-forget |

**Rotation** dans `log()` : fichier plat > 5 Mo → `.1/.2/.3` (corrige `elarc.log` 92 Mo sans rien changer côté app).

## Schéma — `error_log` (LarcCommon/sql/01_error_log.sql)

`id BIGINT IDENTITY PK, ts TIMESTAMPTZ, app_name, app_version, user_id, user_name, role,
conn_mode, level, module, func, line, message, traceback, context JSONB, spool_id BIGINT UNIQUE`
+ index `(ts DESC)`, `(app_name, ts DESC)`, `(user_id)`. **`spool_id UNIQUE` = rejeu idempotent.**

Contexte auto attaché par `report()` : session (user_id, full_name, role, conn_mode, term_id —
getattr avec défauts, jamais de crash), version (`D:\projets\VERSION`, fallback config.ini [App]).

## Config (`config.ini` [ErrorReporting])

`Enabled=true, SpoolDir=, FlushIntervalSec=5, FlushBatchSize=100, QueueMax=1000, SpoolMaxRows=50000, RetryBackoffSec=10, MinLevel=ERROR`

## Checklist

- [ ] `report()` ne fait QUE `put_nowait` — aucun I/O, aucun raise
- [ ] Idempotence spool : `spool_id` présent dans l'INSERT, `ON CONFLICT DO NOTHING`, DELETE après succès
- [ ] Chaîne de dégradation complète testée (PG down → spool → JSONL → dropped)
- [ ] `init_app('NomApp')` appelé dans les 7 main.py avant QApplication
- [ ] Rotation fichier plat active (> 5 Mo → .1/.2/.3)
- [ ] `stop()` via atexit + aboutToQuit, flush ≤ 2 s
- [ ] Aucune donnée sensible en clair dans les tracebacks au-delà du nécessaire

## Références

- `[[sync]]` — modèle offline (outbox locale), `[[audit-log]]` — R2 (même transport de contexte)
- `[[soft-update]]` — R3 (journalise ses résultats via error_log)
- `[[database-operations]]` — connexions DB ; `[[telemetry-review]]` — audit des 3 capacités
- Tests : `LarcCommon/tests/test_error_reporting.py`, `test_error_spool.py` (mock PG, Phase 1)
