# eLarcProfPy — Contexte projet

_Dernière mise à jour : 23 juin 2026_

## Règle importante — Décisions avant actions
Quand je demande "qu'est-ce que tu penses ?" à propos d'une approche ou d'une solution,
**ne rien modifier ni implémenter** avant d'avoir donné mon avis et confirmé la décision.
D'abord répondre avec l'analyse/avis, puis attendre mon accord avant d'exécuter.

## Décision technique
Version **Python/PySide6** retenue pour le desktop. Elle remplace la version Delphi (eLarcProf)
qui a été abandonnée à cause d'erreurs de compilation FireDAC récurrentes.
**Pas PyQt5, pas PyQt6, pas Flet** — PySide6 uniquement.
Mobile/tablette = phase ultérieure (FastAPI + Flutter ou PWA).

## Environnement
- Python 3.x + PySide6 (Qt6)
- Venv : `.venv/` dans le répertoire du projet
- Dépendances : `pip install -r requirements.txt`
- Lancement : `python main.py`
- OS cible : Windows desktop

## Bases de données
| Source | Technologie | Usage |
|---|---|---|
| Intranet | PostgreSQL `192.168.2.90:5432/LMarcIntranet` | Données en ligne réseau local |
| Cloud | Supabase PostgreSQL (PgBouncer port 6543) | Données en ligne internet |
| Device | SQLite `elarc.db` | Projection locale scopée prof |

Config dans `config.ini` (jamais commité — voir `.gitignore`).
Même structure que `D:\Projets\eLarcProf\config.ini` sur la machine de dev.

## Architecture fichiers
```
eLarcProfPy/
├── main.py                 # QApplication + LoginWindow + modes CLI
├── common/
│   ├── network.py          # detect_network() → INTRANET/INTERNET/OFFLINE
│   ├── session.py          # UserRole, ConnMode, AuthResult, Session, session (global)
│   ├── database.py         # Database class, db (global singleton)
│   ├── auth.py             # AuthManager + OAuth2Manager (PKCE Google)
│   ├── sqlite_init.py      # SQLiteInit, DDL, save_session, curseurs sync
│   ├── sync.py             # SyncManager (diff shadow-table device ↔ serveur)
│   ├── theme.py            # ThemeManager (palette + font scaling)
│   ├── grid_config.py      # GridConfig loader (grid_configs/*.json)
│   └── logger.py           # log() vers elarc.log + bascule LOG_TO_FILE
├── views/
│   ├── login.py            # LoginWindow — 4 onglets auth + workers QThread
│   ├── password.py         # ChangePinDialog + ChangePasswordDialog
│   ├── main_window.py      # MainWindow — espace de travail prof (top bar + grille)
│   ├── evaluation_panel.py # (obsolète, remplacé par la top bar)
│   └── eval_manager.py     # _SlotBar, EvalManagerWindow
├── grid_configs/
│   └── pei.json            # Configuration grille PEI (couleurs, largeurs)
├── LarcCloudSync/          # Daemon de sync Intranet ↔ Cloud (projet séparé)
│   ├── sync_agent/         # Agent Python (boucle, diff, push/pull)
│   ├── sql/                # Scripts SQL (colonnes sync + triggers)
│   └── config.json          # Fréquences de sync par table
├── export_to_sqlite.py     # Export PostgreSQL → SQLite (utilitaire)
└── docs/                   # Documentation algorithmique numérotée
```

### Modes CLI de `main.py`
- `python main.py` — lance normalement la fenêtre de connexion.
- `python main.py --mode4 [email]` — crée une instance prof depuis l'Intranet en ligne de commande (auth, init SQLite, `init_module_config`, `take_teacher_data`, save session).
- `python main.py --test-create-db` — initialise une base SQLite temporaire et vérifie les tables via `sqlite_init.verify_tables()`.

## Rôles utilisateurs
| Rôle | Accès |
|---|---|
| PROF | Ses classes, ses notes, son emploi du temps |
| COORD | Tout + coordination pédagogique |
| SECR | Administratif, inscriptions |
| ADMIN | Tout sans restriction |

