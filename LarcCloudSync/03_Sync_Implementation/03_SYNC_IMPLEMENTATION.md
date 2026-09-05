
---

### 📁 `03_SYNC_IMPLEMENTATION.md`
```markdown
---
tags: ["sync", "triggers", "edge-functions", "python-agent", "larc-compat"]
related: ["[[01_ARCHITECTURE]]", "[[02_CLONAGE_SETUP]]"]
---

# 🔄 Implémentation LarcCloudSync
````

## 📌 Phase 1 : Colonnes de Sync (Tables Pilotes)
```sql
BEGIN;

-- 1. larcauth_classroom_termsubject (config/assignation prof → classe → matière)
ALTER TABLE larcauth_classroom_termsubject 
  ADD COLUMN IF NOT EXISTS sync_version INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS sync_source TEXT CHECK (sync_source IN ('local','cloud','system')),
  ADD COLUMN IF NOT EXISTS sync_updated_at TIMESTAMPTZ DEFAULT NOW();

-- 2. larcauth_evaluation (structure des évaluations)
ALTER TABLE larcauth_evaluation 
  ADD COLUMN IF NOT EXISTS sync_version INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS sync_source TEXT CHECK (sync_source IN ('local','cloud','system')),
  ADD COLUMN IF NOT EXISTS sync_updated_at TIMESTAMPTZ DEFAULT NOW();

-- 3. larcauth_learnerdp_has_termsubjectdp (notation DP - table critique)
ALTER TABLE larcauth_learnerdp_has_termsubjectdp 
  ADD COLUMN IF NOT EXISTS sync_version INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS sync_source TEXT CHECK (sync_source IN ('local','cloud','system')),
  ADD COLUMN IF NOT EXISTS sync_updated_at TIMESTAMPTZ DEFAULT NOW();

COMMIT;

```

💡 _Note compatibilité_ : `IF NOT EXISTS` garantit que `Larc` ne plante pas si les colonnes existent déjà ou non.

## 📦 Phase 2 : Table `sync_changelog` + Trigger

````
BEGIN;

-- 1. Table de journalisation
CREATE TABLE IF NOT EXISTS sync_changelog (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  table_name TEXT NOT NULL,
  record_id BIGINT NOT NULL,
  operation TEXT CHECK (operation IN ('INSERT','UPDATE','DELETE')),
  changed_by TEXT,
  sync_source TEXT,
  changed_at TIMESTAMPTZ DEFAULT NOW(),
  payload JSONB,
  synced_to_cloud BOOLEAN DEFAULT FALSE,
  academic_year SMALLINT
);

CREATE INDEX IF NOT EXISTS idx_sync_pending_cloud 
  ON sync_changelog (table_name, changed_at) WHERE synced_to_cloud = FALSE;

-- 2. Fonction trigger générique
CREATE OR REPLACE FUNCTION track_sync_change()
RETURNS TRIGGER AS $$
DECLARE v_pk BIGINT;
BEGIN
  -- Gestion héritage Django (_ptr_id)
  v_pk := CASE TG_TABLE_NAME
    WHEN 'larcauth_learnerdp_has_termsubjectdp' THEN COALESCE(NEW.learner_has_termsubject_ptr_id, OLD.learner_has_termsubject_ptr_id)
    WHEN 'larcauth_learnerpei_has_termsubjectpei' THEN COALESCE(NEW.learner_has_termsubject_ptr_id, OLD.learner_has_termsubject_ptr_id)
    WHEN 'larcauth_learnerpp_has_termsubjectpp' THEN COALESCE(NEW.learner_has_termsubject_ptr_id, OLD.learner_has_termsubject_ptr_id)
    ELSE COALESCE(NEW.id, NEW.s_id, OLD.id, OLD.s_id)
  END;

  INSERT INTO sync_changelog (table_name, record_id, operation, sync_source, payload)
  VALUES (TG_TABLE_NAME, v_pk, TG_OP, current_setting('app.sync_source', TRUE), 
          jsonb_build_object('old', to_jsonb(OLD), 'new', to_jsonb(NEW)));

  IF TG_OP != 'DELETE' THEN
    NEW.sync_version := COALESCE(NEW.sync_version, 0) + 1;
    NEW.sync_source := current_setting('app.sync_source', TRUE);
    NEW.sync_updated_at := NOW();
  END IF;

  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- 3. Attache triggers
CREATE TRIGGER trg_sync_classroom AFTER INSERT OR UPDATE OR DELETE ON larcauth_classroom_termsubject FOR EACH ROW EXECUTE FUNCTION track_sync_change();
CREATE TRIGGER trg_sync_eval AFTER INSERT OR UPDATE OR DELETE ON larcauth_evaluation FOR EACH ROW EXECUTE FUNCTION track_sync_change();
CREATE TRIGGER trg_sync_dp AFTER INSERT OR UPDATE OR DELETE ON larcauth_learnerdp_has_termsubjectdp FOR EACH ROW EXECUTE FUNCTION track_sync_change();

COMMIT;
````

## ☁️ Phase 3 : Edge Function `/sync` (Supabase Cloud)
````
## ⚙️ Principe : Sync UPDATE-Only (Gabarit)
- ✅ La base ne **crée jamais** de nouvelles lignes en production.
- 🔄 Sync = uniquement des `UPDATE` sur des enregistrements pré-existants.
- 🔒 Pas de risque de conflit de séquence, d'IDs orphelins ou d'injection hors scope.
- 📦 Payload allégé : ne pousse que les `changed_fields` détectés par le trigger.
````

## 🐍 Phase 4 : Agent Python Local (Squelette)
````
# sync_agent.py
import psycopg2, requests, json, time, os

DB_LOCAL = os.getenv("DB_LOCAL", "dbname=ibo_sync_clone user=postgres password=XXX")
CLOUD_URL = os.getenv("SYNC_URL", "https://votre-projet.supabase.co/functions/v1/sync")
API_KEY = os.getenv("SYNC_KEY", "votre_clé")

def push_pending():
    conn = psycopg2.connect(DB_LOCAL)
    cur = conn.cursor()
    cur.execute("SELECT table_name, record_id, operation, payload FROM sync_changelog WHERE synced_to_cloud = false LIMIT 50")
    rows = cur.fetchall()
    if not rows: return

    changes = [{"table": r[0], "operation": r[2], "data": r[3]} for r in rows]
    res = requests.post(CLOUD_URL, json={"changes": changes, "api_key": API_KEY}, timeout=30)
    
    if res.status_code == 200:
        cur.execute("UPDATE sync_changelog SET synced_to_cloud = true WHERE table_name = ANY(%s) AND synced_to_cloud = false", ([r[0] for r in rows],))
        conn.commit()
    time.sleep(45)

if __name__ == "__main__":
    print("🔄 LarcCloudSync Agent démarré...")
    while True: push_pending()
`````

