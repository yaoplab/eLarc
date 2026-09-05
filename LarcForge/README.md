# LarcForge — Poste de contrôle unique

Centralise l'audit du monorepo : ~10 linters, pytest (4 repos) et le registre
d'erreurs `error_log` — avec un **registre de problèmes dédoublonné**
(`larc_issue`) et la **détection de régressions** (open → resolved → regressed).

> Contexte : tous les outils pointaient vers `D:\projets` (supprimé) alors que
> le monorepo vit dans `F:\projets` — ils ne scannaient rien et répondaient
> « 0 problème ». LarcForge dérive la racine du package, jamais de chemin en dur.

## Installation

```bash
pip install -e F:\projets\LarcForge
```

Dépendances : `psycopg2-binary` (ou `psycopg[binary]`), `pytest` (collecte).

## Commandes

```bash
python -m larcforge init-db [--cloud]   # crée larc_issue / larc_run / larc_run_module + vue
python -m larcforge lints [--projects A,B] [--linters R,D,V,C,S,FS,DB,AUTH,COV,REACT|all]
python -m larcforge tests [--projects ...] [--include-integration]
python -m larcforge errorlog [--since 24] [--level ERROR,WARNING] [--limit 500]
python -m larcforge run                  # lints → tests → errorlog (1 seul larc_run)
python -m larcforge status [--app A] [--open] [--csv] [--json]
```

Flags globaux (avant OU après la sous-commande) :
`--root R`, `--no-db` (console pure, sans PostgreSQL), `--timeout S`, `--json`.

### Codes de sortie

| Code | Sens |
|---|---|
| 0 | run propre |
| 1 | issues open/regressed détectées |
| 2 | usage (commande inconnue, flag invalide) |
| 3 | erreur technique (collecteur crash, sortie illisible) |
| 4 | base de données injoignable |

## Le registre `larc_issue`

Chaque problème a une **empreinte** (sha256 de
`source|app|module|func|message`, ligne exclue — un décalage de ligne n'est pas
un nouveau bug). Même problème 50× = 1 fiche avec compteur `occurrences`.

- **Création** : première détection → `open`.
- **Réapparition** : un bug `resolved` redétecté → `regressed`, `regressed_count+1`.
- **Résolution automatique** : signatures vues au run précédent *valide*
  (même commande + même scope, sinon pas de faux « résolus ») et absentes du
  run courant → `resolved` avec note « Plus détectée au run #N ».

### Avertissements de conflit (substitut git)

Aucun repo n'a de `.git` : chaque run enregistre l'état des fichiers .py
scannés (`larc_run_module` : mtime_ns + taille). `status` liste les modules
modifiés depuis le dernier run, et alerte si une issue open/regressed concerne
un module modifié depuis sa dernière détection — le signal du bug fantôme.

## Sortie `--no-db`

`run --no-db` collecte sans écrire : candidats en console (ou `--json`),
aucune résolution possible (l'historique se construit en base).

## Tests

```bash
python -m pytest F:\projets\LarcForge\tests -v   # 54 tests, sans PostgreSQL
```

`tests/conftest.py` fournit `FakeConn`/`FakeCursor` (plans de réponses) — le
SQL n'est pas exécuté, la logique de transition est testée par branchement.

## Interface graphique (IHM)

```bash
pip install "larcforge[gui]"   # ajoute PySide6
python -m larcforge ui         # fenêtre de contrôle (5 rubriques)
```

- **Accueil** : tableau de bord (KPIs, alertes, derniers runs).
- **Vérifications** : tout se règle en cases à cocher / menus (projets,
  linters, tests, fenêtre 24 h, niveaux) ; « Tout vérifier » pose le scope
  canonique du CLI → résolution automatique active (bandeau de sécurité).
- **Registre des issues** : fiches filtrables (statut, app, source,
  recherche) + détail + « Résoudre avec une note » / « Réouvrir ».
- **Configuration** : personnalisation école — nom, thème, connexions DB
  multiples (testées avant activation), profils de vérification.
  Persistance `ui_config.json` (surchargeable `LARCFORGE_UI_CONFIG`).
- **Aide** : explications pas-à-pas + guide néophyte
  (`docs/GUIDE_DEBUTANT.md`).

Robustesse : PostgreSQL down → carte « Base de données indisponible » +
Réessayer partout ; fermeture pendant un run → confirmation (run marqué
`error`). Pas de login : poste de contrôle local.

## Notes

- DDL : `sql/01_larc_issue.sql` (style `CREATE TABLE IF NOT EXISTS`, pas de FK
  vers larc_run — cohérent avec error_log ; compatible LarcCloudSync futur).
- `audit_design_system.py` n'a pas de `--json` → exclu des collecteurs v1.
- Encodage : `PYTHONIOENCODING=utf-8` sur tous les sous-processus.
