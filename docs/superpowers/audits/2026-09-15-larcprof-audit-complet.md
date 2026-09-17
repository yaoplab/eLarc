# Audit complet — LarcProf

Date : 2026-09-15
Périmètre : application entière (33 fichiers Python, 11 959 lignes hors `__pycache__`/deepseek) — design system, patterns PySide6, tests, base de données, auth, synchronisation, fonctionnel. Pas de modification de code — audit de constat uniquement.
Méthode : 1 agent en lecture seule appliquant les checklists `.claude/skills/*-review.md` (pyside6, infra, design, testing, auth) + linters partagés (`scripts/*.py`) + lecture intégrale de tous les fichiers listés dans le périmètre (`views/`, `common/`, `tests/`, `main.py`, `__main__.py`).

Note d'environnement : le filesystem temporaire Windows de la machine (`C:\Users\PATRICE\AppData\Local\Temp`) était plein (120 Go/120 Go, 0 Mo libre) au moment de l'audit, ce qui a fait échouer une exécution de linter avant contournement (exécution sans redirection fichier). Sans lien avec le code audité — à signaler côté poste de travail.

## Chiffres bruts des linters (filtrés LarcProf)

| Script | Résultat LarcProf |
|---|---|
| `lint_qss_hardcoding.py` | 0 violation |
| `lint_d1_color_checker.py` (D1+J7) | 0 violation |
| `lint_safe_slot.py --dir ./LarcProf` | 0 violation (voir note méthode ci-dessous — angles morts confirmés par lecture manuelle) |
| `lint_file_size.py --stats` | 0 fichier > 1000 lignes. Plus grand : `views/main_notes.py` (954 l.). Moyenne `views/` : 448 l/fichier (la plus haute des apps du monorepo) |
| `lint_test_coverage.py` | 9 P1 — `common/auth.py`, `database.py`, `eval_helpers.py`, `grid_config.py`, `logger.py`, `network.py`, `session.py`, `sqlite_init.py`, `theme.py` sans test dédié (voir aussi analyse qualitative des 3 fichiers `tests/` existants, section Causes racines) |
| `lint_db_checker.py --dir ./LarcProf` | 0 violation |
| `lint_auth_checker.py --dir ./LarcProf` | 0 violation |
| `lint_ui_quality.py --dir ./LarcProf` | 0 violation |
| `lint_preflight.py --dir ./LarcProf` | 1 violation — `views/weight_dialog.py:591` (C13, return muet sans message utilisateur) |
| `audit_theme_reactive.py --dir ./LarcProf` | 0 classe vulnérable / 14 classes protégées (module Cible 100 % conforme) |
| `audit_design_system.py --path ./LarcProf` | 2 hardcodings — `views/main_window.py:254,302` (20px → `ds.space_md`) |
| `lint_palette_contrast.py --dir ./LarcProf` | 0 écart |

**Note méthode — angle mort du linter `lint_safe_slot.py`** : sa détection ne couvre pas les connexions `.clicked.connect(partial(self._methode, arg))` ni le monkey-patch d'un event handler sur une instance (`widget.mousePressEvent = lambda ...`, `dialog.closeEvent = fn`). La lecture manuelle de tous les fichiers a trouvé 6 handlers non protégés par ce biais (détaillés en section Causes racines n°4), invisibles au chiffre « 0 violation » ci-dessus.

## Tableau macro par écran

| Fichier | Lignes | PB total | P0 | P1 | P2 |
|---|---|---|---|---|---|
| `common/sqlite_init.py` | 901 | 2 | 2 | 0 | 0 |
| `common/sync.py` | 578 | 4 | 2 | 2 | 0 |
| `views/main_window.py` / `main_data.py` / `main_actions.py` / `main_notes.py` (mixins) | 692+354+153+954 = 2153 | 8 | 1 | 4 | 3 |
| `views/home_widget.py` / `home_window.py` / `prof_workspace.py` | 680+792+92 = 1564 | 5 | 2 | 3 | 0 |
| `views/login.py` / `login_auth.py` / `login_creation.py` / `login_helpers.py` | 649+403+191+205 = 1448 | 3 | 1 | 0 | 2 |
| `views/evaluation_panel.py` / `eval_manager.py` / `event_dialog.py` | 904+436+128 = 1468 | 2 | 1 | 1 | 0 |
| `views/grid_table.py` / `weight_dialog.py` / `student_card_view.py` | 381+647+639 = 1667 | 3 | 0 | 1 | 2 |
| `views/password.py` | 216 | 1 | 0 | 0 | 1 |
| `common/theme.py` | 153 | 1 | 0 | 0 | 1 |
| `common/database.py` | 240 | 1 | 0 | 1 | 0 |
| `common/auth.py`, `session.py`, `calc_engine.py`, `event_service.py`, `logger.py`, `network.py`, `grid_config.py`, `eval_helpers.py` | ~1145 | 1 | 0 | 1 | 0 |
| Couverture de tests (`tests/`) | 432 | 1 | 0 | 1 | 0 |
| Adoption design system (`phibuilder.widgets` / `theme=`) — transverse à tout `views/` | — | 1 | 1 | 0 | 0 |
| **Total** | | **33** | **10** | **14** | **9** |

## Causes racines transverses