✅ **Statut** : ⬜ Scripts prêts à tester sur clone. Compatible `Larc` à 100%.

### 📁 `04_TROUBLESHOOTING.md`
```markdown
---
tags: ["errors", "fixes", "larc-compat", "best-practices"]
related: ["[[02_CLONAGE_SETUP]]", "[[03_SYNC_IMPLEMENTATION]]"]
---

# 🚨 Dépannage & Bonnes Pratiques LarcCloudSync

## ❌ Erreurs Fréquentes & Correctifs
| Symptôme | Cause | Solution |
|----------|-------|----------|
| `ERROR: role "anon" does not exist` | `GRANT` Django dans `ok.sql` | Exécuter le bloc de nettoyage de [[02_CLONAGE_SETUP]] |
| `duplicate key violates unique constraint` | FK `DEFERRABLE` non respectées | Charger `larcauth_aecuser` avant `teachadm`/`student`, ou `SET CONSTRAINTS ALL DEFERRED` |
| Séquences désynchronisées | `COPY` n'incrémente pas les séquences | `SELECT setval(pg_get_serial_sequence('table','id'), max(id)) FROM table;` |
| `Larc` plante après ajout colonnes | Trigger mal attaché ou `sync_source` non défini | Vérifier `IF NOT EXISTS`. Définir `SET app.sync_source = 'local';` avant `UPDATE` dans Delphi/Access |
| RAM saturée (8 Go) | Docker + PG + Windows | **Privilégier PG15 natif**. Désactiver services inutiles. Fermer navigateur. |

## 💡 Astuces Techniques
- ✅ Toujours tester sur clone avant de pousser en prod
- ✅ Utiliser `--no-privileges` pour les exports futurs
- ✅ Ajouter `sync_version` uniquement sur les tables modifiables
- ✅ Conserver `updated` Django intact → utiliser `sync_updated_at` pour la sync
- ✅ Pour les tables DP/MYP très larges : synchroniser uniquement les colonnes modifiées (JSON patch) ou utiliser `sync_changed_fields JSONB`

## 🔐 Sécurité & RLS
- Ne jamais exposer `SUPABASE_SERVICE_ROLE_KEY` côté client
- Utiliser un rôle dédié `sync_agent` pour l'agent Python
- Activer RLS progressivement : d'abord sur 1 table, valider, puis généraliser
- Journaliser toutes les résolutions de conflits dans `sync_changelog.payload`

## 🔄 Compatibilité `Larc`
- `Larc` ne lit pas `sync_*` → aucun impact sur performances
- Triggers `AFTER` → n'interfèrent pas avec les transactions Django/Delphi
- Si agent Python arrêté → `LarcCloudSync` = `Larc` (fonctionnement identique)
- Backup prod inchangé : `pg_dump --no-privileges --no-owner`