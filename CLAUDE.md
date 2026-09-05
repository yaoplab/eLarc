# CLAUDE.md — Projets Larc

Dernière mise à jour : 2026-08-14

## TL;DR

- **Stack** : Python 3.x + PySide6 (Qt6) — pas PyQt5/PyQt6/Flet
- **Base** : PostgreSQL `127.0.0.1:5432` NewLarcDB (user:postgres, password:postgres)
- **Config** : `LarcCommon/config.ini` (port 5432 Intranet, 6543 Supabase Cloud, OAuth2)
- **Langue** : `set LARC_LANG=fr` (défaut) ou `en`
- **Design System** : `from larccommon.design_system import ds` — zéro hardcoding
- **Widgets** : `from phibuilder.widgets import *` — jamais PySide6.QtWidgets direct
- **Icônes** : `from larccommon.icons import icon as md3_icon` — 40 icônes MD3 SVG
- **Thèmes** : `theme_manager.phi_theme` pour widgets M3, `theme_manager.palette` pour QSS

## Architecture du monorepo

| Dépôt | Rôle | Entrée |
|---|---|---|
| `LarcCommon/` | Librairie partagée : `larccommon` (infra) + `phibuilder` (UI toolkit M3) | `pip install -e D:\projets\LarcCommon` |
| `LarcSuperviseur/` | Supervision présence/événements élèves | `python -m LarcSuperviseur` |
| `LarcSecretaire/` | Secrétariat (notes, dossiers, parents) | `python -m LarcSecretaire` |
| `LarcHub/` | Hub fusion Supervision + Secrétariat | `python -m LarcHub` |
| `LarcProf/` | Professeurs (notes, évaluations, SQLite locale) | `python -m LarcProf` |
| `LarcConfig/` | Configuration (i18n, thèmes, rôles, logs, types, lieux) | `python -m LarcConfig` |
| `LarcCloudSync/` | Daemon sync PostgreSQL local ↔ Supabase cloud | — |
| `LarcRH/` | Ressources Humaines (enseignants, staff, absences) | `python -m LarcRH` |
| `LarcCompta/` | Scolarité (frais, paiements, rappels) | `python -m LarcCompta` |
| `LarcDocs/` | Génération documentation (manuel, technique, guide) | — |
| `LarcSupMobile/` | App mobile Flutter (spécifications dans `specificationsMobile/`) | — |

## Commandes

```bash
# Activer l'environnement
cd D:\projets
pip install -e LarcCommon

# Lancer les applis
set LARC_LANG=fr
python -m LarcSuperviseur          # Supervision
python -m LarcSecretaire           # Secrétariat
python -m LarcHub                  # Hub
python -m LarcProf                 # Professeurs
python -m LarcRH                   # Ressources Humaines
python -m LarcCompta               # Scolarité
python -m LarcConfig               # Configuration

# Tests
cd D:\projets\LarcCommon && pytest tests/ -v

# Lint (depuis D:\projets)
python scripts/lint_qss_hardcoding.py
python scripts/lint_d1_color_checker.py
python scripts/lint_safe_slot.py
python scripts/lint_file_size.py
python scripts/lint_test_coverage.py
python scripts/lint_db_checker.py
python scripts/lint_auth_checker.py
python scripts/lint_ui_quality.py
python scripts/lint_preflight.py
python scripts/audit_theme_reactive.py
python scripts/audit_design_system.py
python scripts/lint_palette_contrast.py
```

## LarcCommon — librairie partagée

### phibuilder — UI Toolkit Material Design 3 + Fibonacci
```
phibuilder/
  ├── phi/           ← Constantes φ, Fibonacci, PhiScale(base_spacing=4), PhiGrid
  ├── theme/         ← Theme, ThemeConfig, M3ColorScheme, M3Typography, M3Shape
  ├── style/         ← StyleBuilder (QSS pour 16 widgets), QssHelper
  ├── widgets/       ← 25 widgets M3 (bouton, card, table, dialog, menu, etc.)
  └── builder.py     ← PhiBuilder facade
```