1. **`log()` appelé sans jamais être importé — NameError garanti — casse le bootstrap SQLite à chaque appel.** `common/sqlite_init.py` importe uniquement `from .logger import log as _log` (ligne 11) ; jamais le nom `log`. Or `log(...)` est appelé tel quel 23 fois dans ce fichier : lignes 367, 371 (dans `init_intranet`, **les deux branches** de l'existence du fichier, donc **inconditionnellement** dès la première instruction utile de la méthode — avant même `db.connect_sqlite()`), 414, 465, 476, 502, 506, 515 (`init_cloud`), 540 (`save_session`), 564 (`init_module_config`), 599, 689, 702, 733, 745, 752, 761 (`take_teacher_data`), 782 (`_touch_sync_state`), 787, 801, 805, 827, 833 (`_create_table_from_data`/`_insert_rows_from_data`). Conséquence : **`sqlite_init.init()` lève systématiquement une `NameError` dès son premier appel**, avant toute création de table. Cette méthode est le point d'entrée central appelé à ~15 endroits (`main.py:52,114`, `views/login.py:519`, `views/login_auth.py:119,204,226,239,250,300,368`, `views/login_creation.py:136`) — c'est-à-dire **tous les chemins de connexion (Intranet, Cloud, PIN, Nouvelle instance)**. L'exception est absorbée par `@safe_slot` ou un `try/except` local (ex. `login.py:518-523`), donc l'app ne crashe pas brutalement, mais l'initialisation de la base locale échoue silencieusement à chaque tentative — la base SQLite n'est jamais réellement (re)créée par ce chemin. `common/database.py:31-32` reproduit le même bug dans une branche de repli (`except ImportError`) sur `find_cfg()`, plus rarement atteinte mais du même type. Explique probablement une bonne partie du constat « application inachevée » du demandeur.

2. **La synchronisation (`common/sync.py`) ne fonctionne jamais — deux `NameError` indépendants dans `pull_push()`, jamais testés.** Ligne 183 : `log(f'[SYNC] {table}: ...')` — `log` n'est pas importé dans ce fichier (seul `_log` l'est, ligne 30) → NameError dès la première itération de la boucle sur `BUSINESS_TABLES`, immédiatement après le calcul (coûteux) des diffs, **avant** que le moindre pull/push ne soit appliqué. L'exception est absorbée par le `try/except` englobant (ligne 216-221), donc `pull_push()` retourne un `SyncReport` avec une erreur par table et ne synchronise jamais rien. Ligne 207 : `local_conn.commit()` référence une variable jamais assignée dans `pull_push()` (elle n'existe que dans `compute_cell_diff`, `apply_pull`, `apply_push`, `apply_resolution`, `touch_sync_state` — chacune la redéfinit localement) — un second NameError indépendant, qui se déclencherait si le premier était corrigé. Sur le chemin de résolution manuelle des conflits, `apply_resolution` (lignes 493-496) reproduit par ailleurs le bug `SET LOCAL` sous connexion `autocommit=True` déjà documenté dans l'audit LarcSecretaire (§1) — `cur.execute(f"SET LOCAL app.sync_source = '{source}'")` est un no-op silencieux, alors que la méthode sœur `apply_push` (lignes 434-437) utilise correctement `audit_context.attach(conn)`. `tests/test_sync.py` ne teste que les fonctions pures `_decide`/`_normalize`/`SyncReport` — aucun test n'exerce `pull_push`, `compute_cell_diff`, `apply_pull`, `apply_push` ou `apply_resolution`, ce qui explique que ces bugs n'aient jamais été détectés.

3. **0 % d'adoption de `phibuilder.widgets` dans toute l'application — pire que LarcSecretaire.** `grep -rl "phibuilder.widgets" views/ common/` ne retourne **aucun résultat** sur les 33 fichiers du périmètre ; `grep -c "theme=theme_manager" views/*.py common/*.py` ne retourne **aucune occurrence**. Les 18 fichiers de `views/` (login, dashboard, grille de notes, gestion des évaluations, fiche élève, dialogues) sont **entièrement construits avec des widgets PySide6 bruts** (`QLabel`, `QPushButton`, `QLineEdit`, `QComboBox`, `QFrame`, `QTabWidget`, `QScrollArea`, `QMenu`, `QTableWidget`…) et du QSS manuel via des propriétés `_STYLE`/`setStyleSheet`. C'est une régression par rapport à LarcSecretaire, où au moins 6 fichiers (`student_form.py`, `dossier_panel.py`, `parent_manager.py`, `password.py`, `notes_panel.py`, `todo_panel.py`) utilisaient correctement `phibuilder` avec `theme=theme_manager.phi_theme`. Dans LarcProf, la règle CLAUDE.md « jamais de `PySide6.QtWidgets` direct » n'est appliquée nulle part dans l'UI applicative — seuls les widgets composites de `LarcCommon` (`ThemedDialog`, utilisé comme classe de base des dialogues) portent une trace de la boîte à outils M3.

4. **Handlers Qt non protégés par `@safe_slot`, invisibles au linter (angle mort de `lint_safe_slot.py`).** Le linter ne détecte que les connexions directes `signal.connect(self._methode)` ; il manque deux patterns présents dans le code : (a) monkey-patch d'un event handler sur une instance — `views/main_notes.py:140` (`row.mousePressEvent = lambda event, ev=eval_type, si=idx: self._on_slot_icon_clicked(ev, si)`, cible `_on_slot_icon_clicked` ligne 174, **non décorée**), `views/prof_workspace.py:66-78` (`self._main_window.closeEvent = _intercept_close`, plus une variable `original_close` capturée et jamais utilisée), `views/home_window.py:719` (même pattern) ; (b) connexion via `functools.partial` à une méthode non décorée — `views/main_window.py:509,517,525,602` connectent `_on_toggle_all` (`main_notes.py:200`), `_on_toggle_none` (225), `_on_toggle_comment` (235), `_on_toggle_crit` (241) — aucune des quatre n'a `@safe_slot`. `views/grid_table.py:253-259` connecte le menu contextuel (`Fiche détaillée`, `Absence`, `Retard`…) à `_open_student_card`/`_add_event` via lambda, également non décorées. Ces méthodes sont exécutées dans la boucle d'événements Qt sans filet — seul l'excepthook global (`init_app` dans `main.py:15`) rattrape une exception non gérée, avec un message technique plutôt qu'un retour utilisateur propre.

