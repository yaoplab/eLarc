# Audit complet — LarcSecretaire

Date : 2026-09-14
Périmètre : application entière (26 fichiers Python, 10 673 lignes) — design system, patterns PySide6, tests, base de données, auth, fonctionnel. Pas de modification de code — audit de constat uniquement.
Méthode : 1 agent en lecture seule appliquant les checklists `.claude/skills/*-review.md` (design, pyside6, testing, auth, infra, feature, telemetry) + linters partagés (`scripts/*.py`) + lecture intégrale des fichiers principaux.

## Chiffres bruts des linters (filtrés LarcSecretaire)

| Script | Résultat LarcSecretaire |
|---|---|
| `lint_qss_hardcoding.py` | 1 violation (`supervisor_panel.py:341`) |
| `lint_d1_color_checker.py` (D1+J7) | 0 violation |
| `lint_safe_slot.py` | 3 (`print()` dans handler, `login.py:98,101,102`) |
| `lint_file_size.py` | 3 fichiers P0 > 1000 lignes (`student_form.py` 3472, `dossier_panel.py` 1471, `main_window.py` 1139) |
| `lint_test_coverage.py` | P0 — **aucun dossier `tests/`** |
| `lint_db_checker.py` | 0 violation |
| `lint_auth_checker.py` | 0 violation |
| `lint_ui_quality.py` | 5 (3× emoji au lieu de `md3_icon`, 2× `setMinimumSize` en dur) |
| `lint_preflight.py` (C7) | 3 slots connectés sans `@safe_slot` |
| `audit_theme_reactive.py` | 5 classes vulnérables / 4 fichiers (sur 11 classes avec QSS palette) |
| `audit_design_system.py` | 9 hardcodings (8× `setFixedHeight(1)`/`addSpacing`, 1× `setMinimumSectionSize`) |
| `lint_palette_contrast.py` | N/A (palette définie dans LarcCommon) |

## Tableau macro par écran

| Fichier | Lignes | PB total | P0 | P1 | P2 |
|---|---|---|---|---|---|
| `views/main_window.py` | 1139 | 8 | 3 | 3 | 2 |
| `views/supervisor_panel.py` | 916 | 7 | 2 | 3 | 2 |
| `views/login.py` | 517 | 6 | 2 | 2 | 2 |
| `views/student_form.py` | 3472 | 6 | 2 | 3 | 1 |
| `views/parent_manager.py` | 993 | 5 | 1 | 3 | 1 |
| `views/dossier_panel.py` | 1471 | 3 | 1 | 1 | 1 |
| `views/notes_panel.py` / `todo_panel.py` | 388/574 | 3 | 0 | 2 | 1 |
| `common/*` (audit, sync, auth, database, session) | ~800 | 0 | 0 | 0 | 0 |
| Couverture de tests — aucun `tests/` | — | 1 | 1 | 0 | 0 |
| **Total** | | **39** | **10** | **17** | **12** |

## Causes racines transverses

