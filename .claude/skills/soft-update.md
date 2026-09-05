---
name: soft-update
description: Mise à jour douce des apps LARC — registre app_version, UpdateManager, git pull contrôlé, modes silencieux/informé
category: infrastructure
trigger: mise à jour, mise a jour, update, app_version, UpdateManager, pull, redémarrage, version
---

# Soft Update — Mise à jour douce (R3)

Mettre à jour les apps LARC en **mode silencieux** ou **en informant l'utilisateur** — sans casser
la session, sans verrou de fichiers Windows, tout est journalisé via R1.

## Registre de versions

| Source | Rôle |
|---|---|
| `D:\projets\VERSION` (racine monorepo, versionné git) | version **locale** — arrive avec le pull, aucun fichier local à réécrire |
| Table DB `app_version(app_name PK, version, channel, notes, published_at, updated_by)` | version **distante** (le hub existant, pas d'infra web) |
| `config.ini [App] Version` | fallback de la version locale |

Comparaison par channel (`[Update] Channel`, ex. `stable`). `bootstrap.current_app_version()` lit
VERSION puis config.ini. `D:\projets` est **un seul dépôt git** → `git pull` à la racine = mise à
jour atomique de tout (LarcCommon inclus).

## Flux

```
init_app → UpdateChecker (QTimer CheckIntervalMin)
  check() → SELECT app_version (offline → None)
  silencieux : arm_update_on_quit → closeEvent/aboutToQuit → updater au quit, rien montré
  informé   : UpdateDialog (timer 2 s, seulement si aucun modal → « app au repos ») → Installer / Plus tard
apply() → runtime/pending_update.json + QProcess.startDetached(scripts/update_app.py)
  update_app.py : attend extinction PID parent → vérifie verrous runtime/locks/<app>.pid
                  → git fetch + pull --ff-only (retry ×3) → résultat dans error_log
                  → relance `python <main>` avec argv d'origine (state JSON)
```

## Sûreté Windows (verrous de fichiers) ⚠

DLL PySide6/psycopg2 chargées + `elarc.db` ouvert **bloquent le remplacement des fichiers** :

- Registre de verrous `LarcCommon/runtime/locks/<app>.pid` — créé par `init_app`, supprimé à `atexit`
- L'updater **refuse de puller** tant qu'un verrou existe (attente bornée, puis abandon propre)
- Échec → `runtime/pending_update.json` persistant → nouvelle tentative au prochain démarrage
- **Toujours `--ff-only`** (jamais de merge) ; worktree sale → refus propre, journalisé `error_log`

## Checklist

- [ ] `check()` ne lève jamais (offline → None)
- [ ] `--ff-only` partout ; retry ×3 avec attente
- [ ] Verrous `runtime/locks/` créés/supprimés proprement (init_app/atexit)
- [ ] Mode silencieux : aucun dialogue, update au quit, session préservée
- [ ] Mode informé : dialogue seulement si app au repos (aucun modal ouvert)
- [ ] Résultat de l'update journalisé dans `error_log` (succès ET échec)
- [ ] `pending_update.json` relance la tentative au démarrage suivant
- [ ] Relance avec argv d'origine (paramètres `--mode4` LarcProf conservés)

## Références

- `[[error-reporting]]` — journalisation des résultats (R1), `[[audit-log]]` — R2
- `[[sync]]` — le pull peut impacter les shadow-tables `_ref` (re-sync après update)
- `[[telemetry-review]]` — audit des 3 capacités
- Tests : `LarcCommon/tests/test_update_manager.py` (compare versions, channel, offline → None) ;
  vérification manuelle sur branche locale (pull simulé)