### larccommon — Infrastructure partagée
```
larccommon/
  ├── design_system.py  ← ds singleton (tokens, QSS helpers, couleurs, Fibonacci)
  ├── theme.py          ← ThemeManager (5 thèmes) + ImageScale + _LarcM3Colors
  ├── database.py       ← PostgreSQL Intranet + Cloud (psycopg2, autocommit=True)
  ├── auth.py           ← AuthManager (Intranet SHA-256) + OAuth2Manager (PKCE Google)
  ├── session.py        ← Session singleton (UserRole, ConnMode, AuthResult)
  ├── config_loader.py  ← find_cfg() cherche config.ini (priorité LarcCommon/)
  ├── network.py        ← detect_network() → (intranet_ok, internet_ok)
  ├── photos.py         ← Gestion photos élèves
  ├── icons.py          ← 40 icônes MD3 SVG → QIcon
  ├── logger.py         ← log()
  ├── event_helpers.py  ← Helpers événements
  ├── login.py          ← Login partagé (à brancher dans toutes les apps)
  ├── preferences_dialog.py ← Préférences (langue, thème, taille vignettes)
  └── l10n/             ← Translator + fr.json/en.json (~662 clés)
```

### Thèmes (5)
océan (clair/bleu), forêt (clair/vert), nuit (sombre/violet), lave (sombre/rouge), sable (clair/ambre)

## Conventions de code

### Imports UI — RÈGLE ABSOLUE
- **Toujours** depuis `phibuilder.widgets`, **jamais** de `PySide6.QtWidgets` direct
- Exceptions autorisées : `QMessageBox`, `QApplication`, `QVBoxLayout`, `QHBoxLayout`, `QGridLayout`, `QButtonGroup`, `QTableWidgetItem`

### Design System — ZÉRO HARDCODING
```python
from larccommon.design_system import ds

# Espacement
layout.setSpacing(ds.space_sm)         # jamais setSpacing(12)
layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)

# Hauteurs
field.setFixedHeight(ds.field_height)  # jamais setFixedHeight(52)

# Bordures QSS
field.setStyleSheet(ds.flat_input_qss())
table.setStyleSheet(ds.table_qss())

# Couleurs
ds.p.primary, ds.p.surface, ds.p.error, ds.p.outline  # palette
ds.c.primary, ds.c.on_surface, ds.c.outline_variant    # M3

# Fibonacci
phi = theme_manager.phi_theme
sp = phi.spacing.spacing
sp(SpacingToken.XXL)  # 84px
```

### Tokens rapides
| Catégorie | Token | Valeur |
|---|---|---|
| Espacement | `ds.space_xxs` / `ds.space_xs` / `ds.space_sm` / `ds.space_md` / `ds.space_lg` / `ds.space_xl` / `ds.space_xxl` / `ds.space_xxxl` | 4 / 8 / 12 / 20 / 32 / 52 / 84 / 136 px |
| Champs | `ds.field_height` / `ds.button_height` / `ds.header_height` | 52 px |
| Bordures | `ds.radius_xs` / `ds.radius_sm` / `ds.radius_md` / `ds.border_width` | 4 / 8 / 12 / 1 px |
| Polices | `ds.font_title` / `ds.font_body` / `ds.font_small` | 14 / 13 / 11 px |
| Tableaux | `ds.table_row_min` | 32 px |

### Pattern formulaire standard
```python
phi = theme_manager.phi_theme
p = theme_manager.palette

card = M3Card(theme=phi, variant=ds.CARD_ELEVATED)
cl = card.content_layout()
cl.setSpacing(ds.space_sm)

field = M3TextField(theme=phi)
field.setFixedHeight(ds.field_height)
field.setStyleSheet(ds.flat_input_qss())
```

### Contrainte padding champs
Tout champ de saisie DOIT avoir un `padding` gauche ≥ `ds.space_md` (20px). Le pattern `_flat_field` standard :
```python
f"background: transparent; border: 1px solid {p.outline}; "
f"border-radius: {ds.radius_xs}px; padding: {ds.space_md}px; "
f"color: {p.text_strong}; font-size: {ds.font_body}px;"
```