1. **`SET LOCAL` sous `autocommit=True` = no-op silencieux, répété 7×.** `parent_manager.py:557-558,606-607,687-688,901-902`, `student_form.py:1719-1720,3182-3183`, `supervisor_panel.py:730-731` exécutent `SET LOCAL app.sync_source=...` / `SET LOCAL app.modified_by=...` **après** l'INSERT/UPDATE, sur une connexion autocommit — chaque `execute()` est déjà sa propre transaction, donc ces réglages n'atteignent jamais le trigger d'audit serveur. Bug **déjà documenté** dans `LarcSecretaire/docs/rapport_audit_2026-06-12.md` (§1.4) depuis juin 2026, jamais corrigé. Impact : le journal d'audit (R2) perd la traçabilité "qui a modifié quoi" sur tous les liens/déliens parent-élève et les événements de supervision. Contre-exemple correct : `common/audit.py` via `audit_context.attach(conn)`.
2. **`theme=` manquant sur 100% des widgets phibuilder de `main_window.py` et `supervisor_panel.py`** — 0 occurrence de `theme=theme_manager.phi_theme`, contre usage correct dans `student_form.py`, `dossier_panel.py`, `parent_manager.py`, `password.py`, `notes_panel.py`, `todo_panel.py`. Les deux écrans les plus utilisés (tableau de bord + supervision) tournent potentiellement sans style M3 sur leurs widgets.
3. **`views/login.py` n'utilise aucun widget `phibuilder`** — 100% `QLabel`/`QLineEdit`/`QPushButton`/`QTabWidget`/`QCheckBox` bruts, QSS géré à la main. L'écran d'entrée de l'application contourne entièrement le design system.
4. **Garde `if not db.is_server_connected: return` bare, indifférente au type de retour déclaré**, répétée ~40 fois. Casse l'appelant quand la signature promet un tuple/str :
   - **Bug confirmé** `login.py:383-385` — `_check_secretary_exists(...) -> Tuple[bool, dict]` renvoie `None` si déconnecté ; `login.py:425` fait `exists, infos = self._check_secretary_exists(...)` → `TypeError` masqué par `@safe_slot`, échec de connexion silencieux.
   - **Bug confirmé** `student_form.py:2046-2048` — `_build_full_html() -> str` renvoie `None` hors-connexion → `doc.setHtml(None)` lève `TypeError` dans `_export_pdf`/`_export_word`, message technique incompréhensible pour la secrétaire.
5. **Widgets PySide6 bruts hors liste d'exceptions** — `QLabel` en substitut de `M3Label` (9× `student_form.py`, 3× `parent_manager.py`, 2× `main_window.py`, 8× `login.py`), `QDialog` brut au lieu de `M3Dialog` (`main_window.py:881`, `todo_panel.py:484`), `QSplitter` (`dossier_panel.py:658`), `QInputDialog` (×4).
6. **Couverture de tests nulle.** Aucun `tests/`, aucun `conftest.py`, alors que le module manipule auth intranet/OAuth2, INSERT/DELETE sur `larcauth_student_parent`/`secretary_todo`, gestion de fichiers `data/students/`. Aucun test des slots `@safe_slot`, de `_restyle`, ni d'intégration DB.
7. **`student_form.py` = 3472 lignes, 3 classes** (`StudentForm` ~600 l., `StudentEditDialog` ~1620 l., `StudentCreateDialog` ~1246 l.) — les deux dialogues dépassent individuellement 1000 lignes. Découpage naturel : un fichier par classe + extraction des 6 onglets en mixins/sous-widgets.

## Détail par écran

### `views/main_window.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| tout le fichier | pyside6-wrapper E1 | Aucun widget phibuilder ne reçoit `theme=` (M3Frame, M3Button, M3Label, M3Menu, M3ProfileButton, M3ScrollArea, M3StackedWidget, M3TableWidget, M3HeaderView) | P0 | Ajouter `theme=theme_manager.phi_theme` partout, cf. pattern `student_form.py` |
| 1139 lignes | lint_file_size | Fichier > 1000 lignes | P0 | Extraire dashboard, sidebar, KPI dialog dans des sous-modules |
| 455, 881 | zero-hardcoding / W1 | `QLabel()` et `QDialog(self)` bruts au lieu de `M3Label`/`M3Dialog` | P1 | Remplacer par widgets phibuilder |
| 467 | pyside6-wrapper | `f.mousePressEvent = lambda ev, k=key: self._on_action_kpi(k)` — monkey-patch d'event handler sur instance, `_on_action_kpi` non `@safe_slot` alors qu'il agit comme handler cliquable | P1 | Sous-classer un widget cliquable ou `installEventFilter`, décorer `_on_action_kpi` |
| 907 | pyside6-review | Lambda nu multi-actions (`self._create_tasks_from_rows(rows, key), dlg.accept()`), `_create_tasks_from_rows` non `@safe_slot` | P1 | Slot nommé + `@safe_slot` |
| 358, 372 | pyside6-review | Lambda nu appelant `self._content_stack.setCurrentIndex(N)` | P2 | Slot nommé (mineur, action non risquée) |
| 1006-1014 | i18n | Dict `labels` codé en dur en français sans `_()` | P2 | Clés `_("sec_main.scope.*")` |
| 499 | zero-hardcoding | `hdr.setMinimumSectionSize(40)` en dur | P2 | `ds.space_md * 2` |

