# LarcProf — Documentation fonctionnelle complète

Date : 2026-09-16
Périmètre : application entière (33 fichiers Python, ~11 960 lignes) — démarrage, authentification, tableaux de bord, fenêtre principale (grille de notes), système d'évaluations formatives/sommatives, moteur de calcul PEI/DP, synchronisation SQLite ↔ PostgreSQL, thème.
Méthode : lecture intégrale de chaque fichier du périmètre par 3 agents en parallèle (aucune supposition, citations `fichier:ligne` systématiques pour tout mécanisme non trivial), complétée par des tests en conditions réelles (log applicatif `elarc.log`, lecture directe de la base SQLite locale `elarc.db`) effectués le même jour pour vérifier certains comportements (notamment le mécanisme d'affichage des formatives/sommatives activées).

Ce document est la référence unique pour comprendre le fonctionnement actuel de LarcProf, en vue de la poursuite de son développement. Il complète (et corrige ponctuellement) les documents numérotés existants dans ce dossier (`01_introduction.md` à `20_eval_manager.md`).

## Sommaire

- Partie I — Démarrage, authentification, tableau de bord
- Partie II — Fenêtre principale et système d'évaluations
- Partie III — Moteur de calcul, synchronisation, thème

---

## Partie I — Démarrage, authentification, tableau de bord

**Périmètre documenté** : point d'entrée (`main.py`, `__main__.py`), écran de connexion (4 modes),
bootstrap de la base SQLite locale (`common/sqlite_init.py`), infrastructure
session/auth/DB/réseau/logs, et les trois tableaux de bord post-connexion
(`HomeWindow`, `HomeWidget`, `ProfWorkspace`).

**Méthode** : chaque affirmation non triviale est basée sur une lecture intégrale des fichiers
listés ci-dessous, avec citation `fichier:ligne`. Quand un comportement n'a pas pu être vérifié
avec certitude (dépendance à un fichier hors périmètre, schéma PostgreSQL non lu), c'est indiqué
explicitement par « comportement à vérifier ».

Fichiers lus intégralement :
`main.py`, `__main__.py`, `views/login.py`, `views/login_auth.py`, `views/login_creation.py`,
`views/login_helpers.py`, `views/password.py`, `common/sqlite_init.py`, `common/session.py`,
`common/auth.py`, `common/database.py`, `common/network.py`, `common/logger.py`,
`views/home_window.py`, `views/home_widget.py`, `views/prof_workspace.py`, ainsi que leurs
dépendances directes en lecture croisée : `LarcCommon/larccommon/session.py`,
`LarcCommon/larccommon/auth.py`, `LarcCommon/larccommon/network.py`,
`LarcCommon/larccommon/bootstrap.py` (extraits pertinents), `common/theme.py` (en-tête),
`common/sync.py` (dataclass `SyncReport` uniquement).

---

### 1. Point d'entrée — `main.py` et `__main__.py`

#### Rôle

`main.py` est le point d'entrée « riche » de l'application (utilisé par `lancer.bat` et par
l'exécution directe `python main.py` depuis le dossier `LarcProf/`). `__main__.py` est un point
d'entrée alternatif permettant `python -m LarcProf` depuis la racine du monorepo (`D:\projets`),
utilisé notamment par LarcHub pour lancer LarcProf comme sous-module.

#### Flux — `__main__.py`

1. `__main__.py:4-7` : calcule `_root` = dossier parent de `LarcProf/` (donc `D:\projets`) et
   l'insère en tête de `sys.path` s'il n'y est pas déjà — permet les imports `LarcProf.main`,
   `common.*`, `views.*` depuis la racine du monorepo.
2. `__main__.py:9-12` : calcule `_common_root` = `D:\projets\LarcCommon` et l'insère aussi dans
   `sys.path` (si le dossier existe) — permet `larccommon.*` et `phibuilder.*`.
3. `__main__.py:14` : `from LarcProf.main import main` — importe la fonction `main()` de
   `main.py` en tant que sous-module du package `LarcProf`.
4. `__main__.py:16-17` : `if __name__ == '__main__': main()`.

#### Flux — `main.py`

1. `main.py:4` : insère le dossier de `LarcProf/` lui-même en tête de `sys.path` (permet les
   imports relatifs `common.*`, `views.*` quand on lance `python main.py` directement, sans
   passer par `__main__.py`).
2. `main.py:14` : `set_debug(True)` (`larccommon.safe_slot`) — active l'affichage des erreurs de
   slots Qt directement dans l'UI (mode développement ; commentaire dans le code : « Dev: affiche
   les erreurs dans les slots »).
3. `main.py:15` : `init_app('LarcProf')` (`larccommon.bootstrap`) — initialise la télémétrie de
   l'application. D'après `LarcCommon/larccommon/bootstrap.py:152-186` :
   - Crée (si pas déjà fait, la fonction est idempotente via le flag global `_inited`) un
     `ErrorReporter('LarcProf', current_app_version(), cfg)` et l'enregistre comme reporter actif
     (`_set_reporter`) — la config est lue via `_load_error_reporting_cfg()` (config.ini) si non
     fournie.
   - `rep.start()` démarre le reporter (thread d'envoi/écriture des erreurs — implémentation hors
     périmètre de ce document).
   - `install_excepthooks()` (`bootstrap.py:49-64`) : remplace `sys.excepthook` et
     `threading.excepthook` par des handlers qui envoient l'exception au reporter puis
     l'impriment sur stderr (`traceback.print_exception`) — **aucune exception non gérée ne doit
     donc jamais faire planter silencieusement l'appli sans trace**.
   - `install_qt_message_handler()` (`bootstrap.py:90-100`) : installe un handler Qt
     (`QtCore.qInstallMessageHandler`) pour capturer les messages Qt (warnings internes, etc.).
   - `_create_lock()` (`bootstrap.py:123-137`) : écrit un fichier PID dans
     `<racine larccommon>/runtime/locks/LarcProf.pid` et enregistre sa suppression via
     `atexit.register`.
   - Si `check_updates=True` (valeur par défaut) : tente de planifier une vérification de mise à
     jour douce (`schedule_update_check`, module `update_manager`) — dégradation silencieuse si
     absent.
4. `main.py:16-20` : crée le `QApplication`, nom `'eLarcProf'`, organisation `'Arc-en-Ciel'`, style
   `'Fusion'`, police par défaut `Segoe UI 10pt`.
5. Branchement selon les arguments de la ligne de commande (`sys.argv`) :
   - **`--mode4`** (`main.py:23-98`) — création d'instance en ligne de commande, sans passer par
     l'UI de login :
     1. `db.connect_intranet()` (`main.py:31`) — échec fatal (`sys.exit(1)`) si impossible.
     2. Email du professeur pris en 2ᵉ argument (`sys.argv[2]`) ou saisi via `input()` (`main.py:39-42`).
     3. `AuthManager.check_teacher_exists(email)` (`main.py:44`) — échec fatal si le compte n'est
        pas un professeur actif.
     4. `sqlite_init.init()` (`main.py:52`) — crée/vérifie la base SQLite locale.
     5. `sqlite_init.init_module_config(...)` (`main.py:57-62`) — écrit la ligne unique de
        `module_config`.
     6. `sqlite_init.take_teacher_data(infos)` (`main.py:66`) — télécharge les données du
        professeur depuis PostgreSQL vers SQLite (voir §3).
     7. Vérification par comptage (`main.py:74-83`) : `SELECT COUNT(*) FROM larcauth_evaluation`,
        `... larcauth_learnerpei_has_termsubjectpei`, `... larcauth_learnerdp_has_termsubjectdp`.
     8. Construit un `AuthResult` (`main.py:86-93`, rôle forcé `UserRole.PROF`) et appelle
        `sqlite_init.save_session(res)` (`main.py:94`) — **sans PIN** (le mode 4 ne propose pas
        de définir un PIN hors connexion).
     9. Lance `LoginWindow().show()` (`main.py:97-98`) — l'utilisateur devra donc se
        reconnecter manuellement (Intranet/Cloud/PIN) après une création en mode 4, le PIN
        n'étant pas défini.
   - **`--test-create-db`** (`main.py:99-132`) — test d'intégration : crée une base SQLite
     temporaire (`tempfile.mkdtemp()`), appelle `sqlite_init.init(temp_db)`, vérifie les tables
     via `sqlite_init.verify_tables()` (voir §3), nettoie (`db.disconnect_all()`,
     suppression fichier/dossier), puis `sys.exit(0)`.
   - **Sinon** (`main.py:133-135`, cas normal) : `LoginWindow().show()`.
6. `main.py:137` : `sys.exit(app.exec())` — boucle d'événements Qt.

#### Points d'attention

- `main.py:22` : le commentaire dit « Vérifier si le mode 4 est demandé » mais l'implémentation ne
  fait aucune validation de format des arguments suivants (`sys.argv[2]` pris tel quel comme
  email) — un usage incorrect de la CLI (`--mode4` sans email ni saisie) tombe dans le `input()`
  interactif (`main.py:42`), ce qui bloquerait un appel non interactif (script/CI).
- Le mode 4 ne propose pas de PIN hors connexion (contrairement au flux `_apply_session` de
  `login_auth.py`, voir §2.2) — un professeur créé via `--mode4` doit donc passer par
  Intranet/Cloud pour sa première connexion normale.

---

### 2. Écran de connexion (`LoginWindow`)

`LoginWindow` (classe définie dans `views/login.py:40`) hérite de trois mixins
(`LoginAuthMixin`, `LoginCreationMixin`, `LoginHelpersMixin`, définis respectivement dans
`login_auth.py`, `login_creation.py`, `login_helpers.py`) puis de `QMainWindow`. Les quatre
fichiers forment un seul écran logique découpé pour des raisons de taille (`login.py` porte la
UI et le cycle de vie, les mixins portent la logique métier par domaine).

#### 2.1 `views/login.py` — Structure de l'écran et détection réseau

##### Rôle

Construit la fenêtre de connexion : logo, titre, indicateurs réseau (Intranet/Cloud), 4 onglets
(`QTabWidget`), zone d'erreur, zone de log de progression, indicateur de bas de fenêtre, barre de
statut avec pastille réseau colorée. Gère la détection réseau périodique et le réagencement au
changement de thème.

##### Flux

- **Construction** (`login.py:186-223`) :
  - Charge les traductions (`Translator.instance(lang)`, `lang` = `LARC_LANG` env var, défaut
    `'fr'`) — `login.py:190-192`.
  - Charge le thème préféré depuis `QSettings("Larc", "LarcProf")` clé `"theme_pref"`
    (`login.py:195-209`) — applique `theme_manager.set_active(saved_theme)` si la valeur fait
    partie d'une liste blanche de 8 thèmes connus.
  - Construit l'UI (`_setup_ui()`) puis démarre la détection réseau (`_start_net_detection()`).
  - Crée un `QTimer` de 30 000 ms (`login.py:218-220`) qui rappelle `_check_network` en boucle
    tant que la fenêtre est visible (démarré dans `showEvent`, arrêté dans `hideEvent` —
    `login.py:511-533`).
  - Connecte `ds.theme_changed` → `self._restyle` (`login.py:222`).
- **`_setup_ui`** (`login.py:227-320`) : construit dans l'ordre logo (redimensionné à 60 % de la
  largeur de fenêtre, `_resize_logo` `login.py:322-328`, rappelé à chaque `resizeEvent`), titre +
  sous-titre, ligne d'indicateurs réseau (`_intra_indicator`, `_cloud_indicator`), les 4 onglets
  (`_build_intranet_tab`, `_build_cloud_tab`, `_build_pin_tab`, `_build_new_tab`), une zone
  d'erreur (`_err_lbl`, masquée par défaut), une zone de log (`_log_area`, `QPlainTextEdit`
  lecture seule, masquée par défaut), un indicateur de bas de page (`_bottom_indicator` — affiche
  l'état « Module de X : Connecté/Non connecté »), et une `QStatusBar` avec un label réseau et une
  pastille colorée (`_dot_lbl`).
- **Onglet Intranet** (`_build_intranet_tab`, `login.py:363-398`) : champ email
  (`_edt_i_email`), champ mot de passe (`_edt_i_pass`, `QLineEdit.Password`), bouton
  « Se connecter » (`_btn_intra`, classe QSS `btn-primary`, connecté à `_on_intranet` — mixin
  auth) et bouton « Changer le mot de passe » (`_btn_change_pwd_intra`, connecté à
  `_on_change_password`, ouvre `ChangePasswordDialog`). `returnPressed` sur le champ mot de passe
  déclenche le clic du bouton de connexion (`login.py:387`).
- **Onglet Cloud** (`_build_cloud_tab`, `login.py:400-420`) : texte d'info + un seul bouton
  « Se connecter avec Google » (`_btn_google`, classe `btn-google`, connecté à `_on_cloud`).
- **Onglet PIN** (`_build_pin_tab`, `login.py:422-462`) : champ email (`_edt_p_email`), champ PIN
  (`_edt_p_pin`, masqué, longueur max 8), note d'info, bouton « Se connecter » (`_btn_pin`,
  connecté à `_on_pin`) et bouton « Changer le PIN » (`_btn_change_pin`, ouvre `ChangePinDialog`).
- **Onglet Nouvelle instance** (`_build_new_tab`, `login.py:464-501`) : champ email
  (`_edt_n_email`), champ dossier destination en lecture seule + bouton parcourir « … »
  (`_btn_browse`, connecté à `_browse_dest`), bouton « Créer l'instance » (`_btn_create`, classe
  `btn-create`, connecté à `_on_create` — mixin création).
- **`showEvent`** (`login.py:511-529`) : à chaque affichage de la fenêtre : démarre le timer
  réseau, relance une détection réseau synchrone (`detect_network()` — appel bloquant, pas via
  worker), met à jour les indicateurs, **initialise la base SQLite locale**
  (`sqlite_init.init()`, `login.py:519`) et met à jour l'indicateur de bas de page depuis
  `module_config` (`_update_status_bar_from_module_config`, mixin helpers).
- **Détection réseau périodique** (`_check_network`, `login.py:535-539`) : lance un `_Worker`
  (thread Qt, défini dans `login_auth.py:16-31`) exécutant `detect_network()` en tâche de fond,
  résultat traité par `_on_net_detected` (`login.py:541-584`) qui : met à jour les booléens
  `_intranet_ok`/`_internet_ok`, détermine un `NetworkMode` (INTRANET > INTERNET > OFFLINE par
  ordre de priorité), colore la pastille de la barre de statut
  (`network_mode_color`, `common/network.py:5-10`), met à jour les indicateurs texte des onglets,
  et si une session est déjà authentifiée (cas rare à ce stade), rafraîchit l'indicateur de bas de
  page.
- **`_restyle`** (`login.py:600-635`, slot `@safe_slot`) : ré-applique `_STYLE`, ré-applique les
  icônes MD3 (`_apply_icons`), et ré-applique tous les styles inline dépendant de la palette
  (indicateurs, spinner si présent).

##### Requêtes SQL

`login.py` lui-même n'exécute aucune requête SQL directement ; il délègue à `sqlite_init.init()`
(bootstrap complet, voir §3) et aux mixins pour toute lecture/écriture de données.

##### Points d'attention

- La détection réseau synchrone dans `showEvent` (`login.py:514`, appel direct à
  `detect_network()`) bloque le thread UI le temps du test réseau (timeout socket 1.5 s + requête
  HTTP 3 s côté `larccommon.network.detect_network`, voir §4) — contrairement au reste du code qui
  passe systématiquement par un `_Worker` pour ne pas geler l'UI. Ce chemin s'exécute à **chaque**
  affichage de la fenêtre de login (y compris un retour depuis `HomeWindow._logout`).

#### 2.2 `views/login_auth.py` — Authentification (3 modes) et post-traitement

##### Rôle

Contient le `QThread` générique `_Worker` utilisé par tout l'écran de login pour exécuter des
opérations réseau/DB hors du thread UI, et la logique des trois modes d'authentification
(Intranet, Cloud OAuth2, PIN hors connexion) ainsi que le post-traitement commun après succès
(`_on_auth_done`, `_apply_session`).

##### Flux

- **`_Worker`** (`login_auth.py:16-31`) : `QThread` générique — exécute `fn(*args)` dans `run()`,
  émet le résultat via le signal `done`. En cas d'exception, émet `(False, None, str(exc))` au
  lieu de laisser planter le thread. `finished.connect(self.deleteLater)` — auto-destruction.

- **Mode Intranet** (`_on_intranet`, `login_auth.py:39-52`) :
  1. Vérifie que email et mot de passe sont renseignés.
  2. Appelle `_check_email_module(email)` (`login_auth.py:78-110`) — **vérification de
     « liaison d'instance »** : lit `SELECT email_professeur FROM module_config WHERE id = 1` sur
     la base SQLite locale (`db.local_conn`) et compare (insensible à la casse) à l'email saisi.
     Si la base locale n'existe pas, si `module_config` est vide, ou si l'email ne correspond
     pas, affiche une erreur explicite et **arrête la tentative de connexion avant même de
     contacter le serveur**.
  3. Lance en tâche de fond `_connect_then_auth_intranet(email, pwd)` (`login_auth.py:54-58`) :
     `db.connect_intranet()` puis `AuthManager.auth_intranet(email, pwd)` (implémentation dans
     `LarcCommon/larccommon/auth.py:97-149`, voir détail ci-dessous).
  4. Résultat traité par `_on_auth_done(result, ConnMode.INTRANET)`.

- **Mode Cloud** (`_on_cloud`, `login_auth.py:60-66`) :
  1. Lance en tâche de fond `_connect_then_auth_cloud()` (`login_auth.py:68-76`) :
     `db.connect_cloud()` puis `OAuth2Manager.authenticate()` — **le `OAuth2Manager` utilisé ici
     est celui défini localement dans `common/auth.py`**, pas celui de `larccommon.auth` (voir
     §4.2, Points d'attention).
  2. Résultat traité par `_on_auth_done(result, ConnMode.CLOUD)`.
  3. Notez qu'ici **`_check_email_module` n'est pas appelé avant** de lancer l'authentification
     Cloud (contrairement au mode Intranet) — la vérification de liaison d'instance a lieu
     **après** l'authentification Google, à l'intérieur même de
     `common.auth.OAuth2Manager.authenticate()` (`common/auth.py:137-158`).

- **Mode PIN** (`_on_pin`, `login_auth.py:112-147`) :
  1. Vérifie email + PIN renseignés, initialise la base locale (`sqlite_init.init()`), vérifie la
     liaison d'instance (`_check_email_module`).
  2. **Rate limiting PIN** (`login_auth.py:125-141`) : lit
     `SELECT pin_attempts, pin_locked_until FROM session_cache WHERE LOWER(email) = LOWER(?)`. Si
     `pin_locked_until` est défini et que l'heure actuelle (`datetime.now().isoformat()`) est
     **antérieure** à cette valeur, refuse la tentative avec le message « Trop de tentatives.
     Reessayez dans 15 minutes. » sans même appeler `AuthManager.auth_pin`.
  3. Sinon, lance en tâche de fond `AuthManager.auth_pin(email, pin, db.local_conn)`
     (`larccommon/auth.py:151-175`) : recherche
     `SELECT user_id, email, full_name, role, term_id, term_label FROM session_cache WHERE LOWER(email) = ? AND pin_hash = ?`
     (hash SHA-256 du PIN saisi) — succès si une ligne correspond.
  4. Résultat traité par `_on_auth_done(result, ConnMode.OFFLINE, email)`.

- **`_on_auth_done`** (`login_auth.py:149-262`, `@safe_slot`) — dispatcher central appelé pour les
  3 modes :
  1. **Suivi des tentatives PIN échouées** (`login_auth.py:154-188`, uniquement si
     `mode == ConnMode.OFFLINE and email`) :
     - Si échec (`not ok`) : incrémente `pin_attempts` de `session_cache` pour cet email. Si le
       compteur atteint **5**, écrit `pin_locked_until = now() + 15 minutes` et affiche
       « Trop de tentatives. Compte verrouille 15 minutes. » (`login_auth.py:165-174`).
     - Si succès : remet `pin_attempts = 0, pin_locked_until = NULL`
       (`login_auth.py:182-188`).
  2. Si `not ok` (`login_auth.py:190-192`) : affiche l'erreur et arrête.
  3. **Branche Intranet/Cloud** (`login_auth.py:194-214`) : appelle
     `AuthManager.check_teacher_exists(res.email)` — si le compte n'est pas un professeur actif,
     erreur et arrêt. Sinon, complète `res` (`user_id`, `full_name`, `term_id`, `term_label`)
     depuis les `infos` retournées, initialise la base locale, appelle
     `sqlite_init.init_module_config(...)`, puis `_apply_session(res, mode)` (fin du flux).
  4. **Branche OFFLINE avec serveur disponible** (`login_auth.py:216-236`) : même vérification
     `check_teacher_exists`, mêmes mises à jour de `res` et de `module_config`, mais au lieu
     d'appliquer directement la session, affiche **`_show_confirmation_dialog`** (demande
     confirmation avant de retélécharger les données du professeur).
  5. **Branche OFFLINE sans serveur** (`login_auth.py:238-247`) : initialise juste
     `module_config` avec `annee_scolaire=""` et `trimestre_courant=res.term_id` (valeurs issues
     de `session_cache`, pas de PostgreSQL) — **aucun `return` explicite ici**, le flux continue.
  6. **Bloc mort** (`login_auth.py:249-260`) — voir Points d'attention : code strictement
     identique à l'étape 4, jamais atteint.
  7. `_apply_session(res, mode)` (`login_auth.py:262`) — appelée par défaut si aucune branche
     précédente n'a fait de `return` (cas OFFLINE sans serveur, étape 5).

- **`_show_confirmation_dialog`** (`login_auth.py:264-288`) : `QDialog` non thémée listant les
  3 étapes à venir (init SQLite, téléchargement, sauvegarde session) avec boutons OK/Annuler ; OK
  appelle `_execute_steps(res, mode, dlg, infos)`.

- **`_execute_steps`** (`login_auth.py:290-347`) : exécute réellement le téléchargement —
  `sqlite_init.init()`, affiche un spinner (`_show_spinner(True)`), appelle
  `sqlite_init.take_teacher_data(infos, self._log, self._temp_conn, None)` (voir §3 pour le détail
  SQL), masque le spinner, journalise les comptes obtenus
  (`SELECT COUNT(*) FROM larcauth_evaluation` / `larcauth_learnerpei_has_termsubjectpei` /
  `larcauth_learnerdp_has_termsubjectdp`), puis appelle `_apply_session(res, mode)`.

- **`_apply_session`** (`login_auth.py:349-393`) — étape finale commune à tous les modes réussis :
  1. Copie tous les champs de `res` (`AuthResult`) dans le singleton `session`
     (`common.session.session`), `session.conn_mode = mode`, `session.is_authenticated = True`.
  2. `session.load_role_flags()` (voir §4.1) — charge les 5 drapeaux de rôle depuis le serveur ou
     SQLite.
  3. Met à jour les indicateurs réseau visuels selon le mode.
  4. Ré-initialise la base locale (`sqlite_init.init()` — appel redondant, la base est déjà
     initialisée à ce stade dans tous les chemins qui mènent ici).
  5. Lit `SELECT email_professeur FROM module_config WHERE id = 1` pour déterminer
     `skip_pin` (= l'email local déjà enregistré correspond à l'email de connexion actuel).
  6. Si mode Intranet/Cloud et `not skip_pin` : propose de définir un PIN
     (`_ask_pin_setup`, `QInputDialog` texte masqué) puis `sqlite_init.save_session(res, pin)`.
     Sinon (mode PIN, ou instance déjà liée) : `sqlite_init.save_session(res)` sans changer le
     PIN existant (voir §3, `save_session` conserve l'ancien hash via `COALESCE`).
  7. `_update_status_bar(res, mode)` puis `_open_main_window(res)` (mixin helpers, voir §2.4) —
     ouvre `HomeWindow` et cache `LoginWindow`.

##### Requêtes SQL (synthèse)

| Table | Opération | Contexte |
|---|---|---|
| `module_config` | `SELECT email_professeur ... WHERE id = 1` | `_check_email_module`, `_apply_session` |
| `session_cache` | `SELECT pin_attempts, pin_locked_until WHERE LOWER(email)=LOWER(?)` | rate limiting PIN, avant tentative |
| `session_cache` | `SELECT ... WHERE LOWER(email)=? AND pin_hash=?` | `AuthManager.auth_pin` (larccommon) |
| `session_cache` | `UPDATE pin_attempts, pin_locked_until WHERE LOWER(email)=LOWER(?)` | après échec/succès PIN |
| `larcauth_evaluation` / `larcauth_learnerpei_has_termsubjectpei` / `larcauth_learnerdp_has_termsubjectdp` | `SELECT COUNT(*)` | vérification post-téléchargement |
| PostgreSQL `larcauth_aecuser` (Intranet/Cloud) | `SELECT id, email, last_name, first_name, password` puis `SELECT type_director, type_coordonator, type_supervisor, type_secretary` puis `SELECT fk_language` | `AuthManager.auth_intranet` (`larccommon/auth.py:105-138`) |
| PostgreSQL `larcauth_aecuser` / `larcauth_teachadm` / `larcauth_academicyear` + `larcauth_term` | `SELECT` (3 requêtes en cascade) | `AuthManager.check_teacher_exists` (`larccommon/auth.py:183-219`) |

##### Points d'attention

- **Code mort confirmé** : `login_auth.py:249-260` teste exactement la même condition que
  `login_auth.py:216` (`mode == ConnMode.OFFLINE and db.server_conn is not None`). Le premier bloc
  se termine systématiquement par un `return` (`login_auth.py:236`), donc le second bloc
  (`login_auth.py:249-260`, qui ré-exécute `sqlite_init.init()`, `init_module_config` et
  `_show_confirmation_dialog` avec le même code) n'est **jamais atteint**. Ce n'est pas
  fonctionnellement dangereux (code strictement redondant) mais c'est un signal fort de
  copier-coller non nettoyé — à supprimer lors d'un prochain refactor de `_on_auth_done`.
- Le mode Cloud ne bénéficie d'aucun rate limiting (contrairement au mode PIN) : un attaquant avec
  accès à l'app pourrait déclencher `OAuth2Manager.authenticate()` en boucle sans blocage côté
  LarcProf (le flux OAuth2 lui-même impose un serveur HTTP local et un délai de 2 min, mais aucune
  limite de tentatives).
- `_apply_session` (`login_auth.py:368`) rappelle `sqlite_init.init()` même quand la base est déjà
  connectée et initialisée par un appel précédent dans le même flux (`_on_auth_done` ou
  `_execute_steps`) — redondant mais sans effet de bord destructeur (`init_intranet` utilise
  `CREATE TABLE IF NOT EXISTS`).

#### 2.3 `views/login_creation.py` — Création d'une nouvelle instance

##### Rôle

Implémente l'onglet « Nouvelle instance » : clone le projet `LarcProf` (fichiers) dans un nouveau
dossier, y initialise une base SQLite propre pré-remplie avec les données du professeur désigné,
et génère un lanceur (`lancer.bat`) — permet de déployer une instance dédiée par professeur sur un
poste (usage multi-comptes sur une même machine, ou déploiement portable).

##### Flux (`_on_create`, `login_creation.py:29-192`)

1. Vérifie que l'email et le dossier destination sont renseignés (`login_creation.py:32-36`).
2. **Détermine le serveur à utiliser** (`login_creation.py:38-67`) — cascade de fallback :
   - Si une connexion serveur existe déjà (`db.server_conn`), l'utilise directement (Intranet ou
     Cloud selon `db.server_mode`) et vérifie `AuthManager.check_teacher_exists(email)`.
   - Sinon, tente `db.connect_intranet()` puis vérifie l'existence du professeur.
   - Sinon, tente `db.connect_cloud()` puis vérifie l'existence du professeur.
   - Si aucune connexion serveur n'est possible : erreur bloquante, la création est impossible.
3. **Authentification de contrôle** (`login_creation.py:69-98`) — selon le mode serveur retenu :
   - Intranet : demande le mot de passe via `QInputDialog` (masqué), vérifie via
     `AuthManager.auth_intranet(email, pwd)`.
   - Cloud : lance `OAuth2Manager.authenticate()` (implémentation locale de `common/auth.py`) et
     vérifie que l'email du compte Google authentifié correspond exactement (insensible à la
     casse) à l'email saisi dans le formulaire.
