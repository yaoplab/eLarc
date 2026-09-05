---
name: audit-log
description: Journal d'audit PostgreSQL LARC — triggers fn_audit_row() → audit_log, qui a fait quoi et quand, contexte session app.modified_by
category: infrastructure
trigger: audit, journal, qui a fait quoi, audit_log, trigger, modified_by, traçabilité, traçabilite
---

# Audit Log — Qui a fait quoi, quand (R2)

Triggers PostgreSQL sur les tables métier → `audit_log` : **qui** (session), **quoi** (table/champ),
**quand** (ts). Tri par utilisateur / table / date. Côté serveur = capture tous les clients
(apps, daemon, LarcProf offline en poussée) sans instrumenter les chemins d'écriture.

## Attribution — piège `SET LOCAL` sous autocommit ⚠

- Toutes les connexions LARC sont `autocommit = True` → **`SET LOCAL` est un no-op silencieux**
  (chaque instruction = sa propre transaction implicite). Bug latent historique :
  `LarcProf/common/sync.py:413-418` et `LarcProf/common/database.py:175-181` (corrigé : `audit_context.attach`).
- **Toujours** `SELECT set_config('app.modified_by', %s, false)` — `false` = **niveau SESSION**.
- `larccommon/audit_context.py` : `refresh()` (re-lit la session, appelé au login), `attach(conn)`
  (set_config ×4 : `app.modified_by`, `app.modified_by_name`, `app.current_user_id`, `app.sync_source`),
  `current_user_id/name()`. Appelé par `database.py` à chaque `connect_intranet/cloud`.

## Fonction partagée — `fn_audit_row()`

| Opération | Écriture |
|---|---|
| INSERT / DELETE | 1 ligne `field = '*'` avec `to_jsonb(NEW/OLD)` complet |
| UPDATE | 1 ligne **par champ modifié** (`IS DISTINCT FROM`, ancienne → nouvelle valeur) |
| `app.sync_source = 'daemon'` | retourne **sans auditer** (les changements sync ont été audités à l'origine) |

Exclusions : colonnes internes `sync_version, sync_listeMAJ, synced_at, synced_by, sync_revision,
last_modified_at` ; tables de référence pures (gender, language, type_event, lieu, campus…) hors liste.
`row_id TEXT` (PK peut être TEXT — `larcauth_evaluation`). `current_setting(name, true)` → NULL si
absente (jamais d'exception).

## Append-only par privilèges

```sql
REVOKE INSERT, UPDATE, DELETE ON audit_log FROM PUBLIC;  -- INSERT réservé aux triggers (SECURITY DEFINER)
GRANT SELECT ON audit_log TO PUBLIC;
```
La chaîne de hash (design LarcProf à_faire §L) est **différée** — l'append-only par privilèges
suffit côté central ; schéma extensible (`ALTER TABLE ... ADD COLUMN prev_hash`).

## Tables auditées (LarcCommon/sql/02_audit_log.sql, DO-loop sur liste)

`larcauth_student, larcauth_aecuser, larcauth_evaluation, larcauth_learner_has_term{,othersubject,
subjectgroup}, larcauth_learnerpei_has_termsubjectpei, larcauth_learnerdp_has_termsubjectdp,
larcauth_classroom{,termsubject,termothersubject}, larcauth_criteria_of_levelsubject, larcauth_level,
larcauth_levelsubject, larcauth_subjectgroup, larcauth_term, larcauth_academicyear, larcauth_agenda,
larcauth_config, student_event` + LarcCompta : `compta_student_fee, compta_payment,
compta_payment_document, compta_fee_level, compta_payment_schedule, compta_parent_milestone, compta_reminder`

## Migration `audit_trail` → `audit_log`

`audit_trail` reste en archive (lecture seule). `LarcSecretaire/common/audit.py:12-33` bascule sur
`audit_log` (opération `EVENT`, source `'app'`) — les ~10 call sites métier (`login/logout/
create_student/update_student/add_event/...`) ne bougent pas. `LarcConfig get_logs()` lit `audit_log`.

## Checklist

- [ ] `set_config(..., false)` (SESSION) partout — **aucun `SET LOCAL`** sous autocommit
- [ ] `audit_context.attach(conn)` appelé dans les deux `connect_*` + `refresh()` aux logins
- [ ] UPDATE : champs inchangés ignorés, colonnes `sync_*` exclues
- [ ] `sync_source = 'daemon'` exclu
- [ ] `REVOKE INSERT/UPDATE/DELETE FROM PUBLIC` appliqué
- [ ] Index présents : `(ts DESC)`, `(user_id)`, `(table_name, ts DESC)`, `(table_name, row_id)`
- [ ] Charge maîtrisée (interrupteur `DISABLE TRIGGER` documenté si table chaude)

## Références

- `[[error-reporting]]` — R1 (même fixation de contexte), `[[sync]]` — sync/daemon exclus de l'audit
- `[[database-operations]]` — connexions ; `[[telemetry-review]]` — audit des 3 capacités
- Tests : `LarcCommon/tests/test_audit_context.py` (mock), `test_integration_pg.py` (PG réel, `LARC_PG_TEST=1`)