### `views/supervisor_panel.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| tout le fichier | pyside6-wrapper E1 | Aucun widget phibuilder ne reçoit `theme=` | P0 | Ajouter `theme=theme_manager.phi_theme` |
| 730-731 | telemetry-review R2 | `SET LOCAL` après INSERT sous autocommit → no-op ; f-string non paramétré (`{session.user_id}`) | P0 | Supprimer, utiliser `audit_context.attach(conn)` |
| 293, 781, 797 | audit_theme_reactive | `SupervisorPanel` et `ClassListDialog` : QSS palette-dépendant sans `theme_changed.connect`/`_restyle` | P1 | Ajouter la réactivité thème |
| 331 | pyside6-review (C7) | Slot `_on_card_size` connecté sans `@safe_slot` | P1 | Ajouter le décorateur |
| 341 | zero-hardcoding | `hdr_row.addSpacing(3)` — non tokenisé | P2 | `ds.space_xxs` (4px) |
| 67 | ui-quality V1 | Emoji `✕` au lieu de `md3_icon("cancel", ...)` | P2 | Remplacer par icône MD3 |

### `views/login.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| tout le fichier | pyside6-wrapper W1 | 100% widgets bruts (`QLabel`/`QLineEdit`/`QPushButton`/`QTabWidget`/`QCheckBox`) | P0 | Migrer vers `M3TextField`, `M3Button`, `M3TabWidget`, `M3Label` |
| 384-385 | bug confirmé | `_check_secretary_exists(...) -> Tuple[bool, dict]` retourne `None` si déconnecté ; unpacking L425 → `TypeError` masqué | P0 | `return False, {}` |
| 71-72 | cohérence de type | `_get_current_term_label() -> str` retourne `None` (return nu) | P2 | `return ""` |
| 98, 101, 102 | pyside6-review (C6/A5) | `print("[DEBUG] ...")` restants dans `__init__` | P1 | Retirer ou remplacer par `log()` |
| 114, 116 | code mort | `setWindowTitle(_("sec_login.title"))` dupliqué | P2 | Supprimer le doublon |
| — | theme-reactivity | 7 `setStyleSheet` palette-dépendants sans `_restyle` | P1 | Ajouter la réactivité (mineur : écran avant login) |

### `views/student_form.py` (3472 lignes, 3 classes)

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 3472 lignes | lint_file_size | 3.4× la limite ; `StudentEditDialog` (~1620 l.) et `StudentCreateDialog` (~1246 l.) dépassent individuellement 1000 lignes | P0 | Split en 3 fichiers + extraction des onglets en mixins |
| 2046-2048, 2179, 2203 | bug confirmé | `_build_full_html() -> str` retourne `None` hors-connexion → `doc.setHtml(None)` lève `TypeError` dans `_export_pdf`/`_export_word` | P1 | `return ""` ou message d'erreur explicite avant l'export |
| 1102, 2894 | pyside6-review (C7) | Slots `_on_flag_toggled`, `_on_class_changed` sans `@safe_slot` | P1 | Ajouter le décorateur |
| 215,242,263,406,697,842,1019,2277,2407,2577 | W1 | `QLabel()` pour icônes/photos/badges au lieu de `M3Label` | P2 | Remplacer (cohérence à terme) |
| 1360, 2710 | zero-hardcoding | `setMinimumSize(600, ...)` en dur | P2 | Token `ds.*` |
| 852, 2417 | zero-hardcoding | `sep.setFixedHeight(1)` en dur | P2 | `ds.border_width` |