4. **Préparation du dossier destination** (`login_creation.py:100-133`) :
   - `slug` = partie locale de l'email (`avant @`), points remplacés par underscores.
   - `dest` = `<dossier choisi>/eLarcProf_<slug>`.
   - Copie récursive de tout le contenu du dossier source `LarcProf/` (hors `__pycache__`,
     `.git`, `.venv`) via `shutil.copytree`/`shutil.copy2`.
   - Copie (ou crée par défaut) `config.ini` dans le dossier destination.
   - Copie `elarc.db` source vers `elarc.db` destination s'il existe (base **déjà peuplée** de la
     source, qui sera ensuite écrasée par `take_teacher_data`).
5. **Initialisation de la nouvelle base** (`login_creation.py:135-157`) :
   - `sqlite_init.init(dest_db)` sur le chemin `dest/elarc.db`.
   - `sqlite_init.take_teacher_data(infos, self._log, db.local_conn, None)` — télécharge les
     données du professeur désigné (voir §3).
   - `sqlite_init.verify_tables()` — journalise un avertissement si des tables manquent (sans
     bloquer la création).
   - `sqlite_init.init_module_config(...)` avec les infos du professeur.
   - Construit un `AuthResult` (rôle forcé `UserRole.PROF`) et `sqlite_init.save_session(res)`
     (**sans PIN**, comme pour le mode 4 de `main.py`).
6. **Fichiers de métadonnées d'instance** (`login_creation.py:169-179`) :
   - `instance.ini` : `[Instance]\nEmail=<email>\nCreated=auto\n`.
   - `lancer.bat` : `cd /d "%~dp0" && python main.py && pause`.
7. `QMessageBox.information` de succès (`login_creation.py:182-186`).

##### Requêtes SQL

Toutes les requêtes sont déléguées à `AuthManager` (`auth_intranet`, `check_teacher_exists`) et à
`sqlite_init` (`take_teacher_data`, `verify_tables`, `init_module_config`, `save_session`) — voir
détails respectifs en §2.2 et §3. `login_creation.py` n'exécute aucune requête SQL en propre.

##### Points d'attention

- La copie de fichiers (`shutil.copytree`/`copy2`, `login_creation.py:109-117`) copie
  **l'intégralité du dossier source**, y compris potentiellement des fichiers non désirés visibles
  dans le dossier racine actuel de `LarcProf/` (`elarc.log`, `historique_demandes.txt`,
  `Reflexion_1.txt`, etc. — cf. listing racine) puisque seule une liste noire de 3 noms
  (`__pycache__`, `.git`, `.venv`) est exclue. Aucune liste blanche de ce qui doit réellement être
  déployé.