5. **Duplication de code par mixins non nettoyée — bugs qui divergent entre copies quasi identiques.** `views/main_window.py`, `main_data.py`, `main_actions.py`, `main_notes.py` partagent le même docstring d'en-tête mot pour mot (« Fenêtre principale — Espace de travail du professeur… ») et un bloc d'imports PySide6 de ~20 lignes quasi identique dans les 4 fichiers, dont la majorité est inutilisée dans chaque mixin pris isolément (ex. `QMainWindow`, `QTableWidget` importés dans `main_data.py`/`main_actions.py` sans usage). Plus grave : `views/home_widget.py` (dashboard embarqué dans LarcHub) et `views/home_window.py` (dashboard standalone) réimplémentent la **même** fonctionnalité de synchronisation et de restyle indépendamment, et ont chacun un bug différent que l'autre n'a pas : `home_widget.py:648` fait `ok, msg = sync_manager.pull_push()` en dépaquetant un objet `SyncReport` (non itérable, dataclass sans `__iter__`) comme un tuple `(ok, msg)` → `TypeError` systématique au clic sur « Synchroniser » (rattrapé par le `try/except` local, message technique affiché) ; `home_window.py:731-737` traite correctement l'objet `SyncReport` retourné (`report.has_errors`, `report.summary()`). À l'inverse, `home_window.py:763` fait `self.centralWidget().setStyleSheet(self._STYLE())` — `_STYLE` est une `@property` (ligne 76), donc `self._STYLE()` tente d'appeler une **chaîne** comme une fonction → `TypeError` systématique à chaque changement de thème sur le dashboard standalone (rattrapé par `@safe_slot`, mais tout le reste de `_restyle` après cette ligne n'est jamais exécuté — aucun élément ne se re-style réellement) ; `home_widget.py:657-681` fait le même appel correctement (`self.setStyleSheet(self._STYLE)`, sans parenthèses). Deux copies de la même fonctionnalité, deux bugs différents : symptôme classique de copier-coller sans factorisation.

6. **Couverture de tests réelle : logique métier pure uniquement, aucun test des chemins qui contiennent les bugs ci-dessus.** Contrairement à LarcSecretaire (0 test), LarcProf a un dossier `tests/` (3 fichiers, 432 lignes, aucun `conftest.py`) : `test_calc_engine.py` (18 tests, SQLite temporaire réel, couvre `CalcEngine.get_formula/save_formula/compute_note/_apply_boundaries/_recalc_boundaries/get_templates_*`), `test_event_service.py` (11 tests, SQLite temporaire réel, couvre le CRUD `EventService`), `test_sync.py` (13 tests, mais **uniquement** les fonctions pures `_decide`, `_normalize`, la dataclass `SyncReport` — aucun test de `pull_push`, `compute_cell_diff`, `apply_pull`, `apply_push`, `apply_resolution`). Aucun test UI/Qt (`pytest-qt` absent), confirmé et cohérent avec un choix assumé de ne tester que la logique métier. Mais cette couverture n'inclut ni `sqlite_init.py` (0 test, cause racine n°1), ni les méthodes I/O de `sync.py` (cause racine n°2), ni `auth.py`, `database.py`, `session.py`, `theme.py` (9 P1 `lint_test_coverage.py`) — exactement les fichiers où se trouvent les bugs les plus sévères de cet audit.

## Détail par écran

### `common/sqlite_init.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 367, 371, 414, 465, 476, 502, 506, 515, 540, 564, 599, 689, 702, 733, 745, 752, 761, 782, 787, 801, 805, 827, 833 | bug confirmé — NameError | `log(...)` appelé 23× sans jamais être importé (seul `_log` l'est, ligne 11) — `init_intranet` crashe inconditionnellement dès la 2e instruction utile | P0 | `from .logger import log` en plus de `_log`, ou remplacer chaque `log(...)` par `_log(...)` |
| 900 lignes | lint_file_size | Juste sous la limite de 1000 — à surveiller avant tout ajout | P2 | Vigilance ; découpage DDL/logique déjà envisageable |

### `common/sync.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 183 | bug confirmé — NameError | `log(f'[SYNC] ...')` — `log` non importé (seul `_log` l'est, ligne 30) — crash dès la 1ère table de `BUSINESS_TABLES`, rattrapé par le `try/except` englobant → `pull_push()` ne synchronise jamais rien | P0 | Remplacer par `_log(...)` |
| 207 | bug confirmé — NameError | `local_conn.commit()` — variable jamais assignée dans `pull_push()` (définie seulement dans les autres méthodes) | P0 | `local_conn = db.local_conn` en tête de `pull_push()` |
| 493-496 | telemetry-review R2 | `apply_resolution` : `SET LOCAL app.sync_source/app.modified_by` sous connexion `autocommit=True` → no-op silencieux ; f-string non paramétré. `apply_push` (434-437) utilise le pattern correct (`audit_context.attach`) | P1 | Remplacer par `attach(server_conn)` / `refresh()` comme dans `apply_push` |
| 157, 174, 429, 445, 480, 485-487 (table/colonne interpolées en f-string) | SQL — remarque | Noms de table/colonne interpolés via f-string (paramétrage impossible en DB-API pour identifiants) — acceptable car provenant de constantes internes (`BUSINESS_TABLES`), pas d'entrée utilisateur | P2 (information, pas un défaut) | — |