## Phase 1 — TERMINÉE
Écran de connexion `views/login.py` avec 4 modes :
1. **Intranet** — email + mot de passe → `larcauth_aecuser` (hash SHA-256 champ `password`)
2. **Cloud** — OAuth2 PKCE Google `@arc-en-ciel.org` → loopback HTTP port 8765
3. **PIN** — email + PIN → SQLite `session_cache` (hash SHA-256)
4. **Nouvelle instance** — copie le projet dans un nouveau dossier + `lancer.bat`

Changement de credentials via `views/password.py` :
- `ChangePinDialog` — bouton dans l'onglet Hors connexion (PIN 4-8 chiffres, hash SHA-256).
- `ChangePasswordDialog` — bouton dans l'onglet Intranet.

Après auth réussie : popup "Phase 2 à implémenter" (placeholder tableau de bord).

## Changements récents (13 mai 2026)

### 1. Boutons "Changer le mot de passe" et "Changer le code PIN"
- Ajout d'un bouton "Changer le mot de passe" dans l'onglet Intranet.
- Ajout d'un bouton "Changer le code PIN" dans l'onglet Hors connexion.
- Ajustement de la taille des boutons pour correspondre aux boutons de connexion.

### 2. Suppression du bouton "Changer le mot de passe" de la barre d'état
- Le bouton était dans la barre d'état en bas ; il a été supprimé car remplacé par le bouton dans l'onglet Intranet.

### 3. Indicateur d'état en bas
- Remplacement des deux indicateurs "Présence intranet ●" et "Présence cloud ●" par un seul indicateur large centré en bas.
- L'indicateur affiche l'un des 4 états :
  - 0 : "Module eLarcProf non instanciée" (feu noir)
  - 1 : "Module eLarcProf de Nom et prénom du prof Non Connecté" (feu noir)
  - 2 : "Module eLarcProf de Nom et prénom du prof Connecté à l'Intranet" (feu vert)
  - 3 : "Module eLarcProf de Nom et prénom du prof connecté au Cloud" (feu vert)
- Les deux indicateurs "Présence intranet ●" et "Présence cloud ●" ont été remis en haut à côté du titre.