- Le mot de passe demandé à l'étape 3 (mode Intranet) sert uniquement à **vérifier** l'identité
  (`auth_intranet`) mais n'est jamais utilisé après — la nouvelle instance ne stocke pas ce mot de
  passe (cohérent avec l'absence de mot de passe local, seul un PIN optionnel est prévu — mais
  justement, aucun PIN n'est proposé sur ce chemin, voir point suivant).
- Comme pour `main.py --mode4`, aucune proposition de PIN hors connexion n'est faite lors de la
  création d'instance (`sqlite_init.save_session(res)` sans second argument) — la première
  connexion à la nouvelle instance devra donc se faire via Intranet ou Cloud avant qu'un PIN
  puisse être défini (onglet PIN → bouton « Changer le PIN »).

#### 2.4 `views/login_helpers.py` — Utilitaires UI et barre de statut

##### Rôle

Regroupe les méthodes utilitaires partagées par `login.py` et les autres mixins : mise à jour
thread-safe des widgets (les workers tournent dans un `QThread` séparé), lecture de
`module_config`, formatage de la barre de statut, et ouverture de la fenêtre principale post-login.

##### Flux

- **`_set_busy`** (`login_helpers.py:31-35`) : désactive/réactive les 4 boutons de connexion
  (`_btn_intra`, `_btn_google`, `_btn_pin`, `_btn_create`) et change le texte du label réseau —
  **toutes les mises à jour passent par `QMetaObject.invokeMethod(..., Qt.QueuedConnection, ...)`**
  plutôt que par un appel direct, car ces méthodes peuvent être appelées depuis le thread du
  `_Worker` (signal `done` connecté avec une lambda qui appelle `_on_auth_done`, qui elle-même
  appelle `_set_busy` — mais Qt garantit que les slots connectés à un signal cross-thread sont
  exécutés dans le thread de l'émetteur sauf connexion explicite ; ici l'appel est fait
  explicitement en `QueuedConnection` pour forcer l'exécution dans le thread UI).
- **`_show_error`** (`login_helpers.py:37-49`), **`_log`** (`login_helpers.py:51-57`),
  **`_show_progress`** (`login_helpers.py:59-66`) : même pattern thread-safe.
- **`_show_spinner`** (`login_helpers.py:68-83`) : crée paresseusement (`hasattr` check) un
  `QProgressBar` indéterminé (`setRange(0, 0)`) inséré dynamiquement dans le layout juste avant
  `_bottom_indicator`.
- **`_get_module_config`** (`login_helpers.py:88-114`) : vérifie d'abord l'existence de la table
  (`SELECT name FROM sqlite_master WHERE type='table' AND name='module_config'`) puis lit
  `SELECT nom_professeur, annee_scolaire, trimestre_courant, email_professeur FROM module_config LIMIT 1`.
  Retourne `None` si la table n'existe pas ou si `nom_professeur` est vide.
- **`_get_module_config_dates`** (`login_helpers.py:116-140`) : même pattern, lit
  `date_creation_module, derniere_synchronisation`.
- **`_update_status_bar_from_module_config`** (`login_helpers.py:142-170`) : appelée au
  `showEvent` de `LoginWindow` — construit un `AuthResult` partiel (nom seul) à partir de
  `_get_module_config()` et appelle `_update_status_bar`.
- **`_update_status_bar`** (`login_helpers.py:172-194`) : formate le texte et la couleur de
  `_bottom_indicator` selon le `ConnMode` (« Connecté à l'Intranet » / « Connecté au Cloud » /
  « Non connecté » / « Module LarcProf non instanciée » si aucun nom de professeur connu).
- **`_open_main_window`** (`login_helpers.py:196-205`) : `HomeWindow()` créée **sans parent**
  (commentaire explicite `login_helpers.py:199-202` : avec un parent caché, `isVisible()` resterait
  `False`, et `quitOnLastWindowClosed` fermerait l'application au lieu de revenir au tableau de
  bord quand la fenêtre de notes se ferme) — `show()` puis `self.hide()` (masque `LoginWindow`,
  ne la détruit pas).

##### Points d'attention

- `_restyle_all` (`login_helpers.py:20-25`) est un stub vide avec docstring expliquant que c'est
  `LoginWindow._restyle` (dans `login.py`) qui porte réellement la logique de restyle — nom
  trompeur car aucune classe n'appelle `_restyle_all` dans ce fichier (méthode orpheline /
  vestige).

#### 2.5 `views/password.py` — Changement de mot de passe / PIN

##### Rôle

Deux boîtes de dialogue modales indépendantes : `ChangePinDialog` (PIN hors connexion, stocké
localement) et `ChangePasswordDialog` (mot de passe Intranet, stocké côté PostgreSQL).

##### Flux — `ChangePinDialog`

- `_on_accept` (`password.py:79-91`) : valide que le nouveau PIN est numérique, 4 à 8 chiffres.
  Appelle `sqlite_init.save_session(session, new_pin)` (`password.py:89`) — voir Points
  d'attention — puis `QMessageBox.information` de succès et `self.accept()`.
- Aucune vérification de l'ancien PIN n'est demandée (à la différence du mot de passe) : changer
  le PIN ne nécessite pas de le connaître au préalable, seulement d'être déjà connecté (le bouton
  n'est accessible que depuis l'écran de login, sans session active nécessairement — voir Points
  d'attention).

##### Flux — `ChangePasswordDialog`

- `_on_accept` (`password.py:167-212`) :
  1. Valide que les 4 champs (email, ancien mot de passe, nouveau, confirmation) sont renseignés.
  2. Valide que nouveau == confirmation et que le nouveau fait ≥ 6 caractères.
  3. Vérifie l'ancien mot de passe via `AuthManager.auth_intranet(email, old_pass)`
     (`password.py:187`) — **nécessite donc une connexion Intranet active** (`db.server_conn`
     doit être en mode `INTRANET`, sinon `auth_intranet` retourne `False` immédiatement,
     `larccommon/auth.py:99-101`).
  4. Si l'ancien mot de passe est valide, exécute directement en SQL :
     `UPDATE larcauth_aecuser SET password = %s WHERE LOWER(email) = %s` avec le nouveau hash
     SHA-256 (`password.py:198-206`), puis `conn.commit()` et `QMessageBox.information`.

##### Requêtes SQL

| Fichier:ligne | Requête | Table |
|---|---|---|
| `password.py:200-205` | `UPDATE larcauth_aecuser SET password = %s WHERE LOWER(email) = %s` | PostgreSQL `larcauth_aecuser` |

##### Points d'attention

- `password.py:89` — `sqlite_init.save_session(session, new_pin)` passe l'objet **singleton
  `session`** (`common.session.session`, une instance de `Session`) là où la signature de
  `save_session` (`common/sqlite_init.py:510`) attend un `AuthResult`. Cela **fonctionne** en
  pratique car `Session` et `AuthResult` partagent les mêmes noms d'attributs utilisés par
  `save_session` (`user_id`, `email`, `full_name`, `role`, `term_id`, `term_label` — duck typing),
  mais ne respecte pas l'annotation de type déclarée et est fragile : si `Session` gagne un jour un
  attribut `role` de type différent, ou si `save_session` accède à un attribut présent uniquement
  sur `AuthResult` (ex. `fk_language`), ce point de code casserait silencieusement.
- `ChangePasswordDialog._on_accept` (`password.py:198-206`) duplique la logique déjà présente dans
  `AuthManager.change_password` (`LarcCommon/larccommon/auth.py:68-95`, qui fait exactement le
  même `UPDATE` avec en plus une vérification explicite de l'ancien hash) au lieu de l'appeler —
  deux implémentations à maintenir pour la même opération.
- `password.py:206` appelle `conn.commit()` alors que toutes les connexions PostgreSQL du projet
  sont ouvertes en `autocommit = True` (`common/database.py:103`, `LarcCommon` idem) — l'appel est
  un no-op inoffensif chez psycopg2 en autocommit, mais incohérent avec le reste du code qui ne
  l'appelle jamais sur les connexions serveur.
- `ChangePinDialog` ne vérifie ni l'ancien PIN, ni qu'une session authentifiée existe réellement
  au moment de l'appel — elle est accessible directement depuis l'onglet PIN de l'écran de login
  (bouton « Changer le PIN », `login.py:454-458`), potentiellement **avant** toute authentification
  réussie. `sqlite_init.save_session` fonctionne alors sur le `session` singleton par défaut
  (`user_id=0`, cf. valeurs par défaut de `Session`, `larccommon/session.py:35`) — comportement à
  vérifier : le PIN serait alors enregistré sous `session_cache.user_id = 0`, une ligne
  potentiellement sans rapport avec un vrai professeur, si le dialogue est ouvert sans connexion
  préalable.

---

### 3. `common/sqlite_init.py` — Bootstrap de la base SQLite locale

#### Rôle

Classe singleton `SQLiteInit` (instance module-level `sqlite_init`, `sqlite_init.py:883`) chargée
de : créer/migrer le schéma de la base SQLite locale (`elarc.db`), gérer la session en cache
(PIN, rate limiting), gérer la configuration du module (`module_config`), et surtout
**télécharger (« seed »)** les données du professeur connecté depuis PostgreSQL vers SQLite selon
le principe gabarit (téléchargement complet, pas de synchronisation incrémentale à ce niveau — la
synchronisation incrémentale est portée par `common/sync.py`, hors périmètre de ce document).

#### Schéma DDL (`_DDL`, `sqlite_init.py:14-337`)

Tables créées via `CREATE TABLE IF NOT EXISTS` (exécuté en un seul `conn.executescript(_DDL)`,
`sqlite_init.py:375`) :

| Table | Rôle |
|---|---|
| `session_cache` | Cache d'identité pour connexion PIN hors ligne : `user_id` (PK), `email`, `full_name`, `role`, `term_id`, `term_label`, `pin_hash`, `pin_attempts`, `pin_locked_until`, `updated_at`. |
| `sync_cursor` | `table_name` (PK) → `max_rev` — curseur de synchronisation par table (lu/écrit par `read_cursor`/`update_cursor`, `sqlite_init.py:818-836`; utilisation effective par `common/sync.py`, hors périmètre). |
| `module_config` | Ligne unique (`id` contraint à `1`) : `annee_scolaire`, `trimestre_courant`, `nom_professeur`, `email_professeur`, `date_creation_module`, `derniere_synchronisation`, et (via migration) `theme_name`, `font_scale`. |
| `sync_state` | `table_name` (PK) → `last_sync`, `last_source` — horodatage de dernière synchro par table métier. |
| `larcauth_evaluation` / `larcauth_evaluation_ref` | Grille des évaluations (12 slots F/S) — schéma complet typé (crit_a..f, aspects 1-7 par critère, barèmes, etc.). |
| `larcauth_learnerpei_has_termsubjectpei` / `_ref` | Notes PEI par élève × matière-trimestre. |
| `larcauth_learnerdp_has_termsubjectdp` / `_ref` | Notes DP par élève × matière-trimestre. |
| `larcauth_program`, `larcauth_level`, `larcauth_levelsubject`, `larcauth_classroom`, `larcauth_classroom_termsubject`, `larcauth_student`, `larcauth_aecuser`, `larcauth_criteria_of_levelsubject` | Tables de référence pour la cascade programme → niveau → matière → classe (commentaire `sqlite_init.py:182` : « pour la cascade matières → classes »). |
| `larcauth_classroom_termothersubject` / `_ref` | Unités interdisciplinaires / PP / TDC / CAS / Mémoire (« autres matières »). |
| `larcauth_learner_has_termothersubject` / `_ref` | Rattachement élève ↔ autre matière. |
| `student_event` / `_ref` | Journal d'événements élève (absences, retards, etc. — table partagée avec LarcSuperviseur). |

Colonnes clés notables (utilisées ailleurs dans le périmètre documenté) :
- `larcauth_classroom_termsubject.fk_teacher_id` (`sqlite_init.py:215`) — **et non
  `fk_supervisor_id`** (voir §5, Points d'attention, pour une confusion réelle entre ces deux noms
  de colonne ailleurs dans le code).
- `larcauth_classroom_termothersubject.fk_supervisor_id` (`sqlite_init.py:254`) — celui-ci existe
  bel et bien, mais sur une **autre table**.
- `larcauth_classroom` (`sqlite_init.py:202-207`) ne possède **que** `id`, `label`,
  `fk_level_id`, `enabled` — aucune colonne `fk_headteacher_id` n'est définie, ni dans le DDL ni
  dans aucune migration (voir §5, Points d'attention).

#### Flux — `init_intranet` (`init()` en est un simple alias, `sqlite_init.py:351-353`)

1. Calcule le chemin par défaut `<LarcProf>/elarc.db` si non fourni (`sqlite_init.py:357-360`).
2. Crée un fichier vide si absent (`open(db_path, 'w').close()`), journalise dans les deux cas.
3. `db.connect_sqlite(db_path)` — ouvre la connexion SQLite (WAL, `row_factory = sqlite3.Row`, voir
   §4.3).
4. `conn.executescript(_DDL)` — crée toutes les tables ci-dessus si absentes.
5. **Migrations de colonnes** (méthode `_migrate_columns`, `sqlite_init.py:443-449` — lit
   `PRAGMA table_info(table)`, ajoute par `ALTER TABLE ... ADD COLUMN` chaque colonne absente) :
   - `session_cache` : `pin_attempts INTEGER DEFAULT 0`, `pin_locked_until TEXT`.
   - `larcauth_evaluation` et `larcauth_evaluation_ref` : `sync_version`, `synced_at`,
     `synced_by`, `last_modified_at`, `sync_revision`, `source` (toutes `TEXT`).
   - `larcauth_learnerpei_has_termsubjectpei(_ref)` et `larcauth_learnerdp_has_termsubjectdp(_ref)`
     : `note_on_7_checked INTEGER DEFAULT 0` (case « Validé » — colonne locale, jamais synchronisée
     d'après le commentaire `sqlite_init.py:401` et la liste `_IGNORE_COLS` de `common/sync.py:95`).
   - `module_config` : `theme_name TEXT DEFAULT 'material_light'`, `font_scale REAL DEFAULT 1.0`.
   - `larcauth_classroom_termsubject` : `calc_formula TEXT`, `subject_weight REAL DEFAULT 1.0`.
   - `larcauth_aecuser` : `type_secretary BOOLEAN DEFAULT FALSE`.
6. `conn.commit()`.
7. **Migration de `sync_state`** (`sqlite_init.py:414-427`) : si un `SELECT table_name FROM sync_state LIMIT 1`
   échoue (ancien schéma sans cette colonne), la table est supprimée et recréée avec le schéma
   actuel.
8. Retourne `True`.

#### Flux — `init_cloud` (`sqlite_init.py:451-508`)

Chemin alternatif prévu pour initialiser une base via Supabase par API REST — lit `config.ini`
section `[Supabase]` (`url`, `api_key`). D'après les commentaires du code lui-même
(`sqlite_init.py:482-487` : « Pour l'instant, on simule la création locale »), **cette méthode
n'implémente en réalité aucun appel réseau vers Supabase** : elle se contente de créer une base
SQLite locale (`elarc_cloud.db` par défaut) avec le même DDL que `init_intranet`, sans jamais
utiliser `headers`/`supabase_url` construits plus haut dans la fonction. Le module `requests` est
importé (`sqlite_init.py:475`) mais n'est jamais appelé. **Aucun appelant de `init_cloud` n'a été
trouvé dans le périmètre lu** (le mode Cloud du login utilise `db.connect_cloud()` +
`OAuth2Manager`, pas `sqlite_init.init_cloud`) — comportement à vérifier : cette méthode semble
être du code inutilisé/incomplet.

#### Flux — `save_session` (`sqlite_init.py:510-531`)

`INSERT ... ON CONFLICT(user_id) DO UPDATE` sur `session_cache` : upsert par `user_id`. Le hash du
PIN n'est mis à jour que si un nouveau PIN non vide est fourni
(`pin_hash = COALESCE(excluded.pin_hash, pin_hash)`, `sqlite_init.py:525`) — un appel sans PIN
préserve donc le PIN existant. `role` est stocké comme `result.role.value` (chaîne, ex. `'PROF'`).

#### Flux — `init_module_config` (`sqlite_init.py:533-554`)

`INSERT ... ON CONFLICT(id) DO UPDATE` sur `module_config` (ligne unique `id=1`) — upsert de
`annee_scolaire`, `trimestre_courant`, `nom_professeur`, `email_professeur`, et
`derniere_synchronisation = datetime('now')` (mise à jour à chaque appel, y compris lors d'une
simple reconnexion — pas seulement lors d'une vraie synchronisation).

#### Flux — `take_teacher_data` (`sqlite_init.py:556-749`) — cœur du téléchargement gabarit

1. Détermine `conn_pg` (connexion PostgreSQL — reçue en paramètre ou `db.server_conn`) et
   `conn_sqlite` (reçue en paramètre ou `db.local_conn`). Si l'une des deux manque, tente une
   reconnexion automatique (`db.connect_intranet()` puis `db.connect_cloud()`) avant d'abandonner.
2. **Six requêtes SELECT successives sur PostgreSQL**, toutes filtrées par `user_id` (le
   professeur connecté) et `term_id` (trimestre courant) sauf les deux dernières :
   - `larcauth_evaluation` (`sqlite_init.py:597-606`) — jointure `classroom_termsubject` +
     `classroom`, filtrée par `cts.fk_teacher_id = %s AND cts.fk_term_id = %s AND cts.enabled = true AND c.enabled = true`.
   - `larcauth_learnerpei_has_termsubjectpei` (`sqlite_init.py:611-623`) — jointure
     `learner_has_termsubject` → `classroom_termsubject` → `classroom` → `student`, filtrée par
     `fk_teacher_id`, `fk_term_id`, et `enabled = true` sur `cts`, `c` et `s`. Ajoute
     `lht.fk_student_id` en colonne supplémentaire (`pei.*, lht.fk_student_id`).
   - `larcauth_learnerdp_has_termsubjectdp` (`sqlite_init.py:628-640`) — même schéma de jointure
     que ci-dessus pour le DP.
   - `larcauth_classroom_termothersubject` (`sqlite_init.py:645-648`) — filtrée uniquement par
     `fk_supervisor_id = %s` (pas de filtre trimestre ici — **toutes les années/trimestres où le
     professeur est superviseur d'une « autre matière » sont téléchargés**, comportement à
     vérifier si c'est intentionnel).
   - `larcauth_learner_has_termothersubject` (`sqlite_init.py:653-655`) — **sans aucun filtre**
     (`SELECT * FROM public.larcauth_learner_has_termothersubject`) : télécharge l'intégralité de
     cette table pour tous les élèves de l'établissement, pas seulement ceux du professeur
     connecté.
   - `student_event` (`sqlite_init.py:660-669`) — jointure `student` → `classroom_termsubject`,
     filtrée par `cts.fk_teacher_id`, `cts.fk_term_id`, `s.enabled = true`.
3. **Transaction SQLite explicite** (`sqlite_init.py:679-717`) :
   - `PRAGMA foreign_keys = OFF` avant, `= ON` après (bloc `finally`).
   - `BEGIN` explicite.
   - Vide (`DELETE FROM`) les 6 `BUSINESS_TABLES` et leurs `_ref` correspondantes
     (`sqlite_init.py:687-690`).
   - Pour chacune des 6 paires (table, table_ref), `_seed_pair` (fonction interne,
     `sqlite_init.py:694-701`) :
     1. `_create_table_from_data` (`sqlite_init.py:769-782`) — **`DROP TABLE IF EXISTS` puis
        `CREATE TABLE` avec toutes les colonnes en `TEXT`**, d'après la liste de colonnes
        retournée par PostgreSQL (`cur.description`). **Ceci remplace intégralement le schéma
        typé défini dans `_DDL` pour ces 6 tables** par un schéma entièrement `TEXT`, calqué sur
        les colonnes réellement présentes côté PostgreSQL au moment du téléchargement — voir
        Points d'attention.
     2. `_insert_rows_from_data` (`sqlite_init.py:784-816`) — `INSERT OR REPLACE`, avec
        conversion des types Python non natifs SQLite (`date`/`time`/`datetime` → `isoformat()`,
        `dict`/`list` → `json.dumps`, `memoryview`/`bytearray` → `bytes`).
     3. Répété à l'identique pour `<table>_ref` (même colonnes, mêmes lignes — **la table `_ref`
        est un instantané figé de l'état serveur au moment du téléchargement**, utilisé comme
        référence de comparaison par `common/sync.py` et par les compteurs « non synchronisé »
        des tableaux de bord, voir §5).
     4. `_touch_sync_state` (`sqlite_init.py:751-767`) — upsert `sync_state.last_sync = now()`,
        `last_source = 'intranet'`/`'cloud'`/`'unknown'` selon `db.server_mode`.
   - `conn_sqlite.commit()` si tout réussit ; `rollback()` + `raise` en cas d'exception (attrapée
     plus haut).
4. Vérifie par comptage (`SELECT COUNT(*)` sur les 3 premières tables) — journalise un
   avertissement si les 3 comptes sont à zéro.
5. Retourne `(True, '')` en cas de succès, `(False, message)` en cas d'échec.

#### Flux — `verify_tables` (`sqlite_init.py:838-880`)

Compare la liste figée de 23 noms de tables attendues (incluant les tables de référence
`larcauth_program`, `larcauth_level`, etc., qui **ne sont jamais peuplées par
`take_teacher_data`** — voir Points d'attention) à `SELECT name FROM sqlite_master WHERE type='table'`.
Retourne `(True, [])` si complet, sinon `(False, [tables manquantes])`.

#### Points d'attention

- **Duplication de DDL** : `sqlite_init.py:80-109` et `sqlite_init.py:111-140` définissent **deux
  fois consécutivement, de façon strictement identique**, `CREATE TABLE IF NOT EXISTS larcauth_evaluation_ref`.
  Sans effet fonctionnel (`IF NOT EXISTS` rend la deuxième occurrence un no-op), mais c'est du SQL
  mort/dupliqué à nettoyer.
- **Schéma dynamique remplaçant le schéma statique** : les 6 `BUSINESS_TABLES` (et leurs `_ref`)
  sont **recréées entièrement en colonnes `TEXT`** à chaque appel de `take_teacher_data`
  (`_create_table_from_data`, `sqlite_init.py:769-782`), ce qui signifie que le schéma typé défini
  dans `_DDL` pour `larcauth_evaluation` (lignes 49-78, avec ses colonnes `crit_a`..`crit_f`,
  `aspect_*` etc.) n'a d'effet réel qu'**avant** le premier téléchargement de données ; après,
  le schéma effectif dépend entièrement des colonnes renvoyées par la requête PostgreSQL au moment
  du téléchargement. Une conséquence concrète : les migrations de colonnes appliquées par
  `_migrate_columns` sur `larcauth_evaluation`/`larcauth_evaluation_ref`
  (`sqlite_init.py:384-399`, ajout de `sync_version`, `synced_at`, etc.) ne survivent **que** si
  ces colonnes sont également renvoyées par la requête PostgreSQL lors du prochain
  `take_teacher_data` — sinon la table recréée ne les aura pas, et la migration devra s'exécuter à
  nouveau au prochain `init()` (ce qui est bien le comportement observé : `init()` ré-applique les
  migrations à chaque démarrage, donc le système est auto-cohérent, mais il faut comprendre que
  les colonnes « métier » de ces 6 tables sont en réalité pilotées par PostgreSQL et non par
  `_DDL`).
- **Portée des données téléchargées incohérente entre tables** : `larcauth_classroom_termothersubject`
  n'est pas filtrée par trimestre (uniquement par `fk_supervisor_id`, `sqlite_init.py:645-648`),
  et `larcauth_learner_has_termothersubject` n'est filtrée par **rien du tout**
  (`sqlite_init.py:653-655`, télécharge la table entière de l'établissement). Ceci contraste avec
  les 4 autres requêtes, toutes filtrées par `user_id` + `term_id`. Comportement à vérifier :
  s'agit-il d'un choix délibéré (les jointures nécessaires pour filtrer par professeur seraient
  trop coûteuses/complexes) ou d'un oubli ?
- `verify_tables` (`sqlite_init.py:848-873`) attend des tables de référence
  (`larcauth_program`, `larcauth_level`, `larcauth_levelsubject`, `larcauth_classroom`,
  `larcauth_classroom_termsubject`, `larcauth_student`, `larcauth_aecuser`,
  `larcauth_criteria_of_levelsubject`) qui sont créées par `_DDL` mais **jamais peuplées** par
  quoi que ce soit dans ce fichier (`take_teacher_data` ne les touche pas) — leur remplissage
  dépend entièrement de `common/sync.py` (hors périmètre). `verify_tables` vérifie donc seulement
  l'**existence** des tables, pas qu'elles contiennent des données ; un `take_teacher_data` réussi
  sans synchronisation préalable/ultérieure via `common/sync.py` laisserait ces tables de
  référence vides, ce qui expliquerait des requêtes de comptage à zéro dans les tableaux de bord
  (§5) sans qu'aucune erreur ne soit levée.
- `init_cloud` (`sqlite_init.py:451-508`) semble être une implémentation inachevée/inutilisée
  (voir description du flux ci-dessus) — à confirmer avant suppression ou complétion.

---

### 4. Infrastructure : session, auth, database, network, logger

#### 4.1 `common/session.py` — Pont de session et rôles

##### Rôle

Ré-exporte le singleton `session` et les types (`UserRole`, `ConnMode`, `AuthResult`, `Session`)
depuis `LarcCommon/larccommon/session.py`, puis y **attache dynamiquement** des méthodes/propriétés
spécifiques à LarcProf via `MethodType` et modification de classe à l'exécution.

##### Structures sous-jacentes (`LarcCommon/larccommon/session.py`)

- `UserRole` (Enum) : `SUPERVISEUR`, `PROF`, `COORD`, `SECR`, `ADMIN`
  (`larccommon/session.py:8-13`).
- `ConnMode` (Enum) : `INTRANET`, `CLOUD`, `OFFLINE` (`larccommon/session.py:16-19`).
- `AuthResult` (dataclass) : `user_id`, `email`, `full_name`, `role`, `term_id`, `term_label`,
  `fk_language` (`larccommon/session.py:22-30`).
- `Session` (dataclass, singleton `session`) : mêmes champs que `AuthResult` plus `conn_mode`,
  `is_authenticated`, `instance_dir`, `theme_pref`, `card_theme`, `type_flags`, `role_flags`
  (`larccommon/session.py:33-55`). `instance_dir` est initialisé au dossier parent de
  `larccommon/` (donc `LarcCommon/`) — comportement à vérifier : ce chemin ne semble pas
  correspondre au dossier d'instance LarcProf réel (`D:\projets\LarcProf` ou un dossier
  `eLarcProf_<slug>` créé par `login_creation.py`) ; aucun usage de `session.instance_dir` n'a été
  observé dans le périmètre lu.

##### Flux — `load_role_flags` (`common/session.py:18-73`)

1. Tente d'abord PostgreSQL si `db.is_server_connected` :
   `SELECT type_teacher, type_coordonator, type_supervisor, type_secretary, type_director FROM larcauth_aecuser WHERE id = %s`.
2. Si pas de connexion serveur (ou échec), retombe sur SQLite (`db.local_conn`) avec la même
   requête adaptée (`?` au lieu de `%s`).
3. Construit un dict `{'Professeur': bool, 'Coordinateur': bool, 'Superviseur': bool,
   'Secretaire': bool, 'Directeur': bool}`, l'assigne à `self.role_flags` et le retourne.
4. Si ni PostgreSQL ni SQLite ne répondent, retourne un dict vide (sans lever d'exception —
   toutes les erreurs sont absorbées via `get_reporter().report_exception()`).

##### Propriétés attachées

- `active_role_labels` (`common/session.py:76-80`, propriété sur `Session`) : liste des libellés
  de rôles actifs (appelle `load_role_flags` si `role_flags` est vide).
- `role_display` (`common/session.py:83-86`) : les libellés actifs joints par `' | '`, ou
  `self.role.value` si aucun rôle actif détecté — **c'est cette propriété qui alimente le label
  « rôle » affiché sur les cartes profil de `HomeWindow`/`HomeWidget`** (§5).

##### Points d'attention

- Le mapping colonne → libellé fixe l'ordre `type_teacher → 'Professeur'`,
  `type_coordonator → 'Coordinateur'`, `type_supervisor → 'Superviseur'`,
  `type_secretary → 'Secretaire'`, `type_director → 'Directeur'` — un professeur qui est
  également directeur verrait `role_display` afficher `"Professeur | Directeur"` (ordre fixe des
  clés du dict Python 3.7+, qui préserve l'ordre d'insertion).
- Contrairement à `AuthManager.auth_intranet`/`auth_pin` qui **déduisent** un rôle unique
  (`_deduce_role`, priorité admin > coordinateur > secrétaire > superviseur > prof), `role_display`
  peut afficher **plusieurs** rôles simultanément — les deux mécanismes (rôle unique déduit à la
  connexion vs. tous les rôles actifs affichés ensuite) coexistent sans être strictement alignés.

#### 4.2 `common/auth.py` — AuthManager (réexport) + OAuth2Manager (implémentation locale)

##### Rôle

Réexporte `AuthManager` de `larccommon.auth` tel quel (aucune classe `AuthManager` n'est
redéfinie dans ce fichier — seuls quelques symboles utilitaires `_deduce_role`,
`_load_active_term`, `_sha256_hex` sont importés, `common/auth.py:17`), mais **redéfinit
entièrement** `OAuth2Manager` avec un comportement propre à LarcProf.

##### `AuthManager` (implémentation réelle dans `LarcCommon/larccommon/auth.py`)

- `change_password(email, current, new)` (`larccommon/auth.py:68-95`) — vérifie l'ancien hash puis
  `UPDATE larcauth_aecuser SET password = %s WHERE LOWER(email) = %s`. **Non utilisé par
  `views/password.py`** (voir §2.5, Points d'attention — dupliqué au lieu d'être appelé).
- `auth_intranet(email, password)` (`larccommon/auth.py:97-149`) — décrit en détail au §2.2.
- `auth_pin(email, pin, local_conn)` (`larccommon/auth.py:151-175`) — décrit en détail au §2.2.
- `check_teacher_exists(email)` (`larccommon/auth.py:177-224`) — décrit en détail au §2.2 ; exige
  une entrée dans `larcauth_teachadm` (table de liaison prof-administratif) en plus de
  `larcauth_aecuser`, et une année scolaire avec `current_term_number IS NOT NULL`.

##### `OAuth2Manager` local (`common/auth.py:53-201`) — duplication délibérée de `larccommon.auth.OAuth2Manager`

Implémente le flux OAuth2 PKCE Google (serveur HTTP local éphémère sur le port **8765**, écoute
`/callback`, échange de code contre token, décodage du JWT `id_token` sans vérification de
signature — lecture directe du payload base64). Points de divergence volontaire par rapport à la
version `larccommon` (utilisée par LarcSuperviseur) :

| | `common/auth.py` (LarcProf) | `larccommon/auth.py` (LarcSuperviseur) |
|---|---|---|
| Domaine exigé (`hd`) | `arc-en-ciel.org` (constante en dur, `common/auth.py:80`) | `cls.HOSTED_DOMAIN` (`'arc-en-ciel.org'`, `larccommon/auth.py:260`, via attribut de classe) |
| Contrôle d'accès après login Google | **Liaison d'instance** (`common/auth.py:137-158`) : l'email Google doit correspondre à `module_config.email_professeur` en SQLite locale | **Rôle serveur** (`larccommon/auth.py:364-366`) : exige `is_dir or is_coord or is_sup` côté PostgreSQL |
| Détermination du rôle | `_deduce_role` (priorité admin/coord/secr/sup/prof, `common/auth.py:188-189`) | `_deduce_role_superviseur` (priorité admin/coord/sup uniquement, `larccommon/auth.py:368`) |
| Page HTML de callback | Statique, mentionne « eLarcProf » en dur (`common/auth.py:40`) | Utilise `OAuth2Manager.APP_DISPLAY` (`'LarcSuperviseur'`, `larccommon/auth.py:243-246`) |

##### Points d'attention

- Les deux classes `_CallbackHandler` et `OAuth2Manager` sont donc dupliquées presque à l'identique
  entre `common/auth.py` et `larccommon/auth.py`, avec un port HTTP local **identique (8765)** dans
  les deux implémentations. Si une application LarcSuperviseur et une instance LarcProf tentaient
  une authentification OAuth2 simultanément sur le même poste, l'une des deux échouerait au
  `HTTPServer(('localhost', cls.PORT), ...)` (port déjà utilisé) — comportement à vérifier en
  usage réel (cas d'usage peu probable mais non empêché par le code).
- La constante `hd` en dur dans `common/auth.py:80` (`'arc-en-ciel.org'`) duplique
  `OAuth2Manager.HOSTED_DOMAIN` côté `larccommon` — un changement de domaine devrait être
  répercuté aux deux endroits.

#### 4.3 `common/database.py` — Gestion des connexions PostgreSQL/SQLite

##### Rôle

Classe `Database` (singleton `db`) gérant 3 connexions possibles : Intranet (PostgreSQL local),
Cloud (Supabase, PgBouncer), SQLite locale — plus un mécanisme de **synchronisation bidirectionnelle
avec le singleton équivalent de `larccommon.database`**, nécessaire car `AuthManager`
(`larccommon/auth.py`) importe `from .database import db` — c'est-à-dire **le `db` de
`larccommon`**, pas celui de LarcProf — alors que le reste du code LarcProf utilise
`common.database.db`. Les deux singletons doivent donc pointer vers les mêmes connexions
psycopg2 vivantes pour que l'authentification fonctionne.

##### Flux

- `connect_intranet()` (`database.py:94-115`) : lit `config.ini` section `[IntranetDatabase]`
  (host, port, dbname défaut `NewLarcDB`, user, password — défauts `127.0.0.1:5432/postgres/postgres`),
  ouvre une connexion `psycopg2` avec `application_name='eLarcProf'`, `connect_timeout=5`,
  **`autocommit = True`** (`database.py:103`). En cas de succès, appelle
  `_sync_server_to_larccommon()` (`database.py:67-75`) qui copie la référence de connexion dans
  `larccommon.database.db._intranet` et son `_server_mode`.
- `connect_cloud()` (`database.py:117-139`) : idem section `[SupabaseDatabase]`, avec
  `sslmode='require'` en plus.
- `connect_sqlite(db_path)` (`database.py:141-158`) : `sqlite3.connect(..., check_same_thread=False)`,
  `row_factory = sqlite3.Row`, `PRAGMA journal_mode=WAL`.
- `sync_from_larccommon()` (`database.py:77-92`) : sens inverse — copie les connexions déjà
  établies par `larccommon.database.db` (utilisé quand LarcHub a déjà connecté PostgreSQL avant de
  charger le module LarcProf, pour éviter une reconnexion redondante — commentaire
  `database.py:80-81`).
- `disconnect_all()` (`database.py:160-189`) : ferme et vide les 3 connexions **des deux
  singletons** (LarcProf et larccommon), remet les modes à `NONE`.
- `before_update(user_id)` (`database.py:191-199`) : attache un contexte d'audit
  (`larccommon.audit_context.attach`/`refresh`) à la connexion serveur active — utilisé
  (probablement) pour tracer l'auteur des `UPDATE`/`INSERT` côté PostgreSQL (mécanisme d'audit
  hors périmètre détaillé de ce document ; **aucun appelant de `before_update` n'a été trouvé
  dans les fichiers lus** — comportement à vérifier, potentiellement invoqué depuis un module hors
  périmètre comme `common/sync.py`).
- Propriétés `server_conn` (Intranet ou Cloud selon `_server_mode`), `local_conn` (SQLite),
  `mode`, `server_mode`, `is_server_connected`.

##### Points d'attention — bug latent identifié

`database.py:15-33` :
```python
try:
    from larccommon.config_loader import find_cfg
except ImportError:
    from larccommon.error_reporting import get_reporter
    get_reporter().report_exception()
    from .logger import log as _log
    def find_cfg() -> str:
        ...
        for p in candidates:
            ...
            if os.path.isfile(p):
                return p
        _log("AVERTISSEMENT : config.ini introuvable. Utilisation des valeurs par défaut.")
        log("AVERTISSEMENT : config.ini introuvable. Utilisation des valeurs par défaut.")   # <-- database.py:32
        return os.path.normpath(candidates[0])
```
La ligne `database.py:32` appelle `log(...)` — un nom **jamais importé sous ce nom** dans ce
fichier (seul `_log` est importé, ici et à nouveau au niveau module `database.py:35`). Ce chemin
de code n'est exercé que si `from larccommon.config_loader import find_cfg` échoue **et** qu'aucun
`config.ini` n'est trouvé parmi les chemins candidats — un cas rare en usage normal, mais s'il
survient, l'appel lève un `NameError: name 'log' is not defined` non intercepté (aucun
`try/except` autour de cet appel), ce qui ferait planter `find_cfg()` au lieu de simplement
journaliser un avertissement et retourner un chemin par défaut. C'est le même type d'erreur
(appel à un `log()` non importé) que celui déjà corrigé aujourd'hui dans `common/sqlite_init.py`
— cette occurrence-ci n'a pas été corrigée.

#### 4.4 `common/network.py` — Couleur d'état réseau

##### Rôle

Fichier de 10 lignes : une seule fonction, `network_mode_color(mode: NetworkMode) -> str`
(`network.py:5-10`), qui mappe `NetworkMode.INTRANET → '#27ae60'` (vert), `INTERNET → '#2980b9'`
(bleu), `OFFLINE → '#e67e22'` (orange), défaut `'#7f8c8d'` (gris) — utilisée pour colorer la
pastille de statut réseau de `LoginWindow` (`login.py:556`, `login.py:613`).

`NetworkMode` et `detect_network()` sont importés depuis `larccommon.network`
(`network.py:2`) — implémentation réelle :

`LarcCommon/larccommon/network.py:16-41` — `detect_network()` lit `config.ini` section
`[IntranetDatabase]` (host/port), tente une connexion TCP brute (`socket.create_connection`,
timeout 1.5 s) pour détecter l'Intranet, puis une requête HTTP vers `https://www.google.com`
(timeout 3 s) pour détecter Internet. Retourne `(intranet_ok, internet_ok)` — **toutes les
exceptions sont absorbées** (`except OSError`/`except Exception` avec `pass` après report), donc
la fonction ne lève jamais, elle retourne simplement `(False, False)` en cas de problème réseau
total.

##### Points d'attention

- Le test « Internet » interroge `https://www.google.com`, un service externe non contrôlé par
  Arc-en-Ciel — un blocage réseau spécifique à Google (pare-feu scolaire, panne régionale Google)
  ferait passer `internet_ok` à `False` même si le Cloud Supabase reste joignable, et
  inversement.

#### 4.5 `common/logger.py` — Redirection du fichier de log

##### Rôle

Fichier de 6 lignes : réexporte `log`, `set_log_to_file`, `get_log_path`, `set_log_filename`
depuis `larccommon.logger`, puis appelle immédiatement `set_log_filename(...)` avec le chemin
`<LarcProf>/elarc.log` (`logger.py:6`) — **effet de bord global à l'import** : tout module qui
importe `common.logger` (même indirectement) redirige le fichier de log partagé de
`larccommon.logger` vers `LarcProf/elarc.log`, ce qui affecte potentiellement aussi les messages
logués par du code `larccommon` importé dans le même process (ex. si LarcProf tourne dans LarcHub
aux côtés d'autres modules qui logguent aussi via `larccommon.logger`).

---

### 5. Tableaux de bord post-connexion — `HomeWindow`, `HomeWidget`, `ProfWorkspace`

#### Contexte général

Après une authentification réussie, deux chemins distincts mènent à un tableau de bord quasiment
identique visuellement et fonctionnellement, **codés indépendamment dans deux fichiers séparés** :

- **`HomeWindow`** (`views/home_window.py`, `QMainWindow`, 792 lignes) — utilisée en mode
  **standalone** : ouverte par `LoginWindow._open_main_window` (`login_helpers.py:196-205`) et par
  `main.py` (mode 4, indirectement via `LoginWindow`). C'est une vraie fenêtre top-level avec sa
  propre barre de statut.
- **`HomeWidget`** (`views/home_widget.py`, `QWidget`, 685 lignes) — utilisée en mode **intégré**
  dans LarcHub, via `ProfWorkspace` (`views/prof_workspace.py`, 92 lignes) qui l'empile dans un
  `QStackedWidget` aux côtés de `MainWindow` (grille de notes). N'émet pas de fenêtre séparée mais
  des signaux Qt (`navigation_requested`, `status_message`).

Les deux fichiers partagent : les mêmes constantes (`_STAT_TABLE_LABELS`, `_PEI_BUTTONS`,
`_DP_BUTTONS`, `_BTN_VIEW` — définies **séparément et identiquement** dans chaque fichier,
`home_window.py:37-71` / `home_widget.py:33-67`), la même structure visuelle (header, carte
profil, carte synchro, cartes programmes PEI/DP, bouton professeur principal), et une bonne partie
de la logique métier (détection des programmes, visibilité des boutons, comptage des données non
synchronisées). **Ce sont deux implémentations quasi identiques du même tableau de bord,
maintenues en parallèle** — dette technique explicitement identifiée par l'énoncé de ce document
et confirmée par la lecture complète des deux fichiers (voir divergences précises ci-dessous).

#### 5.1 `views/home_window.py` — `HomeWindow` (standalone)

##### Rôle

Fenêtre principale affichée juste après connexion. Affiche le profil du professeur, l'état de
synchronisation, et donne accès aux programmes PEI/DP (boutons vers `MainWindow`, la grille de
notes) ainsi qu'au rôle « professeur principal » et à la déconnexion.

##### Flux

- **Construction** (`__init__`, `home_window.py:138-150`) : taille de fenêtre dérivée de
  `ds.window_width`/`ds.window_height` (106 %×85 % / 82 %×65 % pour min/défaut), `_setup_ui()`,
  `_load_data()`, connexion `ds.theme_changed → self._restyle`.
- **`_setup_ui`** (`home_window.py:155-186`) : header (bandeau coloré `primary`) + corps en deux
  colonnes (`QHBoxLayout`, ratio 4:6) — gauche : carte profil (`_build_profile_card`, ratio 4) +
  carte synchro (`_build_sync_card`, ratio 5) ; droite : zone programmes
  (`_build_pgm_area`). Barre de statut avec message initial « Pret ».
- **Carte profil** (`_build_profile_card`, `home_window.py:233-289`) : nom, rôle
  (`session.role_display`), email, séparateur, année scolaire, trimestre, nombre de
  classes-matières, nombre d'élèves, puis deux indicateurs de connexion (Intranet/Cloud, point
  plein vert si actif).
- **Carte synchro** (`_build_sync_card`, `home_window.py:292-339`) : titre « Synchronisation »,
  date de dernière synchro, mode de synchro (source), gros compteur de modifications non
  synchronisées, détail par table, bouton « Synchroniser » (`_do_sync`).
- **Zone programmes** (`_build_pgm_area`/`_build_program_card`, `home_window.py:342-400`) : une
  carte par programme (PEI, DP), chaque carte affichant une grille 2 colonnes de boutons
  (`_PEI_BUTTONS`/`_DP_BUTTONS`), plus un bouton « Professeur principal » et un bouton
  « Deconnexion » en bas.
- **`_load_data`** (`home_window.py:405-409`) : `_load_profile()`, `_load_sync()`,
  `_apply_program_visibility()` **synchrones**, puis `_load_counts()` **différé de 50 ms**
  (`QTimer.singleShot(50, self._load_counts)`) — vraisemblablement pour laisser l'UI se peindre
  avant d'exécuter les requêtes de comptage.
- **`_load_profile`** (`home_window.py:411-471`) : remplit les labels depuis `session.*` (pas de
  requête SQL pour nom/rôle/email — vient uniquement du singleton `session` déjà peuplé par
  `_apply_session`), puis lit `SELECT updated_at FROM session_cache WHERE user_id = ?`
  (dernière connexion) et `SELECT annee_scolaire, trimestre_courant FROM module_config WHERE id = 1`.
- **`_load_counts`** (`home_window.py:473-502`) : `SELECT COUNT(*) FROM larcauth_classroom_termsubject WHERE fk_teacher_id = ?`
  (classes-matières), puis un comptage d'élèves distincts via jointure
  `classroom_termsubject → classroom → student` filtrée par `fk_teacher_id`
  (`home_window.py:488-496`).
- **`_load_sync`** (`home_window.py:504-546`) : date de dernière synchro
  (`module_config.derniere_synchronisation`), source (`sync_state.last_source`), puis pour
  **chacune des 6 `BUSINESS_TABLES`**, appelle `_count_unsynced_rows(table)`
  (`home_window.py:548-567`) : lit dynamiquement les colonnes de la table via `PRAGMA table_info`,
  construit une clause `OR` comparant **chaque colonne** entre la table de travail (`w`) et sa
  référence (`r`) (`w."col" IS NOT r."col"` + gestion explicite des `NULL`), et compte les lignes
  divergentes par `JOIN ... ON w.id = r.id`. Le total et le détail par table alimentent
  `_lbl_unsynced_count`/`_lbl_unsynced_detail`.
- **`_detect_programs`** (`home_window.py:572-596`) : `SELECT DISTINCT p.sigle FROM larcauth_classroom_termsubject cts JOIN larcauth_classroom c ... JOIN larcauth_level l ... JOIN larcauth_program p ... WHERE cts.fk_teacher_id = ?`
  — classe chaque sigle en PEI (`'PEI'`/`'MYP'`) et/ou DP (`'DPFR'`/`'DPEN'`/`'DP'`).
- **`_detect_button_visibility`** (`home_window.py:598-656`) : logique par clé de bouton — ex.
  `pei_grp_matieres`/`dp_grp_matieres` vérifient une classe-matière active dans le programme
  concerné (`fk_program_id IN (12, 22)` pour PEI, `(13, 23)` pour DP — IDs de programme en dur) ;
  `pei_interdisc`/`pei_pp`/`dp_tdc`/`dp_cas`/`dp_memoire` vérifient des « autres matières »
  (`larcauth_classroom_termothersubject`) filtrées par motif de libellé (`LIKE 'Th%'` pour TDC,
  `'Cr%'` pour CAS, `'Me%'`/`'Ext%'` pour Mémoire, `'Personal%'`/`'Projet%'` pour Projet
  Personnel) et par un flag `unit_multisubjects` pour les unités interdisciplinaires.
- **`_apply_program_visibility`** (`home_window.py:658-682`) : cache les sections/boutons non
  pertinents, et détermine la visibilité du bouton « Professeur principal » via
  `SELECT 1 FROM larcauth_classroom WHERE fk_headteacher_id = ?` (`home_window.py:673-676`) — voir
  Points d'attention.
- **`_on_pgm_btn_clicked`** (`home_window.py:687-692`) : ferme sur `key`, appelle
  `_open_main_window(focus=_BTN_VIEW.get(key, key))`.
- **`_open_main_window`** (`home_window.py:700-719`) : instancie `MainWindow`, l'affiche
  maximisée, cache `HomeWindow` ; intercepte `closeEvent` de `MainWindow` pour revenir au tableau
  de bord (`self.show()`, `_load_sync()`) au lieu de fermer l'application, **à condition que
  `MainWindow._confirm_leave()` retourne `True`** (probablement une confirmation « modifications
  non enregistrées », implémentation hors périmètre).
- **`_do_sync`** (`home_window.py:721-742`) : reconnecte le serveur si nécessaire
  (Intranet puis Cloud en fallback), appelle `sync_manager.pull_push()` (`common/sync.py`, hors
  périmètre détaillé — retourne un `SyncReport`), affiche un message de statut selon
  `report.has_errors`/`has_conflicts`, rafraîchit `_load_sync()`.
- **`_logout`** (`home_window.py:744-756`) : `session.is_authenticated = False`,
  `db.disconnect_all()`, ré-affiche la fenêtre de login parente si elle existe, sinon en crée une
  nouvelle, puis `self.close()`.

##### Requêtes SQL (synthèse)

| Fichier:ligne | Requête | Table(s) |
|---|---|---|
| `home_window.py:447-449` | `SELECT updated_at FROM session_cache WHERE user_id = ?` | `session_cache` |
| `home_window.py:458-460` | `SELECT annee_scolaire, trimestre_courant FROM module_config WHERE id = 1` | `module_config` |
| `home_window.py:478-481` | `SELECT COUNT(*) FROM larcauth_classroom_termsubject WHERE fk_teacher_id = ?` | `larcauth_classroom_termsubject` |
| `home_window.py:489-496` | `SELECT COUNT(DISTINCT s.aecuser_ptr_id) ... JOIN larcauth_classroom ... JOIN larcauth_student ... WHERE cts.fk_teacher_id = ?` | `larcauth_classroom_termsubject`, `larcauth_classroom`, `larcauth_student` |
| `home_window.py:509-511` | `SELECT derniere_synchronisation FROM module_config WHERE id = 1` | `module_config` |
| `home_window.py:521-523` | `SELECT last_source FROM sync_state LIMIT 1` | `sync_state` |
| `home_window.py:561` | `SELECT COUNT(*) FROM "<table>" w JOIN "<table>_ref" r ON w.id = r.id WHERE (<diff colonne par colonne>)` | chaque table de `BUSINESS_TABLES` + son `_ref` |
| `home_window.py:578-585` | `SELECT DISTINCT p.sigle FROM larcauth_classroom_termsubject ... WHERE cts.fk_teacher_id = ?` | `larcauth_classroom_termsubject/classroom/level/program` |
| `home_window.py:608-615`, `618-627`, `629-638`, `646-650` | requêtes de visibilité par bouton (voir Flux) | `larcauth_classroom_termsubject`, `larcauth_classroom_termothersubject` |
| `home_window.py:673-676` | `SELECT 1 FROM larcauth_classroom WHERE fk_headteacher_id = ? LIMIT 1` | `larcauth_classroom` |

##### Points d'attention (spécifiques à `home_window.py`)

- `_apply_program_visibility` (`home_window.py:673-676`) interroge la colonne
  `larcauth_classroom.fk_headteacher_id` — **cette colonne n'existe nulle part dans le schéma
  SQLite local** (ni dans `_DDL`, `sqlite_init.py:202-207`, ni dans aucune migration listée en
  §3). La requête échoue donc systématiquement avec une erreur SQLite (« no such column »),
  silencieusement absorbée par le `try/except` (`home_window.py:678-681`), laissant
  `pp_visible = False` en permanence. **Le bouton « Professeur principal » ne peut donc jamais
  apparaître via ce chemin de code**, quelle que soit la réalité métier. Comportement à vérifier :
  soit la colonne doit être ajoutée (DDL + migration + alimentation par `take_teacher_data` ou
  `common/sync.py`), soit la requête cible la mauvaise table/colonne.

#### 5.2 `views/home_widget.py` — `HomeWidget` (intégré LarcHub)

##### Rôle

Version `QWidget` du même tableau de bord, conçue pour être embarquée par `ProfWorkspace`. N'a pas
de barre de statut propre (`QLabel` de statut en bas, `_status_label`) et communique la navigation
via le signal `navigation_requested(str)` plutôt que d'ouvrir une fenêtre.

##### Flux

Globalement symétrique à `HomeWindow` §5.1 (mêmes cartes, même disposition, mêmes constantes de
boutons) avec les différences suivantes, relevées ligne à ligne :

- **`_build_pgm_area`** (`home_widget.py:317-352`) place les cartes PEI et DP côte à côte dans un
  `QHBoxLayout` (`_pgm_grid`) plutôt que l'une sous l'autre comme dans `HomeWindow`
  (`_build_program_card` empilé verticalement, `home_window.py:348-354`) — différence de mise en
  page héritée de la disposition en widget intégré (plus large, moins haut) plutôt qu'en fenêtre
  dédiée.
- **`_load_profile`** (`home_widget.py:389-457`) : utilise `db.mode` (pas `session.conn_mode`)
  pour le libellé d'en-tête (`_hdr_mode`, mapping `DBMode → texte`, `home_widget.py:391-397`), et
  lit les indicateurs de connexion directement sur `db._intranet is not None` / `db._cloud is not None`
  (accès aux attributs privés de `Database`, `home_widget.py:446-447`) plutôt que sur
  `db.server_mode`/`DBMode` comme le fait `HomeWindow._load_profile`
  (`home_window.py:427-429`, qui compare `db.server_mode == DBMode.INTRANET`) — deux façons
  différentes d'obtenir une information équivalente.
- **`_load_sync`** (`home_widget.py:459-504`) : la source de la date de dernière synchro est
  `SELECT table_name, last_sync, last_source FROM sync_state ORDER BY last_sync DESC LIMIT 1`
  (la ligne la plus récente, toutes tables confondues) — différent de `HomeWindow` qui lit
  `module_config.derniere_synchronisation` (une date globale distincte, mise à jour par
  `init_module_config`, pas par la synchro elle-même). **Le compteur de modifications non
  synchronisées utilise une méthode de calcul différente** : `SELECT COUNT(*) FROM t INNER JOIN r ON t.id=r.id WHERE t.sync_version != r.sync_version`
  (`home_widget.py:488-492`) — une seule colonne comparée (`sync_version`), au lieu de la
  comparaison colonne-par-colonne de `HomeWindow._count_unsynced_rows`. Comportement à vérifier :
  la table `larcauth_learnerpei_has_termsubjectpei` (et les autres `BUSINESS_TABLES` hors
  `larcauth_evaluation`) ne reçoit pas de colonne `sync_version` via les migrations de `_DDL`
  documentées en §3 ; si la requête PostgreSQL sous-jacente de `take_teacher_data` ne renvoie pas
  non plus cette colonne pour ces tables, `SELECT 1 FROM <table> LIMIT 0` (test d'existence,
  `home_widget.py:486-487`) réussirait mais le `SELECT ... WHERE t.sync_version != r.sync_version`
  échouerait (colonne absente), exception absorbée par le `except Exception` englobant
  (`home_widget.py:498-501`) — dans ce cas cette table ne contribuerait jamais au compteur affiché,
  contrairement à `HomeWindow` qui compare bien toutes les colonnes réellement présentes.
- **`_detect_programs`** (`home_widget.py:532-557`) et **`_detect_button_visibility`**
  (`home_widget.py:559-625`) interrogent `cts.fk_supervisor_id` sur `larcauth_classroom_termsubject`
  (`home_widget.py:541`, `549`, `577-580`) — voir Points d'attention, bug confirmé.
- **`_do_sync`** (`home_widget.py:643-660`) : pas de reconnexion automatique au serveur avant
  `sync_manager.pull_push()` (contrairement à `HomeWindow._do_sync`, `home_window.py:726-730`, qui
  tente `connect_intranet()`/`connect_cloud()` si `db.server_conn is None`) ; affiche le message de
  statut dans `_status_label` avec un retour à « Pret » différé de 3 s
  (`QTimer.singleShot(3000, ...)`, `home_widget.py:660`) — absent de `HomeWindow` (qui utilise la
  temporisation native de `QStatusBar.showMessage(msg, ms)`).

##### Requêtes SQL (synthèse — uniquement celles qui diffèrent de `HomeWindow`)

| Fichier:ligne | Requête | Anomalie |
|---|---|---|
| `home_widget.py:420-424` | `SELECT COUNT(DISTINCT fk_classroom_id) FROM larcauth_classroom_termsubject WHERE fk_supervisor_id = ? AND (enabled=1 OR enabled='true')` | **colonne `fk_supervisor_id` inexistante sur cette table** (schéma réel : `fk_teacher_id`, `sqlite_init.py:215`) |
| `home_widget.py:432-438` | `SELECT COUNT(DISTINCT lp.fk_student_id) FROM larcauth_learnerpei_has_termsubjectpei lp JOIN larcauth_classroom_termsubject cts ON lp.fk_classroom_termsubject_ptr_id = cts.id WHERE cts.fk_supervisor_id = ?` | **deux colonnes inexistantes** : `lp.fk_classroom_termsubject_ptr_id` (le schéma réel a `learner_has_termsubject_ptr_id`, `sqlite_init.py:144`) et `cts.fk_supervisor_id` |
| `home_widget.py:538-543`, `546-551` | `_detect_programs` — jointure `larcauth_classroom_termsubject cts ... WHERE cts.fk_supervisor_id = ?` | même colonne inexistante |
| `home_widget.py:574-581` | `_detect_button_visibility('pei_grp_matieres'/'dp_grp_matieres')` — `WHERE cts.fk_supervisor_id = ?` | même colonne inexistante |
| `home_widget.py:522` | `SELECT 1 FROM larcauth_classroom WHERE fk_headteacher_id = ? LIMIT 1` | même colonne absente que `home_window.py:674` (§5.1) |

##### Points d'attention (spécifiques à `home_widget.py`) — bugs confirmés par lecture du schéma

- **Colonne `fk_supervisor_id` inexistante sur `larcauth_classroom_termsubject`** : le schéma
  local (`sqlite_init.py:209-217`) définit `fk_teacher_id` sur cette table (confirmé également par
  l'usage cohérent de `fk_teacher_id` dans `home_window.py` et dans les requêtes PostgreSQL de
  `take_teacher_data`, `sqlite_init.py:602/618/635/666`). `home_widget.py` interroge à quatre
  endroits `cts.fk_supervisor_id` sur cette même table (`_load_profile` deux fois, lignes 421 et
  435-436 ; `_detect_programs`, lignes 541 et 549 ; `_detect_button_visibility`, lignes 577-580).
  Chacune de ces requêtes échoue avec une erreur SQLite (« no such column: cts.fk_supervisor_id »
  ou équivalent selon le moteur de requête), interceptée par un `except Exception` qui affiche
  `"—"` ou renvoie `False`/`{'PEI': False, 'DP': False}` sans remonter d'erreur visible à
  l'utilisateur. **Conséquence pratique** : dans le tableau de bord intégré à LarcHub
  (`HomeWidget`), le nombre de classes, le nombre d'élèves, et la détection des programmes
  PEI/DP (donc l'affichage des cartes de boutons PEI/DP et du bouton professeur principal, qui
  dépend indirectement de `_detect_programs`) sont **structurellement non fonctionnels** — alors
  que la version standalone (`HomeWindow`, colonne `fk_teacher_id` correcte) fonctionne
  normalement pour les mêmes données. C'est une régression silencieuse propre à l'intégration
  LarcHub.
- La colonne `lp.fk_classroom_termsubject_ptr_id` utilisée dans le comptage d'élèves
  (`home_widget.py:433-436`) n'existe pas non plus sur `larcauth_learnerpei_has_termsubjectpei`
  (schéma réel : `learner_has_termsubject_ptr_id`, `fk_pei_id`, `fk_termsubjectpei_id` —
  `sqlite_init.py:142-150`) — deuxième cause indépendante d'échec silencieux de la même requête.
- Ces quatre requêtes cassées n'ont pas d'équivalent fautif dans `home_window.py`, qui utilise
  systématiquement `fk_teacher_id` — la divergence de nommage de colonne entre les deux fichiers
  « jumeaux » illustre concrètement le risque de la duplication : une correction ou une évolution
  de schéma appliquée à l'un des deux fichiers (ici, apparemment, `home_window.py` a le nom de
  colonne correct) n'a pas été répercutée dans l'autre.

#### 5.3 `views/prof_workspace.py` — `ProfWorkspace` (intégration LarcHub)

##### Rôle

Composant de liaison entre `HomeWidget` (page 0) et `MainWindow` (page 1, la grille de notes),
dans un `QStackedWidget`, pour permettre à LarcHub d'afficher LarcProf comme une section standard
de son interface (sans fenêtre séparée).

##### Flux

- **`__init__`** (`prof_workspace.py:24-35`) : crée le `QStackedWidget`, layout sans marges,
  appelle `_init_home()`.
- **`_init_home`** (`prof_workspace.py:40-45`) : instancie `HomeWidget`, connecte son signal
  `navigation_requested` → `self._on_navigate`, l'ajoute au stack (page 0).
- **`_on_navigate(focus)`** (`prof_workspace.py:50-86`, `@safe_slot`) — appelée quand le prof
  clique sur un bouton programme dans `HomeWidget` :
  1. Si une `MainWindow` précédente existe encore dans le stack, la retire et la marque pour
     suppression (`deleteLater()`) — **une nouvelle `MainWindow` est recréée à chaque navigation**,
     jamais réutilisée (contrairement à `HomeWindow._open_main_window` qui recrée aussi à chaque
     fois, donc comportement cohérent entre les deux, mais coûteux si la grille de notes est
     lourde à construire — comportement à vérifier en usage réel).
  2. Instancie `MainWindow()`, vide son titre de fenêtre (`setWindowTitle("")` — sans effet visible
     puisqu'elle n'est pas top-level dans ce contexte).
  3. Intercepte `closeEvent` : au lieu de fermer, revient à la page 0 du stack
     (`self._stack.setCurrentIndex(0)`), rafraîchit `HomeWidget` (`_load_sync()`,
     `_load_profile()`), et **`event.ignore()`** (`prof_workspace.py:76`) — empêche
     définitivement la fermeture réelle du widget `MainWindow` embarqué (cohérent avec le fait
     qu'un `QWidget` enfant d'un `QStackedWidget` n'a pas vocation à se fermer indépendamment).
  4. Masque la barre de statut de `MainWindow` (`sb.hide()`, `prof_workspace.py:81-83`) —
     redondante dans un contexte intégré.
  5. Ajoute la nouvelle `MainWindow` au stack et la rend courante.
- **`refresh_home`** (`prof_workspace.py:88-92`) : méthode publique pour rafraîchir
  `HomeWidget` depuis l'extérieur (probablement appelée par LarcHub lors d'un retour de
  navigation globale — aucun appelant trouvé dans le périmètre lu, comportement à vérifier).

##### Points d'attention

- `_on_navigate` (`prof_workspace.py:66`) lit `original_close = self._main_window.closeEvent`
  mais **ne l'utilise jamais** ensuite (la variable est assignée puis jamais référencée dans
  `_intercept_close` ni ailleurs) — code mort/vestige, probablement un reliquat d'une version
  antérieure qui chaînait l'ancien `closeEvent`.
- Le remplacement systématique de `closeEvent` par une fonction qui ne l'appelle jamais
  (`prof_workspace.py:68-76`) signifie que toute logique définie dans
  `MainWindow.closeEvent` d'origine (hors `_confirm_leave()`, appelée explicitement) est
  **court-circuitée** dans le contexte LarcHub — comportement à vérifier si `MainWindow` a
  d'autres effets de bord dans son `closeEvent` d'origine (fichier hors périmètre de ce document).

---

### 6. Points d'attention généraux (synthèse transverse)

Cette section récapitule, pour référence rapide, les incohérences et bugs relevés lors de la
lecture — aucun n'a été corrigé dans le cadre de la rédaction de ce document, conformément à la
consigne (documentation seulement).

1. **`common/database.py:32`** — appel à `log(...)` non importé dans le chemin de repli
   `find_cfg()` (déclenché seulement si `larccommon.config_loader` est indisponible **et**
   qu'aucun `config.ini` n'est trouvé) → `NameError` non intercepté si ce chemin est exercé. Même
   nature que le bug déjà corrigé aujourd'hui dans `sqlite_init.py`, non corrigé ici.
2. **`views/login_auth.py:249-260`** — bloc de code strictement mort (condition identique à
   `login_auth.py:216-236`, qui retourne toujours avant d'atteindre le second bloc).
3. **`common/sqlite_init.py:80-140`** — `CREATE TABLE IF NOT EXISTS larcauth_evaluation_ref` défini
   deux fois consécutivement à l'identique dans `_DDL` (sans effet fonctionnel, mais SQL mort).
4. **`views/home_widget.py`** — quatre requêtes SQL utilisent une colonne inexistante
   `cts.fk_supervisor_id` sur `larcauth_classroom_termsubject` (le schéma réel a `fk_teacher_id`,
   confirmé à la fois par le DDL et par l'usage correct dans `home_window.py`), et une utilise
   `lp.fk_classroom_termsubject_ptr_id`, colonne également inexistante sur
   `larcauth_learnerpei_has_termsubjectpei`. Conséquence : dans le tableau de bord intégré
   LarcHub, les compteurs classes/élèves et la détection des programmes PEI/DP échouent
   silencieusement (exceptions absorbées) et affichent des valeurs par défaut vides/fausses.
5. **`views/home_window.py:673-676`** et **`views/home_widget.py:522`** — les deux fichiers
   interrogent `larcauth_classroom.fk_headteacher_id`, colonne absente du schéma SQLite local
   (ni dans `_DDL` ni dans aucune migration) — le bouton « Professeur principal » ne peut donc
   jamais devenir visible via ces requêtes, dans aucun des deux tableaux de bord.
6. **`views/home_window.py` vs `views/home_widget.py`** — les deux fichiers calculent le
   « nombre de modifications non synchronisées » avec deux algorithmes différents (comparaison
   colonne-par-colonne vs. comparaison de la seule colonne `sync_version`) et lisent la « date de
   dernière synchronisation » depuis deux sources différentes (`module_config.derniere_synchronisation`
   vs. `MAX(sync_state.last_sync)`) — deux implémentations peuvent afficher des chiffres différents
   pour un même état réel de la base.
7. **`views/password.py:89`** — `sqlite_init.save_session(session, new_pin)` passe le singleton
   `Session` là où `AuthResult` est attendu (fonctionne par duck typing, mais ne respecte pas
   l'annotation de type et est fragile à toute évolution divergente des deux dataclasses).
8. **`views/password.py:198-206`** — duplique la logique de `AuthManager.change_password`
   (`LarcCommon/larccommon/auth.py:68-95`) au lieu de l'appeler.
9. **`common/auth.py`** — `OAuth2Manager` est dupliqué (avec des règles d'accès différentes,
   volontairement) par rapport à `LarcCommon/larccommon/auth.py`, sur le **même port HTTP local
   8765** dans les deux implémentations.
10. **`common/sqlite_init.py`** — les 6 `BUSINESS_TABLES` (et leurs `_ref`) sont recréées en
    schéma 100 % `TEXT` à chaque `take_teacher_data`, ce qui fait du schéma PostgreSQL source la
    véritable source de vérité du schéma local pour ces tables (le DDL typé initial de
    `_DDL` n'a d'effet que jusqu'au premier téléchargement).
11. **`common/sqlite_init.py:653-655`** — `larcauth_learner_has_termothersubject` est téléchargée
    **sans aucun filtre** (toute la table, tous professeurs confondus), contrairement aux 5 autres
    requêtes de `take_teacher_data` qui filtrent par professeur/trimestre — comportement à
    vérifier (choix délibéré ou oubli).
12. **`common/sqlite_init.py`** — `init_cloud()` semble être une implémentation inachevée : elle ne
    fait aucun appel réseau vers Supabase malgré les en-têtes HTTP construits, et aucun appelant
    n'a été trouvé dans le périmètre lu.
13. **`views/prof_workspace.py:66`** — variable `original_close` assignée puis jamais utilisée
    (vestige de code).

---

*Document généré à partir d'une lecture intégrale des fichiers listés en introduction, le
2026-09-16. Toute évolution ultérieure de ces fichiers doit s'accompagner d'une mise à jour de ce
document.*


---

## Partie II — Fenêtre principale et système d'évaluations

**Statut** : brouillon de documentation fonctionnelle exhaustive, rédigé exclusivement à partir
d'une lecture intégrale du code (aucune supposition). Toute affirmation non triviale porte une
référence `fichier:ligne`.

**Fichiers couverts** :
- `views/main_window.py`, `views/main_data.py`, `views/main_actions.py`, `views/main_notes.py`
  (les 4 morceaux qui composent `MainWindow`)
- `views/eval_manager.py`, `views/evaluation_panel.py`
- `views/grid_table.py`, `common/grid_config.py`
- `views/weight_dialog.py` (+ `common/calc_engine.py` pour le contexte de calcul)
- `views/student_card_view.py`
- `views/event_dialog.py`, `common/event_service.py`

---

### 1. Vue d'ensemble

`MainWindow` (`views/main_window.py:65`) est déclarée comme :

```python
class MainWindow(DataMixin, NotesGridMixin, SyncActionsMixin, QMainWindow):
```

Elle n'implémente elle-même que la construction de l'UI (header, sidebar, grille, barre
d'actions) et la réactivité au thème. Toute la logique métier est répartie dans 3 mixins qui
n'héritent d'aucune classe (des `object` implicites) et supposent l'existence des attributs
d'instance créés dans `MainWindow.__init__` :

| Mixin | Fichier | Rôle |
|---|---|---|
| `DataMixin` | `views/main_data.py` | Chargement des données SQLite (items matière-classe, élèves, évaluations) |
| `NotesGridMixin` | `views/main_notes.py` | Construction/rendu de la grille élèves × notes, sauvegarde, calcul auto |
| `SyncActionsMixin` | `views/main_actions.py` | Boutons Enregistrer/Annuler, ouverture des gestionnaires d'évaluations et du dialogue de pondération |

Les 3 fichiers mixins partagent **le même bloc d'imports** (copié-collé, `main_window.py:1-53`,
`main_data.py:1-49`, `main_actions.py:1-50`, `main_notes.py:1-51` sont quasi identiques) — signe
qu'ils ont été découpés à partir d'un seul fichier historique plus gros (voir § 16, Points
d'attention).

Chaque mixin déclare une méthode `_restyle_all(self)` vide avec un commentaire expliquant que
c'est `MainWindow._restyle` (propriétaire de `theme_changed`) qui réapplique les styles
dépendant de la palette (`main_data.py:53-59`, `main_notes.py:55-60`) — remarque : cette méthode
`_restyle_all` n'est en réalité jamais appelée nulle part dans le code lu (ni connectée à un
signal) ; c'est `MainWindow._restyle` (`main_window.py:138-166`) qui fait tout le travail.

---

### 2. Cycle de vie de `MainWindow`

`__init__` (`main_window.py:89-136`) :

1. Applique le style Fusion, définit taille/titre.
2. Initialise le cache de données (`_items`, `_eleves_par_classe`, `_cycle_par_classe`,
   `_items_other`) et les références aux fenêtres enfants (`_manager_f`, `_manager_s` = `None`).
3. Initialise l'état de sélection courant : `_current_ts_id`, `_current_cycle` (`'PEI'` par
   défaut), `_evals_f` / `_evals_s` (listes de dicts), `_visible_f` / `_visible_s` (`set[int]`
   des index de slots affichés **dans la grille**), `_show_f_comment` / `_show_s_comment`,
   `_last_clicked_f` / `_last_clicked_s`, `_show_jgt_comment`, `_visible_crits` (dict
   `{a,b,c,d: bool}`, tous `True` par défaut), `_name_format_prenom_first`.
4. Initialise l'état de sauvegarde : `_row_ids: dict[student_id, learner_row_id]` et
   `_dirty_cells: dict[(student_id, db_col_name), new_value]` (`main_window.py:120-121`).
5. Appelle `_setup_ui()` puis `_load_combined_data()` (chargement initial), puis connecte
   `ds.theme_changed` à `self._restyle`.

`_setup_ui()` (`main_window.py:171-208`) construit :
- Un header coloré (`_build_header`, zone `ZONE_S_COLOR`).
- Une sidebar verticale **de largeur fixe** `ds.workspace_sidebar_width`, dans un `QScrollArea`
  (`main_window.py:181-188`), contenant les 4 sections (`_build_sidebar`).
- Un `_workspace_widget` (grille + barre d'actions), toujours présent dans le layout même sans
  sélection (`main_window.py:191-197`).
- Une `QStatusBar`.

`closeEvent` (`main_window.py:687-693`) empêche la fermeture tant que `_dirty_cells` n'est pas
vide, via `_confirm_leave()` (`main_window.py:675-685`) qui affiche un `QMessageBox.warning` et
retourne `False`. Le même garde-fou protège le changement de matière-classe
(`_on_item_selected`, `main_data.py:239-243`).

---

### 3. Sidebar : 4 sections empilées

`_build_sidebar()` (`main_window.py:328-360`) construit 4 `QFrame` stockés dans
`self._side_frames: dict[str, QFrame]` (clés `'matiere'`, `'F'`, `'S'`, `'jugements'`), pour
pouvoir les restyler individuellement au changement de thème (`_restyle`,
`main_window.py:154-155`).

#### 3.1 Section « Matière - Classe » (`_build_matiere_section`, `main_window.py:382-434`)

- `self._items_combo` : `QComboBox` peuplé par `_load_combined_data` (voir § 4.1). Son
  `currentIndexChanged` déclenche `_on_item_selected` (`main_window.py:402`).
- `self._items_other_combo` : combo « Autre Matière-Classe » (Projet Personnel, TDC, CAS,
  Mémoire…) — **actuellement masqué** (`setVisible(False)`, `main_window.py:410, 420`) car
  l'édition des notes pour `larcauth_learner_has_termothersubject` n'est pas implémentée (TODO
  explicite ligne `main_window.py:406`). Son gestionnaire `_on_other_item_selected`
  (`main_notes.py:936-955`) se contente d'afficher un message de statut, il n'affiche aucune
  grille.
- Bouton `_weight_btn` (« Mode de calcul ») → `_on_weight` (voir § 13).

#### 3.2 Sections « Formatives » (F) et « Sommatives » (S) (`_build_eval_section`,
`main_window.py:440-540`)

Chaque section a :
- Une ligne de titre colorée (`ZONE_F_COLOR` pour F, `ZONE_S_COLOR` pour S) avec un bouton
  **« Gérer »** connecté à `_open_manager_f` / `_open_manager_s`
  (`main_window.py:476-478`) — ouvre `EvalManagerWindow` (voir § 8/10).
- Une zone scrollable (`scroll_content`) qui accueille dynamiquement une rangée cliquable par
  slot **actif** (construite par `NotesGridMixin._update_icons`, § 5.1).
- Trois boutons bascules : **Toute** (`_on_toggle_all`), **Aucune** (`_on_toggle_none`),
  **Commentaire** (`_on_toggle_comment`) (`main_window.py:504-526`).

Le dict retourné par `_build_eval_section` est stocké dans `self._fwidgets` /
`self._swidgets` (`main_window.py:344, 350`) et contient notamment `'scroll_content'`,
`'tout_btn'`, `'aucune_btn'`, `'comm_btn'`, et `'slot_rows'` (dict `index → QFrame`, reconstruit
à chaque appel de `_update_icons`).

#### 3.3 Section « Jugements » / Affichage colonnes (`_build_jugements_section`,
`main_window.py:542-616`)

Trois boutons bascules : **Jugement** (affiche les colonnes `jgt_a..d`), **Note sur 7**
(affiche `note_on_7`/`moy_on_20` + la colonne virtuelle « Valide »), **Commentaire** (affiche
`term_observation`). Puis 4 boutons **Critère A/B/C/D** qui pilotent `self._visible_crits`
(`main_window.py:594-604`), tous cochés par défaut.

---

### 4. `DataMixin` — chargement des données (`views/main_data.py`)

#### 4.1 `_load_combined_data()` (`main_data.py:84-214`)

Requête principale (« Items Matière-Classe ») :

```sql
SELECT cts.id AS termsubject_id, ls.label AS matiere, c.id AS class_id,
       c.label AS classe, c.fk_level_id
FROM larcauth_classroom_termsubject cts
JOIN larcauth_levelsubject ls ON ls.id = cts.fk_levelsubject_id
JOIN larcauth_classroom c ON c.id = cts.fk_classroom_id
WHERE cts.fk_teacher_id = ? AND cts.fk_term_id = ?
  AND cts.enabled = 1 AND c.enabled = 1
ORDER BY ls.label, c.label
```
(`main_data.py:108-122`, params `= (session.user_id, session.term_id)`)

Pour chaque classe rencontrée, le cycle (`'PEI'` ou `'DP'`) est déterminé une seule fois via
`_determine_cycle(conn, level_id)` (`main_data.py:216-233`), qui lit
`larcauth_program.sigle` en remontant `larcauth_level` — `'DP'` si le sigle est dans
`('DP','IBDP','DIPLOMA','DPFR','DPEN')`, sinon `'PEI'` par défaut (y compris en cas
d'exception, ligne 233).

Une deuxième requête symétrique charge les items « Autre Matière-Classe »
(`larcauth_classroom_termothersubject`, filtré par `fk_supervisor_id`, `main_data.py:145-157`).

Une troisième boucle charge, pour **chaque classe présente dans `_items`**, la liste des élèves
actifs :

```sql
SELECT s.aecuser_ptr_id, u.last_name, u.first_name
FROM larcauth_student s
JOIN larcauth_aecuser u ON u.id = s.aecuser_ptr_id
WHERE s.s_classroom_id = ? AND s.enabled = 1
ORDER BY u.last_name, u.first_name
```
(`main_data.py:173-183`)

Les deux combos sont ensuite peuplés (signaux bloqués pendant le remplissage). Si l'enseignant
n'a qu'une seule matière-classe, elle est sélectionnée automatiquement (`main_data.py:203-204`).

#### 4.2 `_on_item_selected(idx)` (`main_data.py:235-295`)

Déclenché par le changement de sélection dans `_items_combo`. Séquence exacte :

1. Garde `_confirm_leave()` : si des cellules sont modifiées non sauvegardées, l'index est
   restauré sur `_last_item_idx` et la fonction s'arrête (`main_data.py:239-243`).
2. Résout l'`item` (dict) correspondant au `class_id` sélectionné dans `self._items`.
3. Affecte `_current_ts_id`, `_current_cycle`, `_current_item`.
4. `_load_evaluations_from_db(ts_id)` (§ 4.3) — recharge `_evals_f` / `_evals_s` depuis SQLite.
5. **Réinitialise** `_visible_f` / `_visible_s` et sélectionne automatiquement **le premier
   slot actif** de chaque type comme seul élément visible (`main_data.py:274-285`) :
   ```python
   self._visible_f.clear()
   for e in self._evals_f:
       if e['is_active']:
           self._visible_f.add(e['index'])
           self._last_clicked_f = e['index']
           break
   ```
   (idem pour S). Autrement dit, au changement de matière-classe, la grille ne montre jamais
   automatiquement TOUS les slots actifs — seulement le premier.
6. `_update_top_bar()` reconstruit les rangées de la sidebar F/S (§ 5.1).
7. `_fill_grille(item, cycle, eleves)` une première fois, PUIS `_auto_compute_judgments_and_note()`
   (qui a besoin de `_row_ids`/`_current_student_ids`, peuplés par `_fill_grille`), PUIS un
   second `_fill_grille(...)` pour réafficher les valeurs calculées (`main_data.py:288-292`,
   commentaire explicite dans le code).

#### 4.3 `_load_evaluations_from_db(ts_id)` (`main_data.py:297-337`)

```sql
SELECT id, index_eval, label, nature, source, crit_a, crit_b, crit_c, crit_d
FROM larcauth_evaluation
WHERE fk_classroom_termsubject_id = ? AND type_evaluation = ?
  AND CAST(index_eval AS INTEGER) BETWEEN 1 AND 12
ORDER BY CAST(index_eval AS INTEGER)
```
exécutée une fois pour `eval_type = 'F'` et une fois pour `'S'` (params : `(str(ts_id),
eval_type)` — `ts_id` est castée en `str` car `fk_classroom_termsubject_id` est stockée comme
texte dans SQLite local). Pour chaque ligne :

```python
crits_active = any((r[i] or '0') == '1' for i in (5, 6, 7, 8))  # crit_a..crit_d
```
(`main_data.py:317`) — **c'est ici, et nulle part ailleurs, que l'état "actif" d'un slot est
calculé** côté `MainWindow`. Voir § 11 pour la discussion terminologique complète.

Le résultat alimente `self._evals_f` / `self._evals_s`, listes de dicts
`{id, index, label, nature, source, crit_a..d, is_active}`.

#### 4.4 `_update_top_bar()` (`main_data.py:351-354`)

Appelle `self._update_icons('F', self._evals_f, self._fwidgets)` et l'équivalent pour S — voir
§ 5.1. C'est le point d'entrée unique pour rafraîchir les panneaux sidebar F/S après tout
chargement ou modification d'état.

---

### 5. `NotesGridMixin` — grille et calculs (`views/main_notes.py`)

#### 5.1 `_update_icons(eval_type, evals, widgets)` (`main_notes.py:62-168`)

Reconstruit entièrement la liste scrollable de rangées de slots dans la sidebar (F ou S) :

- Vide l'ancien layout (`layout.takeAt(0)` en boucle, `main_notes.py:66-69`).
- **Ne crée une rangée que pour les slots `is_active` == True** (`main_notes.py:76-77`) — les
  slots inactifs n'apparaissent pas du tout dans ce panneau, quel que soit leur contenu.
- Pour chaque slot actif, la rangée est stylée différemment selon qu'il est dans
  `visible_set` (= `_visible_f`/`_visible_s`, c.-à-d. affiché dans la grille) ou non
  (`main_notes.py:85-97`) : fond `primary_container` + bordure gauche `primary` épaisse de 3px
  si visible, fond `background` neutre sinon.
- Chaque rangée affiche : l'index (`F03`), la nature tronquée à 20 caractères, et 4 lettres
  A/B/C/D dont seules celles actives pour ce slot sont affichées en clair (`main_notes.py:127-134`).
- **La rangée entière est cliquable** via un `mousePressEvent` lambda-assigné
  (`main_notes.py:140`) qui appelle `_on_slot_icon_clicked(eval_type, idx)` — c'est le mécanisme
  qui permet à l'utilisateur de rendre un slot visible/invisible manuellement (§ 5.2 et § 10).
- Si aucun slot n'est actif, un label placeholder « Aucune évaluation active » est affiché
  (`main_notes.py:146-151`).
- En fin de fonction, les boutons Toute/Aucune/Commentaire sont resynchronisés visuellement
  (`main_notes.py:159-168`) : `Toute` est coché seulement si `visible_set == {tous les actifs}`,
  `Aucune` seulement si `visible_set` est vide.

#### 5.2 Handlers d'interaction sidebar (`main_notes.py:174-267`)

| Handler | Effet |
|---|---|
| `_on_slot_icon_clicked(eval_type, slot_index)` (174-198) | Bascule `slot_index` dans/hors `visible_set` (`discard`/`add`), met à jour `_last_clicked_f/s`, puis `_on_selection_changed()`. Ne fait rien si le slot n'est pas actif. |
| `_on_toggle_all(eval_type)` (200-223) | Bascule global : si `visible_set == {tous les actifs}`, vide `visible_set` ; sinon remplit `visible_set` avec **tous** les index actifs. |
| `_on_toggle_none(eval_type)` (225-233) | Vide `visible_set`. |
| `_on_toggle_comment(eval_type)` (235-239) | Bascule `_show_f_comment`/`_show_s_comment`. |
| `_on_toggle_crit(letter)` (241-245) | Bascule `_visible_crits[letter]` (global, pas par type). |
| `_on_jgt_toggle` / `_on_jgt_note_toggle` / `_on_jgt_comment_toggle` (247-267) | Bascule respectivement les 4 colonnes `jgt_*`, la colonne note/7 + case Validé, et `term_observation`. |

Tous appellent en dernier `_on_selection_changed()` (269-280), qui **sauvegarde d'abord les
cellules modifiées** (`_save_grid_edits()`), relance le calcul auto
(`_auto_compute_judgments_and_note()`), rafraîchit la sidebar (`_update_top_bar()`) puis
reconstruit la grille (`_fill_grille`).

#### 5.3 `_fill_grille(item, cycle, eleves)` (`main_notes.py:293-585`) — construction de la grille

Étapes précises :

1. **Coupe le tri** (`setSortingEnabled(False)`) pendant le remplissage, en mémorisant la
   colonne/l'ordre de tri courants (`main_notes.py:311-314`), pour éviter que Qt ne réordonne
   les lignes en cours d'insertion (bug documenté en commentaire : les cases à cocher
   « Validé » se retrouvaient sur la mauvaise ligne).
2. **Détermine `synth_display`** (`'note_on_7'` en PEI, `'moy_on_20'` en DP) et `table`
   (`larcauth_learnerpei_has_termsubjectpei` ou `larcauth_learnerdp_has_termsubjectdp`)
   (`main_notes.py:317-319`).
3. **Construit `visible_db_cols`**, la liste ordonnée des noms de colonnes SQLite à afficher :
   - Pour chaque `slot_idx` de `sorted(self._visible_f)`, pour chaque critère actif
     ET visible (`_crit_visible`, croise `_visible_crits[letter]` ET le `crit_x` du slot dans
     `_evals_f`), ajoute `f{slot_idx:02d}_note_{crit}` ; si `_show_f_comment`, ajoute aussi
     `f{slot_idx:02d}_observation` (`main_notes.py:341-347`). Même logique pour
     `_visible_s`/`s{slot_idx:02d}_note_{crit}` (350-356).
   - Si le bouton Jugement est coché, ajoute `jgt_a..d` **uniquement pour les lettres encore
     visibles dans `_visible_crits`** (358-363) — cohérence voulue : un critère décoché
     disparaît de partout (notes ET jugements).
   - Si le bouton Note sur 7 est coché, ajoute `synth_display` puis la colonne **virtuelle**
     `_note_validated` (n'existe pas en base, remplacée par `note_on_7_checked` au chargement,
     voir point 5).
   - Si `_show_jgt_comment`, ajoute `term_observation`.
4. **Filtre par colonnes existantes** : lit `PRAGMA table_info("{table}")` pour ne garder que
   les colonnes réellement présentes (`existing_visible`, `main_notes.py:371-388`) — tolère un
   schéma SQLite local en retard par rapport au code.
5. **Noms d'affichage** (`display_names`, 391-420) : ex. `F03_A`, `Jgt A`, `Note`/`Moy.`,
   `F Obs.`, `Obs. Terme`, `Valide`.
6. **Colore les entêtes par zone** via `ZoneHeaderView.set_zone_colors` (§ 12.3) : colonne 0 =
   `ZONE_NEUTRAL`, colonnes `f*` = `ZONE_F_COLOR` (texte clair), colonnes `s*` = `ZONE_S_COLOR`
   (texte clair), le reste = `ZONE_NEUTRAL` (`main_notes.py:429-444`).
7. **Charge les notes** (`main_notes.py:448-502`) : détecte si la table a une colonne
   `fk_student_id` (préférée) ou, à défaut, `learner_has_termsubject_ptr_id`
   (`has_fk`/`fk_col`, lignes 453-469). Si `_note_validated` est demandée, elle est remplacée
   dans le `SELECT` par la vraie colonne `note_on_7_checked` (475-479). Exécute
   `SELECT id, {fk_col}, ...cols... FROM "{table}"` **sans filtre** (charge toute la table, pas
   seulement les élèves de la classe courante), puis indexe par `student_id` dans `notes` et
   `self._row_ids[student_id] = pei_id` (id de la ligne `learner_has_termsubject`)
   (`main_notes.py:480-498`). Si la table n'a ni l'une ni l'autre colonne FK, affiche un message
   « Données ancienne génération — relancez --mode4 » (500-502).
8. **Remplit les lignes** (504-559) : colonne 0 = nom élève (non éditable,
   `UserRole`=id, `UserRole+1`=nom, `UserRole+2`=prénom, `UserRole+3`=couleur de fond neutre).
   Pour `_note_validated`, un vrai `QCheckBox` est posé via `setCellWidget` (pas un item
   checkable — commentaire explicite : un item checkable se rebasculait deux fois à cause du
   double traitement du clic natif Qt + `ClipboardTable.mouseReleaseEvent`,
   `main_notes.py:524-544`). Pour les autres colonnes, un `ColorItem` avec dégradé
   rouge→vert calculé par `_note_gradient(val, cycle)` si c'est une colonne de note
   (`main_notes.py:547-559`).
9. Mémorise `_current_table`, `_current_col_names` (= `existing_visible`, sert d'index
   colonne-grille → nom-colonne-SQL), `_current_student_ids`.
10. Applique les largeurs de colonnes depuis `pei_config` (`common/grid_config.py`, § 12.2).
11. Réapplique le tri sauvegardé à l'étape 1, réactive `setSortingEnabled(True)`, débloque les
    signaux, puis **recale les `QCheckBox` « Valide »** sur leurs lignes
    (`_resync_validated_widgets`) car le tri déplace les items mais pas les `cellWidget`
    (`main_notes.py:576-585`).

#### 5.4 `_on_cell_changed(row, col)` (`main_notes.py:587-622`) — édition d'une cellule

1. Ignore colonne 0 (nom, non éditable).
2. Résout `student_id` depuis l'item colonne 0 (`UserRole`), `db_name` depuis
   `_current_col_names[col-1]`.
3. Recalcule le dégradé de couleur de la cellule si c'est une colonne de note
   (`_note_` ou `note_on_7`/`moy_on_20`).
4. **Marque la cellule modifiée** : `self._dirty_cells[(student_id, db_name)] = val`
   (`main_notes.py:608`) — c'est la seule écriture dans `_dirty_cells`, et elle se produit à
   chaque frappe/édition de cellule (le signal `cellChanged` de `QTableWidget` se déclenche à
   chaque changement de texte de l'item).
5. **Si cycle PEI et colonne de note** (`'_note_' in db_name`), déclenche immédiatement
   `_live_recompute(student_id)` (§ 5.7) — recalcul en direct des jugements et de la note/7 à
   partir des valeurs en cours de saisie (pas encore enregistrées en base).
6. Si la colonne modifiée est une note, un jugement ou la note/7 elle-même, appelle
   `_invalidate_note(student_id)` (§ 5.6) — décoche systématiquement la case « Validé ».

#### 5.5 `_save_grid_edits()` (`main_notes.py:660-690`) — LE mécanisme de sauvegarde

```python
def _save_grid_edits(self) -> int:
    conn = db.local_conn
    if conn is None or not self._dirty_cells:
        return 0
    table = getattr(self, '_current_table', None)
    if table is None:
        return 0
    saved = 0
    for (student_id, db_name), val in list(self._dirty_cells.items()):
        pei_id = self._row_ids.get(student_id)
        if pei_id is None:
            continue
        conn.execute(f'UPDATE "{table}" SET "{db_name}" = ? WHERE id = ?', (val, pei_id))
        saved += 1
    conn.commit()
    self._dirty_cells.clear()
    ...
    return saved
```

Points clés :
- La sauvegarde est **toujours une `UPDATE`**, jamais d'`INSERT` — conforme au principe gabarit
  du monorepo (les lignes `learner_has_termsubject*` existent déjà, une par élève).
- La clé de mise à jour est l'`id` **local SQLite** de la ligne `learner_has_termsubject{pei|dp}`
  (variable nommée `pei_id` même en DP), résolu via `self._row_ids[student_id]` — ce dict est
  reconstruit intégralement à chaque `_fill_grille` (§ 5.3, étape 7), donc **stale si l'appelant
  n'a pas rechargé la grille depuis le dernier changement de matière-classe**.
- Si `student_id` n'a pas d'entrée dans `_row_ids` (élève sans ligne PEI/DP), la cellule est
  silencieusement ignorée (`continue`, pas d'erreur ni de log) — voir § 16.
- Appelée par : `_on_save_only` (bouton Enregistrer, `main_actions.py:59`),
  `_on_selection_changed` (à chaque bascule de colonnes, `main_notes.py:271`),
  `MainWindow._restyle` (avant de reconstruire la grille au changement de thème,
  `main_window.py:162`).
- **Non appelée** par `_on_cancel` (`main_actions.py:64-69`), qui au contraire **vide**
  `_dirty_cells` sans sauvegarder puis ferme la fenêtre — c'est le mécanisme d'abandon.

#### 5.6 `_invalidate_note(student_id)` (`main_notes.py:858-893`)

Toute modification d'une note, d'un jugement ou de la note/7 remet
`note_on_7_checked = 0` en base **immédiatement** (`UPDATE ... conn.commit()`, indépendant de
`_dirty_cells`/`_save_grid_edits`) et décoche visuellement la case « Valide » dans la grille
(sans redéclencher sa propre sauvegarde, `main_notes.py:876-893`). Rationale documentée en
commentaire : soit le calcul a été redéclenché (note modifiée), soit l'enseignant a corrigé
lui-même le jugement ou la note/7 — dans les deux cas la validation précédente n'est plus fiable.

#### 5.7 `_auto_compute_judgments_and_note()` (`main_notes.py:692-709`) et
`_recompute_one_student` (`main_notes.py:729-805`)

`_auto_compute_judgments_and_note` ne fait rien si `_current_ts_id is None`, si
`_current_student_ids` est vide, ou **si le cycle est DP** (`main_notes.py:698-699`, commentaire
« calcul différent, à implémenter plus tard » — le calcul auto n'existe donc qu'en PEI).
Elle construit le cache `_evals_by_crit` (`_build_evals_by_crit`, `main_notes.py:711-727` —
requête `SELECT type_evaluation, index_eval, crit_a..d FROM larcauth_evaluation WHERE
fk_classroom_termsubject_id = ?`, indexé par lettre de critère), puis appelle
`_recompute_one_student(student_id)` pour chaque élève ayant une ligne dans `_row_ids`.

`_recompute_one_student(student_id, override=None)` fait, pour la table
`larcauth_learnerpei_has_termsubjectpei` :

1. Lit la formule de calcul via `CalcEngine.get_formula(self._current_ts_id)`
   (`common/calc_engine.py`, § 13.2) → poids `wf` (formative_weight, défaut 0.4) et `ws`
   (summative_weight, défaut 0.6).
2. Pour chaque critère **A-D encore visible dans `_visible_crits`** (un critère décoché est
   **exclu du calcul**, cohérence avec l'affichage, `main_notes.py:760`) :
   - Pour chaque évaluation active portant ce critère (`_evals_by_crit[crit]`), lit la note
     correspondante (`f{idx:02d}_note_{crit}` ou `s{idx:02d}_note_{crit}`) soit depuis
     `override` (saisie en cours, non enregistrée — prioritaire) soit depuis la base.
   - `f_mean`/`s_mean` = moyennes simples des notes F / S disponibles pour ce critère.
   - Jugement = `round(f_mean*wf + s_mean*ws)` si les deux existent, sinon `round(s_mean)` ou
     `round(f_mean)` seul (règle « solo », toujours arrondi à l'entier — jamais de virgule).
3. `UPDATE larcauth_learnerpei_has_termsubjectpei SET jgt_a=?, jgt_b=?... WHERE id=?` pour les
   jugements calculés (`main_notes.py:787-790`).
4. Calcule la note finale via `CalcEngine.compute_note(student_id, ts_id,
   active_crits=<critères visibles>, override=...)` (§ 13.2) puis `UPDATE ... SET note_on_7 = ?
   WHERE id = ?` si non `None` (`main_notes.py:797-804`).
5. Retourne `(note, jgt_values)`.

**Différence importante avec `_save_grid_edits`** : ces `UPDATE` sont commités immédiatement
(via `conn.commit()` appelé par le code appelant, `_auto_compute_judgments_and_note` ligne 709,
ou par `_live_recompute`/`_invalidate_note` qui commitent chacun séparément) — ils ne passent
**jamais** par `_dirty_cells`. Les colonnes calculées (`jgt_*`, `note_on_7`) sont donc
persistées même si l'utilisateur clique « Annuler » ensuite (`_on_cancel` ne vide que
`_dirty_cells`, pas les écritures déjà commitées par le moteur de calcul) — voir § 16.

#### 5.8 `_live_recompute` / `_update_grille_student_cells` (`main_notes.py:895-934`)

`_live_recompute(student_id)` construit un `override` = sous-ensemble de `_dirty_cells`
concernant cet élève et une colonne de note (`'_note_' in db_name`), appelle
`_recompute_one_student(student_id, override)`, puis `_update_grille_student_cells` réécrit
directement le texte des cellules `jgt_a..d` et `note_on_7`/`moy_on_20` **dans la grille déjà
affichée**, sans redéclencher `cellChanged` (signaux bloqués, `main_notes.py:918-934`).

#### 5.9 Case « Valide » (`_on_validated_toggled`, `_save_note_validation`,
`_resync_validated_widgets`)

`_on_validated_toggled(student_id, state)` (`main_notes.py:824-830`) sauvegarde directement
`note_on_7_checked` sans passer par `_dirty_cells` ni redéclencher de calcul — c'est une
validation manuelle de l'enseignant, distincte du contenu des notes.

---

### 6. `SyncActionsMixin` — actions et fenêtres enfants (`views/main_actions.py`)

#### 6.1 `_on_save_only` / `_on_cancel` (`main_actions.py:55-69`)

`_on_save_only` appelle uniquement `_save_grid_edits()` — **aucune synchronisation réseau**
n'est déclenchée depuis cette fenêtre (commentaire explicite : « la synchronisation reste un
geste explicite du dashboard », `main_window.py:663-664`). `_on_cancel` vide `_dirty_cells`
puis ferme la fenêtre — les modifications de cellules non enregistrées sont perdues, mais **pas**
les écritures déjà commitées par le moteur de calcul auto (§ 5.7).

#### 6.2 `_on_weight` (`main_actions.py:75-89`)

Résout le libellé `"{matiere} - {classe}"` pour la matière courante, ouvre `WeightDialog`
(modal) — voir § 13.

#### 6.3 `_open_manager(eval_type)` (`main_actions.py:99-123`)

```python
def _open_manager(self, eval_type: str):
    if self._current_ts_id is None: ...
    existing = self._manager_f if eval_type == 'F' else self._manager_s
    if existing is not None:
        existing.close()
    ...
    w = EvalManagerWindow(eval_type, self._current_ts_id, slot_label, self)
    w.finished.connect(lambda result: self._on_manager_closed(eval_type))
    w.show()
    if eval_type == 'F': self._manager_f = w
    else: self._manager_s = w
```

- Ferme toute instance déjà ouverte du même type avant d'en recréer une (empêche les doublons).
- `EvalManagerWindow` est une `ThemedDialog` **non modale** (`setModal(False)`,
  `eval_manager.py:145`) affichée avec `.show()` (pas `.exec()`) — l'utilisateur peut continuer
  à interagir avec `MainWindow` pendant que le gestionnaire est ouvert.
- Le signal `finished` (émis à la fermeture, quel que soit `result`) déclenche
  `_on_manager_closed(eval_type)` — voir § 6.4 et § 10 pour le détail complet.

#### 6.4 `_on_manager_closed(eval_type)` (`main_actions.py:125-153`) — mécanisme de visibilité

Voir la section dédiée § 10 (le sujet central demandé). Résumé du flux : recharge les
évaluations depuis SQLite, **filtre** `visible_set` pour ne garder que les index toujours
actifs, ne rajoute **rien** automatiquement sauf si `visible_set` devient vide (fallback sur le
premier actif), ajuste `_last_clicked_f/s` si besoin, puis rafraîchit sidebar + grille. Le
`try/except RuntimeError` (`main_actions.py:146-149`) protège contre le cas où la fenêtre
`MainWindow` elle-même a été détruite entre-temps (widget Qt déjà supprimé côté C++).

---

### 7. `EvalManagerWindow` — fenêtre de gestion (`views/eval_manager.py`)

#### 7.1 Vue d'ensemble

`EvalManagerWindow(ThemedDialog)` (`eval_manager.py:132-437`) est instanciée avec
`(eval_type, termsubject_id, subject_label, parent)`. Fenêtre **non modale**
(`setModal(False)`, ligne 145), taille minimale `3/4` de `ds.window_width/height` (ligne 144).

`_build_ui()` (179-201) : un `QSplitter` horizontal avec panneau gauche (`_build_left_panel`)
et droit (`_build_right_panel`), tailles initiales dérivées de tokens `ds.*` (ligne 189-190 —
**pas de valeurs littérales 400/500** comme l'ancienne doc le laissait entendre ; les tailles
réelles en pixels dépendent de la configuration du design system).

#### 7.2 Panneau gauche : tabs + barres de slots

`_build_tabs` (247-272) : 12 `QPushButton` checkable `F01`..`F12` (ou `S01..S12`), colorés en
`p.success`/blanc si `active`, en `p.outline_variant`/`p.text_disabled` sinon
(`_update_tabs`, 359-378). Clic → `_on_tab_clicked(idx)` → `_on_slot_selected(idx)`.

En dessous, la légende des critères (`self._legend`, chargée dans `_load_data`, § 7.4) puis la
liste scrollable des 12 `_SlotBar` (`_build_left_panel`, 203-245).

##### Classe `_SlotBar(QFrame)` (`eval_manager.py:34-129`)

Barre horizontale cliquable : code (`F03`), label = nature tronquée à 72 caractères, 4
`QCheckBox` A-D **désactivées** (`cb.setEnabled(False)`, ligne 76 — lecture seule, la case
n'est qu'un indicateur visuel, pas un contrôle).

`set_data(eval_id, data)` (84-96) :
```python
active = False
for letter in ('A', 'B', 'C', 'D'):
    val = data.get(f'crit_{letter.lower()}', '0')
    checked = val in ('1', 1, True)
    self._crits[letter].setChecked(checked)
    if checked:
        active = True
self._active = active
```
**C'est ici que l'état actif d'une `_SlotBar` est déterminé — un booléen local `self._active`,
recalculé à chaque `set_data`, jamais lu depuis une colonne `enabled`.** Voir § 11.

`restyle()` (106-123) : style « actif » (fond `p.surface`, bordure pleine `p.success`) si
`self._active and self.eval_id is not None`, sinon style « suivant » (fond
`p.surface_variant`, bordure pointillée `p.outline_variant`).

#### 7.3 `_update_visibility()` (`eval_manager.py:346-357`) — affichage progressif

```python
def _update_visibility(self):
    found_next = False
    for bar in self._bars:
        if bar._active and bar.eval_id is not None:
            bar.restyle(); bar.setVisible(True)
        elif not found_next:
            bar.restyle(); bar.setVisible(True)
            found_next = True
        else:
            bar.setVisible(False)
```
Règle : toutes les barres **actives** sont visibles, PLUS la **première** barre inactive
rencontrée dans l'ordre F01→F12 (le « slot suivant » à activer), toutes les suivantes étant
masquées. Ce comportement est indépendant et sans lien avec `MainWindow._visible_f/_s` (§ 10) —
il ne concerne que l'affichage **à l'intérieur de `EvalManagerWindow`**, pas la grille de notes.

#### 7.4 Chargement (`_load_data`, `eval_manager.py:299-344`)

Légende des critères :
```sql
SELECT fk_levelsubject_id FROM larcauth_classroom_termsubject WHERE id = ?
-- puis
SELECT criteria_letter, criteria_label FROM larcauth_criteria_of_levelsubject
WHERE fk_levelsubject_id = ? AND criteria_letter IN ('A','B','C','D')
ORDER BY criteria_letter
```
Slots (les 12 évaluations du type courant) :
```sql
SELECT id, index_eval, crit_a, crit_b, crit_c, crit_d, label, nature, source
FROM larcauth_evaluation
WHERE fk_classroom_termsubject_id = ? AND type_evaluation = ?
  AND CAST(index_eval AS INTEGER) BETWEEN 1 AND 12
ORDER BY CAST(index_eval AS INTEGER)
```
Chaque ligne alimente `bar.set_data(id, {...})` pour la barre correspondante ; les slots absents
(non trouvés dans le SELECT) appellent `bar.clear()`. **Remarque** : la requête ne sélectionne
jamais de colonne `enabled` — elle n'existe pas dans le SELECT (confirmé également dans
`main_data.py:307-308` et `student_card_view.py:192-197`), seul un `crit_a..d` sert de source de
vérité.

#### 7.5 Sélection et sauvegarde (`_on_slot_selected`, `_on_save_slot`,
`eval_manager.py:384-417`)

`_on_slot_selected(slot_index)` (384-391) met à jour `_current_slot_index`, transmet
`bar._data` au panneau droit (`self._detail.set_data(...)`), recharge les labels des critères
(`self._detail._load_criteria_labels()`), rafraîchit les tabs.

`_on_save_slot()` (393-417) :
```python
bar = self._bars[self._current_slot_index - 1]
form_data = self._detail.get_form_data()
slot_id = bar.eval_id
if slot_id is None:
    self._status_msg("Impossible d'enregistrer: evaluation non identifiee"); return
label_val = (bar._data or {}).get('label', '')
save_evaluation_criteria(slot_id, label_val, form_data['nature'], form_data['source'],
    {crit_a..d: form_data[...]})
# met à jour bar._data localement, puis bar.set_data(slot_id, bar._data)
self._update_visibility(); self._update_tabs()
```
`save_evaluation_criteria` (`common/eval_helpers.py:5-40`) exécute la requête d'écriture
exacte :
```sql
UPDATE larcauth_evaluation
SET label=?, nature=?, source=?, crit_a=?, crit_b=?, crit_c=?, crit_d=?
WHERE id=?
```
suivi de `conn.commit()`. C'est la seule fonction d'écriture de `larcauth_evaluation` dans tout
le périmètre documenté ici (utilisée aussi bien par `EvalManagerWindow` que par
`EvaluationPanel._save_criteria`, § 9.4 — bien que cette seconde classe ne soit pas utilisée en
pratique, voir § 16).

---

### 8. `EvaluationDetailWidget` (`views/evaluation_panel.py:79-323`)

Formulaire embarqué dans le panneau droit d'`EvalManagerWindow` (une seule instance réutilisée
pour les 12 slots, pas recréée à chaque sélection — `set_slot_info`/`set_data` sont appelés
pour la reconfigurer, `eval_manager.py:388-390`).

#### 8.1 Champs

- **Titre** (`_title_lbl`) : `{eval_type}{slot_index:02d}` (ex. `F03`), mis à jour par
  `set_slot_info` (`evaluation_panel.py:310-317`).
- **Label** (`_label_display`) : `QLabel` **lecture seule** — jamais éditée par l'utilisateur
  dans ce widget (`get_form_data()` ne la retourne même pas, § 8.3).
- **Nature** (`_nature_edit`) : `QLineEdit` éditable, placeholder « Nature (ex: Devoir,
  Interrogation, Projet...) » (`evaluation_panel.py:134-138`).
- **Source** (`_source_edit`) : `QTextEdit` en mode texte brut (`setAcceptRichText(False)`)
  mais interprété comme Markdown au chargement (`self._source_edit.setMarkdown(md)`,
  `evaluation_panel.py:248`) et resérialisé en Markdown à la sauvegarde
  (`self._source_edit.toMarkdown()`, ligne 292). Une barre d'outils (`_insert_md`,
  `evaluation_panel.py:319-323`) insère des extraits Markdown à la position du curseur : Gras
  (`**texte**`), Italique (`*texte*`), Titre (`## `), Liste (`- `), Lien (`[texte](url)`)
  (`evaluation_panel.py:148-154`).
- **Correcteur orthographique** (`_SpellHighlighter`, `evaluation_panel.py:47-72`) : souligne
  en rouge les mots absents du dictionnaire `enchant` `fr_FR`, **seulement si le module Python
  `enchant` est installé** (`HAS_ENCHANT`, lignes 34-40) — sinon `_dict is None` et
  `highlightBlock` ne fait rien silencieusement.
- **Critères** (`_crit_grid`, grille 2×4) : ligne 0 = 4 `QCheckBox` A-D **éditables** (aucun
  `setEnabled(False)` contrairement à `_SlotBar` — c'est ici que l'enseignant active/désactive
  effectivement un slot), ligne 1 = 4 `QLabel` affichant le libellé du critère (rempli par
  `_load_criteria_labels`, § 8.2).

#### 8.2 `_load_criteria_labels()` (`evaluation_panel.py:255-286`)

```sql
SELECT fk_levelsubject_id FROM larcauth_classroom_termsubject WHERE id = ?
-- puis
SELECT criteria_letter, criteria_label FROM larcauth_criteria_of_levelsubject
WHERE fk_levelsubject_id = ? AND criteria_letter IN ('A','B','C','D')
ORDER BY criteria_letter
```
Remplit `_crit_widgets[letter]['label']` avec le libellé (nettoyé des retours à la ligne).
Rappelée explicitement après chaque `_on_slot_selected` dans `EvalManagerWindow`
(`eval_manager.py:390`), car les libellés de critères peuvent varier par... en réalité non, ils
sont fixes pour tout le `termsubject_id` (dépendent de `fk_levelsubject_id`, constant pour toute
la fenêtre) — l'appel répété à chaque sélection de slot est donc redondant mais inoffensif (voir
§ 16).

#### 8.3 `get_form_data()` (`evaluation_panel.py:288-297`)

```python
def get_form_data(self) -> dict:
    crits = {letter: w['check'].isChecked() for letter, w in self._crit_widgets.items()}
    return {
        'nature': self._nature_edit.text().strip(),
        'source': self._source_edit.toMarkdown().strip(),
        'crit_a': '1' if crits['a'] else '0',
        'crit_b': '1' if crits['b'] else '0',
        'crit_c': '1' if crits['c'] else '0',
        'crit_d': '1' if crits['d'] else '0',
    }
```
Ne retourne jamais `label` (le label existant est repris tel quel côté appelant, voir § 7.5).
Les critères sont sérialisés en chaînes `'1'`/`'0'` — cohérent avec le format lu partout
ailleurs (`main_data.py:317`, `eval_manager.py:91`, etc., qui comparent toujours à la chaîne
`'1'` ou au tuple `('1', 1, True)`).

#### 8.4 Autres classes du fichier (non utilisées par `MainWindow`)

`evaluation_panel.py` définit également `EvaluationDetailDialog`, `_SlotButton` et
`EvaluationPanel` (lignes 330-903) — voir § 16, ces classes ne sont référencées par aucun autre
fichier du dépôt (recherche exhaustive effectuée) et constituent une implémentation alternative
non branchée, probablement un ancien prototype conservé dans le même fichier que le widget
réellement utilisé (`EvaluationDetailWidget`).

---

### 9. Rendu de la grille : `views/grid_table.py` + `common/grid_config.py`

#### 9.1 `ColorItem` (`grid_table.py:52-64`)

Sous-classe de `QTableWidgetItem` qui stocke une `QColor` de fond privée (`_bg`) et l'expose via
`data(Qt.UserRole + 3)`. C'est le canal utilisé par `ColorDelegate` (§ 9.2) et
`ZoneHeaderView`/`_fill_grille` pour peindre les fonds sans dépendre du `BackgroundRole`
standard de Qt (ignoré par endroits dans le rendu custom).

#### 9.2 `_note_gradient(val, cycle, default_bg=white)` (`grid_table.py:67-84`)

Calcule un dégradé rouge→jaune→vert :
- `max_note` = 8 (PEI) ou 20 (DP), `half = max_note / 2`.
- Si `val` vide ou non convertible en `float` → couleur par défaut (blanc).
- Sous la moitié : interpolation de rouge pur vers jaune (`r=255, g/b croissants`).
- Au-dessus : interpolation de jaune vers vert pur (`r décroissant, g=255, b décroissant`).

Utilisée à la fois au remplissage (`_fill_grille`, `main_notes.py:555`) et au recalcul en
direct (`_on_cell_changed`, `main_notes.py:606`; `_update_grille_student_cells`,
`main_notes.py:932`).

#### 9.3 `ColorDelegate` (`grid_table.py:87-147`)

`QStyledItemDelegate` custom : peint le fond depuis `UserRole+3` (ou `theme_manager.palette.
background` par défaut), une surbrillance de sélection semi-transparente
(`option.palette.highlight()` alpha 80), le texte centré avec padding fixe `8,4,-8,-4` en
utilisant `Qt.ForegroundRole` si défini (texte blanc forcé sur les colonnes de zone sombres via
`zone_fgs`, § 5.3 étape 6), et redessine manuellement l'indicateur de case à cocher **centré**
(`_check_rect`, 14px, centré sur la cellule) — nécessaire car le rect natif du style Qt est
décalé et ne correspond pas à la zone cliquable gérée par `ClipboardTable.mouseReleaseEvent`
(§ 9.5).

#### 9.4 `ZoneHeaderView` (`grid_table.py:150-202`)

`QHeaderView` custom qui repeint, dans son `paintEvent` (après `super().paintEvent`), un fond
de couleur par section (`_zone_bgs[col]`) puis le texte en gras par-dessus, avec une couleur de
texte par colonne (`_zone_fgs`). Commentaire du code : nécessaire car ni le `BackgroundRole`
d'un header item ni un delegate installé via `setItemDelegate` ne sont pris en compte par le
rendu natif de `QHeaderView` — seul le `paintEvent` du widget lui-même est fiable
(`grid_table.py:151-157`).

#### 9.5 `ClipboardTable` (`grid_table.py:205-381`)

`QTableWidget` étendue avec :
- **Copier/Coller** (`Ctrl+C`/`Ctrl+V`) au format tabulaire compatible Excel
  (`_copy_selection`, `_paste_clipboard`, lignes 296-374). Le collage valide chaque valeur
  contre une plage `[0, max_val]` (`max_val = 20` si la table courante se termine par `dp`,
  sinon `8`) et affiche un message d'erreur listant les 5 premières cellules hors plage
  (`grid_table.py:323-370`) sans empêcher le collage des autres valeurs. Chaque cellule collée
  déclenche `parent._on_cell_changed(r, c)` via `QTimer.singleShot(0, ...)` (ligne 363) pour
  laisser le texte se stabiliser avant de marquer la cellule "dirty".
- **Clic droit → menu contextuel** (`contextMenuEvent`, 237-260) sur la colonne élève : Fiche
  détaillée, Absence/Retard/Sortie anticipée (création directe sans dialogue via
  `EventService.insert_event`), Autre événement (ouvre `EventDialog`).
- **`mouseReleaseEvent`** (208-226) : bascule manuellement l'état d'une vraie case à cocher
  (détectée par `item.data(Qt.CheckStateRole) is not None`, pas juste le flag
  `ItemIsUserCheckable` présent par défaut sur tout `QTableWidgetItem` depuis Qt 6.7+) — sans
  cette détection explicite, n'importe quelle cellule de note serait considérée comme une case à
  cocher.

#### 9.6 `common/grid_config.py` — `GridConfig` / `pei_config`

Charge `grid_configs/pei.json` (singleton `pei_config`, `_manager.get('pei')`,
`grid_config.py:85`) et expose `student_width`, `note_width`, `remark_width`,
`note_on_7_color`/`note_on_7_bold`, et une méthode `color_for(value)` retournant `(bg, fg,
bold)` selon des tranches `grade_ranges` du JSON — **non utilisée dans le périmètre documenté
ici** : `_fill_grille` utilise exclusivement `_note_gradient` (calcul dynamique) pour la
couleur des cellules de note ; `pei_config` ne sert qu'aux **largeurs de colonnes**
(`main_notes.py:565-572`). Le fichier `grid_configs/pei.json` lui-même n'a pas été lu dans le
cadre de cette documentation (hors périmètre demandé) — sa structure (`grade_ranges`,
`note_on_7`) n'est donc décrite ici que d'après `GridConfig.__init__`
(`grid_config.py:36-59`), pas vérifiée contre son contenu réel.

---

### 10. `_on_manager_closed` — le mécanisme de visibilité voulu (analyse détaillée)

C'est le point le plus important à documenter précisément (demande explicite). Code complet
(`main_actions.py:125-153`) :

```python
@safe_slot("MainWindow._on_manager_closed")
def _on_manager_closed(self, eval_type: str):
    try:
        if self._current_ts_id:
            self._load_evaluations_from_db(self._current_ts_id)
            evals = self._evals_f if eval_type == 'F' else self._evals_s
            visible_set = self._visible_f if eval_type == 'F' else self._visible_s
            still_visible = {idx for idx in visible_set
                              if any(e['index'] == idx and e['is_active'] for e in evals)}
            visible_set.clear()
            visible_set.update(still_visible)
            if not visible_set:
                for e in evals:
                    if e['is_active']:
                        visible_set.add(e['index'])
                        break
            last_key = '_last_clicked_f' if eval_type == 'F' else '_last_clicked_s'
            lc = getattr(self, last_key)
            if lc is not None and not any(e['index'] == lc and e['is_active'] for e in evals):
                setattr(self, last_key, next((e['index'] for e in evals if e['is_active']), None))
            self._update_top_bar()
            self._on_selection_changed()
    except RuntimeError:
        ...
    if eval_type == 'F':
        self._manager_f = None
    else:
        self._manager_s = None
```

#### 10.1 Déroulement pas à pas

1. **Recharge** `_evals_f`/`_evals_s` depuis SQLite (`_load_evaluations_from_db`) — reflète tous
   les changements faits dans `EvalManagerWindow` (activation/désactivation de critères,
   nature, source).
2. **`still_visible`** = intersection de l'ancien `visible_set` (l'état de la grille **avant**
   ouverture du gestionnaire) avec l'ensemble des index **encore actifs** après rechargement.
   Concrètement :
   - Un slot qui était visible et **reste actif** → reste dans `visible_set` (persiste).
   - Un slot qui était visible mais a été **désactivé** dans le gestionnaire (tous ses critères
     décochés) → **disparaît** de `visible_set` (n'est plus filtré par `is_active`).
   - Un slot **nouvellement activé** dans le gestionnaire (il n'était PAS dans l'ancien
     `visible_set`, puisqu'il n'était pas encore actif) → **n'est jamais ajouté** par cette
     ligne, quelle que soit la logique : `still_visible` ne peut contenir que des index déjà
     présents dans l'ancien `visible_set`.
3. **Fallback uniquement si `visible_set` devient totalement vide** (ligne 135-139) : dans ce
   cas seulement, le premier slot actif (dans l'ordre F01→F12 / S01→S12) est ajouté
   automatiquement. Ce cas ne se produit que si TOUS les slots précédemment visibles ont été
   désactivés (et qu'aucun autre n'était déjà visible) — **pas** dans le cas où de nouveaux
   slots sont activés en plus des existants.
4. Ajuste `_last_clicked_f`/`_last_clicked_s` si le dernier slot cliqué n'est plus actif
   (retombe sur le premier actif, ou `None` s'il n'y en a aucun).
5. `_update_top_bar()` → `_update_icons` (`main_notes.py:62-168`) reconstruit les rangées
   cliquables de la sidebar F/S pour **tous les slots actifs**, y compris les nouvellement
   activés — donc le slot nouvellement activé **apparaît bien comme rangée cliquable** dans le
   panneau « Formatives »/« Sommatives », mais avec le style « non visible » (fond neutre, pas
   `primary_container`) puisqu'il n'est pas dans `visible_set` (§ 5.1).
6. `_on_selection_changed()` sauvegarde, recalcule, et **reconstruit la grille** avec les
   colonnes de `visible_set` uniquement — le nouveau slot n'apparaît donc **pas** comme colonne
   dans la grille.

#### 10.2 Conséquence utilisateur (comportement voulu, confirmé par l'utilisateur en direct)

Un slot nouvellement activé dans le gestionnaire (via les cases à cocher critères de
`EvaluationDetailWidget`, § 8.1) :
- **N'apparaît PAS automatiquement** comme colonne dans la grille de notes après fermeture du
  gestionnaire.
- **Apparaît** comme rangée cliquable (grisée/non surlignée) dans le panneau sidebar
  Formatives/Sommatives correspondant.
- Devient visible dans la grille seulement si l'utilisateur :
  - **clique sur cette rangée** dans le panneau sidebar (`_on_slot_icon_clicked`, § 5.2), ou
  - **clique sur « Toute »** (`_on_toggle_all`, § 5.2), qui remplit `visible_set` avec tous les
    slots actifs (y compris les nouveaux).

Ce comportement est **confirmé comme un choix de design volontaire** (indication explicite de
l'utilisateur, vérifiée en direct le jour de rédaction de cette doc) : il évite qu'une simple
activation de critère dans le gestionnaire ne modifie silencieusement la composition de la
grille de notes déjà affichée à l'écran — la visibilité dans la grille est un geste explicite et
séparé de l'activation d'un slot.

---

### 11. Terminologie : absence de colonne `enabled` sur `larcauth_evaluation`

Contrairement au principe gabarit général du monorepo (`enabled=FALSE→TRUE` pour élèves,
parents, etc. — voir `D:\projets\CLAUDE.md`), **la table `larcauth_evaluation` n'expose, dans
aucune requête lue dans ce périmètre, de colonne `enabled`**. Toutes les requêtes qui lisent
cette table (`main_data.py:306-309`, `eval_manager.py:325-331`, `evaluation_panel.py:865-874`,
`student_card_view.py:192-198`) sélectionnent uniquement `id, index_eval, label, nature, source,
crit_a, crit_b, crit_c, crit_d` (+ `type_evaluation` selon le contexte) — jamais de colonne
`enabled`.

L'état « actif » (analogue fonctionnel du `enabled=true` du principe gabarit) est **déduit** à
la volée, à chaque lecture, du fait qu'**au moins un des 4 critères `crit_a`..`crit_d` vaut
`'1'`** (ou `1`/`True` selon le contexte de comparaison) :

| Endroit | Calcul |
|---|---|
| `main_data.py:317` | `crits_active = any((r[i] or '0') == '1' for i in (5,6,7,8))` → `evals_list[...]['is_active']` |
| `eval_manager.py:89-96` (`_SlotBar.set_data`) | boucle sur A-D, `checked = val in ('1', 1, True)`, `active = True` dès qu'une case est cochée |
| `evaluation_panel.py:505` (`_SlotButton.set_data`) | `self._active = len(crits) > 0` (classe non utilisée en pratique, § 16) |

**Un slot désactivé n'est donc pas "vidé"** (pas de `DELETE`, pas de remise à zéro de `label`,
`nature`, `source` — ces champs restent en base) : il suffit de décocher les 4 critères pour
qu'il redevienne invisible dans tous les panneaux (sidebar, gestionnaire), sans perte de
contenu texte. Réciproquement, cocher un seul critère suffit à activer un slot, quel que soit le
contenu de `nature`/`source` (même vides).

Ce mécanisme est un **analogue fonctionnel** du principe gabarit (« slot pré-existant, jamais
supprimé, juste montré/masqué »), mais son implémentation technique diffère complètement de la
paire `enabled=FALSE/TRUE AND last_name LIKE 'Name of %'` utilisée pour élèves/parents. À ne pas
confondre.

---

### 12. Dialogue « Mode de calcul » (`views/weight_dialog.py`) et `CalcEngine`

#### 12.1 `WeightDialog` — rôle et droits

Dialogue modal (`setModal(True)`, `weight_dialog.py:79`) à deux aspects **seulement** (le
fichier documente explicitement que les critères eux-mêmes ne s'y configurent plus, en-tête du
fichier lignes 1-9) :
1. **Pondération de la matière entière** : coefficient multiplicateur `{1, 2, 3}`, stocké dans
   `larcauth_classroom_termsubject.subject_weight` (`_on_save`, `weight_dialog.py:620-626`).
2. **Calcul de la moyenne avec les critères** : poids Formatives/Sommatives (curseur unique
   `_f_slider`, 0-100, la valeur complémentaire est déduite : `ws = 100 - wf`) et conversion
   somme→note/7 (bandes IB, déclinées par nombre de critères 4/3/2/1).

**Droits** (`weight_dialog.py:86-91`) : seuls `Directeur` ou `Coordinateur`
(`session.role_flags`) peuvent modifier (`_is_editor`). Sinon `_apply_read_only()`
(`weight_dialog.py:572-584`) désactive tous les contrôles ; `_on_save` accepte silencieusement
sans rien enregistrer (`weight_dialog.py:588-591`) si l'utilisateur n'est pas éditeur.

#### 12.2 Formule PEI

Chargée/sauvegardée via `CalcEngine.get_formula`/`save_formula` (JSON dans
`larcauth_classroom_termsubject.calc_formula`, `common/calc_engine.py:82-123`). Structure par
défaut `_DEFAULT_PEI` (`calc_engine.py:19-39`) : `formative_weight=0.4`,
`summative_weight=0.6`, `solo_rule="if_only_one_type"`, `conversion.method="boundaries"` avec 7
bandes fixes pour 4 critères (`min/max` sur une échelle 0-32, `note` 1-7).

Le slider `_f_slider` pilote `_formula["formative_weight"]`/`["summative_weight"]` en direct
(`_on_weight_changed`, `weight_dialog.py:510-519`) et génère une formule HTML lisible
(`_update_formula_label`, 455-465) : `Jugement = moy(Formatives) × x% + moy(Sommatives) ×
(100-x)%`, toujours arrondi à l'entier.

Les bandes IB (`_boundaries_table`, 7 lignes) ne sont **éditables** que pour la déclinaison « 4
critères » et seulement par un éditeur (`_show_boundaries`, `weight_dialog.py:532-549`) ; les
déclinaisons 3/2/1 sont **recalculées automatiquement** (lecture seule) via
`_recalc_boundaries(n)` (`calc_engine.py:60-75`), qui répartit proportionnellement les seuils
sur `n × 8` points.

#### 12.3 `CalcEngine.compute_note` (`calc_engine.py:126-144`, `_compute_pei`
`149-255`)

Pour un élève et un `termsubject_id` donnés, avec des `active_crits` (critères effectifs, passés
par `MainWindow._recompute_one_student`, § 5.7) et un `override` optionnel (valeurs en cours de
saisie) :
1. Pour chaque critère actif, moyenne F et moyenne S séparément à partir des colonnes
   `{f|s}{idx:02d}_note_{crit}` des évaluations actives portant ce critère.
2. Combine par critère selon la règle solo (F×wf + S×ws si les deux existent, sinon le seul
   disponible).
3. Somme les moyennes de tous les critères actifs (`total_sum`).
4. Convertit `total_sum` en note 1-7 via les bandes IB — **reproportionnées** dynamiquement si
   `len(active_crits) != len(full_criteria)` de la formule (`calc_engine.py:246-250`), pour que
   la conversion reste cohérente même si l'enseignant a décoché un ou plusieurs critères dans le
   top bar « Affichage colonnes ».
5. `_apply_boundaries` (257-273) retourne la note de la bande la plus haute dont le seuil `min`
   est atteint (comparaison sur `min` uniquement, pas sur l'intervalle fermé — commentaire
   explicite sur un bug corrigé de trous entre bandes recalculées).

#### 12.4 Formule DP

`_compute_dp` (`calc_engine.py:278-325`) : `note = ei_note × ei_coefficient + moyenne(f01..f12
_note) × formative_coefficient + moyenne(s01..s12_note) × summative_coefficient`, arrondi à 1
décimale. **Non appelée automatiquement** par `MainWindow` (§ 5.7 — `_auto_compute_judgments_
and_note` s'arrête si `cycle == 'DP'`) ; seul un appel manuel à `CalcEngine.compute_note` (non
observé dans ce périmètre) la déclencherait.

---

### 13. Fiche élève détaillée (`views/student_card_view.py`)

`StudentCardView(ThemedDialog)` — fenêtre non modale (`setModal(False)`,
`student_card_view.py:92`) ouverte par double-clic sur le nom d'un élève dans la grille
(`_open_student_card`, `main_notes.py:635-644`) ou depuis le menu contextuel
(`ClipboardTable._open_student_card`, `grid_table.py:290-294`).

#### 13.1 Chargement (`_load_data`, `student_card_view.py:177-214`)

Charge la liste des élèves de la classe (mêmes critères `enabled=1` que `_load_combined_data`),
puis **toutes** les évaluations F/S du `termsubject_id` (label, nature, source, crit_a..d) —
regroupées en `_evals_f`/`_evals_s` (peu importe leur état actif : les 12 slots de chaque type
sont chargés). `_refresh_student_data` (216-260) charge ensuite, pour l'élève sélectionné, la
ligne complète de `larcauth_learnerpei_has_termsubjectpei`/`...dp` via
`SELECT * ... WHERE fk_student_id = ? LIMIT 1`, puis calcule `_judgments` (jgt_a..d), `_note_on_7`
(ou `moy_on_20`), `_note_checked` et `_term_obs`.

#### 13.2 Tableau par section (`_build_section_table`/`_fill_section_table`,
`student_card_view.py:396-459`)