### `views/main_window.py` / `main_data.py` / `main_actions.py` / `main_notes.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| tous les 4 fichiers | pyside6-wrapper W1 | 0 widget `phibuilder` — 100 % `QLabel`/`QPushButton`/`QComboBox`/`QFrame`/`QScrollArea`/`QMenu`/`QTableWidget` bruts (voir cause racine n°3) | P0 | Migration vers `phibuilder.widgets` + `theme=theme_manager.phi_theme` |
| `main_notes.py:140` | pyside6-review anti-pattern | `row.mousePressEvent = lambda ...` monkey-patché sur instance ; cible `_on_slot_icon_clicked` (174) non `@safe_slot` | P1 | Sous-classer un widget cliquable ou `installEventFilter` ; décorer la cible |
| `main_window.py:509,517,525,602` → `main_notes.py:200,225,235,241` | pyside6-review (angle mort lint_safe_slot) | `_on_toggle_all`, `_on_toggle_none`, `_on_toggle_comment`, `_on_toggle_crit` connectées via `partial()`, aucune `@safe_slot` | P1 | Ajouter le décorateur sur les 4 méthodes |
| `main_window.py:254` | audit_design_system | `QSize(20, 20)` en dur | P2 | `QSize(ds.icon_sm, ds.icon_sm)` ou équivalent tokenisé |
| `main_window.py:302` | audit_design_system | `size=20` en dur (icône thème) | P2 | Token `ds.icon_*` |
| `main_window.py:39` | code mort | `from common.logger import log` importé, jamais utilisé dans le fichier | P2 | Retirer l'import |
| 4 fichiers, en-tête | duplication | Docstring identique + bloc d'imports PySide6 ~20 lignes dupliqué à l'identique dans les 4 mixins, en grande partie inutilisé par fichier (voir cause racine n°5) | P1 | Factoriser les imports communs, nettoyer les imports morts par mixin |
| `main_notes.py` 954 lignes | lint_file_size | Le plus gros fichier de LarcProf, juste sous la limite | P2 | Surveiller ; découpage déjà amorcé via les mixins (data/actions/notes) — poursuivre |

### `views/home_widget.py` / `home_window.py` / `prof_workspace.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| `home_widget.py:648` | bug confirmé — TypeError | `ok, msg = sync_manager.pull_push()` dépaquette un `SyncReport` (non itérable) comme un tuple — crash à chaque clic « Synchroniser » depuis LarcHub | P0 | `report = sync_manager.pull_push()` puis utiliser `report.has_errors/summary()` comme dans `home_window.py:731-737` |
| `home_window.py:763` | bug confirmé — TypeError | `self.centralWidget().setStyleSheet(self._STYLE())` — `_STYLE` est une `@property` ; l'appeler comme une fonction lève `TypeError`, tout le reste de `_restyle` (indicateurs connexion, labels sync) n'est jamais exécuté | P0 | `self.centralWidget().setStyleSheet(self._STYLE)` (sans parenthèses), comme `home_widget.py:661` |
| `prof_workspace.py:66-78`, `home_window.py:700-719` | pyside6-review anti-pattern | `closeEvent` monkey-patché sur l'instance de `MainWindow` (`self._main_window.closeEvent = _intercept_close`) ; `original_close` capturé (prof_workspace.py:66) jamais utilisé | P1 | Sous-classer ou passer un callback au constructeur ; retirer la variable morte |
| tous les 3 fichiers | pyside6-wrapper W1 | 0 widget `phibuilder` (voir cause racine n°3) | P0 (déjà comptabilisé transverse) | — |
| `home_widget.py` / `home_window.py` | duplication | Même dashboard réimplémenté deux fois (`_STAT_TABLE_LABELS`, `_PEI_BUTTONS`, `_DP_BUTTONS`, `_BTN_VIEW`, `_STYLE`, `_load_profile`, `_load_sync`, `_detect_programs`, `_do_sync`, `_restyle` quasi identiques) — cause directe des deux bugs P0 ci-dessus (voir cause racine n°5) | P1 | Extraire un mixin `DashboardDataMixin` partagé par `HomeWidget`/`HomeWindow` |

### `views/login.py` / `login_auth.py` / `login_creation.py` / `login_helpers.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| `login.py` entier | pyside6-wrapper W1 | 100 % widgets bruts (`QLabel`/`QLineEdit`/`QPushButton`/`QTabWidget`/`QStatusBar`/`QPlainTextEdit`), QSS géré à la main via `_STYLE` — écran d'entrée hors design system, comme dans LarcSecretaire | P0 (comptabilisé transverse) | Migration `phibuilder.widgets` |
| `login_auth.py:119,204,226,239,250,300,368`, `login.py:519`, `login_creation.py:136` | conséquence bug n°1 | Tous ces appels à `sqlite_init.init()` échouent systématiquement avec `NameError` tant que la cause racine n°1 n'est pas corrigée ; certains sont protégés par un `try/except` local (`login.py:518-523`), d'autres reposent uniquement sur `@safe_slot` | P0 (déjà comptabilisé cause racine n°1) | — |
| `password.py:89` | cohérence de type | `sqlite_init.save_session(session, new_pin)` — passe le singleton `Session`, pas un `AuthResult` comme le déclare la signature ; fonctionne par duck-typing (mêmes attributs) mais viole le contrat déclaré | P2 | Construire un `AuthResult` explicite ou élargir le type hint |
| `login_auth.py:395-403` | ui-quality | `QInputDialog.getText` brut pour la saisie du PIN de secours — cohérent avec le reste du fichier (W1) mais un composant standard non désigné dans la liste d'exceptions | P2 | Dialogue `phibuilder` dédié si migration W1 entreprise |