### Autres conventions
- **Dataclasses** pour les structures de données
- **Singletons** pour DB, session, theme_manager, app_config
- **QSS** généré via StyleBuilder/QssHelper (pas de QSS inline)
- **Traductions** via `_("cle.contextuelle")`
- **Photos** : `D:\projets\LarcSuperviseur\photos\{id}.png`
- **Ne pas utiliser `_`** comme variable throwaway (écrase la fonction i18n)
- **Pas d'images PNG/JPG comme icônes** — toujours SVG Material Design 3
- **Héritage fenêtre** : toujours `QWidget`, jamais `M3Card`

### Règles PySide6
- `@safe_slot` obligatoire sur tous les slots Qt
- Anti-patterns Qt interdits (pas de `QTimer.singleShot` pour contourner des bugs, pas de `processEvents`)
- Fichiers > 1000 lignes = refactoring obligatoire

## Architecture par application

### LarcSuperviseur
| Fichier | Rôle |
|---|---|
| `main.py` | Point d'entrée |
| `views/main_window.py` | Orchestrateur principal |
| `views/top_bar.py` | Barre du haut (date, réseau, thème, périodes) |
| `views/panels/sidebar.py` | Navigation gauche (programmes, classes) |
| `views/panels/group_panel.py` | Stats groupe : KPIs, charts, historique |
| `views/panels/class_panel.py` | Grille cartes élèves |
| `views/panels/student_detail.py` | Détail élève : photo, infos, événements |
| `views/core/data_loader.py` | Toutes les requêtes DB |
| `views/core/event_actions.py` | CRUD événements + menu contextuel |
| `views/dialogs/event_generator.py` | Wizard génération événements (3 modes) |
| `views/dialogs/timetable_editor.py` | Éditeur emploi du temps |

### LarcSecretaire
| Fichier | Rôle |
|---|---|
| `views/main_window.py` | Orchestrateur principal |
| `views/supervisor_panel.py` | Grille élèves, présence, événements |
| `views/student_form.py` | Fiche élève — recherche + popup édition 6 onglets |
| `views/parent_manager.py` | Gestion parents, foyers, liens élèves↔parents |
| `views/dossier_panel.py` | Dossiers élèves par catégories + documents |

### LarcRH
| Fichier | Rôle |
|---|---|
| `views/main_window.py` | Orchestrateur : sidebar 4 catégories + QStackedWidget |
| `views/staff_grid.py` | Grille photos adaptative par plage d'IDs |
| `views/staff_form.py` | Dialogue édition/création enseignant ou staff |
| `views/staff_detail.py` | Détail + timeline événements (absences/retards) |
| `views/staff_events.py` | EventGenerator adapté (staff_event au lieu de student_event) |
| `sql/init_staff.sql` | DDL : `larcauth_staff` + `staff_event` |

### LarcCompta
| Fichier | Rôle |
|---|---|
| `views/main_window.py` | Orchestrateur : sidebar navigation + QStackedWidget |
| `views/dashboard.py` | KPIs + donut chart + bar chart + detail par programme |
| `views/payment_list.py` | Liste des paiements + dialogue ajout avec recherche élève |
| `views/reminders.py` | Liste des impayés + envoi rappels (email/SMS/WhatsApp/courrier) |
| `sql/init_compta.sql` | DDL : `compta_fee_structure` + `compta_payment_schedule` + `compta_payment` + `compta_reminder` |

### LarcProf
| Fichier | Rôle |
|---|---|
| `views/login.py` | Login 4 onglets (Intranet/Cloud/PIN/Nouvelle instance) |
| `views/home_window.py` | Dashboard intermédiaire (profil, synchro, boutons PEI/DP) |
| `views/main_window.py` | Espace de travail : top bar + grille élèves × notes |
| `views/eval_manager.py` | Gestionnaire d'évaluations (non-modal) |
| `common/sync.py` | SyncManager (shadow-table _ref, diff cellule, pull/push) |
| `common/sqlite_init.py` | SQLiteInit (DDL, seed, take_teacher_data, migrations) |