Deux tableaux **lecture seule** (Formatives | Sommatives), colonnes `Label | Nature | A | B | C
| D` — une ligne par évaluation (les 12 slots, actifs ou non). Pour chaque critère : `—` en gris
(`p.text_disabled`) si le critère n'est pas coché pour ce slot OU si la valeur est absente/`'0'`
/`'None'` ; sinon la valeur numérique colorée en vert (`p.success`, si ≥ 4) ou rouge (`p.error`,
si < 4) — seuil binaire codé en dur à 4 (pas de dégradé continu comme dans la grille principale,
`student_card_view.py:450-457`).

#### 13.3 Jugements, note, validation, commentaire

- Panneau jugements : 4 valeurs `jgt_a..d`, couleur verte si ≥4, rouge si présent et <4, grise
  si absent (`_update_judgments`, 560-567).
- Panneau note : affiche `note_on_7`/`moy_on_20`, case `Validée` (`_valid_cb`) liée à
  `_on_validation_toggled` (599-612) qui écrit **directement**
  `UPDATE ... SET note_on_7_checked = ? WHERE id = ?` (pas de passage par un état "dirty").
- Commentaire général (`_comment_edit`, avec le même `_SpellHighlighter` fr_FR que
  `EvaluationDetailWidget`) : bouton « Enregistrer le commentaire », activé seulement après
  modification (`_on_comment_changed`, 594-597), écrit `term_observation` dans
  `_on_save` (614-629).
