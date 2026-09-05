
# LarcCommon — Bibliothèque commune Larc

> Bibliothèque centrale partagée par toutes les applications Larc
> (LarcSuperviseur, LarcSecretaire, eLarcProf, etc.)
> Fournit UI toolkit (PhiBuilder), infrastructure partagée (DB, auth, logger, l10n).

## Architecture

```
┌─────────────────────────────────────────────┐
│              Application hôte               │
│  (LarcSuperviseur, LarcSecretaire, ...)     │
└──────────────────┬──────────────────────────┘
                   │ import
┌──────────────────▼──────────────────────────┐
│              LarcCommon                      │
│                                              │
│  ┌──────────────────┐  ┌──────────────────┐  │
│  │   phibuilder/    │  │   larccommon/    │  │
│  │  UI Toolkit      │  │  Infrastructure  │  │
│  │                  │  │                  │  │
│  │ • M3 widgets    │  │ • database.py    │  │
│  │ • M3ColorScheme │  │ • auth.py        │  │
│  │ • StyleBuilder  │  │ • session.py     │  │
│  │ • Theme engine   │  │ • config_loader  │  │
│  │ • Fibonacci/φ    │  │ • logger.py      │  │
│  └──────────────────┘  │ • network.py     │  │
│                         │ • photos.py      │  │
│                         │ • theme.py       │  │
│                         │ • event_helpers  │  │
│                         │ • l10n/          │  │
│                         │   (traductions)  │  │
│                         └──────────────────┘  │
└───────────────────────────────────────────────┘
```

## Dépendances

| Package | Version | Usage |
|---|---|---|
| `PySide6` | >=6.5 | Qt6 bindings |
| `materialyoucolor` | >=3.0 | M3 HCT color engine |
| `psycopg2-binary` | >=2.9 | PostgreSQL (optionnel, pour larccommon) |

## Packages

### `phibuilder` — UI Toolkit Material Design 3 + Fibonacci

Génère une UI complète avec proportions basées sur le nombre d'or (φ ≈ 1.618)
et la suite de Fibonacci, combinées au système de thème Material Design 3.

- **φ module** : constantes (PHI, PHI_INV, golden angle), suite de Fibonacci, PhiScale, PhiGrid, PhiLayout
- **theme module** : M3ColorScheme (60+ couleurs, 9 variants, light/dark), M3Typography (15 styles M3), M3Shape, M3Elevation
- **style module** : StyleBuilder générant du QSS complet pour 16 types de widgets
- **widgets module** : M3Button, M3Card, M3TextField, M3Label, M3ComboBox, M3ListWidget, M3TableWidget, M3Dialog, M3Snackbar, M3BottomSheet, M3NavigationBar, M3Sidebar
- **builder module** : PhiBuilder facade (apply, set_dark_mode, toggle, seed_color, font, variant, export)

### `larccommon` — Infrastructure partagée Larc

Modules réutilisables par toutes les applications Larc.

| Module | Classes/Fonctions | Description |
|---|---|---|
| `database.py` | `Database`, `db` | Singleton PostgreSQL (Intranet + Cloud) |
| `auth.py` | `OAuth2Manager` | OAuth2 PKCE Google + auth local |
| `session.py` | `Session`, `UserRole`, `ConnMode`, `session` | État de session global |
| `config_loader.py` | `find_cfg()` | Localisation de config.ini |
| `app_config.py` | `AppConfig`, `app_config` | Configuration DB (larcauth_config) |
| `logger.py` | `log()`, gestion fichiers | Logger applicatif |
| `network.py` | `detect_network()` | Détection Intranet/Internet |
| `photos.py` | `get_photo_path()`, `PhotoPreloader` | Gestion photos élèves |
| `theme.py` | `ThemeManager`, `theme_manager` | Gestion thèmes (5 thèmes, intégration PhiBuilder) |
| `event_helpers.py` | `event_icon()`, `event_color()` | Icônes/couleurs par type d'événement |
| `l10n/` | `Translator`, `_()` | Traductions multilingues (JSON) |

## Thèmes disponibles (5)

| Thème | Seed | Mode | Palette dominante |
|---|---|---|---|
| Océan | `#0D47A1` | ☀️ clair | Bleu |
| Forêt | `#2E7D32` | ☀️ clair | Vert |
| Nuit | `#4A148C` | 🌙 sombre | Violet |
| Lave | `#C62828` | 🌙 sombre | Rouge |
| Sable | `#E65100` | ☀️ clair | Orange/Ambre |

## Traductions (l10n)

Format : JSON par langue. Clés contextuelles (`module.composant.action`).

```
larccommon/l10n/
  ├── fr.json    ← Français (défaut)
  └── en.json    ← Anglais
```

Chaque application peut ajouter son propre dossier `l10n/` fusionné automatiquement.
