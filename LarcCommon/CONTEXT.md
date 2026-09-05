
# LarcCommon — Contexte du projet

## Objectif
Bibliothèque centrale partagée par toutes les applications Larc
(LarcSuperviseur, LarcSecretaire, eLarcProf, etc.).

Composants :
- **phibuilder/** : UI toolkit Material Design 3 + proportions Fibonacci
- **larccommon/** : Infrastructure partagée (DB, auth, session, logger, l10n)

## Structure

```
D:\projets\LarcCommon\
  ├── phibuilder/          ← UI Toolkit M3 + Fibonacci
  │     ├── phi/           ← Constantes φ, Fibonacci, PhiScale, PhiGrid
  │     ├── theme/         ← M3ColorScheme, M3Typography, M3Shape, M3Elevation
  │     ├── style/         ← StyleBuilder (QSS pour 16 widgets)
  │     ├── widgets/       ← 12 widgets M3
  │     └── builder.py     ← PhiBuilder facade
  ├── larccommon/          ← Infrastructure partagée
  │     ├── database.py    ← PostgreSQL (Intranet + Cloud)
  │     ├── auth.py        ← OAuth2 PKCE + local
  │     ├── session.py     ← Session singleton
  │     ├── config_loader.py
  │     ├── app_config.py
  │     ├── logger.py
  │     ├── network.py
  │     ├── photos.py
  │     ├── theme.py       ← ThemeManager (5 thèmes, PhiBuilder)
  │     ├── event_helpers.py
  │     └── l10n/          ← Traductions fr/en
  ├── docs/                ← Documentation
  ├── algo/                ← Décisions algorithmiques
  ├── tests/               ← 51 tests
  └── pyproject.toml       ← pip install -e .
```

## Dépendances
- materialyoucolor>=3.0
- PySide6>=6.5
- psycopg2-binary>=2.9

## Thèmes (5)
océan (clair/bleu), forêt (clair/vert), nuit (sombre/violet),
lave (sombre/rouge), sable (clair/ambre)

## Installation
```bash
cd D:\projets\LarcCommon
pip install -e .
```

## Tests
```bash
cd D:\projets\LarcCommon
pytest tests/
```