- Photo (`_update_photo`, 373-394) : `larccommon.photos.get_photo_path(student_id)`, ou
  initiales sur fond neutre si absente/introuvable.

Ce widget est strictement en lecture seule pour les notes elles-mêmes (`NoEditTriggers`,
`NoSelection`, ligne 411-413) — seuls le commentaire général et la case de validation sont
modifiables ici.

---

### 14. Gestion des événements (`views/event_dialog.py`, `common/event_service.py`)

#### 14.1 Points d'entrée

Depuis `ClipboardTable.contextMenuEvent` (`grid_table.py:237-260`), clic droit sur un élève de
la grille : Absence/Retard/Sortie anticipée créent l'événement **directement** sans dialogue
(`_add_event(..., event_type='absence'|'late'|'exit')`, `grid_table.py:262-281`) ; « Autre
événement... » ouvre `EventDialog` (`event_type=None`).

#### 14.2 `EventDialog` (`views/event_dialog.py`)

Dialogue modal simple : combo `EventService.EVENT_TYPES`, zone de note (200 caractères max,
tronquée côté `_on_save`, ligne 111), bouton « Enregistrer » → `EventService.insert_event(...)`
puis `self.accept()`.

#### 14.3 `EventService.insert_event` (`common/event_service.py:38-75`)