## Base de données

### Connexions
- **Intranet** : `127.0.0.1:5432` dbname=NewLarcDB user=postgres password=postgres
- **Cloud** : Supabase `aws-1-eu-north-1.pooler.supabase.com:6543` PgBouncer
- **Device** : SQLite `elarc.db` (LarcProf) / `larcsecretaire.db` (LarcSecretaire)
- `autocommit = True` sur toutes les connexions

### Principe gabarit — FONDAMENTAL
- **Jamais d'INSERT** ni de DELETE sur les tables de gabarit (élèves, parents, évals)
- **Toujours des UPDATE** — tous les slots pré-existent
- Slot libre = `enabled = FALSE AND last_name LIKE 'Name of %'`
- IDs parents réservés : 10001–10800
- Format ID élève : `XXYYZZ` (classe + n°)

### Exceptions à l'UPDATE uniquement
- `student_event` — timeline d'événements imprévisible, INSERT libre
- Fichiers joints `data/students/{id}/` — création fichiers disque

### Sync (LarcProf)
- Pattern shadow-table `_ref` : diff cellule par cellule
- Trimestre courant uniquement (trimestres passés figés en lecture seule)
- Déclencheurs : création instance (mode4), clic "Connecter", clic "Synchroniser", sortie avec enregistrement
- Pas de connexion automatique au démarrage — test présence réseau seulement

### Terme actif
Défini par `larcauth_academicyear.current_term_number`, PAS par les dates

### Jour ouvré (agenda) — règle bloquante
`larcauth_agenda.working_day` est le « enabled » du jour :
- `TRUE` (jour ouvré) → génération d'événements RH autorisée (`HRDatabase.is_working_day()`)
- `FALSE` (week-end, férié) → `open_staff_event_generator` **refuse** ; l'absence du jour
  ne s'applique pas (cartes, KPI « Absents du jour », effectifs présents)

## Documentation

### Structure des docs
```
LarcCommon/
  ├── docs/              ← Architecture, phibuilder, larccommon, état projet
  ├── algo/              ← Décisions algorithmiques
  └── AGENTS.md          ← Conventions agent IA

.claude/skills/          ← Base de connaissances agent (skills + reviews, format Claude)

LarcSuperviseur/
  ├── docs/              ← Architecture, panels, core, dialogs, common
  ├── algo/              ← Navigation, lifecycle, data flow, card reflow
  ├── Wireframe1.68/     ← Spécifications visuelles par écran
  ├── CONTEXT.md         ← Contexte projet
  └── AGENTS.md          ← Conventions agent IA (LE PLUS COMPLET)

LarcProf/
  ├── docs/              ← 20 docs numérotés (intro → eval_manager)
  ├── à_faire/           ← Suivi des tâches
  └── CONTEXT.md         ← Contexte projet

LarcSecretaire/
  ├── docs/              ← Spécifications, auth, sync, SQL
  ├── CONTEXT.md         ← Contexte projet
  └── AGENTS.md          ← Conventions agent IA

LarcCloudSync/
  ├── 01_Architecture/   ← Architecture + classification tables
  ├── 02_Clone_Setup/    ← Clonage et configuration
  └── 03_Sync_Implementation/ ← Implémentation sync

specificationsMobile/    ← 17 specs numérotées pour LarcSupMobile
LarcDocs/output/         ← Documents générés (manuel, technique, guide)
```

### Base de connaissances agent (`.claude/skills/`)
```
.claude/skills/          ← Base de connaissances agent UNIQUE (racine D:\projets)
  ├── <nom>.md           ← 27 skills (design, patterns, infra, features)
  └── <nom>-review.md    ← 9 reviews (design, pyside6, testing, auth, infra, feature, graphify, scolarite, rh-audit)
```
Chaque fichier a un frontmatter `name/description/category/trigger` — le harness charge le skill sur trigger. Les linters associés vivent dans `scripts/`. Pas de génération, pas de miroir : `.claude/skills/` est la source unique.