### 4. Correction de l'authentification Intranet
- Remplacement de `UserRole.TEACHER` par `UserRole.PROF` (car `TEACHER` n'existe pas).
- Suppression de la colonne `enabled` dans les requêtes (car elle n'existe pas).
- Utilisation des colonnes correctes : `is_adm`, `is_coordonator`, `is_secretary`.
- Vérification du hash du mot de passe stocké (colonne `password`) au lieu de comparer avec `'Aec-2026'`.

### 5. Base de données unique `elarc.db`
- Suppression de `SQLiteDB.db` (plus utilisé).
- `elarc.db` est créée directement avec les tables métiers (`larcauth_evaluation`, `larcauth_learnerpei_has_termsubjectpei`, `larcauth_learnerdp_has_termsubjectdp`) et les tables locales (`session_cache`, `sync_cursor`, `module_config`).
- `export_to_sqlite.py` exporte maintenant vers `elarc.db` (au lieu de `SQLiteDB.db`).
- `sqlite_init.init()` crée `elarc.db` vide puis exécute `_DDL` pour créer les tables.

### 6. Téléchargement des données du professeur
- `take_teacher_data` accepte maintenant `infos` (dict) au lieu de `user_id` et `term_id`.
- Les tables métiers sont vidées avant d'être remplies.
- La connexion serveur est vérifiée avant le téléchargement.
- `_on_auth_done` appelle `sqlite_init.init()` avant `init_module_config()`.

### 7. Création d'instance
- `elarc.db` est copié dans le dossier de destination lors de la création d'une nouvelle instance.

### 8. Validation du PIN
- La validation du PIN vérifie maintenant `len(new_pin) > 8` (max 8 chiffres).

## Phase 2 — EN COURS

Top bar refactorée (4 sections toujours visibles), grille élèves × notes fonctionnelle avec données réelles, édition par double-clic et sauvegarde.

Fonctionnel :
- Connexion Intranet (SHA-256 password) → MainWindow
- Top bar sections : **Matière-Classe** (combos), **Formatives** (liste scrollable slots actifs seuls), **Sommatives** (idem), **Jugements** (boutons toggles Jgt/Note/Commentaire + critères A/B/C/D)
- Slots inactifs masqués ; seuls les actifs (≥1 critère coché) apparaissent dans la top bar
- Clic sur un slot dans la top bar → bascule sa colonne dans la grille
- Grille élèves × notes : colonnes dynamiques selon slots visibles + critères + jugements
- Édition par double-clic dans la grille → `_on_cell_changed` marque la cellule comme modifiée
- Sauvegarde : `_save_grid_edits()` écrit les cellules modifiées dans SQLite (`UPDATE ... WHERE id = pei_row_id`)
- Sync + "Enregistrer et quitter" sauvegardent la grille avant de synchro/fermeture
- EvalManagerWindow : création, _load_data, sauvegarde critères, slot progressif
- Migration automatique des colonnes manquantes (source, sync_version, etc.) à l'init SQLite
- `take_teacher_data` contourné pour le login normal (réservé au --mode4)

Données connues :
- Prof 1021 (Patrice LABONNE), trimestre 3 : 31 CTS, 189 évaluations, **0 critères cochés**
- Toutes les colonnes `crit_a..crit_d` = `'0'` → aucune évaluation active affichée
- Les évals avec critères cochés sont sur les trimestres 1-2 uniquement
- C'est un problème de données serveur, pas un bug applicatif

Prochaines étapes :
1. Grille F/S inactive sur données T3 (serveur) — contourner avec jeu de test
2. Validation des notes échelle 0-8 (PEI) / 0-20 (DP)
3. Dashboard par rôle : PROF, COORD, SECR, ADMIN
4. Test sur données réelles T1/T2

---

## Changements récents (25 mai 2026)

### 1. Panneaux F/S avec slots cliquables
- Création de `views/evaluation_panel.py` avec `EvaluationPanel`, `_SlotButton`, `EvaluationDetailDialog`.
- Grille 4×3 de slots F01-F12 / S01-S12.
- Barre d'indicateurs en haut (vert si actif, gris si inactif).
- Clic sur un slot ouvre `EvaluationDetailDialog` avec label, nature, source, critères A/B/C/D + aspects.
- Sauvegarde immédiate en SQLite (`UPDATE larcauth_evaluation`).

### 2. Layout compact et titres liés au contenu
- Suppression des `QSplitter` (vertical et horizontal). Layout à hauteur fixe.
- Chaque panneau est un `QFrame` borduré avec titre intégré.
- Police Roboto 8-10px, interligne 0, marges minimales.
- Couleurs inactifs lisibles (#555, #777 au lieu de #bbb).

### 3. Documentation mise à jour
- `docs/16_main_window.md` réécrite.
- `docs/historique_construction.md` : itérations 12 et 13.
- `CONTEXT.md` : architecture fichiers, progression, changements récents.

---

## Changements récents (27 mai 2026)

### 1. `views/eval_manager.py` — Fenêtre de gestion des évaluations
- Nouveau fichier avec `EvalManagerWindow` (non-modal, splitter horizontal)
- `_SlotBar` : barre horizontale `[F01] | Nature (72 chars max) | ☐A ☐B ☐C ☐D`
- Tabs F01-F12 en haut du panneau gauche, cliquables
- Légende des critères chargée depuis `larcauth_criteria_of_levelsubject`

### 2. Affichage progressif des slots
- Seuls les slots **actifs** + le premier slot inactif ("suivant") sont visibles
- Les autres slots inactifs sont masqués
- Quand le prof active un slot (critère coché + sauvegarde), le suivant apparaît grisé

### 3. Éditeur Markdown + barre d'outils + correcteur orthographique
- Source : `QTextEdit` avec `setMarkdown()`/`toMarkdown()` au lieu de `QPlainTextEdit`
- Barre d'outils : **B** (gras), *I* (italique), **H** (titre), **•** (liste), **🔗** (lien)
- `_SpellHighlighter` : `QSyntaxHighlighter` utilisant `pyenchant` (si installé) pour surligner les mots mal orthographiés en rouge

### 4. Grille critères 4×2
- Remplace les 4 frames verticales par un `QGridLayout` 4 colonnes × 2 lignes :
  ```
  ☐A          ☑B          ☐C          ☑D
  Recherche   Développement  Création    Évaluation
  et analyse  des idées      de la solution
  ```
- Les `\n` dans les labels critères sont nettoyés

### 5. Label en lecture seule
- "Label" passe de `QLineEdit` → `QLabel` (non modifiable)
- `get_form_data()` ne renvoie plus `label`, la sauvegarde conserve la valeur

### 6. Architecture
```
┌────────────────────────────────────────────────────────────────┐
│  Gestion des Formatives — Design - PEI-1 (900×600 min)        │
├──────────────────────────┬─────────────────────────────────────┤
│ [F01][F02][F03]... tabs  │  F03 — Détails                      │
│                          │                                     │
│ A: Rech. | B: Dév. ...   │  Label : (lecture seule)            │
│                          │  Nature : [_______]                  │
│ ┌──────────────────────┐ │  Source : [B I H • 🔗]             │
│ │ F01 | Titre... ☑A☐B  │ │  ┌─────────────────────────────┐   │
│ │ F02 | Titre... ☑A☑B  │ │  │ Markdown éditable (stretch) │   │
│ │ F03 | Titre... ☐A☐B  │ │  └─────────────────────────────┘   │
│ │ (actifs + suivante)   │ │  ☐A  ☑B  ☐C  ☑D                  │
│ └──────────────────────┘ │  Rech. Dév. Créa. Éval.             │
│                          │  [Enregistrer ce slot]               │
├──────────────────────────┴─────────────────────────────────────┤
│  QSplitter (400/500)                                            │
└────────────────────────────────────────────────────────────────┘
```

### 7. Nouveaux fichiers de documentation
- `docs/20_eval_manager.md` — documentation de `EvalManagerWindow` et `_SlotBar`
- `docs/historique_construction.md` — itérations 14, 15, 16

---

## ARCHITECTURE BASE DE DONNÉES DEVICE — DÉCISIONS STRATÉGIQUES

### Philosophie "Gabarit" (fondamentale — ne pas oublier)
La base PostgreSQL intranet fonctionne sur ce principe depuis **10 ans**.
**On ne crée rien, on ne détruit rien.** Tous les éléments existent dans la base
sous forme de slots pré-alloués. L'activation se fait exclusivement par des **booléens**.

```sql
-- Jamais :  INSERT  ou  DELETE
-- Toujours : UPDATE ... SET enabled = TRUE/FALSE
--            UPDATE ... SET valeur = x, enabled = TRUE
```

Le SQLite device est une **projection filtrée** de ce gabarit PostgreSQL.
Même philosophie, même structure, moins de tables, scopé au prof.

> Les capacités maximales du gabarit (nb de classes, d'élèves, de matières, d'évals, etc.) ne concernent **pas** l'IHM ni le code applicatif : les slots existent déjà côté base, et l'utilisateur perçoit ces limites naturellement à travers l'interface (slots vides = désactivés). Ne pas coder de constantes de dimensionnement.

### Conséquence sur la sync
Le daemon de sync n'a jamais à vérifier si une ligne existe côté device —
elle existe toujours. La sync ne fait que des **UPDATE**. Aucun conflit possible.

### Système de notation
| Niveau | Périmètre | Échelle | Détail |
|---|---|---|---|
| Collège (PEI) | par critère | 0–8 | **4 critères** affichés (a, b, c, d) — colonne `note_on_7` pour la synthèse |
| Collège (PEI) | synthèse trimestre/matière | 0–7 | 1 note finale par matière par trimestre (`note_on_7`) |
| Lycée (DP) | note directe | 0–20 | `moy_on_20`, `cc_on_20`, `bacblanc`, `bacblanc2` — en plus du système critères |

### Évaluations par trimestre
- **12 formatives** + **12 sommatives** par matière par trimestre exposées à l'IHM — règle métier (≈ 1/semaine sur 12 semaines).
- Les 12 slots sont toujours rendus dans l'IHM ; les lignes sans critère coché sont grisées/inactives.

### Décalage base ⟷ IHM v1 (à connaître absolument)
Le schéma serveur a une capacité supérieure à ce que l'IHM v1 expose. Ces "extras" sont **réservés en base** pour des usages futurs, sans modification de schéma :

| Sujet | Base | IHM v1 | Réserve pour |
|---|---|---|---|
| Critères par évaluation | 6 colonnes (`crit_a..crit_e`, `crit_F`) | 4 (a, b, c, d) | Évolutions du logiciel (v2+), pas de migration DDL |
| Slots formatives / sommatives | 15 (`f01..f15`, `s01..s15`) | 12 (`f01..f12`, `s01..s12`) | Calculs statistiques récurrents (moyennes, etc.) |
| Aspects par critère | 7 (`aspect_a1..a7`, …) | 0 | Version 2 — "éléments de contenu" des critères |

**Convention de nommage des colonnes notes** (côté `larcauth_learnerpei_has_termsubjectpei` et `larcauth_learnerdp_has_termsubjectdp`) :

```
formatives :  f01_note_a, f01_note_b, f01_note_c, f01_note_d   (a..d uniquement en v1)
              f02_note_a … f12_note_d
sommatives :  s01_note_a … s12_note_d
synthèse    :  note_on_7 (PEI)  ou  moy_on_20 (DP)
observation :  fXX_observation, sXX_observation, cp_observation, term_observation
jugement    :  jgt_a..jgt_d
```

### Particularités à connaître
- **Bug schéma serveur** : la colonne `S09_note_f` est en majuscule (vs `s09_note_f` attendu). Non corrigée car l'attribut n'est pas encore utilisé. À ignorer pour l'IHM v1 (n'expose pas `_f`).
- **`crit_F`** : également en majuscule isolée. Même statut — non exposé en v1, donc sans impact.

### Architecture SQLite device (2 niveaux)
```
Niveau 1 — Structure (gabarit pur, pré-alloué)
  classes, élèves-slots, matières-slots, éval-slots
  → toujours présent, activé/désactivé par boolean

Niveau 2 — Notes (générées à l'activation d'une éval)
  quand eval.enabled passe à TRUE
  → génération automatique des lignes notes pour chaque élève actif
  → ensuite uniquement des UPDATE, jamais INSERT/DELETE
```

### Queries statiques
Les requêtes SQL ne changent jamais. Seules les données changent.
C'est le principe fondamental : **schéma fixe → queries fixes → seules les valeurs varient**.

---

## Architecture de synchronisation device ↔ serveur

### Pattern shadow-table (tables `_ref`)
Chaque table métier du device a une **jumelle `_ref`** au schéma identique :

| Table de travail | Table de référence |
|---|---|
| `larcauth_evaluation` | `larcauth_evaluation_ref` |
| `larcauth_learnerpei_has_termsubjectpei` | `larcauth_learnerpei_has_termsubjectpei_ref` |
| `larcauth_learnerdp_has_termsubjectdp` | `larcauth_learnerdp_has_termsubjectdp_ref` |

- **Table de travail** = état local courant, modifié par les saisies du prof.
- **Table `_ref`** = snapshot du dernier état serveur connu (acté à la dernière synchro réussie).
- Au seed (`take_teacher_data`), les deux tables sont peuplées avec les mêmes données serveur.

### Diff au niveau cellule
Les lignes existent toujours des deux côtés (gabarit pré-alloué) → aucun INSERT/DELETE à détecter. Le diff est **cellule par cellule** : jointure par `id`, comparaison colonne par colonne.

### Matrice de décision (par cellule, à la synchro)
| local vs ref | serveur vs ref | Action |
|---|---|---|
| = | = | rien à faire |
| = | ≠ | **pull** : `local = serveur`, `ref = serveur` |
| ≠ | = | **push** : `serveur = local`, `ref = local` |
| ≠ | ≠ | **conflit** → IHM de résolution |

### Scope de la synchro
- **Trimestre courant uniquement** : `WHERE term_id = module_config.trimestre_courant`.
- **Trimestres passés figés** : aucune modification ni synchro acceptée — règle business stricte. Les cellules des trimestres antérieurs sont read-only dans l'IHM (grisées) et ignorées par le diff.

### Déclencheurs de la synchro
La synchro **n'est jamais automatique au démarrage**. Elle se déclenche uniquement :
1. À la **création de l'instance** (mode 4) — seed initial : `local = ref = serveur`.
2. Sur **clic explicite "Connecter"** dans l'onglet Intranet ou Cloud (puis flux de synchro).
3. Sur **clic "Synchroniser"** depuis le tableau de bord (Phase 2).
4. À la **sortie avec enregistrement** (Phase 2).

Au démarrage, on **teste seulement la présence** réseau (intranet / internet) pour mettre à jour les indicateurs visuels — on ne se connecte pas.

### Conflits (cas 4 de la matrice)
- Rares en pratique (saisie simultanée prof / coord sur la même cellule).
- Possibles **uniquement sur le trimestre en cours**.
- Présentés via une IHM dédiée (Phase 2) qui liste les cellules en conflit et permet au prof de trancher cellule par cellule.

### État de synchro par table — table `sync_state`
```sql
CREATE TABLE sync_state (
    table_name  TEXT PRIMARY KEY,   -- nom de la table métier (sans suffixe _ref)
    last_sync   TEXT,               -- ISO 8601 ; NULL = jamais synchro
    last_source TEXT                -- 'intranet' ou 'cloud' (diagnostic)
);
```
Un timestamp par table, mis à jour à la fin de chaque synchro réussie pour cette table.

### Le daemon serveur n'est pas concerné
Toute cette logique vit côté device. Le daemon Python qui synchronise intranet ↔ cloud continue son boulot sans modification — il ne sait rien des tables `_ref` ni du diff cellule local.

---

## Règles métier importantes
- **Ne jamais DELETE** — désactivation logique via `enabled = FALSE`
- **Trimestres passés en lecture seule** — la synchro ne touche que `term_id = trimestre_courant`
- **Démarrage = test de présence réseau seulement**, pas de connexion auto
- Le daemon Python de sync intranet ↔ cloud tourne séparément — projet `LarcCloudSync/`
- Schéma PostgreSQL de référence : `D:\Projets\eLarcProf\Data\LarcNewCloud.sql`
- Tables clés auth : `larcauth_aecuser`, `larcauth_teachadm`, `larcib_term`

## Synchronisation — Nouveau système (3 juin 2026)

Chaque table métier a :
- `sync_version INT DEFAULT 0` — version incrémentée à chaque UPDATE
- `sync_listeMAJ JSONB DEFAULT '[]'::jsonb` — historique des 50 dernières modifs

Trigger `track_sync_update()` (BEFORE UPDATE) :
- Calcule les colonnes modifiées (diff NEW vs OLD)
- Incrémente `sync_version`
- Ajoute `{v, user, at, src, fields}` dans `sync_listeMAJ`
- Limite à 50 entrées (archivage)

Daemon `LarcCloudSync` :
- Compare `sync_version` entre Intranet et Cloud
- Celui avec la version la plus élevée est source → destination
- Lecture par niveau de table (config `config.json`) : N0=1min, N1=5min, N2=1h, N3=1j

## Changements récents (1er juin 2026)

### 1. Content widget — combo toujours visible
- Le combo matière-classe reste visible en haut en permanence.
- Le reste du workspace (panneaux F/S, filtres, grille, actions) est encapsulé dans un `_content_widget` caché tant qu'aucune matière-classe n'est sélectionnée.
- `_on_item_selected` montre/cache le `_content_widget`.

### 2. `take_teacher_data` contourné pour le login normal
- Dans `views/login.py`, l'appel à `take_teacher_data` est supprimé pour les connexions Intranet et Cloud.
- Réservé uniquement au `--mode4` (création d'instance) et à la confirmation PIN opt-in.
- Évite le wipe des données locales à chaque connexion.

### 3. Placeholder "Aucune évaluation active" dans les panneaux
- `EvaluationPanel._empty_placeholder` : label affiché quand aucun slot n'est actif (aucun critère coché).
- `_update_layout()` bascule entre la grille de slots et le placeholder.

### 4. Dead code supprimé dans `eval_manager.py`
- 3 définitions `statusBar` en double supprimées.
- Code `QLabel(...)` orphelin après `setCentralWidget` retiré.

### 5. Migration automatique des colonnes manquantes
- `sqlite_init._migrate_columns()` : ajoute `ALTER TABLE ADD COLUMN` pour les colonnes ajoutées après la création initiale de la base.
- Colonnes migrées : `sync_version`, `synced_at`, `synced_by`, `last_modified_at`, `sync_revision`, `source` sur `larcauth_evaluation` et `larcauth_evaluation_ref`.

### 6. Bug Gérer boutons
- Cause : requête SQL `SELECT source` sur `larcauth_evaluation` → colonne manquante dans l'ancienne base SQLite.
- L'exception dans `load_evaluations` appelait `clear_panel()` qui reset `_termsubject_id = None`.
- Gérer voyait `_termsubject_id = None` et abortait.
- Fix : migration DDL automatique + try/except avec affichage d'erreur.

### 7. Diagnostic données serveur
- Prof 1021 (Patrice LABONNE), trimestre 3 : 31 CTS, 189 évaluations, **0 critères cochés**.
- Toutes les colonnes `crit_a..crit_d` = `'0'` → aucune évaluation active.
- Les 57 évals avec critères cochés sont sur les trimestres 1-2 uniquement.

## Changements récents (2 juin 2026)

### 1. Top bar refactorée — liste scrollable des slots actifs
- Suppression des panneaux `EvaluationPanel` (grille 4×3 de slots).
- Nouvelle top bar 4 sections : **Matière-Classe** (210px), **Formatives** (stretch), **Sommatives** (stretch), **Jugements** (170px).
- Chaque section F/S est une `QScrollArea` qui n'affiche **que les slots actifs** (≥1 critère).
- Les slots inactifs sont invisibles — plus de grise ni de placeholder "inactif".
- Clic sur un slot → bascule la visibilité de sa colonne dans la grille (bordure orange `#ff6b00` si visible).
- Boutons **Toute** / **Aucune** / **Commentaire** par section.
- Section Jugements : 3 toggles (Jugement, Note sur 7, Commentaire) + 4 toggles Critère A/B/C/D (déplacés de la section Matière).

### 2. Grille élèves × notes fonctionnelle
- `_fill_grille()` construit les colonnes dynamiquement selon les slots F/S visibles + critères sélectionnés + jugements.
- Données chargées depuis `larcauth_learnerpei_has_termsubjectpei` ou `larcauth_learnerdp_has_termsubjectdp`.
- Matching élèves → notes via `fk_student_id` (ajouté au seed `take_teacher_data`).
- Fallback pour bases anciennes : message en barre d'état invitant à relancer `--mode4`.

### 3. Édition et sauvegarde des notes
- `cellChanged` connecté sur la grille → `_on_cell_changed()` enregistre les cellules modifiées dans `_dirty_cells`.
- `_save_grid_edits()` : écrit les cellules sales dans SQLite (`UPDATE table SET colonne = ? WHERE id = ?`).
- Sauvegarde automatique avant : changement de sélection, sync, fermeture.

### 4. SyncManager
- Module `common/sync.py` complet (489 lignes) : diff cellule via shadow-tables, pull/push/conflit, `sync_state`.
- Bouton **Synchroniser** branché sur `sync.pull_push()`.
- Bouton **Enregistrer et quitter** : sauvegarde grille → sync → fermeture.

## Changements récents (3 juin 2026)

### 1. Projet LarcCloudSync — Daemon de synchronisation Intranet ↔ Cloud
- Nouveau dossier `LarcCloudSync/` avec architecture complète.
- `sync_agent/main.py` : boucle principale avec polling par niveau (N0=1min, N1=5min, N2=1h, N3=1j).
- `sync_agent/sync.py` : `fetch_versions()` + `resolve()` (gagnant = version la plus élevée → push vers perdant).
- `sync_agent/db.py` : connexions PostgreSQL Intranet + Supabase, query builders.
- `sync_agent/config.py` : configuration chargée depuis `config.json`.
- `sync_agent/logger.py` : logging structuré vers fichier + rotation.

### 2. Scripts SQL de synchronisation
- `sql/01_add_sync_columns.sql` : `ALTER TABLE` ajoute `sync_version INT DEFAULT 0` et `sync_listeMAJ JSONB DEFAULT '[]'::jsonb` sur toutes les tables.
- `sql/02_create_triggers.sql` : fonction `track_sync_update()` (BEFORE UPDATE) qui incrémente `sync_version`, calcule le diff NEW vs OLD, et append `{v, user, at, src, fields}` dans `sync_listeMAJ`. Limite à 50 entrées.

### 3. Classification des 40 tables en 4 niveaux de synchronisation
- N0 (1min) : `larcauth_evaluation`, tables de notes PEI/DP, `session_cache`
- N1 (5min) : `larcauth_aecuser`, `larcauth_teachadm`, tables d'inscription
- N2 (1h) : `larcauth_criteria_of_levelsubject`, `larcib_subject`, tables de configuration
- N3 (1j) : `student_has_events`, logs, tables historiques

### 4. Conflit simplifié
- Admin gagne toujours (PULL forcé côté prof).
- Prof notifié via `sync_listeMAJ` (champ `src` côté admin = `'admin'`).
- Pas de conflit entre profs : pas de chevauchement de données par conception.

### 5. Remote GitHub migré
- `origin` changé de `github.com/larcspace/eLarcProfPy` → `github.com/yaoplab/eLarcProfPy`.
- Commit `559ab9c` : "Daemon LarcCloudSync : structure + classification tables + colonnes sync + triggers".
- `.obsidian/` ajouté à `.gitignore`.

## État GitHub
- Repo : `github.com/yaoplab/eLarcProfPy`
- Branche : `main`
- Dernier commit : `559ab9c` — Daemon LarcCloudSync : structure + classification tables + colonnes sync + triggers (3 juin 2026)

## Notes pour le 23 juin (prochaine session)

### 1. Migration LarcCommon — terminée (4 modules)
- `common/logger.py` ✅ shim vers larccommon
- `common/network.py` ✅ shim vers larccommon + `network_mode_color()` local
- `common/session.py` ✅ local avec champs `active_term_*` synchronisés
- `common/database.py` ✅ local avec `find_cfg()` depuis larccommon, SQLite intact
- `common/theme.py` ⏭️ gardé local (trop spécifique)
- `common/auth.py` ✅ shim vers LarcCommon (AuthManager + _deduce_role migrés dans LarcCommon, OAuth2 local gardé pour instance binding)

### 2. Filtre langue `_load_active_term` — corrigé dans LarcCommon
- Utilise `academicyear.current_term_number` + filtre `fk_language = 2`
- eLarcProfPy a sa propre copie de `_load_active_term` dans `auth.py` — à mettre à jour

### 3. Stats absences LarcSuperviseur — corrigé
- `ILIKE 'Absence%'` ajouté dans les 7 requêtes stats

### 4. Liste des absents LarcSuperviseur — ajoutée
- Vue groupe : sous les KPIs, avant l'historique
- Vue classe : avant les vignettes élèves

### 5. i18n — POC terminé LarcSuperviseur
- Système `larccommon/l10n/` : Translator + `fr.json`/`en.json`
- Variable d'env `LARC_LANG=fr|en`
- 8 vues traduites (~200 clés)

### 6. TODO : langue préférence en DB
- Stocker `fk_language` dans `larcauth_aecuser` (per user) + `larcauth_config` (global)
- Au login : charger la langue depuis la DB, initialiser le Translator
- Permet de regenerer une instance avec la bonne langue
