# Audit complet — LarcConfig

Date : 2026-09-16
Périmètre : application entière (12 fichiers Python, 2772 lignes) — design system, patterns PySide6, tests, base de données, fonctionnel. Pas de modification de code — audit de constat uniquement.
Méthode : lecture intégrale des 12 fichiers `.py` (`main.py`, `__main__.py`, `views/*.py`, `common/db_access.py`, `tests/*.py`) + checklists `.claude/skills/*-review.md` (pyside6, design, infra, testing, feature) + linters partagés (`scripts/*.py`, avec `--dir LarcConfig` quand disponible) + **connexion réelle à PostgreSQL Intranet (`127.0.0.1:5432 NewLarcDB`) pour exécuter en direct les requêtes de `common/db_access.py` et vérifier leur schéma** — deux bugs (`get_roles`, `get_locations`) ont ainsi été reproduits en conditions réelles, pas seulement déduits de la lecture du code.

Contrairement aux audits LarcSecretaire/LarcProf, LarcConfig est explicitement décrit par l'utilisateur comme « à moitié terminé » : ce rapport porte donc autant sur la **complétude** (Volet B) que sur la qualité/les bugs (Volet A), plus un complément héritage LarcCommon (Volet C).

## Chiffres bruts des linters (filtrés LarcConfig)

| Script | Résultat LarcConfig |
|---|---|
| `lint_qss_hardcoding.py --dir LarcConfig` | 0 violation |
| `lint_d1_color_checker.py --dir LarcConfig --rule D1+J7+D3+D4+D5+D6+D7` | 4 violations : 1×D3 (`panel_accueil.py:539` — **faux positif**, voir Détail), 1×D6 (`panel_logs.py:102`), 2×D7 (`panel_temps.py:84,150` — naming, voir Détail) |
| `lint_safe_slot.py --dir LarcConfig` | 0 violation (angle mort confirmé par lecture manuelle — voir Causes racines n°4) |
| `lint_file_size.py --stats` | 0 fichier > 1000 lignes. Plus grand : `common/db_access.py` (590 l.) |
| `lint_test_coverage.py --dir LarcConfig` | 10 P1 — tous les modules sauf `panel_types.py` sans test dédié |
| `lint_db_checker.py --dir LarcConfig` | 0 violation |
| `lint_auth_checker.py --dir LarcConfig` | 2 P0 — `main.py:24,39` `session.is_authenticated` modifié hors LoginWindow. **Vérifié comme faux positif probable** : pattern identique (callback `_on_intranet_login`/`_on_cloud_login` passé à `LoginWindow(on_intranet_login=...)`) présent à l'identique dans `LarcCompta/main.py`, `LarcHub/main.py`, `LarcRH/main.py` — architecture intentionnelle du monorepo, pas spécifique à LarcConfig |
| `lint_ui_quality.py --dir LarcConfig` | 0 violation |
| `lint_preflight.py --dir LarcConfig` | 0 violation |
| `audit_theme_reactive.py --dir LarcConfig` | 1 classe vulnérable (`_ErrorsTab`, `panel_logs.py:102`) / 6 classes protégées |
| `audit_design_system.py --path LarcConfig` | 0 hardcoding |
| `lint_palette_contrast.py` | N/A (palette définie dans LarcCommon, testée globalement) |

**Note méthode — `lint_qss_hardcoding.py` et `lint_d1_color_checker.py` ont une liste `PROJECTS` codée en dur** (`LarcCommon/larccommon`, `LarcSuperviseur`, `LarcSecretaire`, `LarcProf`, `LarcHub`) qui **exclut LarcConfig** (ainsi que LarcRH/LarcCompta/LarcForge). Lancés sans `--dir`, ces deux linters ne scannent jamais LarcConfig et rapportent une fausse impression d'absence — les chiffres ci-dessus n'ont été obtenus qu'en forçant `--dir LarcConfig` explicitement. Un lancement `pre-commit`/CI standard (sans argument) laisse donc LarcConfig hors de portée de ces deux linters.

## Tableau macro par fichier