### `views/evaluation_panel.py` / `eval_manager.py` / `event_dialog.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| `evaluation_panel.py:707` | bug confirmé — NameError | `dlg.exec() == QDialog.Accepted` — `QDialog` jamais importé (import list lignes 9-24 ne le contient pas) — `_on_slot_clicked` (mode compact, clic sur un slot d'évaluation) crashe systématiquement ; rattrapé par `@safe_slot` (ligne 698) | P0 | `from PySide6.QtWidgets import QDialog` |
| `evaluation_panel.py` / `eval_manager.py` / `event_dialog.py` | pyside6-wrapper W1 | 0 widget `phibuilder` (voir cause racine n°3) ; ces 3 fichiers utilisent néanmoins `ThemedDialog`/`ds.theme_changed.connect(self._restyle)` de façon cohérente — meilleure hygiène QSS que le reste de l'app | P0 (comptabilisé transverse) | — |
| `evaluation_panel.py` 904 lignes | lint_file_size | 3 classes (`EvaluationDetailWidget`, `EvaluationDetailDialog`, `_SlotButton`, `EvaluationPanel`) dans un seul fichier, proche de la limite | P2 (déjà comptabilisé dans le macro, non recompté) | Un fichier par classe si le fichier grossit encore |

### `views/grid_table.py` / `weight_dialog.py` / `student_card_view.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| `grid_table.py:253-259` | pyside6-review (angle mort lint_safe_slot) | Menu contextuel : `menu.addAction(..., lambda: self._open_student_card(student_id))` etc. — cibles `_open_student_card`/`_add_event` non `@safe_slot` | P1 | Décorer les méthodes cibles |
| `weight_dialog.py:590-591` | lint_preflight C13 | `if not self._is_editor: self.accept(); return` — professeur en lecture seule : le dialogue se ferme sans aucun message (le linter le signale comme `return` muet, bien que le comportement — fermeture silencieuse pour un rôle non-éditeur — soit probablement voulu) | P2 | Ajouter un message discret ("Lecture seule — droits réservés à Directeur/Coordonnateur") avant `accept()` si un retour explicite est souhaité |
| `weight_dialog.py`, `student_card_view.py` | Conforme | Usage cohérent de `ds.*`, `theme_manager.palette`, `ThemedDialog`, `_restyle` — parmi les fichiers les mieux tenus de l'app malgré l'absence de `phibuilder` | — | — |
| `grid_table.py`, `weight_dialog.py`, `student_card_view.py` | pyside6-wrapper W1 | 0 widget `phibuilder` (voir cause racine n°3) | P0 (comptabilisé transverse) | — |

### `common/theme.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 37, 42, 54, 59, 129, 134 | zero-hardcoding (non détecté par les linters — QSS généré dynamiquement) | `height: {height}px` (paramètre par défaut `22`), `padding: 0 8px` en dur dans `btn_toggle_style`/`btn_toggle_style_dark`/`btn_crit_style` | P2 | `height: ds.field_height`-dérivé, `padding: 0 {ds.space_xs}px` |
| 7-12 | design — remarque | `ZONE_F_COLOR`/`ZONE_S_COLOR`/etc. hex fixes, explicitement documentés comme choix visuel indépendant du thème (commentaire ligne 5-6) — dérogation assumée, pas un oubli | — (information) | — |

### `common/database.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 31-32 | bug confirmé (branche rare) — NameError | Fallback `find_cfg()` (si `larccommon.config_loader` était absent) appelle `log(...)` non importé dans ce scope (seul `_log` l'est) | P1 | Remplacer par `_log(...)` |
| 191-199 | Conforme | `before_update()` utilise correctement `audit_context.attach(conn)`/`refresh()` — bon contre-exemple, cohérent avec `sync.py:apply_push` | — | — |

### `common/auth.py`, `session.py`, `calc_engine.py`, `event_service.py`, `logger.py`, `network.py`, `grid_config.py`, `eval_helpers.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| `event_service.py:157,170,173-174` | SQL non paramétré | `fetch_event_stats_for_students` : IN-clause construite par `','.join(str(sid)...)` et `date_from`/`date_to` interpolés directement en f-string dans la requête SQL (`DATE(se.event_at) = '{today}'`, `BETWEEN '{date_from}' AND '{date_to}'`) — `student_ids` sont des int internes (risque faible), mais `date_from`/`date_to` sont des paramètres de fonction appelables avec une chaîne arbitraire | P1 | Paramétrer avec `?` : `WHERE se.student_id IN ({placeholders})` + liste de valeurs, `AND DATE(se.event_at) BETWEEN ? AND ?` |
| `auth.py` (OAuth2Manager) | Conforme | PKCE correct (`code_verifier`/`code_challenge` S256), vérification `hd == 'arc-en-ciel.org'`, binding d'instance (email ↔ `module_config.email_professeur`) | — | — |
| `session.py`, `calc_engine.py`, `logger.py`, `network.py`, `grid_config.py`, `eval_helpers.py` | Conforme | Aucune violation trouvée à la lecture ; `calc_engine.py` particulièrement soigné (règles métier PEI/DP documentées en commentaires, `_apply_boundaries` avec justification du choix `<` vs intervalle fermé) | — | — |

### Couverture de tests (`tests/`)

