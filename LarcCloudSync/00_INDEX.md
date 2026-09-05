---
tags: ["project/ibo-sync", "status/active", "type/index"]
created: {{date}}
updated: {{date}}
---

# 🔄 Système de Notation IBO - Documentation Sync

> **Objectif** : Synchronisation offline-first entre base locale PostgreSQL 15 et cloud Supabase, avec isolation des années scolaires.

## 🧭 Navigation
- [[01_Architecture/01_ARCHITECTURE_GLOBALE]] → Conception, flux, stratégie multi-années
- [[02_Clone_Setup/02_CLONAGE_POSTGRES15]] → Installation, restauration, nettoyage droits
- [[03_SYNC_IMPLEMENTATION]] → Colonnes sync, triggers, Edge Functions, agent Python
- [[04_Troubleshooting/04_ERREURS_FREQUENTES]] → Correctifs, bonnes pratiques
- [[05_Journal/05_JOURNAL_PROJET]] → Historique, décisions, prochaines étapes

## 📊 État d'Avancement
| Phase                  | Statut     | Livrable                                        |
| ---------------------- | ---------- | ----------------------------------------------- |
| 🔹 0. Clonage & PG15   | ⬜ En cours | Base locale propre, droits alignés              |
| 🔹 1. Métadonnées Sync | ⬜ À faire  | `sync_version`, `sync_source`, `sync_changelog` |
| 🔹 2. Edge Functions   | ⬜ À faire  | `/sync-config` + `/sync`                        |
| 🔹 3. Agent Python     | ⬜ À faire  | File offline → push cloud                       |
| 🔹 4. UI & RLS         | ⬜ À faire  | Reflex/Delphi offline, policies                 |
| 🔹 5. Validation       | ⬜ À faire  | Tests offline, rollback, docs                   |

## 🛡️ Règles d'Or
- ⛔ **Jamais modifier la production** pendant les tests
- 🔄 Toujours travailler sur le **clone local**
- 📦 Utiliser `pg_dump --no-privileges --no-owner` pour les exports
- 📅 Isoler les années via **schémas `year_YYYY_ZZ`** (lecture seule archives)
- 📝 Tout documenter ici ou dans [[05_Journal/05_JOURNAL_PROJET]]