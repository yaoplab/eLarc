# AGENTS.md — Projets Larc (Racine)

Ce fichier est lu automatiquement par opencode au début de chaque session.
Contient tout le contexte pour travailler sur LarcCommon, LarcSuperviseur, LarcSecretaire, LarcHub.

Voir `LarcSuperviseur/AGENTS.md` pour le détail complet.

## TL;DR

- **PostgreSQL** local `127.0.0.1:5432` NewLarcDB (user:postgres, password:postgres)
- **Config** dans `LarcCommon/config.ini` (port 5432, Supabase 6543)
- **Thèmes** : `theme_manager.phi_theme` pour les widgets M3, `theme_manager.palette` pour le QSS
- **Icônes** : `from larccommon.icons import icon as md3_icon` — 33 icônes MD3
- **EventGenerator** : wizard séquentiel à 3 modes (Absence journée / Retard / Événements)
- **AGENTS.md complet** → `LarcSuperviseur/AGENTS.md`

## Commandes

```bash
cd C:\Projets
pip install -e LarcCommon          # si larccommon/phibuilder changent
set LARC_LANG=fr
python -m LarcSuperviseur          # Supervision
python -m LarcSecretaire           # Secrétariat
python -m LarcHub                  # Hub (supervision + secrétariat)
python -m LarcSuperviseur.tools.show_icons  # Aperçu icônes
```