| Fichier | Lignes | PB total | P0 | P1 | P2 |
|---|---|---|---|---|---|
| `main.py` | 76 | 1 | 0 | 0 | 1 |
| `views/config_window.py` | 185 | 1 | 0 | 1 | 0 |
| `views/login.py` | 16 | 0 | 0 | 0 | 0 |
| `views/panel_accueil.py` | 555 | 2 | 1 | 0 | 1 |
| `views/panel_temps.py` | 428 | 2 | 0 | 0 | 2 |
| `views/panel_logs.py` | 251 | 3 | 2 | 1 | 0 |
| `views/panel_i18n.py` | 113 | 2 | 0 | 1 | 1 |
| `views/panel_types.py` | 168 | 3 | 0 | 1 | 2 |
| `views/panel_themes.py` | 63 | 1 | 0 | 0 | 1 |
| `views/panel_roles.py` | 41 | 1 | 0 | 0 | 1 |
| `views/panel_lieux.py` | 40 | 1 | 0 | 0 | 1 |
| `common/db_access.py` | 590 | 6 | 2 | 3 | 1 |
| Couverture de tests (`tests/`, 236 l., 2 fichiers) | 236 | 1 | 0 | 1 | 0 |
| **Total** | **2772** | **24** | **5** | **8** | **11** |

## Causes racines transverses