| Constat | Sévérité | Correction suggérée |
|---|---|---|
| `test_calc_engine.py` (18 tests) et `test_event_service.py` (11 tests) : bonne couverture de la logique métier pure sur SQLite temporaire réel, patterns de setUp/tearDown propres | — (Conforme) | — |
| `test_sync.py` (13 tests) : ne couvre que `_decide`/`_normalize`/`SyncReport` — 0 test de `pull_push`, `compute_cell_diff`, `apply_pull`, `apply_push`, `apply_resolution` — c'est exactement là que se trouvent les 2 NameError de la cause racine n°2 | P1 | Ajouter des tests d'intégration SQLite (comme `test_event_service.py`) pour `pull_push`/`compute_cell_diff` a minima |
| Aucun `conftest.py`, aucun test sur `sqlite_init.py`, `auth.py`, `database.py`, `session.py`, `theme.py` (9 P1 `lint_test_coverage.py`) | P1 (déjà comptabilisé dans le macro) | Prioriser un test sur `sqlite_init.init_intranet()` — aurait détecté la cause racine n°1 immédiatement |
| Aucun test UI/Qt (`pytest-qt` absent) | — (information, choix assumé cohérent avec Phase 1 de `larc-testing`) | — |

## Conforme

- **`lint_safe_slot.py`, `lint_qss_hardcoding.py`, `lint_d1_color_checker.py`, `lint_db_checker.py`, `lint_auth_checker.py`, `lint_ui_quality.py`, `lint_palette_contrast.py`** : tous à 0 violation sur le périmètre LarcProf — bien meilleur score linter brut que LarcSecretaire (qui avait des violations sur 6 de ces 8 scripts).
- **`audit_theme_reactive.py`** : 14 classes protégées, 0 vulnérable — 100 % conforme, alors que LarcSecretaire avait 5 classes vulnérables.
- **`lint_db_checker` / `lint_auth_checker`** : 0 violation — aucune connexion `psycopg2` directe hors `common/database.py`, `AuthManager`/`OAuth2Manager` jamais contournés.
- **`common/database.py`, `common/session.py`** : réexports propres depuis `larccommon`, `before_update()` utilise le bon pattern d'audit (`audit_context.attach`/`refresh`), cohérent avec la sync unifiée LarcHub.
- **`common/auth.py`** : OAuth2 PKCE et vérification de domaine corrects ; binding d'instance explicite et clair.
- **`common/calc_engine.py`** : logique métier PEI/DP dense mais bien commentée, règles de calcul (solo_rule, bandes IB, arrondi) documentées inline pour tout logiciel tiers.
- **`tests/test_calc_engine.py`, `tests/test_event_service.py`** : contrairement à LarcSecretaire (0 test), présence d'une vraie suite de tests d'intégration sur SQLite temporaire pour la logique métier critique (calcul de notes, CRUD événements) — absent le reste de l'app (UI, sync I/O, bootstrap).
- **Fichiers > 1000 lignes** : aucun (le plus gros, `main_notes.py`, fait 954 lignes) — LarcProf est déjà découpé en mixins (`main_data.py`/`main_actions.py`/`main_notes.py`), contrairement à `student_form.py` (3472 lignes) dans LarcSecretaire. La duplication résultante (cause racine n°5) est le prix payé pour ce découpage non finalisé.
- **`weight_dialog.py`, `student_card_view.py`, `eval_manager.py`, `evaluation_panel.py`, `event_dialog.py`** : usage cohérent de `ds.*` et `theme_manager.palette`/`ThemedDialog`/`_restyle` malgré l'absence de `phibuilder.widgets` — la discipline design-tokens est réelle même sans la boîte à outils M3.

## Audit design/graphisme — cohérence LarcCommon/phibuilder (complément)

Complément à l'audit ci-dessus, focalisé sur l'angle design/graphisme et sur la comparaison avec les 3 correctifs `f10741f`/`b46b526`/`9a4a077` posés le 2026-09-14 sur LarcCommon/phibuilder pendant l'audit de LarcSuperviseur. Méthode : lecture directe de `LarcCommon/larccommon/theme.py` (valeurs hex réelles des 4 thèmes, pas déduites) + lecture intégrale des fichiers `views/` cités + calcul de contraste WCAG (luminance relative sRGB) sur les paires de couleurs trouvées en thème `dark`, plutôt qu'une évaluation à l'œil. Confirmation préalable du constat du 1er rapport : `grep -rl "phibuilder.widgets" LarcProf` ne retourne que 3 fichiers (`views/login.py`, `views/login_helpers.py`, `__main__.py`) — aucun ne l'importe réellement pour un widget M3 (à vérifier, mais hors périmètre ici) ; `grep "theme=theme_manager|theme=phi"` : 0 occurrence confirmée. `LarcProf` lit bien `theme_manager.palette` en direct, mais via un shim local `common/theme.py` (153 lignes lues intégralement) qui réexporte `larccommon.theme.theme_manager` derrière un wrapper `ThemeManagerWrapper` — donc la source de vérité couleur est la même que LarcCommon (pas une copie divergente), ce qui rend les 3 bugs LarcSuperviseur directement transposables valeur pour valeur.

### Valeurs réelles lues dans `LarcCommon/larccommon/theme.py` (thème `dark`)

| Token | Hex | Ligne |
|---|---|---|
| `primary` | `#1F4494` | 181 |
| `surface` | `#1E293B` | 194 |
| `background` | `#0F172A` | 200 |

Ce sont exactement les couleurs en cause dans `f10741f` (`p.primary` sur `p.surface`). Contrastes calculés (luminance relative sRGB, formule WCAG) :
- `#1F4494` sur `#1E293B` → **≈ 1.6:1**
- `#1F4494` sur `#0F172A` → **≈ 2.0:1**

Seuils WCAG AA : 4.5:1 (texte normal), 3:1 (texte large ≥ 18px ou ≥ 14px gras). Les deux ratios calculés sont donc en échec, y compris pour le texte large/gras.

### P0 — Contraste KPI illisible en thème dark, reproduit indépendamment (convergence directe avec `f10741f`)