```python
row = cur.execute('SELECT COALESCE(MIN(event_id), -1) FROM student_event').fetchone()
next_id = min(row[0] - 1, -1) if row else -1
...
INSERT INTO student_event
   (event_id, student_id, event_type, event_at, note, source, created_by,
    lieu_label, subject_label)
VALUES (?, ?, ?, ?, ?, 'intranet', ?, ?, ?)
```
Contrairement à toutes les autres écritures documentées ici (toujours `UPDATE`), `student_event`
est une table à **`INSERT` libre** — cohérent avec l'exception explicite du principe gabarit
(`D:\projets\CLAUDE.md`, § « Exceptions à l'UPDATE uniquement »). L'`event_id` local est généré
**négatif** (`MIN(event_id) - 1`, jamais positif) pour ne jamais entrer en collision avec les
ids serveur (positifs) lors de la synchronisation ultérieure ; `source` est toujours codé en dur
à `'intranet'`.

`EventService.EVENT_TYPES` (`event_service.py:19-26`) : `absence`, `late`, `exit`, `justified`,
`departure`, `arrival` — 6 clés, avec libellés français.

Autres méthodes de lecture (`fetch_events_for_student`, `fetch_events_for_class`,
`fetch_absents_today`, `fetch_event_stats_for_students`, lignes 80-186) : **non utilisées dans
le périmètre `MainWindow` documenté ici** — aucun appelant trouvé dans `views/main_*.py`,
`views/grid_table.py`, `views/event_dialog.py`, `views/student_card_view.py`. Elles semblent
préparées pour un futur panneau de suivi de présence côté LarcProf, non branché à ce jour dans
cet écran (voir § 16).

---

### 15. Sommaire des tables SQLite touchées (vue transverse)

| Table | Lue par | Écrite (UPDATE) par | Écrite (INSERT) par |
|---|---|---|---|
| `larcauth_classroom_termsubject` | `main_data.py`, `weight_dialog.py`, `eval_manager.py`, `evaluation_panel.py`, `student_card_view.py` | `weight_dialog.py` (`subject_weight`, `calc_formula`), `calc_engine.py` (`calc_formula`) | — |
| `larcauth_classroom_termothersubject` | `main_data.py` | — | — |
| `larcauth_student` / `larcauth_aecuser` | `main_data.py`, `student_card_view.py`, `grid_table.py`(contextmenu) | — | — |
| `larcauth_evaluation` | `main_data.py`, `eval_manager.py`, `evaluation_panel.py`, `student_card_view.py` | `common/eval_helpers.py::save_evaluation_criteria` (label, nature, source, crit_a..d) | — |
| `larcauth_criteria_of_levelsubject` | `eval_manager.py`, `evaluation_panel.py` | — | — |
| `larcauth_learnerpei_has_termsubjectpei` | `main_notes.py`, `student_card_view.py` | `main_notes.py` (`_save_grid_edits`, `_recompute_one_student`, `_save_note_validation`, `_invalidate_note`), `student_card_view.py` (`_on_validation_toggled`, `_on_save`) | — |
| `larcauth_learnerdp_has_termsubjectdp` | idem (chemin DP) | idem (chemin DP, calcul auto désactivé) | — |
| `student_event` | `common/event_service.py` | — | `common/event_service.py::insert_event` |
| `module_config` | `main_data.py::_read_annee_scolaire` | — | — |

---

### 16. Points d'attention (observations de lecture — documentation seulement, aucun code modifié)

1. **Code dupliqué entre les 4 fichiers `main_*.py`** : les blocs d'imports de `main_window.py`,
   `main_data.py`, `main_actions.py`, `main_notes.py` sont quasi identiques (mêmes 40+ lignes
   d'import PySide6, y compris des symboles inutilisés dans certains fichiers — ex.
   `QStyledItemDelegate`, `QDialog`, `QKeySequence` importés dans `main_actions.py` sans être
   utilisés). Signe d'un découpage par copier-coller depuis un fichier historique unique.

2. **`_save_grid_edits` ignore silencieusement les cellules sans `_row_ids`** (`main_notes.py:
   672-674`, `continue` sans log ni message utilisateur) : si un élève n'a pas de ligne
   `learner_has_termsubject*` (données non initialisées), ses modifications de notes sont
   **perdues silencieusement** au clic sur "Enregistrer", sans avertissement — la barre de statut
   annoncera quand même « N cellule(s) sauvegardée(s) » avec N < nombre de cellules réellement
   modifiées, ce qui peut masquer la perte à l'utilisateur.

3. **`_on_cancel` ne défait pas les écritures déjà commitées par le moteur de calcul auto** (§
   5.7-5.9) : `jgt_a..d`, `note_on_7`/`moy_on_20` et `note_on_7_checked` sont écrits en base
   immédiatement (à chaque frappe en PEI, ou à chaque bascule de colonne visible) via des
   `conn.commit()` séparés de `_dirty_cells`. Cliquer « Annuler » après avoir saisi puis corrigé
   des notes laisse donc les jugements/notes recalculés en base même si les valeurs de notes
   source, elles, redeviennent celles d'avant (car jamais sauvegardées). Le nom du bouton
   (« Annuler ») suggère un rollback complet qui n'a pas lieu pour les colonnes calculées.

4. **`_fill_grille` charge la table entière sans filtre `WHERE`** (`main_notes.py:480-484`,
   commentaire de code dit « scoped par CTS, matchées par fk_student_id » mais la requête SQL
   elle-même ne filtre ni par `termsubject_id` ni par classe) — le filtrage effectif se fait
   ensuite en Python via le dict `eleves` de la classe courante (`notes.get(eleve['id'], {})`,
   ligne 521). Sur une base avec beaucoup d'élèves/matières, cela charge potentiellement toute
   la table `learnerpei_has_termsubjectpei` de toutes les classes/matières à chaque `_fill_grille`
   (chaque changement de colonne visible, chaque changement de thème…).

5. **`_load_criteria_labels()` est rappelée à chaque sélection de slot dans `EvalManagerWindow`**
   (`eval_manager.py:390`) alors que son résultat ne dépend que de `fk_levelsubject_id`, constant
   pour toute la durée de vie de la fenêtre (un seul `termsubject_id` par instance) — requête
   SQL redondante à chaque clic sur un tab ou une barre (12 requêtes possibles pour rien si
   l'utilisateur parcourt tous les slots).

6. **Classes mortes dans `views/evaluation_panel.py`** : `EvaluationDetailDialog`,
   `_SlotButton`, `EvaluationPanel` (lignes 330-903, plus de la moitié du fichier) ne sont
   importées/instanciées nulle part ailleurs dans le dépôt (recherche exhaustive
   `EvaluationPanel|EvaluationDetailDialog|_SlotButton` limitée au fichier lui-même). Elles
   dupliquent partiellement la logique de `_SlotBar`/`EvalManagerWindow` avec un design
   différent (grille adaptative de `_SlotButton`, dialogue modal par slot). Sans confirmation
   externe, il n'est pas possible de dire si c'est un prototype abandonné ou du code prévu pour
   un futur écran — à vérifier avec l'équipe avant suppression éventuelle.

7. **`common/event_service.py` : méthodes de lecture non branchées** (§ 14.3) —
   `fetch_events_for_student`, `fetch_events_for_class`, `fetch_absents_today`,
   `fetch_event_stats_for_students` n'ont aucun appelant dans le périmètre `views/main_*.py` /
   `views/*.py` lu. Seul `insert_event` est utilisé (depuis le menu contextuel de la grille et
   `EventDialog`). Il n'existe, dans ce périmètre, aucun écran LarcProf qui *affiche* les
   événements créés — seule leur création est exposée.

8. **`common/grid_config.py` / `pei_config.color_for()` non utilisée** (§ 9.6) — la coloration
   des notes passe exclusivement par `_note_gradient` (calcul dynamique dans `grid_table.py`),
   rendant `color_for` et les `grade_ranges` du JSON `pei.json` potentiellement obsolètes ou
   réservés à un usage non trouvé dans ce périmètre.

9. **Incohérence de vocabulaire mineure** : dans `_recompute_one_student`
   (`main_notes.py:729-805`) et `CalcEngine._compute_pei`, la variable est nommée `pei_id`
   même lorsqu'elle référence potentiellement un id de la table DP (le nom `_row_ids` est
   générique côté `MainWindow` mais réutilisé sous le nom local `pei_id` dans plusieurs
   méthodes qui ne sont en réalité appelées qu'en contexte PEI — pas un bug fonctionnel
   puisque `_auto_compute_judgments_and_note` s'arrête en DP, mais le nommage peut induire en
   erreur un futur lecteur qui étendrait le calcul auto au DP).

10. **Ancienne documentation `docs/20_eval_manager.md`** contenait deux inexactitudes mineures
    corrigées ici : (a) les couleurs « vert `#27ae60` » et « gris `#bbb` » citées pour l'état
    actif/suivant d'une `_SlotBar` sont en réalité des tokens de palette (`p.success`,
    `p.outline_variant`) et non des couleurs codées en dur (`eval_manager.py:111-117`) ; (b) les
    tailles de splitter « 400 / 500 » sont en réalité dérivées de tokens `ds.*`
    (`eval_manager.py:189-190`), pas des valeurs littérales.


---

## Partie III — Moteur de calcul, synchronisation, thème

Périmètre couvert (lecture intégrale, fichier par fichier) :
- `LarcProf/common/calc_engine.py` (360 lignes)
- `LarcProf/common/eval_helpers.py` (40 lignes)
- `LarcProf/common/sync.py` (578 lignes)
- `LarcProf/common/theme.py` (153 lignes)
- `LarcProf/common/grid_config.py` (87 lignes) et `LarcProf/common/session.py` (94 lignes), en appui