1. **Deux panneaux affichent silencieusement une table vide à cause de SQL désynchronisé du schéma réel — reproduit en direct contre PostgreSQL, pas déduit.** `common/db_access.py:get_roles()` (L40-44) sélectionne une colonne `is_adm` sur `larcauth_aecuser` qui **n'existe pas** (la vraie colonne la plus proche est `is_superuser` ; confirmé par `information_schema.columns` et par exécution réelle de la requête, qui lève `ERREUR: la colonne « is_adm » n'existe pas`). `common/db_access.py:get_locations()` (L207) sélectionne `id, fk_etablissement, nom_lieu` sur `larcauth_lieu`, dont les colonnes réelles sont `IDLieu, Lieu, fk_language, s_IDLieu` (aucune des 3 colonnes demandées n'existe ; la table contient pourtant 11 lignes réelles, vérifiées par `SELECT COUNT(*)`). Les deux `except:` nus (cause racine n°2) avalent l'erreur PostgreSQL sans log ni remontée — `RolesPanel` et `LieuxPanel` affichent donc en permanence un tableau vide, sans aucun message d'erreur, quel que soit le contenu réel de la base. C'est un bug bloquant de premier ordre, invisible à toute lecture statique ou à tout linter — seule l'exécution réelle contre le schéma l'a révélé.

2. **10 `except:` nus dans `common/db_access.py`, aucune télémétrie — cause directe du bug n°1.** Lignes 57 (`get_roles`), 209 (`get_locations`), 227 (`get_logs`), 259 (`get_errors`), 281 (`get_error_detail`), 299 (`get_audit`), 404 (`save_annee`), 433 (`save_trimestre`), 462 (`save_unite`), 589 (`get_audit_meta`) : toutes avalent **toute** exception (y compris une erreur de schéma comme ci-dessus) et retournent silencieusement `[]`/`None`/`False`, sans appel à `log_error()` ni `get_reporter().report_exception()`. À l'inverse, `get_temps()` (L383-387), `get_stats()` (L567-571) et `activate_event_type()` (L194-198) suivent correctement le pattern R1 (`error_reporting`/`log_error`). Cette incohérence — 10 fonctions muettes contre 3 correctement instrumentées — explique pourquoi les deux bugs de schéma de la cause n°1 n'ont jamais été détectés en usage : rien dans les logs `error_log`/console n'indique jamais qu'une requête a échoué.

3. **Filtres de recherche cosmétiques dans `panel_logs.py` — les valeurs sélectionnées sont perdues avant l'appel DB, indépendamment des bugs de `db_access.py`.** `_ErrorsTab.reload()` (L141-142) : `app, user, _t, frm, to = self.filters.params()` puis `get_errors(app, None, frm, to)` — la valeur `user` sélectionnée dans le combo « Utilisateur » est capturée puis remplacée par `None` : le filtre par utilisateur sur l'onglet Erreurs ne fait jamais rien. `_AuditTab.reload()` (L203-204) : `app, user, table, frm, to = self.filters.params()` puis `get_audit(None, table, frm, to)` — **`app` et `user` sont tous deux abandonnés**, et `get_audit()` n'a même pas de paramètre `app_name` dans sa signature (L285) : le filtre « App » de l'onglet Audit est structurellement impossible sans modifier `db_access.py`. Complément : même en corrigeant le simple passage de `user`, la comparaison resterait cassée — `get_audit_meta()` (L574-588) peuple le combo « Utilisateur » avec `user_name` (texte, `SELECT DISTINCT user_name FROM audit_log`), alors que `_filters()` (L231-244) compare `AND user_id = %s` sur une colonne `integer` (vérifié via `information_schema.columns` : `user_id integer`, `user_name text` dans `error_log` et `audit_log`) — un type mismatch qui lèverait une erreur PostgreSQL, elle-même avalée par le bare `except:` de la cause n°2.

4. **Angle mort de `lint_safe_slot.py` : la navigation principale de l'application n'est pas protégée.** `views/config_window.py:86` connecte les 8 boutons de la sidebar via `btn.clicked.connect(lambda checked, k=key: self._switch(k))` ; la cible `_switch()` (L114-126, qui construit et bascule sur chacun des 8 panneaux) n'a **pas** de décorateur `@safe_slot` — seuls `_on_topbar_theme` et `_restyle_all` le sont dans ce fichier. Le linter ne détecte pas les connexions enveloppées dans un lambda (même angle mort déjà documenté dans l'audit LarcProf). Une exception levée pendant la construction d'un panneau (ex. erreur DB non prévue) remonterait donc sans filet jusqu'à la boucle d'événements Qt, au lieu d'être proprement journalisée par `safe_slot`.

5. **Deux panneaux « coquille vide » partagent la même affordance trompeuse.** `panel_roles.py` (L33-37) et `panel_lieux.py` (L34-36) créent des `QTableWidgetItem` sans jamais retirer le flag `Qt.ItemIsEditable` (contrairement à `panel_types.py:_readonly_item()`, qui le fait explicitement). Un double-clic permet donc de modifier visuellement une cellule « Rôles » ou « Lieux », mais aucun `itemChanged`/`cellChanged` n'est connecté dans ces deux fichiers : la modification est perdue au prochain rafraîchissement, sans qu'aucun message ne prévienne l'utilisateur. Combiné à la cause n°1 (tables toujours vides), ces deux panneaux sont aujourd'hui les plus éloignés d'une fonctionnalité « Configuration des rôles »/« Configuration des lieux » telle qu'annoncée par leur nom et par le rôle de LarcConfig dans `CLAUDE.md`.

6. **Adoption `phibuilder`/`theme=` globalement excellente — meilleure que LarcSecretaire et LarcProf sur ce point précis.** Les 8 panneaux + `config_window.py` passent systématiquement `theme=theme_manager.phi_theme` (aliasé localement `phi`) à chaque widget `phibuilder`. Seul `views/login.py` (16 lignes) n'utilise aucun widget — attendu, car il ne fait que surcharger `_open_main_window()` sur la classe de base `larccommon.login.LoginWindow`, sans construire d'UI propre. Note de méthode : le grep `theme=phi` prescrit par `pyside6-review.md` (« règle G ») matche ~40 occurrences légitimes dans LarcConfig, car `phi = theme_manager.phi_theme` est le nom de variable local canonique enseigné par les skills `form-pattern.md`/`dashboard-pattern.md`/`data-entry-ui.md` eux-mêmes — ce grep ne peut pas distinguer la variable correcte d'un token littéral fautif ; aucune de ces occurrences n'est une violation réelle une fois vérifiée par lecture (`phi` est bien assigné à `theme_manager.phi_theme` en tête de chaque constructeur).

## Détail par fichier

### `main.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 24, 39 | lint_auth_checker (C2) | `session.is_authenticated = True` hors LoginWindow — flag levé par le linter, mais pattern identique et intentionnel dans `LarcCompta/main.py`, `LarcHub/main.py`, `LarcRH/main.py` (callback passé à `LoginWindow(on_intranet_login=...)`) | P2 (faux positif probable, à confirmer au niveau monorepo) | Si confirmé faux positif : whitelister ce pattern de callback dans `lint_auth_checker.py` plutôt que de modifier le code |

### `views/config_window.py`

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 86, 114 | pyside6-review (angle mort lint_safe_slot) | `_switch()` connectée via lambda depuis les 8 boutons de la sidebar, non `@safe_slot` (voir cause racine n°4) | P1 | Ajouter `@safe_slot("ConfigWindow.switch")` |

