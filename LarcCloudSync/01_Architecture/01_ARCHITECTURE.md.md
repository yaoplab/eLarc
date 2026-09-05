---
tags: ["architecture", "larc-compat", "sync-flow", "multi-year"]
related: ["[[00_INDEX]]", "[[03_SYNC_IMPLEMENTATION]]"]
---

# 🏗️ Architecture LarcCloudSync

## 🆚 Larc vs LarcCloudSync
| Aspect | `Larc` (Standalone) | `LarcCloudSync` (Cloud-Enabled) |
|--------|---------------------|---------------------------------|
| Base | PostgreSQL 15 local | PostgreSQL 15 local + Supabase Cloud |
| Sync | Aucun | Agent Python → Edge Functions → Cloud |
| Compatibilité | N/A | 100% ascendante. `Larc` continue de fonctionner sans modification. |
| Offline | Natif | Natif + file de synchronisation intelligente |
| Multi-années | Manuelle | Schémas `year_XXXX` + policies `READ ONLY` automatisées |

## 🔁 Stratégie de Compatibilité Ascendante
1. **Schéma inchangé** : Tables Django conservées à l'identique.
2. **Ajouts sécurisés** : `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` → ignoré par `Larc`.
3. **Triggers non-bloquants** : `log_sync_change()` s'exécute en `AFTER`, ne modifie pas le flux transactionnel Django/Delphi.
4. **Requêtes identiques** : `SELECT *`, `JOIN`, `WHERE` fonctionnent comme avant. Les colonnes `sync_*` sont simplement ignorées par les apps existantes.
5. **Cloud optionnel** : Si l'agent Python n'est pas lancé, `LarcCloudSync` se comporte exactement comme `Larc`.

## 🌐 Flux de Données
[Larc Desktop/Delphi/Access] ←→ [PostgreSQL 15 Local] │ ├─ (Trigger AFTER) → [[sync_changelog]] │ ▼ [Agent Python Local] │ ├─ File SQLite/JSON (offline) │ ▼ [Supabase Edge Functions /sync] │ ▼ [Supabase Cloud DB (RLS actif)]


## 📂 Classification des Tables
| Type | Exemples (`ok.sql`) | Sens Sync | Règle Conflit |
|------|---------------------|-----------|---------------|
| **Config** | `larcauth_program`, `larcauth_level`, `larcauth_criteria_*` | 🔵 Local → Cloud | Local gagne. Ignore RLS (`service_role`). |
| **Opérationnel Critique** | `larcauth_learnerdp_has_termsubjectdp`, `larcauth_evaluation` | 🔁 Bidirectionnel | `sync_version` + `changed_at`. Flag conflit si modification croisée. |
| **Opérationnel Non-Critique** | `larcauth_agenda`, `larcauth_termsubject_has_homework` | 🔁 Bidirectionnel | Last-write-wins + historique. |
| **Archives** | Schémas `year_2024_2025` | 🔴 Lecture seule | RLS `FOR SELECT ONLY`. |

## 🔑 Modèle Auth & Rôles
- Table centrale : `larcauth_aecuser` (id, flags `type_teacher`, `type_student`, etc.)
- Profils 1:1 : `larcauth_teachadm`, `larcauth_student` (héritage via `_ptr_id`)
- Mapping sync : `current_setting('app.current_user_id')` → filtrage RLS par rôle
- Rôles DB : `anon`, `authenticated`, `service_role`, `larcuser` (droits alignés via script de nettoyage)

## 📅 Stratégie Multi-Années
- **Année active** : Schéma `public` ou `year_2025_2026` → écriture + sync active
- **Années passées** : Schémas dédiés → `READ ONLY`, accessibles via `search_path` dynamique ou API `/data?year=2024`
- **Bascule annuelle** : Script → copie schéma → activation RLS lecture seule → update `active_year`

## ⚙️ Contraintes Techniques
- PG 15 natif Windows (8 Go RAM → pas de Docker)
- `ok.sql` généré depuis PG 15.6 → 100% compatible
- Contraintes `DEFERRABLE INITIALLY DEFERRED` → préserver pour chargements batch
- Windows 10 LTSC 2021 → stable, léger, parfait pour dev isolé