Toutes les affirmations non triviales sont sourcées `fichier:ligne`. Quand un point du code n'est pas
explicite (ambiguïté, comportement non testé, absence de vérification possible), c'est dit noir sur blanc
plutôt que supposé.

---

### 1. `calc_engine.py` — Moteur de calcul des notes PEI/DP

#### 1.1 Rôle général

`CalcEngine` (classe à méthodes de classe, aucune instance) calcule la note finale d'un élève pour un
`termsubject` donné, à partir :
- d'une **formule JSON** stockée dans `larcauth_classroom_termsubject.calc_formula` (colonne SQLite locale),
- des **notes de critères** saisies dans `larcauth_evaluation` (grille PEI) ou dans les colonnes
  `f{NN}_note`/`s{NN}_note`/`ei_note` de `larcauth_learnerdp_has_termsubjectdp` (grille DP).

Deux moteurs distincts cohabitent dans la même classe : `_compute_pei` (note sur 7, bandes IB) et
`_compute_dp` (note sur 20, formule pondérée). Le type de formule (`formula["type"]`) détermine lequel
est appelé — `calc_engine.py:126-144` (`compute_note`).

#### 1.2 Formule par défaut PEI — `_DEFAULT_PEI` (`calc_engine.py:19-39`)

```python
{
  "type": "PEI",
  "criteria": ["A", "B", "C", "D"],
  "formative_weight": 0.4,
  "summative_weight": 0.6,
  "solo_rule": "if_only_one_type",
  "conversion": {
    "method": "boundaries",
    "boundaries": [
      {"min": 0,  "max": 5,  "note": 1},
      {"min": 6,  "max": 9,  "note": 2},
      {"min": 10, "max": 14, "note": 3},
      {"min": 15, "max": 18, "note": 4},
      {"min": 19, "max": 23, "note": 5},
      {"min": 24, "max": 27, "note": 6},
      {"min": 28, "max": 32, "note": 7},
    ],
  },
}
```

Ces bandes IB correspondent à 4 critères notés chacun sur 8 points max (A/B/C/D), soit un total maximal
de 32 points.

#### 1.3 Formule par défaut DP — `_DEFAULT_DP` (`calc_engine.py:41-50`)

```python
{
  "type": "DP",
  "criteria": [],
  "conversion": {
    "method": "formula",
    "ei_coefficient": 0.125,
    "formative_coefficient": 1.125,
    "summative_coefficient": 0.75,
  },
}
```

Le docstring en tête de fichier (`calc_engine.py:8`) résume la formule DP :
`EI × coeff_ei + moy(F/20) × coeff_f + moy(S/20) × coeff_s`.

**Remarque factuelle (pas une supposition, juste une observation) :** la somme des trois coefficients par
défaut vaut `0.125 + 1.125 + 0.75 = 2.0`. Le fichier ne documente nulle part l'échelle attendue de `ei_note`
(0-7 ? 0-20 ?) ; il n'est donc pas possible de confirmer à la seule lecture de `calc_engine.py` que le
résultat final est borné à 20. Voir aussi §7 (points d'attention).

#### 1.4 Templates PEI — `_TEMPLATES_PEI` (`calc_engine.py:52-57`)

Quatre gabarits de critères actifs, utilisés par `get_templates_pei()` :

| Clé | Critères |
|---|---|
| `4c` | A, B, C, D |
| `3c` | A, C, D |
| `2c` | A, D |
| `1c` | A |

`get_templates_pei()` (`calc_engine.py:329-346`) construit, pour chaque gabarit, une formule complète
(`type=PEI`, `formative_weight=0.4`, `summative_weight=0.6`, `solo_rule="if_only_one_type"`) dont les
bandes `conversion.boundaries` sont **recalculées** via `_recalc_boundaries(len(crits))` plutôt que
copiées depuis `_DEFAULT_PEI` — donc proportionnées au nombre de critères du gabarit (ex. `1c` → bandes sur
0-8, `2c` → bandes sur 0-16, etc.).

`get_templates_dp()` (`calc_engine.py:348-360`) retourne deux entrées :
- `"standard"` : copie de `_DEFAULT_DP` (methode `"formula"`, coefficients 0.125/1.125/0.75) ;
- `"simple"` : `{"type": "DP", "criteria": [], "conversion": {"method": "simple_avg"}}`.

**Point d'attention (voir §7.5)** : `_compute_dp` (§1.7) ne lit jamais `conversion.method` — il applique
toujours la même formule pondérée EI/F/S quels que soient les coefficients trouvés (ou leurs valeurs par
défaut si absents). Le template `"simple"` (`method: "simple_avg"`) n'a donc **aucun effet différencié** :
sélectionner ce gabarit produit exactement le même calcul que `"standard"`, malgré son nom qui laisse
attendre une simple moyenne.

#### 1.5 `_recalc_boundaries(criteria_count)` (`calc_engine.py:60-75`)

Recalcule les 7 bandes IB proportionnellement au nombre de critères effectifs :

```
max_total = criteria_count * 8
pour note de 1 à 7 :
    pct_low  = (note - 1) / 7
    pct_high = note / 7
    min = round(pct_low  * max_total)
    max = round(pct_high * max_total) - 1   si note < 7
        = max_total                          si note == 7
```

Après la boucle, le `max` de la **dernière** bande (note 7) est forcé une seconde fois à `max_total`
(`calc_engine.py:74`) — redondant avec la condition `note < 7` déjà présente dans la boucle, mais sans
effet néfaste (idempotent).

Exemple pour `criteria_count = 1` (`max_total = 8`) :
notes 1..7 avec `pct_low/pct_high` = 0/0.14, 0.14/0.29, 0.29/0.43, 0.43/0.57, 0.57/0.71, 0.71/0.86,
0.86/1 → bandes arrondies approximativement `0-0`, `1-1`, `2-2`, `3-4`, `4-5`, `5-6`, `6-8` (les valeurs
exactes dépendent de l'arrondi Python `round()`, banker's rounding).

#### 1.6 `get_formula` / `save_formula` (`calc_engine.py:82-123`)

- **`get_formula(termsubject_id)`** (82-109) :
  1. `SELECT calc_formula FROM larcauth_classroom_termsubject WHERE id = ?` sur `db.local_conn` (SQLite) — `calc_engine.py:87-90`.
  2. Si une ligne existe et `calc_formula` est non NULL : parse JSON. Si `formula["type"] == "PEI"`, force
     `formula.setdefault("solo_rule", "if_only_one_type")` (`calc_engine.py:95-96`) — garantit que même une
     ancienne formule enregistrée avant l'introduction de la règle « solo » expose la clé (compatibilité
     lecture tierce).
  3. Si `calc_formula` est NULL (ou table absente) : détection du cycle par une jointure
     `larcauth_classroom_termsubject → larcauth_classroom → larcauth_level → larcauth_program`
     (`calc_engine.py:99-105`), lecture de `p.sigle` en majuscules. Si le sigle est dans
     `('DP', 'DPFR', 'DPEN', 'IBDP', 'DIPLOMA')` → retourne `dict(_DEFAULT_DP)`, sinon → `dict(_DEFAULT_PEI)`.
  4. Si `db.local_conn is None` : retourne directement `_DEFAULT_PEI` (pas de copie — l'appelant reçoit
     l'objet module-level partagé, donc toute mutation ultérieure par un appelant modifierait le défaut
     global ; comportement différent du cas §3 qui retourne bien une copie `dict(...)`. Non exploité nulle
     part dans ce fichier, signalé par prudence en §7).