### `views/panel_accueil.py` (555 lignes)

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 370 (KpiCard) | Héritage LarcCommon (voir Volet C) | `KpiCard(..., "primary")` — contraste texte/fond ≈ 1.6:1 en thème dark, bug hérité de `larccommon/widgets/kpi.py`, pas du code LarcConfig | P0 | Voir Volet C — correction côté `LarcCommon/larccommon/widgets/kpi.py` |
| 539-540 | lint_d1_color_checker (D3) | Linter signale `#acc` comme hex hardcodé — **faux positif** : c'est `#accueil_container` (sélecteur d'ID Qt) mal reconnu par la regex du linter (`{c}QWidget#accueil_container{{ background: {p.background}; }}`), aucune couleur hex n'est en dur dans ce code | — (information, non compté) | Affiner la regex D3 du linter pour ignorer les sélecteurs `#nom_objet` suivis d'espace/accolade |
| 77, 332, 347, 404 | pyside6-wrapper W1 | `QLabel()` brut ×4 (titre `_ChartCard`, icônes « aujourd'hui »/états vides) au lieu de `M3Label` | P2 | Remplacer par `M3Label` (cohérence à terme, faible impact visuel) |

### `views/panel_temps.py` (428 lignes)

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 84, 104, 110-119 | lint_d1_color_checker (D7) / naming | `_SectionCard` connecte `ds.theme_changed` à une méthode nommée `_style()` (pas `_restyle()`) — le linter D7 la classe « inefficace » par convention de nom, mais `audit_theme_reactive.py` (sans `--rule` strict) confirme que la classe est bien protégée : `_style()` fait le même travail qu'un `_restyle()` standard | P2 (confusion outillage, pas un bug fonctionnel) | Renommer `_style` → `_restyle` pour lever l'ambiguïté entre les deux linters |
| 95, 238, 277-278 | pyside6-wrapper W1 | `QLabel()` ×2 (titre `_SectionCard`, icône héros) et `QSpinBox()` ×2 (trimestre/unité courants) bruts | P2 | Remplacer par `M3Label`/équivalent phibuilder si disponible pour spinbox |

### `views/panel_logs.py` (251 lignes)

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 141-142 | bug confirmé | `_ErrorsTab.reload()` : `user` capturé depuis les filtres puis remplacé par `None` dans `get_errors(app, None, frm, to)` — le filtre « Utilisateur » de l'onglet Erreurs ne fait jamais rien | P0 | `get_errors(app, user, frm, to)` — puis résoudre le mismatch texte/id (voir ligne suivante) |
| 203-204 | bug confirmé | `_AuditTab.reload()` : `app` ET `user` capturés puis abandonnés dans `get_audit(None, table, frm, to)` ; `get_audit()` n'a de toute façon pas de paramètre `app_name` (voir `db_access.py`) | P0 | Passer `user` ; étendre `get_audit()`/`_filters()` avec `app_name` (voir `db_access.py`) |
| 102, 122-130 | audit_theme_reactive (D6) | `_ErrorsTab.detail` (QTextEdit) stylé une seule fois à la construction avec des couleurs palette (`theme_manager.palette.outline`/`text_strong`), aucun `ds.theme_changed.connect` dans la classe | P1 | Ajouter `ds.theme_changed.connect(self._restyle)` + méthode `_restyle()` |

### `views/panel_i18n.py` (113 lignes)

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 110-113 | risque fonctionnel | `_save()` écrit directement `LarcCommon/larccommon/l10n/fr.json` et `en.json` — fichiers **partagés par les 6+ applications du monorepo** (~662 clés selon `CLAUDE.md`) — sans confirmation, sans diff, sans sauvegarde. Une faute de frappe ou un `Enregistrer` accidentel affecte toutes les apps immédiatement | P1 | Ajouter une confirmation avant écrasement + option d'export/backup avant `save_json` |
| — | complétude (Volet B) | Pas d'action de suppression de clé (CRUD incomplet : Create + Update, pas de Delete) | P2 | Ajouter une action « Supprimer la clé » sur la ligne sélectionnée |

### `views/panel_types.py` (168 lignes)

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 137 | pyside6-wrapper E1 | `ok_btn = M3Button("Créer")` dans `_on_create_type` — `theme=` manquant (émet un `UserWarning` selon la règle E1 depuis 2026-09-08) | P1 | `M3Button("Créer", theme=theme_manager.phi_theme)` |
| 125 | pyside6-wrapper W1 | `QDialog(self)` brut au lieu de `M3Dialog` | P2 | Remplacer si un équivalent phibuilder existe |
| 128, 130, 131, 132 | pyside6-wrapper W1 | `QLineEdit()` brut ×4 dans le dialogue de création | P2 | Remplacer par `M3TextField` |

### `views/panel_themes.py` (63 lignes)

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 45-46 | code smell | `from PySide6.QtWidgets import QHBoxLayout` et `from phibuilder.widgets import M3Button` réimportés à chaque itération de la boucle interne (4 thèmes × 12 champs = 48 exécutions) | P2 | Déplacer les deux imports en tête de fichier |

### `views/panel_roles.py` (41 lignes)

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 33-37 | ui-quality / affordance trompeuse | `QTableWidgetItem` créés sans retirer `Qt.ItemIsEditable` (contrairement à `panel_types.py:_readonly_item()`) — cellules visuellement éditables par double-clic, aucune sauvegarde connectée | P2 | Retirer le flag `Qt.ItemIsEditable`, comme `panel_types.py` |
| — | bug confirmé — voir `db_access.py:get_roles()` | Le tableau est en réalité **toujours vide** en conditions réelles (voir cause racine n°1) | P0 (comptabilisé sur `db_access.py`) | — |

### `views/panel_lieux.py` (40 lignes)

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 34-36 | ui-quality / affordance trompeuse | Même constat que `panel_roles.py` : cellules éditables en apparence, aucune sauvegarde | P2 | Retirer le flag `Qt.ItemIsEditable` |
| — | bug confirmé — voir `db_access.py:get_locations()` | Tableau toujours vide malgré 11 lignes réelles dans `larcauth_lieu` (voir cause racine n°1) | P0 (comptabilisé sur `db_access.py`) | — |

### `common/db_access.py` (590 lignes)

| Ligne | Règle/Catégorie | Constat | Sévérité | Correction suggérée |
|---|---|---|---|---|
| 40-44 | bug confirmé (reproduit en direct) | `get_roles()` sélectionne `is_adm` sur `larcauth_aecuser` — colonne inexistante (`ERREUR: la colonne « is_adm » n'existe pas`, reproduit via connexion réelle ; colonnes réelles : `type_supervisor/type_coordonator/type_secretary/is_superuser`) → `RolesPanel` toujours vide | P0 | `is_adm` → `is_superuser` (ou colonne équivalente réelle à confirmer avec le métier) |
| 201-208 | bug confirmé (reproduit en direct) | `get_locations()` sélectionne `id, fk_etablissement, nom_lieu` sur `larcauth_lieu` — aucune des 3 colonnes n'existe (réelles : `IDLieu, Lieu, fk_language, s_IDLieu`, table non vide : 11 lignes) → `LieuxPanel` toujours vide | P0 | Réécrire la requête sur le schéma réel — `s_IDLieu`/`fk_language` suggèrent une table par langue, à clarifier avec le modèle `larcauth_event_type_config` |
| 285-300 | bug confirmé (cause racine n°3) | `get_audit()` n'a pas de paramètre `app_name` — le filtre « App » de `_AuditTab` ne peut jamais fonctionner, quel que soit l'état de `panel_logs.py` | P1 | Ajouter `app_name=None` à la signature et le transmettre à `_filters()` |
| 231-244, 574-588 | bug confirmé (cause racine n°3) | `_filters()` compare `user_id` (colonne `integer`, vérifié) alors que `get_audit_meta()` peuple les combos avec `user_name` (colonne `text`) — mismatch de type qui échouerait même si la valeur était transmise | P1 | `get_audit_meta()` doit renvoyer des paires `(user_id, user_name)`, combos à peupler avec l'id comme `itemData` |
| 57, 209, 227, 259, 281, 299, 404, 433, 462, 589 | telemetry-review R1 (cause racine n°2) | 10× `except:` nu, aucun log ni `error_reporting`, contre 3 fonctions correctement instrumentées (`get_temps`, `get_stats`, `activate_event_type`) | P1 | Remplacer par `except Exception as e:` + `log_error()`/`get_reporter().report_exception()`, cohérent avec le reste du fichier |
| 213-228 | code mort | `get_logs()` définie, jamais importée ni appelée (`panel_logs.py` utilise `get_errors`/`get_audit` à la place) ; son docstring évoque un « ancien audit_trail » alors qu'elle interroge `audit_log` (même table que `get_audit`) | P2 | Supprimer, ou documenter son rôle réel si conservée intentionnellement |

### Couverture de tests (`tests/`)

| Constat | Sévérité | Correction suggérée |
|---|---|---|
| 9 tests (2 fichiers, 236 lignes), tous passent (`pytest LarcConfig/tests/ -v` → 9 passed) — bonne couverture ciblée de `panel_types.py`/`get_event_types`/`set_event_type_*`/`activate_event_type`, y compris un test de non-régression sur le bug d'indentation tronquée | — (Conforme, seul panneau testé) | — |
| Aucun `conftest.py`, aucune fixture `mock_db`/`mock_session` partagée ; 10 modules sur 12 sans aucun test dédié (`db_access.py` lui-même n'est testé que sur 4 de ses ~15 fonctions — aucun test sur `get_roles`, `get_locations`, `get_errors`, `get_audit`, `get_temps`, `save_*`, `get_stats`) | P1 (comptabilisé une fois) | Un test d'intégration minimal sur `get_roles()`/`get_locations()` (même mocké au niveau curseur) aurait détecté immédiatement les deux bugs P0 de la cause racine n°1 |
| Aucun test UI/Qt hors `panel_types.py` (`config_window.py`, tous les autres panneaux) | — (déjà comptabilisé) | — |

## Complétude par panneau (Volet B)

| Panneau | Statut | Ce qui manque | Effort estimé |
|---|---|---|---|
| `views/panel_accueil.py` (555 l.) | **Fonctionnel** | Dashboard complet et connecté (`get_temps`/`get_stats`, états vides gérés proprement, frise + KPI + graphiques). Seul défaut : contraste du KPI « Année » en thème dark (hérité de LarcCommon, Volet C) | Faible (< 1h, cosmétique) |
| `views/panel_temps.py` (428 l.) | **Fonctionnel** | CRUD complet (année/3 trimestres/6 unités, UPDATE-first + INSERT de repli), sauvegarde par onglet actif. Ergonomie mineure : pas de « tout sauvegarder » en un clic, naming `_style`/`_restyle` à clarifier | Faible |
| `views/panel_logs.py` (251 l.) | **Partiel** | Les deux onglets chargent et affichent de vraies données (`get_errors`/`get_audit` fonctionnent), mais 3 des 4 filtres promis par l'UI sont cosmétiques : « Utilisateur » (onglet Erreurs), « App » et « Utilisateur » (onglet Audit) ne changent jamais le résultat (cause racine n°3). `get_audit()` n'a structurellement pas de filtre App | Moyen (0,5-1 j : câblage des valeurs + `app_name` sur `get_audit` + résolution `user_id`/`user_name`) |
| `views/panel_i18n.py` (113 l.) | **Partiel** | Édition/ajout/sauvegarde fonctionnels sur les fichiers `fr.json`/`en.json` partagés par tout le monorepo. Manque : suppression de clé, recherche/filtre dans ~662 clés listées à plat, confirmation avant écrasement d'un fichier partagé | Moyen (0,5 j) |
| `views/panel_types.py` (168 l.) | **Fonctionnel** | CRUD quasi complet (activation de slot gabarit — conforme au principe « jamais d'INSERT »/toujours UPDATE —, édition de libellé inline, activation/désactivation), seul panneau testé (9 tests). Manque : pas de désactivation groupée, `theme=` manquant sur un bouton | Faible |
| `views/panel_themes.py` (63 l.) | **Fonctionnel** (pour son périmètre déclaré) | Visualisation en lecture seule des 4 palettes — cohérent avec le fait que les thèmes sont codés en dur dans `theme.py` (`CLAUDE.md` : ajouter un thème = édition de code). Aucune action de configuration (sélection du thème par défaut, etc.) — hors périmètre actuel, pas un manque au sens strict | N/A à moyen si le périmètre doit s'élargir |
| `views/panel_roles.py` (41 l.) | **Coquille vide / cassée** | Liste en lecture seule censée afficher utilisateurs + rôles calculés, mais **toujours vide en pratique** : `get_roles()` référence une colonne SQL inexistante (`is_adm`), confirmé en conditions réelles. Aucune attribution/retrait de rôle, aucune recherche. Le nom du panneau et le rôle « rôles » de LarcConfig dans `CLAUDE.md` laissent attendre une vraie gestion | Élevé (corriger la requête = 15 min ; ajouter la gestion de rôles = 1-2 j) |
| `views/panel_lieux.py` (40 l.) | **Coquille vide / cassée** | Même diagnostic : `get_locations()` référence 3 colonnes SQL inexistantes sur `larcauth_lieu`, confirmé en conditions réelles (11 lignes réelles, jamais affichées). 0 création/édition/suppression de lieu | Élevé (corriger la requête = 15-30 min après clarification du schéma ; CRUD complet = 0,5-1 j) |
| `views/config_window.py` (185 l.) | **Fonctionnel** | Orchestrateur complet : topbar, sidebar 8 sections, navigation par pile, réactivité thème avec cas spécial pour widgets figés à la construction (pattern LarcRH documenté en commentaire). Seul défaut : `_switch()` non protégée par `@safe_slot` | Faible |
| `common/db_access.py` (590 l.) | **Fonctionnel avec lacunes ciblées** | Toutes les fonctions attendues par les 8 panneaux existent et exécutent de vraies requêtes SQL paramétrées. Lacunes concrètes : 2 requêtes cassées par désynchronisation de schéma (bloquantes), `get_audit()` sans filtre App, 10 fonctions sans télémétrie d'erreur | Moyen (corrections ciblées : 1 j au total) |

**Travail bloquant côté schéma identifié** : les colonnes utilisées par `get_roles()` (`is_adm`) et `get_locations()` (`id`, `fk_etablissement`, `nom_lieu`) n'existent pas dans le schéma PostgreSQL réel (vérifié par connexion directe le 2026-09-16). Ce n'est pas une table manquante — les deux tables (`larcauth_aecuser`, `larcauth_lieu`) existent et contiennent des données — mais un désalignement pur entre le code LarcConfig et le schéma actuel, probablement dû à un renommage de colonnes fait ailleurs dans le monorepo sans répercussion sur ces deux requêtes.

## Héritage LarcCommon — cohérence avec les correctifs `f10741f`/`b46b526`/`9a4a077` (Volet C)

Méthode : `grep -rn "phibuilder.widgets"` confirme un usage réel et large de `phibuilder.widgets` dans LarcConfig (9 des 12 fichiers, voir cause racine n°6) — contrairement à LarcProf (0 %) et à l'essentiel de LarcSecretaire hors 6 fichiers. `grep -rn "KpiCard\(|M3TableWidget|QssHelper"` a servi à vérifier l'usage effectif des composants concernés par les 3 correctifs.

### `b46b526` — empilement padding/min-height sur les lignes de table

**Non reproduit.** 5 fichiers (`panel_i18n.py`, `panel_lieux.py`, `panel_logs.py`, `panel_roles.py`, `panel_types.py`) utilisent `M3TableWidget` et **aucun** n'ajoute de `setStyleSheet`/QSS additionnel sur le tableau ou ses lignes (vérifié par grep ciblé `setStyleSheet|::item|min-height|padding|setDefaultSectionSize|resizeRowsToContents|verticalHeader` — seul `panel_logs.py:125` a un `setStyleSheet`, sur le `QTextEdit` de détail, sans rapport avec les tables). LarcConfig consomme le widget partagé tel quel, sans QSS concurrent — hors d'atteinte de cette classe de bug par construction.

### `9a4a077` — widget stylé une seule fois, jamais reconnecté à `theme_changed`

**Reproduit une fois, sous une forme légèrement différente.** `audit_theme_reactive.py` confirme 6 classes protégées sur 7 avec QSS palette-dépendant, et **1 classe vulnérable : `_ErrorsTab`** (`panel_logs.py:102`, détail L122-130) — pas une reconnexion cassée comme dans le bug source, mais une classe qui n'a **jamais** connecté `ds.theme_changed` du tout. L'effet observable est identique : le panneau de détail des erreurs garde les couleurs du thème actif au moment de la construction de `ConfigWindow`, quel que soit le nombre de changements de thème ultérieurs.

### `f10741f` — contraste `p.primary` sur `p.surface` illisible en thème dark

**Reproduit indépendamment, via un widget partagé différent de celui corrigé.** LarcConfig n'a **aucune** occurrence de `QssHelper.kpi_common()` en appel direct dans son propre code (0 résultat), mais `panel_accueil.py:370` instancie `KpiCard(_("panel.accueil.year"), "school", "primary")` — le widget partagé `LarcCommon/larccommon/widgets/kpi.py` (utilisé aussi par `panel_accueil.py:371-372` avec les rôles `"active"`/`"success"`, et par `LarcForge/larcforge/ui/panels/dashboard_panel.py`, seuls consommateurs directs de cette classe dans le monorepo — LarcRH et LarcCompta ont leurs propres `_KpiCard` locaux, hors périmètre).

Lecture de `larccommon/widgets/kpi.py:100-113` (`KpiCard._restyle()`) : la méthode appelle bien `QssHelper.kpi_common(p, theme_manager.design, s)` (dont le `#kpi_value` est fixé à `p.text_strong` depuis `f10741f`, vérifié en lisant `theme.py:812`), **mais l'ajoute immédiatement après une règle QSS locale qui réécrit `QLabel#kpi_value { color: {accent} }`** (L108-109), où `accent = getattr(p, self._accent_token, p.primary)`. En cascade CSS, cette seconde règle gagne : la couleur réellement appliquée au chiffre du KPI est celle du rôle passé en 3ᵉ argument du constructeur, pas `text_strong`.

Pour `self._kv_year = KpiCard(..., "primary")` en thème dark, cela réintroduit exactement la paire corrigée par `f10741f` :

| Token | Hex (thème dark, `theme.py`) |
|---|---|
| `primary` | `#1F4494` (ligne 181) |
| `surface` | `#1E293B` (ligne 194) |

Contraste calculé (luminance relative sRGB, formule WCAG) : **≈ 1.6:1** — en échec des deux seuils AA (4.5:1 texte normal, 3:1 texte large/gras), alors même que le texte est en 24px gras (`s(ds.font_headline_md)`). C'est la même paire, le même écart, que documenté dans le complément design de l'audit LarcProf — mais ici la cause est dans un composant `LarcCommon` **différent** de celui touché par `f10741f` (`larccommon/widgets/kpi.py`, pas la version LarcSuperviseur), donc non couvert par ce correctif. Les 2 autres cartes (`"active"`, `"success"`) ne sont pas concernées — leurs couleurs respectives contrastent correctement sur `surface` en dark (à vérifier au cas par cas si le thème change).

**Sévérité** : P0 — comptabilisé au tableau macro sur `panel_accueil.py`, correction à faire dans `LarcCommon/larccommon/widgets/kpi.py` (retirer l'override `color: {accent}` de `#kpi_value`, ou appliquer l'accent uniquement à la barre latérale/l'icône comme le fait déjà le reste du widget).

## Conforme

- **`lint_qss_hardcoding.py`, `lint_ui_quality.py`, `lint_preflight.py`, `lint_db_checker.py`, `audit_design_system.py`** : 0 violation sur LarcConfig une fois scannés avec `--dir` — aucun hardcoding pixel, aucune couleur hex en dur (hors le faux positif D3 documenté), aucun `psycopg2.connect()` direct hors `common/db_access.py`.
- **Adoption `phibuilder.widgets`/`theme=`** : la meilleure du monorepo à ce jour parmi les audits déjà menés (9/12 fichiers, 100 % des panneaux) — contraste net avec LarcProf (0 %) et les écrans `login.py`/`main_window.py` de LarcSecretaire.
- **SQL globalement paramétré** : tous les `execute()` de `db_access.py` utilisent `%s`, aucune interpolation f-string dans une requête (hors les 2 requêtes de la cause racine n°1, qui sont paramétrées correctement mais portent sur des colonnes inexistantes — un problème de schéma, pas d'injection).
- **Principe gabarit respecté** : `set_event_type_active`/`set_event_type_label`/`activate_event_type` (types d'événements) n'utilisent que des `UPDATE`, jamais de `DELETE`/`INSERT` non maîtrisé — `activate_event_type()` documente explicitement (commentaire L144-150) pourquoi la résolution des 2 langues se fait en 2 phases avant toute mutation, pour éviter un état incohérent sous `autocommit=True`.
- **`views/panel_types.py`** : seul panneau testé (9 tests, 2 fichiers), y compris un test de non-régression documenté et bien commenté sur un bug réel déjà corrigé (troncature du libellé lors d'une édition pleine cellule).
- **`views/config_window.py`** : gestion de la réactivité thème la plus soignée du périmètre — re-style du chrome (sidebar, fond, boutons) + délégation au panneau courant (`_restyle()` si disponible, sinon reconstruction complète), pattern documenté en commentaire comme repris de LarcRH.
- **0 emoji, 0 `QMessageBox`/`QInputDialog` en substitut d'icône ou de champ** trouvé dans tout le périmètre — meilleur score `ui-quality` que LarcSecretaire/LarcProf sur ce point précis.
- **`views/panel_accueil.py`** : gestion d'états vides propre et testée par construction (`_show_empty_data`/`_show_empty_stats`, `log_error` appelé sur échec, cohérent avec le reste du fichier).