### Skills — ordre de lecture
1. `design-tokens` (P0) — fondation numérique
2. `color-rules` (P0) — palette et règles couleur
3. `zero-hardcoding` (P0) — règle absolue tokens
4. `theme-reactivity` (P1) — pattern _STYLE + _restyle_all
5. `pyside6-wrapper` (P0) — @safe_slot, anti-patterns Qt
6. `graphify` (P0) — graphe de connaissances interrogeable du codebase
7. Puis les skills spécialisés : input-ergonomics (saisie sûre), preflight (C1-C13), ergonomics, sidebar-spec (K1-K26), ui-quality (V1-V8), scolarite-finance (LarcCompta), event-generator, sync, auth-intranet/auth-oauth2/auth-pin, database-operations, larc-testing, patterns (form, dashboard, card-grid, search-detail), card-dashboard, student-record, toolkit-reference
8. Télémétrie (P1) : `error-reporting` (erreurs centralisées R1), `audit-log` (journal qui/quoi/quand R2), `soft-update` (mise à jour douce R3) — audit via `telemetry-review`
9. Data entry (P1) : `data-entry-ui` (saisie dense, palette marque) + `pyside6-data-entry-ui-builder` (skill source complet)

### Graphify — Graphe de connaissances du codebase

**Graphify** transforme le codebase en graphe interrogeable (4233 nœuds, 8421 arêtes, 255 communautés).
C'est le "cerveau Obsidian" du projet : au lieu de lire tous les fichiers, l'agent parcourt le graphe.

```bash
# Régénérer le graphe après un changement structurel
graphify extract . --code-only --force
graphify cluster-only .

# Interroger le graphe
graphify query "Comment LarcProf se connecte a la base ?"
graphify explain "ThemeManager"
graphify path LarcCommon LarcSuperviseur

# Visualiser — ouvrir dans le navigateur
start graphify-out/graph.html

# God nodes (les concepts les plus connectes)
graphify god-nodes --top 20
```

**God nodes actuels** : DataLoader (156), safe_slot (151), log (141), SpacingToken (109), Theme (89),
_DesignSystem (74), MainWindow (70), LoginWindow (58), PhiScale (52), EventActions (50)

**Règle** : Toujours consulter le graphe (`graphify query` ou `graphify explain`) AVANT une tâche
touchant ≥3 fichiers. Régénérer après chaque refactoring.

## Linting, Reviews et CI

### Reviews (dans `.claude/skills/`)
| Review | Déclencheur | Périmètre |
|---|---|---|
| `design-review` | audit/vérifie/check design | tokens, couleurs, hardcoding, thème |
| `pyside6-review` | audit pyside6, vérifie slots | @safe_slot, anti-patterns Qt, 1000 lignes |
| `testing-review` | audit tests, couverture | Phase 1 mock, Phase 2 réel |
| `auth-review` | audit auth, login, OAuth | OAuth2, Intranet SHA-256, PIN |
| `infra-review` | audit infra, sync, graphify | DB, synchronisation, graphe |
| `telemetry-review` | audit télémétrie, erreurs, mise à jour | error_log, audit_log, app_version |
| `feature-review` | audit feature, événements | event-gen, cards, dossier élève |
| `graphify-review` | audit graphe, god nodes | fraîcheur, complétude, cohérence |
| `scolarite-review` | construit/audite LarcCompta | règles métier SF/S1-S5 + design system |
| `rh-audit-fonctionnel` | audit RH, analyse RH Togo | 14 domaines RH, CNSS, barème impôt |

### Scripts de lint (dans `scripts/`)
| Script | Périmètre |
|---|---|
| `lint_qss_hardcoding.py` | Détection hardcoding px/couleurs dans QSS |
| `lint_d1_color_checker.py` | Vérification couleurs palette |
| `lint_safe_slot.py` | Vérification @safe_slot sur tous les slots Qt |
| `lint_file_size.py` | Détection fichiers > 1000 lignes |
| `lint_test_coverage.py` | Vérification couverture de tests |
| `lint_db_checker.py` | Vérification connexions DB |
| `lint_auth_checker.py` | Vérification flux auth |
| `lint_ui_quality.py` | V1-V8 finitions UI (icônes, tooltips, gap icône-texte…) |
| `lint_preflight.py` | C1-C13 check-list pré-soumission |
| `audit_theme_reactive.py` | Audit réactivité thème |
| `audit_design_system.py` | Audit utilisation design system |
| `lint_palette_contrast.py` | Contraste texte/fond de la palette (background vs text, règle D8) |
| `fix_safe_slot.py` | Auto-fix @safe_slot manquants |

