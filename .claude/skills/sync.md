---
name: sync
description: Synchronisation PostgreSQL local ↔ Supabase Cloud — daemon LarcCloudSync + SyncManager LarcProf (shadow-table _ref, trimestre courant)
category: infrastructure
trigger: sync, synchronisation, Supabase, cloud, shadow-table, _ref, pull, push
---

# Sync — Local ↔ Cloud

Deux mécanismes distincts :

## LarcCloudSync (daemon)

```
PostgreSQL local (127.0.0.1:5432) ──(upsert)──→ Supabase Cloud (6543, PgBouncer)
PostgreSQL local ←──(pull)──── Supabase Cloud
```
Classification des tables par direction dans `LarcCloudSync/01_Architecture/`.

## LarcProf SyncManager (SQLite locale)

- Pattern **shadow-table `_ref`** : diff cellule par cellule entre SQLite locale et PostgreSQL
- **Trimestre courant uniquement** — trimestres passés figés en lecture seule
- Déclencheurs : création instance (mode 4), clic « Connecter », clic « Synchroniser », sortie avec enregistrement
- Pas de connexion automatique au démarrage — test de présence réseau seulement

## Vérification

- `lint_db_checker.py` ; `infra-review` (ON CONFLICT DO NOTHING, sslmode=require, mode dégradé).
