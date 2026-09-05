---
tags: ["setup", "clone", "postgresql15", "rights-fix"]
related: ["[[00_INDEX]]", "[[04_Troubleshooting/04_ERREURS_FREQUENTES]]"]
---
# 🛠️ Clonage & Installation PostgreSQL 15

## 📥 Prérequis
- ✅ Windows 10 LTSC 2021
- ✅ PostgreSQL 15.x natif (pas Docker, RAM limitée)
- ✅ Fichier `ok.sql` exporté depuis prod (lecture seule)

## 🧪 Étapes de Restauration
```1. **Installer PG15** : [postgresql.org/download/windows](https://www.postgresql.org/download/windows/)
1. **Créer la base** :
   ``bash
   createdb -U postgres -h localhost -p 5432 ibo_sync_clone
   
   
2. Restaurer le dump
   Bash
   psql -U postgres -h localhost -p 5432 -d ibo_sync_clone -f "C:\chemin\vers\ok.sql"
   
3. Vérifier
   sql
   psql -U postgres -h localhost -p 5432 -d ibo_sync_clone -f "C:\chemin\vers\ok.sql" `   
```

## 🧹 Nettoyage des Droits (OBLIGATOIRE)
```
SQL

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN CREATE ROLE service_role NOLOGIN; END IF;
END $$;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated, larcuser;
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role, larcuser;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role, larcuser;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role, larcuser;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO service_role, larcuser;
```

## 🔍 Vérification Post-Correction
```
-- 1. Tables critiques présentes ?
SELECT 'aecuser' as tbl, count(*) FROM public.larcauth_aecuser
UNION ALL SELECT 'student', count(*) FROM public.larcauth_student;

-- 2. Séquences synchronisées ?
SELECT setval(pg_get_serial_sequence('larcauth_aecuser','id'), max(id)) FROM larcauth_aecuser;

-- 3. Test jointure IBO
SELECT count(*) FROM larcauth_classroom_termsubject cts
JOIN larcauth_teachadm t ON cts.fk_teacher_id = t.aecuser_ptr_id;

```

✅ **Statut** : ⬜ Prêt pour [[03_SYNC_IMPLEMENTATION]]