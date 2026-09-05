
---

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