### `views/parent_manager.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 557-558, 606-607, 687-688, 901-902 | telemetry-review R2 | 4× `SET LOCAL` no-op + f-string non paramétré | P0 | Supprimer, utiliser `audit_context.attach(conn)` |
| 172, 334, 791 | W1 | `QLabel()` pour avatar/icône | P2 | Remplacer par `M3Label` |
| 679 | W1 | `QInputDialog.getItem(...)` brut | P2 | `M3Dialog`/combo custom si cohérence stricte souhaitée |
| 677 | ui-quality V1 | Emoji `⚠` au lieu de `md3_icon("warning", ...)` | P2 | Remplacer |
| 182, 370, 801 | zero-hardcoding | `sep.setFixedHeight(1)` ×3 | P2 | `ds.border_width` |
| 993 lignes | lint_file_size | Juste sous la limite — à surveiller | P2 | Vigilance avant prochain ajout |

### `views/dossier_panel.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 1471 lignes | lint_file_size | 5 classes en un seul fichier (`_EntryDialog`, `_Page`, `ConfidentialPanel`, `_TimelinePage`, `DossierPanel`) | P0 | Un fichier par classe |
| 323, 344-528 | audit_theme_reactive | 10 `setStyleSheet` palette-dépendants sans `_restyle` (`_EntryDialog`, dialogue de saisie très utilisé) | P1 | Ajouter la réactivité thème |
| 658 | W1 | `QSplitter` brut | P2 | Exception assumée si pas d'équivalent phibuilder — à documenter |
| 1330 | zero-hardcoding | `sep.setFixedHeight(1)` | P2 | `ds.border_width` |

### `views/notes_panel.py` / `views/todo_panel.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| `notes_panel.py:58-66` | audit_theme_reactive | `_MultilineDelegate` : QSS palette-dépendant sans réactivité | P1 | Ajouter `_restyle` ou reconstruire au changement de thème |
| `notes_panel.py:38-43` | code smell | `TEMPLATE_ENTRIES` construit au niveau module avec `QDate.currentDate()` figé à l'import | P2 | Générer à la demande dans `_empty_entries()` |
| `notes_panel.py:129` | zero-hardcoding | `setMinimumSectionSize(21)` en dur | P2 | `ds.table_row_min` |
| `todo_panel.py:390` | ui-quality V1 | Emoji `✕` au lieu de `md3_icon("cancel", ...)` | P2 | Remplacer |
| `todo_panel.py:484` | W1 | `QDialog(self)` brut | P1 | Remplacer par `M3Dialog` |

## Conforme

- **`main_window.py`** : seul fichier marqué `✔ Protégé` par `audit_theme_reactive.py` — `_restyle_all()` bien connecté malgré le manque de `theme=`. Gestion réseau/timer d'inactivité propre, SQL entièrement paramétré, chaque bloc DB protégé par `try/except` + `error_reporting`.
- **`supervisor_panel.py` / `student_form.py`** : 0 hardcoding QSS détecté (hors la ligne signalée) ; usage cohérent de `ds.table_qss()`, `ds.flat_input_qss()`.
- **`student_form.py`, `parent_manager.py`, `dossier_panel.py`, `notes_panel.py`, `todo_panel.py`, `password.py`** : passent `theme=theme_manager.phi_theme` correctement (contrairement à `main_window.py`/`supervisor_panel.py`).
- **`common/audit.py`** : implémentation R2 conforme (`audit_context.attach(conn)`/`refresh()`, table `audit_log`, troncature des champs) — bon contre-exemple face aux `SET LOCAL` cassés des vues.
- **`common/database.py`, `common/session.py`** : réexports propres de `larccommon`, alignés sur la session unifiée LarcHub.
- **`common/auth.py`** : PKCE OAuth2 correct (code_verifier/challenge S256, vérification `hd=arc-en-ciel.org`), SHA-256 intranet, aucun `psycopg2.connect()` direct hors `database.py`.
- **i18n** : quasi 100% des textes UI via `_("clé")` (seule exception notable : `main_window.py:1006-1014`).
- **SQL** : globalement bien paramétré (`%s`), rollback systématique sur exception — seule ombre : les `SET LOCAL` en f-string (cause racine n°1).
- **`lint_db_checker` / `lint_auth_checker`** : 0 violation — aucune connexion directe hors `database.py`, pas de contournement d'`AuthManager`.