### CI
- Ruff + Black + pre-commit sur tous les repos
- GitHub Actions dans `.github/workflows/ci.yml` (6 repos)

## Règles de maintenance

### Ajouter un thème
1. Ajouter une entrée dans `THEMES_CONFIG` (LarcCommon/larccommon/theme.py)
2. Ajouter une `Palette` dans `_THEME_PALETTES`
3. Les tests et le sélecteur UI s'adaptent automatiquement

### Ajouter une skill
1. Créer `.claude/skills/<nom>.md` avec frontmatter `name/description/category/trigger`
2. Format condensé (10-80 lignes) : règles en table, code clé, checklist, références croisées
3. Si nouveau linter : créer le script dans `scripts/`
4. L'ajouter à la section « Skills — ordre de lecture » si P0/P1

### Ajouter une review
1. Créer `.claude/skills/<nom>-review.md` (frontmatter + commandes linters + check-lists)
2. L'ajouter à la table « Reviews (dans `.claude/skills/`) »

### Ajouter une application
1. Copier la structure d'une app existante (login LarcSuperviseur)
2. Installer LarcCommon : `pip install -e D:\projets\LarcCommon`
3. Utiliser `larccommon/login.py` pour l'auth
4. Design System via `ds.*` — zéro hardcoding
5. Widgets via `phibuilder.widgets` — jamais PySide6 direct

### Avant chaque commit
1. `python scripts/lint_safe_slot.py` — vérifier @safe_slot
2. `python scripts/lint_qss_hardcoding.py` — vérifier pas de hardcoding
3. `python scripts/lint_d1_color_checker.py` — vérifier couleurs
4. `python scripts/lint_palette_contrast.py` — vérifier contraste texte/fond de la palette (si theme.py modifié)
5. `python scripts/lint_file_size.py` — vérifier pas de fichiers > 1000 lignes
6. Lancer l'app concernée pour test visuel
7. Si changement structurel : `graphify extract . --code-only --force && graphify cluster-only .`

## État actuel (2026-08-06)

### Intégration LarcHub
- **LarcProf intégré** dans LarcHub via `ProfWorkspace` + `HomeWidget`
- **Session unifiée** : LarcProf réexporte `larccommon.session` (plus de double session)
- **Navigation par rôle** dans la sidebar LarcHub :
  - Supervision (supervisor/coordinator/director) → LarcSuperviseur MainWindow
  - Secrétariat (secretary/director) → LarcSecretaire MainWindow
  - Enseignement (teacher/director) → ProfWorkspace (HomeWidget + MainWindow)
  - Coordination (coordinator/director) → placeholder désactivé
- **LarcProf standalone** préservé (`python -m LarcProf` fonctionne inchangé)
- **Sidebar** : scroll area, icônes MD3, affichage multi-rôle
- Fichiers créés : `LarcProf/views/home_widget.py`, `LarcProf/views/prof_workspace.py`
- Fichiers modifiés : `LarcHub/main.py`, `LarcHub/views/hub_window.py`, `LarcHub/views/login.py`, `LarcCommon/larccommon/session.py`, `LarcProf/common/session.py`, `LarcProf/common/database.py`

### Restant
- **LarcCommon** : design_system.py, login.py, preferences_dialog.py en cours de modification
- **Toutes les apps** : modifications en cours sur les vues principales
- **~170 hardcodings** restants à migrer vers ds.* tokens (priorité basse, UI fonctionnelle)
- **Fichier de référence** pour conformité Design System : `LarcSecretaire/views/parent_manager.py` (0 hardcoded)