- **`save_formula(termsubject_id, formula)`** (112-123) : `UPDATE larcauth_classroom_termsubject SET
  calc_formula = ? WHERE id = ?` avec le JSON sérialisé (`json.dumps(formula, ensure_ascii=False)`), puis
  `conn.commit()`. Conforme au principe gabarit (UPDATE seul, jamais d'INSERT).

#### 1.7 `compute_note` — point d'entrée (`calc_engine.py:126-144`)

```python
compute_note(student_id, termsubject_id, active_crits=None, override=None)
```

- `active_crits` : liste des critères actuellement affichés/actifs dans la grille (ex. suite à une
  désélection de colonne dans la barre supérieure). Documenté dans le docstring (129-134) : la note/7
  s'adapte proportionnellement au nombre de critères restants.
- `override` : dict `{nom_colonne: valeur_str}` représentant des cellules **en cours de saisie, non encore
  enregistrées en base** — utilisé pour un recalcul « live » pendant que l'utilisateur tape, avant tout
  commit SQLite.
- Dispatch : `formula = cls.get_formula(termsubject_id)` ; si `formula["type"] == "DP"` → `_compute_dp`,
  sinon → `_compute_pei`.

#### 1.8 `_compute_pei` — calcul détaillé (`calc_engine.py:148-255`)

**Étape 1 — Détermination des critères effectifs** (152-160)

```python
full_criteria = formula.get("criteria", ["A", "B", "C", "D"])
criteria = list(active_crits) if active_crits else list(full_criteria)
if not criteria:
    return None
```

Commentaire du code (153-157) : la formule PEI ne pilote plus le choix des critères via sa propre clé
`criteria` — c'est l'affichage des colonnes du top bar (`active_crits`) qui fait foi. `full_criteria` sert
uniquement de repli (si `active_crits` est vide/`None`) et de référence pour détecter un sous-ensemble
(voir étape 5).

**Étape 2 — Poids formatif/sommatif** (161-165)

```python
wf = formula.get("formative_weight", 0.4)
ws = formula.get("summative_weight", 0.6)
total_w = wf + ws
if total_w == 0: return None
```

`total_w` est calculé mais **jamais utilisé comme diviseur** dans la suite du calcul (voir §1.8 étape 4 —
la pondération appliquée est `f_mean*wf + s_mean*ws` sans division par `total_w`). Le seul rôle de
`total_w` est le garde-fou « les deux poids sont nuls → impossible de calculer ». Si `wf + ws ≠ 1` (ex.
`wf=0.4, ws=0.5`), la moyenne pondérée par critère ne sera **pas normalisée** à 1 — c'est un comportement
réel du code, signalé en §7.

**Étape 3 — Chargement des évaluations actives** (167-185)

```sql
SELECT type_evaluation, index_eval, crit_a, crit_b, crit_c, crit_d
FROM larcauth_evaluation
WHERE fk_classroom_termsubject_id = ? AND CAST(index_eval AS INTEGER) BETWEEN 1 AND 12
```

Pour chaque ligne : `etype = type_evaluation.strip().upper()`, `idx = int(index_eval)`. Pour chacun des 4
critères A/B/C/D, si le critère fait partie de `criteria` **et** que la colonne `crit_X` correspondante
vaut `'1'`, `'TRUE'` ou `'ON'` (comparaison texte après `str(...).strip()`), le couple `(etype, idx)` est
ajouté à `evals_by_criterion[crit]` (`calc_engine.py:178-185`). Autrement dit : une évaluation ne compte
pour un critère que si elle a été explicitement marquée active sur ce critère (via
`save_evaluation_criteria`, voir §2).

**Étape 4 — Localisation de l'élève et moyenne par critère** (187-233)

```sql
SELECT learner_has_termsubject_ptr_id FROM larcauth_learnerpei_has_termsubjectpei
WHERE fk_student_id = ? LIMIT 1
```
Si aucune ligne → `return None`. `learner_id` = `learner_has_termsubject_ptr_id` trouvé.

Pour chaque critère actif, pour chaque `(etype, idx)` associé :
```python
col = f"{etype[0].lower()}{idx:02d}_note_{crit.lower()}"
```
ex. `type_evaluation="F"`, `index_eval=3`, critère `B` → colonne `f03_note_b`. Lecture :
```sql
SELECT "{col}" FROM larcauth_learnerpei_has_termsubjectpei WHERE learner_has_termsubject_ptr_id = ?
```
- Si `override` contient `col` et que la valeur n'est ni `None` ni `''` : `float(override[col])` remplace
  la valeur base — dispatché dans `f_vals` si `etype in ("F", "FORMATIVES")`, sinon `s_vals`.
- Sinon, si la ligne existe et la valeur base n'est pas `NULL` : même dispatch F/S.

`f_mean = moyenne(f_vals)` ou `None` si vide ; `s_mean` de même pour `s_vals`.

**Règle « solo »** (`solo_rule = "if_only_one_type"`, documentée dans la formule elle-même) — `calc_engine.py:224-233` :
```python
if f_mean is not None and s_mean is not None:
    criterion_averages[crit] = f_mean * wf + s_mean * ws
elif s_mean is not None:
    criterion_averages[crit] = s_mean          # 100 % sommatives
elif f_mean is not None:
    criterion_averages[crit] = f_mean          # 100 % formatives
else:
    criterion_averages[crit] = 0.0
```
Si un seul des deux types (F ou S) a des notes saisies pour ce critère, ce type compte seul à 100 % — la
pondération `wf/ws` ne s'applique que lorsque les deux types ont au moins une note.

**Étape 5 — Somme et conversion** (235-255)

```python
total_sum = sum(criterion_averages.values())
if total_sum == 0: return None
```

Conversion (`conv = formula.get("conversion", {})`, `method = conv.get("method", "boundaries")`) :

- **`method == "boundaries"`** (défaut) :
  - Si `len(criteria) != len(full_criteria)` (des critères ont été désélectionnés dans le top bar) :
    les bandes de la formule (calibrées pour `len(full_criteria)` critères) ne s'appliquent plus — elles
    sont **recalculées** via `_recalc_boundaries(len(criteria))` (§1.5), proportionnellement au nombre de
    critères effectifs.
  - Sinon : les bandes définies dans `formula["conversion"]["boundaries"]` sont utilisées telles quelles.
  - Résultat : `cls._apply_boundaries(total_sum, boundaries)`.
- **Sinon (toute autre valeur, ex. `"linear"`)** :
  ```python
  max_total = len(criteria) * 8
  return round((total_sum / max_total) * 7)
  ```
  Conversion linéaire proportionnelle sur 7, arrondi Python standard (banker's rounding).

#### 1.9 `_apply_boundaries(total, boundaries)` (`calc_engine.py:258-273`)

```python
note = 1
for b in boundaries:
    if total < b["min"]:
        break
    note = int(b["note"])
return note
```

Le docstring (259-266) explicite la règle : le résultat est **toujours un entier** (jamais de note à
virgule en PEI). La comparaison porte sur le seuil `min` de chaque bande (pas sur l'intervalle fermé
`[min, max]`) — la note retournée est celle de la **bande la plus haute dont le seuil minimal est
atteint**. Le commentaire précise pourquoi : les bandes recalculées par `_recalc_boundaries` peuvent
laisser des trous entre `max` d'une bande et `min` de la suivante (arrondis), et une comparaison stricte
sur l'intervalle fermé aurait fait retomber certains totaux (ex. 17.6) dans le cas par défaut (`note = 1`)
au lieu de la bande réellement atteinte.

**Note factuelle** : cette fonction suppose que `boundaries` est trié par `min` croissant. Aucun tri n'est
fait dans `_apply_boundaries` lui-même — l'ordre dépend entièrement de l'ordre de construction en amont
(`_DEFAULT_PEI["conversion"]["boundaries"]` et `_recalc_boundaries` produisent tous deux des listes déjà
triées par construction). Si une formule custom enregistrée via `save_formula` contenait des bandes
non triées, le résultat serait potentiellement incorrect — non vérifiable depuis ce seul fichier.

#### 1.10 `_compute_dp` (`calc_engine.py:277-325`)

```sql
SELECT learner_has_termsubject_ptr_id FROM larcauth_learnerdp_has_termsubjectdp
WHERE fk_student_id = ? LIMIT 1
```
Si absent → `None`. Sinon `learner_id`.

Coefficients lus depuis `formula["conversion"]` avec défauts `_DEFAULT_DP` : `ei_c = conv.get("ei_coefficient", 0.125)`, `f_c = conv.get("formative_coefficient", 1.125)`, `s_c = conv.get("summative_coefficient", 0.75)`.

`_read(col)` (298-303) : `SELECT "{col}" FROM larcauth_learnerdp_has_termsubjectdp WHERE
learner_has_termsubject_ptr_id = ?` → `float(row[0])` si non NULL, sinon `0.0`.

- `ei_val = _read("ei_note")`.
- Formatives : boucle `f{01..12}_note`, **seules les valeurs `v > 0` sont retenues** dans `f_vals`
  (`calc_engine.py:310-313`) ; `f_mean = moyenne(f_vals)` ou `0.0` si aucune valeur `> 0`.
- Sommatives : même logique sur `s{01..12}_note` → `s_mean`.
- **Note factuelle importante** : le filtre `v > 0` traite de façon identique une case *non remplie*
  (`_read` renvoie `0.0` pour NULL) et une note **réellement saisie à 0**. Une note de 0/20 réellement
  attribuée à un élève serait donc **exclue de la moyenne** exactement comme une case vide, ce qui change
  le résultat par rapport à une moyenne qui inclurait ce 0. Ce comportement est présent tel quel dans le
  code ; aucun commentaire ne le justifie explicitement dans `calc_engine.py`. Signalé en §7.

Formule finale (`calc_engine.py:324-325`) :
```python
note = ei_val * ei_c + f_mean * f_c + s_mean * s_c
return round(note, 1)
```
Arrondi à 1 décimale (contrairement au PEI qui est toujours un entier).

---

### 2. `eval_helpers.py` — `save_evaluation_criteria` (documentation brève)

Fonction unique, module de 40 lignes (`eval_helpers.py:5-40`).

```python
save_evaluation_criteria(eval_id: int, label: str, nature: str, source: str, crits: dict) -> bool
```

Effectue un **UPDATE unique** sur SQLite local (`db.local_conn`) :

```sql
UPDATE larcauth_evaluation
SET label=?, nature=?, source=?, crit_a=?, crit_b=?, crit_c=?, crit_d=?
WHERE id=?
```

`crits` est un dict avec les clés `crit_a`..`crit_d`, valeurs `'1'` ou `'0'` (défaut `'0'` via
`crits.get('crit_X', '0')` si la clé est absente, `eval_helpers.py:28-31`). En cas d'exception, l'erreur
est envoyée à `larccommon.error_reporting.get_reporter().report_exception()` puis affichée en console
(`print`), et la fonction retourne `False` plutôt que de propager l'exception. C'est cette table
(`crit_a..crit_d`) et ces valeurs `'1'/'TRUE'/'ON'` que `_compute_pei` relit ensuite (§1.8, étape 3) pour
savoir quelles évaluations comptent pour quel critère.

---

### 3. `sync.py` — Synchronisation device (SQLite) ↔ serveur (PostgreSQL), pattern shadow-table `_ref`

#### 3.1 Principe (docstring `sync.py:1-22`)

Chaque table métier listée dans `BUSINESS_TABLES` (définie dans `LarcProf/common/sqlite_init.py:340-347`,
importée `sync.py:31`) possède une jumelle `<table>_ref` au schéma identique, toutes deux en SQLite local :

- `<table>` : état local courant, modifiable par le professeur dans l'IHM.
- `<table>_ref` : dernier état serveur connu au moment de la dernière synchro réussie (snapshot).

`BUSINESS_TABLES` = `larcauth_evaluation`, `larcauth_learnerpei_has_termsubjectpei`,
`larcauth_learnerdp_has_termsubjectdp`, `larcauth_classroom_termothersubject`,
`larcauth_learner_has_termothersubject`, `student_event`.

Le diff se fait **cellule par cellule**, lignes jointes par `id`, avec la matrice de décision suivante
(`sync.py:12-17`, implémentée dans `_decide`, §3.6) :

| local vs ref | serveur vs ref | Action |
|---|---|---|
| = | = | NOOP |
| = | ≠ | PULL (le serveur a changé, pas le local) |
| ≠ | = | PUSH (le local a changé, pas le serveur) |
| ≠ | ≠ | CONFLICT (les deux ont changé) |

Portée : uniquement le trimestre courant (`term_id = module_config.trimestre_courant`), lu par
`_ensure_current_term` (§3.3). Les trimestres passés sont figés et hors périmètre du diff.

#### 3.2 Structures de données

- **`CellAction`** (Enum, `sync.py:34-39`) : `NOOP`, `PULL`, `PUSH`, `CONFLICT`.
- **`CellDiff`** (dataclass, `sync.py:42-51`) : `table`, `row_id`, `column`, `local_value`, `ref_value`,
  `server_value`, `action`.
- **`SyncReport`** (dataclass, `sync.py:54-80`) : compteurs `pulled`/`pushed`, listes `conflicts`
  (`list[CellDiff]`) et `errors` (`list[str]`), propriétés `has_conflicts`/`has_errors`, méthode
  `summary()` qui construit une chaîne lisible (`"N pull(s) | M push(es) | K conflit(s) | J erreur(s)"`).

#### 3.3 Garde-fous — `_ensure_current_term` / `_ensure_server_connected` (`sync.py:104-124`)

- `_ensure_current_term()` : `SELECT trimestre_courant FROM module_config WHERE id = 1` sur
  `db.local_conn`. Lève `RuntimeError` si `conn is None`, si la ligne est absente (« module non instancié »)
  ou si `term <= 0`. Retourne `term` (int) et le stocke dans `self._current_term`.
- `_ensure_server_connected()` : lève `RuntimeError` si `db.server_conn is None` (ni intranet ni cloud actif).

#### 3.4 `_get_cols(table, conn)` — colonnes métier hors métadonnées (`sync.py:129-152`)

Liste blanche par exclusion : `_IGNORE_COLS` (`sync.py:92-96`) = `{'id', 'sync_version', 'synced_at',
'synced_by', 'last_modified_at', 'sync_revision', 'note_on_7_checked'}`. `note_on_7_checked` est
explicitement documentée comme colonne locale de validation d'affichage (case « note validée sur 7 »),
jamais synchronisée.

Tente d'abord `SELECT * FROM "{table}" LIMIT 0` via `cur.description` (fonctionne pour PostgreSQL comme
pour SQLite), avec repli sur `PRAGMA table_info("{table}")` en cas d'exception (spécifique SQLite).

#### 3.5 `pull_push()` — point d'entrée principal (`sync.py:157-228`)

Flux complet :

1. `local_conn = db.local_conn` capturé **en tête de fonction** (`sync.py:164`), avant le bloc
   `try/except` des garde-fous — c'est la correction appliquée aujourd'hui (voir §7.2) : `local_conn` est
   ainsi garanti défini avant tout usage ultérieur (boucle `for table in BUSINESS_TABLES`, `local_conn.commit()`
   à la ligne 211), même si une exception survient entre-temps.
2. Si `local_conn is None` → `report.errors.append(...)`, retour immédiat.
3. `_ensure_current_term()` puis `_ensure_server_connected()` dans un `try/except RuntimeError` — en cas
   d'échec, l'erreur est journalisée (`_log`), ajoutée à `report.errors`, et la fonction retourne
   immédiatement (`sync.py:169-177`).
4. Pour chaque `table` de `BUSINESS_TABLES` (ordre de la constante, §3.1), dans un `try/except Exception`
   individuel (une erreur sur une table n'interrompt pas les suivantes) :
   - `diffs = list(self.compute_cell_diff(table))` (§3.6), chronométré (`time.time()`), journalisé.
   - Si aucune diff : `continue` (table suivante).
   - Pour chaque `diff` : `apply_pull` si `PULL`, `apply_push` si `PUSH`, accumulation dans `conflicts`
     si `CONFLICT` (§3.7).
   - `report.pulled`/`report.pushed` incrémentés, `report.conflicts.extend(conflicts)`.
   - `local_conn.commit()` (`sync.py:211`) — commit SQLite après traitement de **toutes** les diffs de la
     table (pas un commit par cellule ; `apply_push`, lui, fait son propre `local_conn.commit()` interne,
     voir §3.7).
   - Si `not conflicts` : `self.touch_sync_state(table)` (§3.8) ; sinon, `sync_state` **n'est pas mis à
     jour** pour cette table tant que des conflits existent (log explicite `sync.py:218`).
5. À la fin, log de synthèse via `report.summary()`.

#### 3.6 `compute_cell_diff(table)` — diff cellule par cellule (`sync.py:233-351`)

1. `ref_table = f"{table}_ref"`. `cols = self._get_cols(table, local_conn)` — si vide, log et `return`
   (générateur vide).
2. **Lecture locale** : `SELECT * FROM "{table}"`, indexé par `str(row_dict['id'])` dans `local_rows`
   (`sync.py:255-260`). La clé est explicitement convertie en `str` — commentaire : SQLite renvoie `id` en
   TEXT tandis que le serveur PostgreSQL le renvoie en BIGINT ; sans cette normalisation, chaque id
   apparaîtrait en double dans `all_ids` et les diffs s'écraseraient mutuellement.
3. **Lecture ref** : `SELECT * FROM "{ref_table}"`, même indexation dans `ref_rows`.
4. **Lecture serveur** (`sync.py:277-324`) : `from common.session import session` est importé **avant**
   le `if/else` qui distingue les deux requêtes (§7.1 — correction appliquée aujourd'hui). Deux cas :
   - **`table == 'larcauth_evaluation'`** :
     ```sql
     SELECT e.* FROM public."larcauth_evaluation" e
     JOIN public.larcauth_classroom_termsubject cts ON cts.id = e.fk_classroom_termsubject_id
     JOIN public.larcauth_classroom c ON c.id = cts.fk_classroom_id
     WHERE cts.fk_term_id = %s AND cts.fk_teacher_id = %s
       AND cts.enabled = true AND c.enabled = true
     ```
     paramètres `(self._current_term, session.user_id)`.
   - **Toutes les autres tables** (dont PEI/DP) :
     ```sql
     SELECT e.*, lht.fk_student_id
     FROM public."{table}" e
     JOIN public.larcauth_learner_has_termsubject lht ON lht.id = e.learner_has_termsubject_ptr_id
     JOIN public.larcauth_classroom_termsubject cts ON cts.id = lht.fk_classroom_termsubject_id
     JOIN public.larcauth_classroom c ON c.id = cts.fk_classroom_id
     WHERE cts.fk_term_id = %s AND cts.fk_teacher_id = %s
       AND cts.enabled = true AND c.enabled = true
     ```
     paramètres identiques. **Remarque** : cette seconde requête suppose que la table a une colonne
     `learner_has_termsubject_ptr_id` — ce qui exclut de fait `larcauth_classroom_termothersubject`,
     `larcauth_learner_has_termothersubject` et `student_event` de ce filtrage par
     `learner_has_termsubject` si elles ne portent pas cette colonne (non vérifié indépendamment ici, hors
     du périmètre PEI/DP demandé).
   - `server_rows` indexé par `str(row_dict['id'])` (`sync.py:319`) — **cette ligne suppose que la requête
     serveur renvoie une colonne `id`**. Voir §7.3 pour l'implication directe de cette hypothèse sur
     `apply_push`.
   - Toute exception ici est absorbée (`report_exception()` + log), et le traitement continue avec les
     `server_rows` déjà obtenues (commentaire : pull impossible mais push encore possible).
5. **Comparaison** : `all_ids = local_rows.keys() | ref_rows.keys() | server_rows.keys()`. Pour chaque
   `row_id`, pour chaque colonne métier `col` : `_normalize()` (§3.9) appliqué aux trois valeurs, puis
   `_decide(local_val, ref_val, server_val)` (§3.9). Si `NOOP`, la cellule est ignorée ; sinon un `CellDiff`
   est produit (générateur `yield`).

#### 3.7 `apply_pull` / `apply_push` / `apply_resolution` — application des décisions

**`apply_pull(diff)`** (`sync.py:356-420`) — `local = serveur`, `ref = serveur` :
- Si `local_conn is None` → `return` sans effet.
- Vérifie d'abord l'existence de la ligne en local (`SELECT 1 FROM "{table}" WHERE id = ?`). Si absente
  **et** `server_conn` disponible : va chercher la ligne complète côté serveur
  (`SELECT * FROM public."{table}" WHERE id = %s`), puis l'insère à l'identique dans `<table>` **et**
  `<table>_ref` (`INSERT INTO ... VALUES (...)`, valeurs converties par `_to_sqlite`, §3.9). Commentaire
  explicite (`sync.py:369-372`) : sans cette création préalable, l'`UPDATE` de cellule suivant ne
  toucherait aucune ligne et celle-ci resterait absente en local indéfiniment.
- Puis, dans tous les cas : `UPDATE "{table}" SET "{col}" = ? WHERE id = ?` et
  `UPDATE "{ref_table}" SET "{col}" = ? WHERE id = ?`, valeur = `diff.server_value` convertie par
  `_to_sqlite`.
- Toute exception SQL est journalisée puis **re-levée** (`raise`) — contrairement à d'autres endroits du
  fichier qui absorbent silencieusement.

**`apply_push(diff)`** (`sync.py:422-458`) — `serveur = local`, `ref = local` :
- Si `local_conn is None` ou `server_conn is None` → `return` sans effet.
- Contexte d'audit posé sur la connexion serveur via `larccommon.audit_context.refresh()` puis `attach(server_conn)`
  (`sync.py:438-441`), qui exécutent des `SELECT set_config('app.xxx', valeur, false)` **au niveau
  session** (le `false` de `set_config` signifie « pas seulement pour la transaction courante » —
  fonctionne correctement même sous `autocommit=True`, voir `LarcCommon/larccommon/audit_context.py:31-48`).
- Puis :
  ```sql
  UPDATE public."{table}" SET "{col}" = %s WHERE id = %s
  ```
  (`sync.py:442-445`) avec `val = diff.local_value`, `row_id = diff.row_id`. **C'est le point du bug
  documenté en §7.3.**
- `UPDATE "{ref_table}" SET "{col}" = ? WHERE id = ?` côté local (`_to_sqlite(val)`), puis
  `local_conn.commit()` (`sync.py:452`) — commit local explicite **par cellule poussée**, contrairement à
  `pull_push()` qui commit une seule fois par table (§3.5 point 4).
- Exception journalisée puis re-levée.

**`apply_resolution(diff, keep)`** (`sync.py:460-511`) — résolution manuelle d'un conflit par le prof,
`keep ∈ {'local', 'server'}` :
- `val = diff.local_value if keep == 'local' else diff.server_value`.
- `UPDATE` sur `<table>` et `<table>_ref` en local, puis `local_conn.commit()`.
- **Si `server_conn is not None` ET `keep == 'local'`** (c'est-à-dire seulement quand la valeur retenue
  doit remonter au serveur — si `keep == 'server'`, aucune écriture serveur n'est faite car le serveur a
  déjà la bonne valeur) :
  ```python
  source = 'intranet' if db.server_mode == DBMode.INTRANET else 'cloud'
  cur.execute(f"SET LOCAL app.sync_source = '{source}'")
  from common.session import session
  cur.execute(f"SET LOCAL app.modified_by = {int(session.user_id or 0)}")
  cur.execute('UPDATE public."{table}" SET "{col}" = %s WHERE id = %s', (val, row_id))
  ```
  (`sync.py:495-504`). **C'est le point du bug documenté en §7.4** : `SET LOCAL` sous `autocommit=True`,
  et f-strings non paramétrées pour `sync_source`/`modified_by`.

#### 3.8 `touch_sync_state(table)` (`sync.py:513-533`)

```sql
INSERT INTO sync_state (table_name, last_sync, last_source)
VALUES (?, datetime('now'), ?)
ON CONFLICT(table_name) DO UPDATE SET last_sync = excluded.last_sync, last_source = excluded.last_source
```
`last_source` = `'intranet'` / `'cloud'` / `'unknown'` selon `db.server_mode` (`DBMode`, défini dans
`LarcProf/common/database.py:38-42`). `commit()` local puis log. Toute exception est absorbée (log
seulement, pas de `raise`) — cohérent avec le fait que `pull_push()` n'appelle cette méthode qu'après un
commit déjà réussi (§3.5).

#### 3.9 Fonctions utilitaires (`sync.py:540-578`)

- **`_normalize(val)`** (540-549) : `None` reste `None` ; `int`/`float` inchangés ; toute autre valeur est
  convertie en `str(val).strip()`, et si le résultat est `''` ou `'null'`/`'none'` (insensible à la casse)
  → `None`. Sert à neutraliser les différences de représentation entre SQLite (TEXT) et PostgreSQL (types
  natifs) avant comparaison.
- **`_to_sqlite(val)`** (552-556) : `None` → `None`, sinon `str(val)` — SQLite local stocke donc tout en
  texte (cohérent avec le schéma `_create_table_from_data` de `sqlite_init.py`, §7.3).
- **`_decide(local, ref, server)`** (559-578) : implémente exactement la matrice de décision du §3.1 par
  comparaison d'égalité Python (`!=`) sur les valeurs déjà normalisées.

#### 3.10 Singleton (`sync.py:582`)

`sync = SyncManager()` — instance unique importée ailleurs dans l'application (pattern identique à
`db`/`theme_manager`/`sqlite_init` mentionné dans `D:\projets\CLAUDE.md`, section « Singletons »).

---

### 4. `theme.py` — Shim de thème local LarcProf

#### 4.1 Rôle (`theme.py:1`)

« Shim vers `larccommon.theme` — ajoute `btn_toggle_style` pour LarcProf. » Le module ne redéfinit pas de
thème propre : il importe `DesignTokens`, `FontScale`, `Palette`, `QssHelper`, `Theme`, `ThemeManager` et le
singleton `theme_manager` depuis `larccommon.theme` (`theme.py:15-23`), puis les ré-expose (avec un
wrapper, §4.4) augmentés de fonctions spécifiques à la grille de notes PEI/DP.

#### 4.2 Constantes couleur figées hors thème — `ZONE_*` (`theme.py:5-12`)

```python
ZONE_F_COLOR    = '#26A9E1'  # Formatives — bleu ciel
ZONE_S_COLOR    = '#1E4394'  # Sommatives — bleu marine
ZONE_NEUTRAL    = '#F0F0F0'  # Matière / Affichage colonnes — gris très clair
ZONE_TEXT_LIGHT = '#FFFFFF'  # Texte sur les panneaux F (bleu ciel) et S (bleu marine)
ZONE_BORDER     = '#BDBDBD'  # Cadre des 4 sections du sidebar
ZONE_BTN_BG     = '#F57C00'  # Boutons Pondération / Gérer — orange, texte blanc bold
```

Commentaire du code (`theme.py:5-6`) : « Couleurs des zones sidebar/grille demandées par l'utilisateur
(2026-08-18). Fixes par choix visuel : elles ne suivent pas le thème actif. » — c'est donc une dérogation
**assumée et documentée dans le code lui-même** à la règle zéro-hardcoding / réactivité thème du reste du
monorepo (voir `D:\projets\CLAUDE.md`, sections « Design System » et « theme-reactivity »). Ces 6
constantes sont des couleurs hex littérales, valables quel que soit le thème actif (`blue`, `dark`, `sobre`,
`contrast`).

#### 4.3 Fonctions de style bouton

**`btn_toggle_style(checked: bool, height: int = 22) -> str`** (`theme.py:26-44`) : style QSS pour les
boutons toggle type OUI/NON du grid PEI/DP. Utilise `theme_manager.palette` (donc réactif au thème, à la
différence des `ZONE_*`). Coché → fond `primary_container`, texte `primary`, bordure `primary`, gras.
Décoché → fond transparent, texte `text_strong`, bordure `outline_variant`, avec `:hover` sur
`surface_variant`. Rayon de bordure `ds.radius_xs`. Docstring (28-30) : « Cochés = bleu clair
(primary_container) : consultation. Les actions de gestion (Gérer, Pondération) restent en primary plein. »

**`btn_toggle_style_dark(checked, height=22)`** (`theme.py:47-61`) : variante pour panneau sombre
(sommatives) — même style coché, mais décoché avec texte `on_primary` (clair) et `:hover` en
`rgba(255,255,255,0.15)` au lieu de `surface_variant`, pour rester lisible sur fond sombre.

**`btn_crit_style(checked)`** — exposée uniquement via la méthode du wrapper (`theme.py:123-136`, voir
§4.4), pas en fonction module-level. Style similaire aux toggles, hauteur fixe 22px, padding
`ds.space_xs`, utilisé pour les boutons de sélection de critère (A/B/C/D) dans le top bar.

#### 4.4 `ThemeManagerWrapper` (`theme.py:64-142`)

Classe qui enveloppe le singleton `theme_manager` de `larccommon.theme` (stocké dans `self._original`,
`theme.py:68`) et expose :
- Toutes les propriétés déléguées telles quelles : `palette`, `fonts`, `design`, `theme`, `phi_theme`,
  `active_name`, `image` (`theme.py:70-96`).
- Les méthodes déléguées : `set_active(name)`, `get_palette(name)`, `font_size(base)`,
  `font(base, weight)`, `names()`, `bind(app)` (`theme.py:98-116`).
- Les méthodes spécifiques LarcProf ajoutées par ce shim : `btn_toggle_style`, `btn_toggle_style_dark`
  (délèguent aux fonctions module-level §4.3), `btn_crit_style` (implémentation inline, §4.3), et
  `set_font_multiplier(mult)` (`theme.py:138-139`) qui écrit directement
  `self._original._theme.fonts.multiplier = mult` — accès à un attribut « privé » (`_theme`) de l'objet
  `larccommon.theme.theme_manager`, en dehors de son API publique documentée.

Le module instancie ensuite `theme_manager = ThemeManagerWrapper()` (`theme.py:142`) — **ce nom masque
l'import initial du vrai `theme_manager` de `larccommon.theme`** effectué ligne 22 : à partir de la ligne
142, tout le reste du module (et tout code qui fait `from LarcProf.common.theme import theme_manager`)
reçoit le wrapper, pas l'objet original. `__all__` (`theme.py:143-153`) exporte explicitement
`theme_manager`, `ThemeManager`, `Theme`, `Palette`, `FontScale`, `DesignTokens`, `QssHelper`,
`btn_toggle_style`, `btn_toggle_style_dark` (mais pas `btn_crit_style`, accessible uniquement via
`theme_manager.btn_crit_style(...)`).

---

### 5. `grid_config.py` et `session.py` — appui

#### 5.1 `grid_config.py` (87 lignes)

Charge la configuration visuelle de la grille de notes depuis des fichiers JSON `grid_configs/*.json`
(`grid_config.py:16`, chemin relatif au module : `LarcProf/grid_configs/`). Classe `GridConfig` :
- `student_width`/`min`/`max`, `note_width`/`min`/`max`, `remark_width`/`min`/`max` : dimensions de
  colonnes (`grid_config.py:40-53`).
- `note_on_7_color` / `note_on_7_bold` (55-57) : style visuel de la note finale calculée par
  `CalcEngine.compute_note` (§1) quand elle est affichée sur 7 (PEI).
- `_ranges` (liste de `_GradeRange`, 19-30) : bandes couleur `{min, max, bg, fg, bold}` chargées depuis
  `data['grade_ranges']` du JSON — `color_for(value)` (61-66) retourne le premier `(bg, fg, bold)` dont la
  plage `[min, max]` contient `value` (comparaison `<=` inclusive des deux bornes), ou `('#ffffff',
  '#212121', False)` par défaut si aucune plage ne correspond ou si `value is None`. C'est donc la
  colorimétrie appliquée à la note produite par `_apply_boundaries`/`_compute_dp` dans la grille, distincte
  du calcul lui-même.

`_GridConfigManager` (69-81) : cache singleton par nom de config (`get(name)`), lazy-load depuis le fichier
`grid_configs/{name}.json`. `pei_config` (`grid_config.py:85`) est pré-chargé au niveau module pour
`grid_configs/pei.json` — pas d'équivalent `dp_config` pré-chargé dans ce fichier.

#### 5.2 `session.py` (94 lignes)

« Pont de session LarcProf → larccommon » (`session.py:1-5`). Ré-exporte `UserRole`, `ConnMode`,
`AuthResult`, `Session`, `session` depuis `larccommon.session` sans redéfinition — un seul singleton de
session pour toute l'application (cohérent avec l'intégration LarcHub documentée dans `D:\projets\CLAUDE.md`,
section « État actuel » : « Session unifiée : LarcProf réexporte `larccommon.session` »).

Ajoute deux extensions par monkey-patch sur le singleton/la classe existants :
- **`load_role_flags(self)`** (18-73) : tente d'abord `db.server_conn` (`SELECT type_teacher,
  type_coordonator, type_supervisor, type_secretary, type_director FROM larcauth_aecuser WHERE id = %s`),
  puis retombe sur `db.local_conn` (même requête, syntaxe `?`) si le serveur n'est pas connecté ou échoue.
  Peuple `self.role_flags` avec un dict `{'Professeur': bool, 'Coordinateur': bool, 'Superviseur': bool,
  'Secretaire': bool, 'Directeur': bool}`. Toute exception est absorbée (`report_exception()` + `pass`).
  Attaché au singleton `session` via `session.load_role_flags = MethodType(load_role_flags, session)`
  (`session.py:90`) plutôt que par héritage — modification de l'instance, pas de la classe.
- **`active_role_labels`** / **`role_display`** : propriétés ajoutées à la **classe** `Session`
  elle-même (`Session.active_role_labels = property(...)`, `session.py:93-94`) — donc, contrairement à
  `load_role_flags`, ces deux propriétés seraient visibles sur toute instance de `Session`, pas seulement
  le singleton `session`. `role_display` retourne les libellés de rôles actifs séparés par `' | '`, ou
  `self.role.value` (valeur brute de l'enum `UserRole`) si aucun rôle actif n'est chargé.

Pertinence pour le calcul/sync : `session.user_id` est utilisé directement dans les requêtes de filtrage
serveur de `sync.py` (§3.6, `cts.fk_teacher_id = %s`) et de `apply_resolution`/`apply_push` (audit
`modified_by`). Aucune interaction directe avec `calc_engine.py`.

---

### 6. Synthèse du flux de bout en bout

1. Le prof saisit une note dans la grille PEI/DP (colonne `f{NN}_note_{crit}` / `s{NN}_note_{crit}` /
   `ei_note` / `f{NN}_note` / `s{NN}_note` selon PEI ou DP) → écriture locale SQLite (hors périmètre de ce
   document ; probablement dans les vues, non lues ici).
2. `CalcEngine.compute_note` (§1) relit ces colonnes locales (avec un éventuel `override` pour la saisie
   en cours non committée) et calcule la note finale affichée, sur 7 (PEI, bandes IB) ou sur 20 (DP,
   formule pondérée).
3. `grid_config.pei_config.color_for(note)` (§5.1) détermine la couleur d'affichage de la note calculée.
4. Au déclenchement d'une synchro (clic « Synchroniser », sortie avec enregistrement, etc. — voir
   `D:\projets\CLAUDE.md` section « Sync (LarcProf) »), `sync.pull_push()` (§3.5) parcourt
   `BUSINESS_TABLES`, calcule les diffs cellule par cellule via `compute_cell_diff` (§3.6) contre le
   serveur PostgreSQL filtré par prof + trimestre courant, puis applique `apply_pull`/`apply_push`/accumule
   les conflits pour résolution manuelle (`apply_resolution`, déclenchée ailleurs, hors périmètre lu ici).
5. `touch_sync_state` (§3.8) horodate la dernière synchro réussie par table, dans `sync_state`.

---

### 7. Points d'attention / bugs connus

#### 7.1 [CORRIGÉ AUJOURD'HUI] `session` non importé dans la branche `else` de `compute_cell_diff`

**État actuel du code (déjà corrigé)** : `from common.session import session` se trouve à `sync.py:287`,
**avant** le `if table == 'larcauth_evaluation': ... else: ...` qui commence à `sync.py:288`. L'import est
donc partagé par les deux branches et `session.user_id` est utilisable aux deux endroits (`sync.py:298` et
`sync.py:314`) sans risque de `UnboundLocalError`. Avant cette correction, l'import se trouvait
vraisemblablement seulement dans la branche `if`, provoquant un `UnboundLocalError` sur `session` dès que
`compute_cell_diff` était appelée pour une table autre que `larcauth_evaluation` — soit précisément les
tables PEI/DP (`larcauth_learnerpei_has_termsubjectpei`, `larcauth_learnerdp_has_termsubjectdp`) et les
trois autres tables métier. Documenté ici comme demandé : comportement **actuel** = corrigé, plus
d'`UnboundLocalError`.

#### 7.2 [CORRIGÉ AUJOURD'HUI] `local_conn` non assigné dans `pull_push()`

**État actuel** : `local_conn = db.local_conn` est la toute première instruction du corps de `pull_push()`
(`sync.py:164`), avant même l'initialisation de `report` n'est... — précisément : `report = SyncReport()`
est à la ligne 163, puis `local_conn = db.local_conn` ligne 164, avant le `if local_conn is None` (165) et
avant le `try` des garde-fous (169). `local_conn` est donc garanti défini pour tout usage ultérieur dans la
fonction (boucle `for table in BUSINESS_TABLES`, `local_conn.commit()` ligne 211). Avant cette correction,
`local_conn` n'était probablement assigné qu'à l'intérieur d'une branche conditionnelle plus tardive,
provoquant un risque de référence à une variable non définie si le flux atteignait la boucle sans être
passé par cette assignation.

#### 7.3 [NON CORRIGÉ] `apply_push` suppose une colonne littérale `id` côté serveur PostgreSQL — bug confirmé en conditions réelles

**Code en cause** : `sync.py:442-445`
```python
cur.execute(
    f'UPDATE public."{table}" SET "{col}" = %s WHERE id = %s',
    (val, row_id)
)
```

Ce code suppose que **toute** table de `BUSINESS_TABLES` a, côté serveur PostgreSQL, une colonne littérale
`id` utilisable comme clé de mise à jour. Or, d'après le schéma SQLite local reconstruit dynamiquement
depuis les colonnes serveur (`LarcProf/common/sqlite_init.py`, voir ci-dessous), au moins
`larcauth_learnerpei_has_termsubjectpei` utilise le pattern d'héritage multi-table Django (« Django MTI ») :
sa clé primaire réelle côté serveur est `learner_has_termsubject_ptr_id`, **pas** `id`.

Preuve indirecte dans le code lu :
- `sqlite_init.py:769-782` (`_create_table_from_data`) :
  ```python
  has_id = any(col.lower() == 'id' for col in columns)
  if has_id:
      sql = f'CREATE TABLE "{table_name}" ({col_defs})'
  else:
      sql = f'CREATE TABLE "{table_name}" (id INTEGER PRIMARY KEY, {col_defs})'
  ```
  `columns` provient directement de `pei_cols` (`sqlite_init.py:625`, extrait des colonnes réellement
  renvoyées par `SELECT pei.*, lht.fk_student_id FROM public.larcauth_learnerpei_has_termsubjectpei pei
  JOIN ...` — `sqlite_init.py:610-625`). Le fait que ce code prévoie explicitement le cas `has_id = False`
  et **injecte alors un `id INTEGER PRIMARY KEY` auto-incrémenté purement local**, confirme que ce cas se
  produit réellement pour au moins une des tables métier — cohérent avec l'erreur observée en log
  applicatif réel citée dans la demande : `ERREUR: la colonne « id » n'existe pas` lors d'un push.
- Le même mécanisme (`_create_table_from_data` avec la même détection `has_id`) est appliqué de façon
  identique à `larcauth_learnerdp_has_termsubjectdp` (`sqlite_init.py:704` / `dp_cols` extrait de
  `dp.*` à `sqlite_init.py:627-642`, structure de requête rigoureusement symétrique à celle de PEI, même
  jointure sur `learner_has_termsubject_ptr_id`). Il est donc **très probable** que
  `larcauth_learnerdp_has_termsubjectdp` souffre du même défaut de colonne `id`. **Je n'ai pas pu vérifier
  ce point directement contre le schéma PostgreSQL réel** : une tentative de connexion au serveur intranet
  (`127.0.0.1:5432`, `NewLarcDB`) depuis cette session a échoué (erreur d'authentification renvoyée par le
  serveur, elle-même mal décodée par le driver psycopg2 côté client — `UnicodeDecodeError` avant même
  d'atteindre le message d'erreur PostgreSQL). Cette confirmation pour la table DP reste donc **une
  inférence par symétrie de code, pas une vérification directe**.

**Conséquence concrète** : quand `apply_push` traite une cellule de `larcauth_learnerpei_has_termsubjectpei`
(et vraisemblablement `larcauth_learnerdp_has_termsubjectdp`), le `row_id` utilisé (`diff.row_id`, dérivé de
la colonne `id` **locale**, qui est un entier auto-incrémenté SQLite sans rapport avec la table serveur)
est passé tel quel dans `UPDATE public."{table}" SET "{col}" = %s WHERE id = %s` côté PostgreSQL — la
colonne `id` n'existant pas sur cette table serveur, PostgreSQL renvoie l'erreur `la colonne « id » n'existe
pas`, confirmée en conditions réelles. Le push échoue systématiquement pour ces deux tables (ou au moins
pour PEI, confirmé).

**Ce document ne corrige pas ce bug** — il est signalé tel quel, comme demandé, en tant que défaut
architectural non résolu à date.

#### 7.4 [NON CORRIGÉ] `apply_resolution` incohérent avec `apply_push` sur le contexte d'audit

`apply_resolution` (`sync.py:493-504`) utilise, sous connexion `autocommit=True`
(`LarcProf/common/database.py:103`, `self._intranet.autocommit = True`) :
```python
cur.execute(f"SET LOCAL app.sync_source = '{source}'")
from common.session import session
cur.execute(f"SET LOCAL app.modified_by = {int(session.user_id or 0)}")
```
alors que `apply_push` (`sync.py:438-441`) utilise correctement :
```python
from larccommon.audit_context import attach, refresh
refresh()
attach(server_conn)
```
qui exécute des `SELECT set_config('app.xxx', valeur, false)` — le troisième argument `false` de
`set_config` signifie explicitement « portée session, pas seulement transaction » (voir
`LarcCommon/larccommon/audit_context.py:31-48`), ce qui fonctionne correctement même quand chaque
instruction SQL est sa propre transaction implicite (`autocommit=True`).

`SET LOCAL`, par contraste, ne s'applique qu'à la transaction en cours — sous `autocommit=True`, chaque
instruction (y compris le `SET LOCAL` lui-même) constitue sa propre transaction distincte qui se termine
immédiatement après son exécution. Le `SET LOCAL app.sync_source = ...` exécuté à la ligne 498 n'a donc
**plus aucun effet observable** au moment où l'`UPDATE` s'exécute à la ligne 502 (transaction différente) —
c'est un **no-op silencieux** : ni erreur, ni effet.

De plus, ces deux `SET LOCAL` sont construits par **f-string directement interpolées** dans la requête SQL
(`f"SET LOCAL app.sync_source = '{source}'"`, `f"SET LOCAL app.modified_by = {int(session.user_id or 0)}"`)
plutôt que paramétrées via `%s`. `source` provient d'un `if/else` interne fermé (`'intranet'`/`'cloud'`,
`sync.py:497`) et `session.user_id` est casté en `int(...)`, ce qui limite le risque d'injection SQL dans
ce cas précis — mais le pattern diffère de celui, paramétré, utilisé partout ailleurs dans le fichier
(`%s` avec tuple de paramètres), et de `audit_context.attach()` qui passe ses valeurs en paramètres liés
(`cur.execute("SELECT set_config('app.modified_by', %s, false)", (str(_user_id or ''),))`,
`audit_context.py:37-38`).

**Conséquence fonctionnelle** : lors d'une résolution de conflit qui pousse la valeur locale vers le
serveur (`keep == 'local'`), le contexte d'audit (`app.sync_source`, `app.modified_by`) n'est **pas**
effectivement posé sur la connexion avant l'`UPDATE` — contrairement à un push normal via `apply_push`, où
le contexte est correctement posé. Si des triggers PostgreSQL côté serveur dépendent de ces variables de
session pour journaliser qui a fait la modification (`audit_log`, mentionné dans
`D:\projets\CLAUDE.md` section Télémétrie), les résolutions de conflit échapperaient à cette traçabilité —
non vérifié ici faute d'avoir lu le code des triggers serveur, qui est hors périmètre de cette
documentation.

#### 7.5 [Observation, non demandée explicitement mais repérée en lisant `calc_engine.py`] Template DP « simple » sans implémentation dédiée

Voir §1.4. `get_templates_dp()["simple"]` déclare `conversion.method = "simple_avg"`, mais `_compute_dp`
(`calc_engine.py:277-325`) ne lit jamais `conv.get("method")` — il applique inconditionnellement
`ei_val*ei_c + f_mean*f_c + s_mean*s_c` avec les coefficients trouvés (ou les défauts 0.125/1.125/0.75 si
absents, ce qui est le cas pour le template `"simple"` qui ne définit aucun des trois coefficients). Le
gabarit `"simple"` produit donc, à ce jour, un résultat **identique** au gabarit `"standard"` malgré son
nom. Ce n'est pas un crash ni une erreur visible — juste une fonctionnalité annoncée (moyenne simple) qui
n'a pas de branche de calcul correspondante dans le moteur.

#### 7.6 [Observation] `total_w` calculé mais non utilisé comme diviseur en PEI

Voir §1.8 étape 2. `_compute_pei` calcule `total_w = wf + ws` et l'utilise uniquement comme garde-fou
(`if total_w == 0: return None`), pas comme diviseur de la moyenne pondérée `f_mean*wf + s_mean*ws`
(`calc_engine.py:227`). Si une formule custom enregistre des poids dont la somme n'est pas 1 (ex.
`formative_weight=0.4, summative_weight=0.5`), la moyenne pondérée par critère ne sera pas normalisée —
comportement réel du code, à garder à l'esprit pour quiconque construirait un éditeur de formule côté UI
qui laisserait saisir des poids arbitraires.

#### 7.7 [Observation] Filtre `v > 0` en DP confond « case vide » et « note 0 réelle »

Voir §1.10. Dans `_compute_dp`, `_read()` renvoie `0.0` pour une colonne NULL comme pour une colonne
contenant réellement `0`. Le filtre `if v > 0` (`calc_engine.py:312` et son équivalent pour les
sommatives) exclut les deux cas de façon identique de la moyenne — une vraie note de 0/20 attribuée à un
élève n'est donc **pas comptée** dans `f_mean`/`s_mean`, au même titre qu'une évaluation non encore notée.
Comportement réel du code, non commenté comme intentionnel dans le fichier.

#### 7.8 [Observation] `get_formula` peut retourner l'objet module-level partagé (pas une copie) si `db.local_conn is None`

Voir §1.6. `calc_engine.py:85-86` : `if conn is None: return _DEFAULT_PEI` — retourne directement la
référence au dict module-level `_DEFAULT_PEI`, sans `dict(...)`. Tous les autres chemins de retour de
`get_formula` font `dict(_DEFAULT_DP)` / `dict(_DEFAULT_PEI)` (copies) ou `json.loads(...)` (nouvel objet).
Aucun appelant lu dans ce périmètre ne mute la formule retournée, donc pas d'impact observé à ce jour —
signalé par prudence pour tout futur code qui muterait le dict reçu de `get_formula()` en pensant obtenir
une copie isolée.

#### 7.9 Rappel — tentative de vérification live du schéma serveur, non concluante

Une tentative a été faite dans le cadre de la rédaction de ce document pour confirmer indépendamment
l'absence de colonne `id` sur `larcauth_learnerdp_has_termsubjectdp` côté PostgreSQL (intranet
`127.0.0.1:5432`, base `NewLarcDB`), afin de trancher le « à vérifier si tu peux » de la demande. La
connexion via `psycopg2` (depuis l'environnement virtuel `D:\projets\.venv`) a échoué avec une
`UnicodeDecodeError` avant même de renvoyer un message d'erreur PostgreSQL exploitable (vraisemblablement
un message d'échec d'authentification renvoyé par le serveur dans un encodage que le driver n'a pas su
décoder en UTF-8). Aucune donnée n'a été lue ni modifiée. Le point 7.3 reste donc, pour la table DP
spécifiquement, une inférence par symétrie de code et non une vérification directe du schéma serveur.

---

### Sources consultées

- `D:\projets\LarcProf\common\calc_engine.py` (lu intégralement, 360 lignes)
- `D:\projets\LarcProf\common\eval_helpers.py` (lu intégralement, 40 lignes)
- `D:\projets\LarcProf\common\sync.py` (lu intégralement, 578 lignes)
- `D:\projets\LarcProf\common\theme.py` (lu intégralement, 153 lignes)
- `D:\projets\LarcProf\common\grid_config.py` (lu intégralement, 87 lignes)
- `D:\projets\LarcProf\common\session.py` (lu intégralement, 94 lignes)
- `D:\projets\LarcProf\common\sqlite_init.py` (extraits ciblés : lignes 140-180, 338-350, 595-720, 750-817)
- `D:\projets\LarcProf\common\database.py` (extraits ciblés : lignes 30-115, 190-223)
- `D:\projets\LarcCommon\larccommon\audit_context.py` (extraits ciblés : lignes 12-56)
