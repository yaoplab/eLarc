---
name: infra-review
description: Audit de l'infrastructure — base de données, synchronisation, graphe de connaissances
category: quality
trigger: audit infra, vérifie infra, check infra, revue infra, base de données, synchronisation, sync, graphify, graphe
---

# Infra Review — Audit Infrastructure Larc

Vérifier les connexions PostgreSQL, la synchronisation, et le graphe de connaissances.

## Procédure

1. Lancer les linters :
```bash
python D:/projets/scripts/lint_db_checker.py --json
python D:/projets/scripts/lint_auth_checker.py --json
python D:/projets/scripts/lint_file_size.py --stats
```

2. Tester les connexions :
```bash
python -c "from larccommon.database import db; print('INTRANET OK' if db.connect_intranet() else 'FAIL')"
```

3. Vérifier le graphe de connaissances :
```bash
graphify god-nodes --top 10 --graph graphify-out/graph.json
graphify query "Quelles sont les connexions principales entre les modules ?"
```

4. Tester la synchronisation (si LarcCloudSync) :
```bash
python -c "from thothcommon.sync import sync_manager; print(sync_manager.sync_table('larcauth_aecuser'))"
```

## Checklist Database
- [ ] [IntranetDatabase] et [SupabaseDatabase] dans config.ini
- [ ] db.connect_intranet() → True
- [ ] 0 import psycopg2 hors de database.py
- [ ] 0 psycopg2.connect() direct
- [ ] is_server_connected vérifié avant requête
- [ ] disconnect_all() à la fermeture

## Checklist Sync
- [ ] Connexion locale + cloud OK
- [ ] sync_version présent
- [ ] ON CONFLICT DO NOTHING sur INSERT
- [ ] sslmode=require sur cloud
- [ ] Mode dégradé si cloud inaccessible

## Checklist Graphify
- [ ] Graphe à jour : `graphify god-nodes --top 5`
- [ ] graphify-out/graph.json < 7 jours
- [ ] God nodes cohérents avec l'architecture
- [ ] Pas de fichiers critiques absents du graphe
- [ ] Régénération après changement structurel

## Skills de référence

- `database-operations` — connexions DB
- `sync` — synchronisation local↔cloud
- `auth-intranet` — auth PostgreSQL
- `graphify` — graphe de connaissances du codebase