| Fichier:Ligne | Widget | Fond du panneau | Couleur texte | Contraste calculé | Constat |
|---|---|---|---|---|---|
| `views/home_widget.py:298` et `:678` | `_lbl_sync_count` (36px bold, chiffre « à synchroniser ») | `QFrame#sync_card` → `p.surface` (ligne 111-114) | `theme_manager.palette.primary` | ≈ 1.6:1 | Identique en pixel-couple à la paire corrigée par `f10741f` dans `QssHelper.kpi_common()` — mais ce label n'utilise pas `QssHelper`, il a son propre QSS inline (`_STYLE` property), donc le correctif LarcCommon ne le couvre pas |
| `views/home_window.py:101` (QSS `#sync_count`) | `_lbl_unsynced_count` (36px bold, doublon du même KPI dans la version standalone) | `QFrame#sync_card` → `p.surface` | `p.primary` | ≈ 1.6:1 | Même bug, 2ᵉ occurrence — conséquence de la duplication `home_widget.py`/`home_window.py` déjà documentée en cause racine n°5 du rapport principal : le bug de contraste, comme les 2 bugs `TypeError` déjà relevés, existe dans les deux copies |
| `views/student_card_view.py:141` (QSS `#jval`) | Valeur « Jugement » (22px bold) | `QFrame#judgment_panel` → `p.surface` (ligne 119-122) | `p.primary` | ≈ 1.6:1 | 3ᵉ occurrence indépendante, fichier distinct, même paire de tokens |
| `views/student_card_view.py:575-576` | `_note_display` (« Note prévue », 16px bold) | `QWidget#root` → `p.background` (ligne 104) | `p.primary` | ≈ 2.0:1 | Variante sur `p.background` plutôt que `p.surface` — toujours en échec du seuil AA texte large (3:1) |
| `views/home_widget.py:109` / `home_window.py:92` (QSS `#profile_role`) | Rôle utilisateur (13px bold) | `QFrame#profile_card` → `p.surface` | `p.primary` | ≈ 1.6:1 | Texte plus petit, mais même paire — échec du seuil (3:1 même en gras à cette taille) |
| `views/home_widget.py:125` / `home_window.py:121` (QSS `#pgm_title`) | Titre section « PEI »/« DP » (14px bold) | `QFrame#pgm_card` → `p.surface` | `p.primary` | ≈ 1.6:1 | Idem |

**Analyse de la cause** : `f10741f` a corrigé `QssHelper.kpi_common()` dans `LarcCommon/larccommon/theme.py` (partagé par toutes les apps qui l'appellent). Mais LarcProf n'appelle `QssHelper.kpi_common()` nulle part (cohérent avec le constat 0 % `phibuilder` du 1er rapport — LarcProf ne consomme aucun helper QSS partagé pour ses cartes, il réécrit son propre QSS à la main dans chaque `_STYLE` property). Résultat : le bug corrigé côté LarcCommon/LarcSuperviseur **existe toujours, indépendamment, dans LarcProf**, sous la même forme exacte (texte `primary` sur fond `surface`/`background` en thème dark) mais à 6 endroits distincts au lieu d'un seul point central — donc plus coûteux à corriger (pas de fonction commune à patcher une fois).

### P0 — `home_window.py:763` : le bug déjà signalé (P0, rapport principal) empêche aussi la correction du contraste de se propager

Le rapport principal a déjà relevé `self.centralWidget().setStyleSheet(self._STYLE())` (appel de `_STYLE` comme une fonction alors que c'est une `@property`) comme `TypeError` systématique au changement de thème. Complément design : cette ligne est **avant**, dans l'ordre d'exécution de `_restyle()`, toute tentative de réappliquer `#sync_count`/`#profile_role`/`#pgm_title` — donc même si un correctif de contraste était posé dans le QSS de `home_window.py`, il ne serait **jamais réappliqué** après un changement de thème à chaud (seule la valeur figée à la construction s'affiche, cf. bug suivant). Les deux bugs (contraste + `_restyle` cassé) sont indépendants mais se cumulent au même endroit : l'utilisateur du dashboard standalone `HomeWindow` en thème dark voit un chiffre invisible dès le lancement, et rien ne change s'il navigue entre thèmes ensuite.

### Convergence avec les bugs LarcSuperviseur du 2026-09-14

| Bug LarcSuperviseur | Reproduit dans LarcProf ? | Détail |
|---|---|---|
| **`f10741f` — contraste `p.primary` sur `p.surface` en thème dark** | **Oui, reproduit indépendamment, 6 occurrences confirmées** (tableau ci-dessus) | Pas une régression du correctif (LarcProf n'a jamais consommé `QssHelper.kpi_common()`) — un bug jumeau, de la même famille (couleur de rôle mal choisie pour un texte de premier plan en thème dark), commis indépendamment dans le QSS inline propre à LarcProf. Le correctif LarcCommon ne peut pas le couvrir par ricochet puisque LarcProf ne l'appelle pas. |
| **`b46b526` — empilement `padding` vertical + `min-height` sur les lignes de table** | **Non reproduit.** LarcProf n'utilise pas `M3TableWidget`/`QssHelper` pour ses 2 `QTableWidget` bruts (`student_card_view.py:407`, `weight_dialog.py:370`) — la hauteur de ligne y est fixée via l'API `verticalHeader().setDefaultSectionSize(...)` (pixels, hors QSS) et non via un `min-height` CSS cumulable avec le `padding: {ds.space_xxs}px` de `::item` (4px, jamais 10px comme dans le bug source). Aucun appel à `resizeRowsToContents()` trouvé qui pourrait faire recalculer une hauteur plus grande. Vérifié par lecture directe des deux blocs QSS (`student_card_view.py:123-130`, `weight_dialog.py:377-379`) — divergence confirmée, pas supposée. |
| **`9a4a077` — widget stylé une fois à la construction, jamais reconnecté à `theme_changed`** | **Non reproduit au sens strict, mais un symptôme équivalent existe par un autre mécanisme.** `audit_theme_reactive.py` (0 classe vulnérable, 14 protégées) est confirmé exact à la lecture : toutes les classes visuelles citées dans la consigne (`home_window.py`, `home_widget.py`, `student_card_view.py`, `evaluation_panel.py`, `eval_manager.py`, `weight_dialog.py`, `main_window.py`, `password.py`, `event_dialog.py`) connectent bien `ds.theme_changed.connect(self._restyle)` et définissent un `_restyle`/`_restyle_all`. Contrairement à LarcSuperviseur, ce n'est donc pas une connexion manquante. **Mais** `home_window.py._restyle()` (ligne 763, déjà en P0 dans le rapport principal) **crashe à chaque exécution** avant de réappliquer le moindre style — l'effet observable pour l'utilisateur (le dashboard reste figé dans les couleurs de sa construction initiale après un changement de thème) est identique à celui du bug `9a4a077`, alors que la cause est différente (TypeError vs. `deleteLater()`/absence de connexion). `ColorDelegate.paint()` dans `grid_table.py:98` est à l'inverse un bon contre-exemple : il lit `theme_manager.palette.background` à chaque `paint()`, donc structurellement immunisé contre toute la classe de bug (pas de couleur mise en cache). |

### Autres écarts couleur relevés (hors périmètre direct des 3 bugs, mais même catégorie `color-rules` D3)

| Fichier:Ligne | Constat | Sévérité |
|---|---|---|
| `views/home_window.py:432,436,781,784` | `'#27ae60'` (vert) en dur au lieu de `theme_manager.palette.success`, dupliqué entre `_load_profile()` et `_restyle()` (même duplication que cause racine n°5 du rapport principal, mais ici sur une valeur couleur) — pas de garantie de cohérence si `success` change de teinte dans un futur thème | P1 |
| `views/student_card_view.py:587,590,592` | `'#2E7D32'` (vert) / `'#E65100'` (orange) en dur sur la checkbox de validation, alors que `p.success`/`p.warning` existent et sont utilisés correctement ailleurs dans le même fichier (ligne 565 `p.success`/`p.error`) | P1 |
| `views/main_window.py:267` | `color=pal.primary if pal is not None else '#1565C0'` — fallback hex en dur pour le cas `pal is None` (branche rare, icône de menu thème) | P2 |
| `common/theme.py:7-12` | `ZONE_F_COLOR`/`ZONE_S_COLOR`/`ZONE_NEUTRAL`/`ZONE_TEXT_LIGHT`/`ZONE_BORDER`/`ZONE_BTN_BG` en hex fixes — **dérogation assumée et documentée** (commentaire ligne 5-6 : « Fixes par choix visuel : elles ne suivent pas le thème actif »), déjà relevé en P2 par le rapport principal (ligne 133) ; vérifié que le pairage fond/texte (`ZONE_S_COLOR` bleu marine + `ZONE_TEXT_LIGHT` blanc) reste cohérent quel que soit le thème puisque les deux valeurs sont fixes ensemble — pas un cas de contraste cassé comme le tableau P0 ci-dessus | — (information, non recompté) |
| `views/evaluation_panel.py:152` | Icône emoji `'🔗'` (bouton « Lien » de la barre de formatage Markdown) au lieu de `md3_icon` — seule occurrence emoji trouvée sur l'ensemble du périmètre grep (`common/auth.py:39` et les glyphes `☑`/`☐`/`•` de `evaluation_panel.py` sont du texte de contenu/état, pas des icônes de bouton) | P2 |

### Ce qui est conforme (complément)

- **`common/theme.py` (153 lignes lues intégralement)** : shim correct, pas de copie divergente de palette — réexporte `larccommon.theme.theme_manager` via un wrapper fin ; la seule addition propre (`btn_toggle_style`/`btn_toggle_style_dark`/`btn_crit_style`) utilise correctement `ds.radius_xs`/`ds.space_xs` et les tokens de palette, à l'exception du paramètre `height: int = 22` en dur (déjà signalé P2 par le rapport principal, non recompté).
- **`grid_table.py:ColorDelegate.paint()`** : lecture live de `theme_manager.palette` à chaque peinture — pattern structurellement plus robuste que `_STYLE` property + `_restyle`, à considérer comme référence si LarcProf migre vers `phibuilder` un jour.
- **Hauteurs de table** : les 2 `QTableWidget` bruts de LarcProf pilotent leur hauteur de ligne par API (`setDefaultSectionSize`) et non par cumul de règles QSS — ce choix les met hors d'atteinte de la classe de bug `b46b526`, même sans utiliser `M3TableWidget`.
- **14/14 classes visuelles connectées à `theme_changed`** avec un `_restyle`/`_restyle_all` défini (confirmé par lecture, pas seulement par le linter) — largement au-dessus du niveau structurel de LarcSuperviseur avant `9a4a077`. Le seul point noir est l'exécution qui plante dans `home_window.py` (P0 déjà comptabilisé).

### Bilan chiffré du complément

| Sévérité | Nouveaux constats (angle design, non comptés dans le tableau macro du rapport principal) |
|---|---|
| P0 | 2 (contraste KPI multi-occurrences `p.primary`/`p.surface`-`background` en thème dark — 6 occurrences groupées en 1 constat P0 + le cumul avec le crash `_restyle` de `home_window.py:763`, déjà compté en P0 côté bug fonctionnel mais ajouté ici comme constat design distinct) |
| P1 | 2 (couleurs `success`/`warning` dupliquées en hex au lieu des tokens palette) |
| P2 | 2 (fallback hex `main_window.py:267`, emoji `evaluation_panel.py:152`) |
