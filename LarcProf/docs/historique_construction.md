# Historique de construction — eLarcProfPy

> Journal chronologique des itérations de développement.
> Chaque entrée décrit **ce qui a été fait, pourquoi, et comment**.
> Indépendant du langage : utilisable pour un portage Delphi (eLarcProf).

---

## Itération 0 — Décision technique

### Contexte

La version Delphi (eLarcProf) a été abandonnée à cause d'erreurs de compilation FireDAC récurrentes.
Le projet a été réécrit en Python/PySide6.

### Décisions fondatrices

| Décision | Choix | Raison |
|---|---|---|
| Langage | Python 3.11 | Rapidité de développement, portabilité |
| UI | PySide6 (Qt6) | Pas PyQt5/PyQt6/Flet — PySide6 uniquement |
| Base locale | SQLite | Projection locale scopée prof |
| Base serveur | PostgreSQL | Intranet + Supabase Cloud |
| Mobile/tablette | Phase ultérieure | FastAPI + Flutter ou PWA |

Ces décisions n'impactent pas le portage Delphi — les algorithmes sont les mêmes.

---

## Itération 1 — Détection réseau

### Objectif

Savoir au démarrage si l'intranet, internet, ou aucun des deux est accessible — **sans se connecter**.

### Algorithme

```pseudo
detect_network():
    host = lire_config(IntranetDatabase.Host)  // défaut 192.168.2.90
    port = lire_config(IntranetDatabase.Port)  // défaut 5432

    intranet_ok = socket.connect(host, port, timeout=1.5s)
    internet_ok = http_get(https://www.google.com, timeout=3s)

    retourner (intranet_ok, internet_ok)
```

### Décisions

- **Test TCP seulement** : on teste si le port PostgreSQL répond, on ne lance pas de handshake complet.
- **Timeout court** (1.5s) : ne pas bloquer l'IHM au démarrage.
- **Google pour internet** : valeur universelle, pas de DNS spécifique.

### Pour le portage Delphi

Utiliser `TIdTCPClient` (Indy) pour le test socket, `TIdHTTP` pour le test internet.
Lancer dans un thread séparé pour ne pas bloquer l'UI.

---

## Itération 2 — Connexion aux bases de données

### Objectif

Gérer 3 types de connexion : Intranet (PostgreSQL local), Cloud (Supabase), SQLite (device).
Une classe unique `Database` avec un singleton global `db`.

### Architecture

```pseudo
class Database:
    _intranet: Connection PostgreSQL  (mode INTRANET)
    _cloud:    Connection PostgreSQL  (mode CLOUD)
    _sqlite:   Connection SQLite      (mode SQLITE)
    _mode:     DBMode                 (NONE/INTRANET/CLOUD/SQLITE)

    connect_intranet()  → psycopg2.connect(params depuis config.ini)
    connect_cloud()     → psycopg2.connect(params depuis config.ini)
    connect_sqlite()    → sqlite3.connect(elarc.db)
    disconnect_all()
```

### Décisions

- **`autocommit = True`** en PostgreSQL : pas de gestion transactionnelle côté applicatif.
- **`check_same_thread=False`** en SQLite : accès depuis plusieurs threads (workers Qt).
- **`PRAGMA journal_mode=WAL`** en SQLite : meilleures performances en lecture/écriture concurrentes.
- **config.ini unique** : lu au runtime, ne pas dupliquer les infos de connexion.

### Erreur rencontrée — base de données inexistante

**Symptôme :** `'utf-8' codec can't decode byte 0xe9 in position 78`

**Cause :** le `config.ini` pointait vers `NewLarcDB` mais la base réelle s'appelait `NewLarcLocal`.
PostgreSQL renvoie une erreur en français (`la base de données « NewLarcDB » n'existe pas`)
encodée en Windows-1252 (`0xe9` = `é`), et psycopg2 tente de la décoder en UTF-8 → crash.

**Correction :** renommer la base dans pgAdmin4 (`NewLarcLocal` → `NewLarcDB`) ou corriger `config.ini`.

**Leçon :** le serveur PostgreSQL était en UTF8. L'erreur d'encodage était un **symptôme**,
pas la cause. La cause était un nom de base erroné.

### Pour le portage Delphi

- `TADOConnection` pour PostgreSQL via `ODBC` ou `dbGo`.
- `TFDConnection` pour SQLite (FireDAC).
- FireDAC était justement la source des erreurs — vérifier la version ou utiliser `dbGo` (ADO).

---

## Itération 3 — Authentification Intranet

### Objectif

Vérifier email + mot de passe contre la table `larcauth_aecuser` en PostgreSQL.

### Algorithme

```pseudo
auth_intranet(email, password):
    pass_hash = SHA256(password)

    user = SELECT id, email, last_name, first_name, password
           FROM larcauth_aecuser
           WHERE LOWER(email) = LOWER(email_input)

    si user est NULL → "Utilisateur introuvable"

    si user.password != pass_hash → "Mot de passe incorrect"

    tadm = SELECT is_adm, is_coordonator, is_secretary
           FROM larcauth_teachadm
           WHERE aecuser_ptr_id = user.id

    si tadm est NULL → "Aucun profil enseignant"

    term = SELECT id, label FROM larcib_term
           WHERE is_active = TRUE ORDER BY id DESC LIMIT 1

    role = déduire_rôle(is_adm, is_coordonator, is_secretary)
    // PROF si rien, COORD si coord, SECR si secretaire, ADMIN si admin

    retourner AuthResult(user_id, email, full_name, role, term_id, term_label)
```

### Décisions

- **Hash SHA-256** : mot de passe stocké en hash hexadécimal, jamais en clair.
- **`LOWER(email)`** : les emails sont stockés en minuscules, comparaison insensible à la casse.
- **Table `teachadm`** : un utilisateur peut exister dans `aecuser` sans être enseignant — la présence dans `teachadm` fait foi.
- **Colonnes de rôle** : `is_adm`, `is_coordonator`, `is_secretary`. Pas de colonne `enabled` — on utilise `is_adm` etc.

### Bug rencontré

Le code utilisait `UserRole.TEACHER` qui n'existe pas — remplacé par `UserRole.PROF`.
Les requêtes référençaient une colonne `enabled` inexistante — supprimée.

### Pour le portage Delphi

- `TFDQuery` ou `TADOQuery` avec paramètres nommés.
- Fonction de hash SHA-256 disponible via `TIdHashSHA256` (Indy).
- Attention aux rôles : le mapping doit utiliser `is_adm`, `is_coordonator`, `is_secretary` directement.

---

## Itération 4 — Authentification Cloud (OAuth2 Google)

### Objectif

Authentifier les utilisateurs `@arc-en-ciel.org` via OAuth2 PKCE avec Google Workspace.

### Algorithme

```pseudo
oauth2_authenticate():
    // 1. PKCE : générer verifier + challenge
    verifier  = base64url(randombits(32))
    challenge = base64url(SHA256(verifier))

    // 2. Construire URL d'autorisation Google
    url = "https://accounts.google.com/o/oauth2/v2/auth" + params:
        client_id, redirect_uri, response_type=code,
        code_challenge=challenge, hd=arc-en-ciel.org, ...

    // 3. Serveur HTTP local sur port 8765 pour capturer le callback
    démarrer serveur HTTP sur localhost:8765
    ouvrir url dans le navigateur
    attendre 120s max que le code soit reçu

    // 4. Échanger le code contre des tokens
    POST https://oauth2.googleapis.com/token
        Body: code, client_id, client_secret, verifier, grant_type

    // 5. Décoder le JWT id_token
    payload = base64url_decode(id_token.split('.')[1])
    email = payload.email
    hd = payload.hd

    si hd != 'arc-en-ciel.org' → refuser

    // 6. Chercher l'utilisateur en base
    user = SELECT FROM larcauth_aecuser WHERE LOWER(email) = ?
    tadm = SELECT FROM larcauth_teachadm WHERE aecuser_ptr_id = ?
    // même logique que auth Intranet
```

### Décisions

- **PKCE obligatoire** : pas de secret client pour les apps desktop (code flow standard interdit).
- **Serveur HTTP local** : pas d'URL distante, tout tourne sur `localhost:8765`.
- **`hd=arc-en-ciel.org`** : Google force le domaine, empêche les comptes Gmail personnels.
- **Timeout 120s** : l'utilisateur peut prendre le temps de se connecter à Google.

### Pour le portage Delphi

- `TIdHTTP` (Indy) pour les appels REST.
- Application console/forms avec un `TIdHTTPServer` sur le port 8765 pour le callback.
- Unité `System.Net.HttpClient` disponible dans les versions récentes de Delphi.
- Décodage base64url + JWT manuel (le payload est du JSON simplement encodé).

---

## Itération 5 — Authentification PIN (hors ligne)

### Objectif

Permettre la connexion sans accès serveur via un code PIN stocké localement.

### Algorithme

```pseudo
auth_pin(email, pin):
    pin_hash = SHA256(pin)

    row = SELECT user_id, email, full_name, role, term_id, term_label
          FROM session_cache
          WHERE LOWER(email) = ? AND pin_hash = ?

    si row NULL → "Email ou PIN incorrect"
    sinon → AuthResult(...)
```

### Décisions

- **PIN 4-8 chiffres** : validation stricte, pas de lettres.
- **Hash SHA-256** : même mécanisme que le mot de passe.
- **Stockage dans `session_cache`** : table locale SQLite, créée au seed.
- **Pas de connexion serveur nécessaire** : fonctionne même en OFFLINE.

### Pour le portage Delphi

- Même logique : hash + SELECT dans table locale SQLite.
- FireDAC peut lire/écrire dans SQLite directement.

---

## Itération 6 — Initialisation de la base locale SQLite

### Objectif

Créer la structure SQLite complète au premier lancement : tables métier + tables système.

### Tables créées

```sql
-- Tables métier (gabarit pré-alloué, jamais INSERT/DELETE, seulement UPDATE)
larcauth_evaluation
larcauth_learnerpei_has_termsubjectpei
larcauth_learnerdp_has_termsubjectdp

-- Tables de référence (shadow pour sync)
larcauth_evaluation_ref
larcauth_learnerpei_has_termsubjectpei_ref
larcauth_learnerdp_has_termsubjectdp_ref

-- Tables système
session_cache        -- email, full_name, role, pin_hash, term_id, term_label
module_config        -- annee_scolaire, trimestre_courant, nom_professeur, ...
sync_cursor          -- curseurs de synchronisation
sync_state           -- last_sync, last_source par table
```

### Décisions

- **DDL exécuté dans `init()`** : appelé après chaque connexion réussie avant toute opération.
- **`init_module_config()`** : insère ou met à jour (`ON CONFLICT(id) DO UPDATE`).
- **Deux niveaux** : tables structure (gabarit) + tables notes (générées à l'activation).
- **Même philosophie que PostgreSQL** : jamais de DELETE, activation par booléen.

### Pour le portage Delphi

- FireDBC peut exécuter ce DDL via `TFDConnection.ExecuteDirect()`.
- La même structure SQLite sera utilisée — pas de changement côté schéma.

---

## Itération 7 — Export PostgreSQL → SQLite (take_teacher_data)

### Objectif

Télécharger les données du professeur depuis PostgreSQL vers SQLite local pour le trimestre courant.

### Algorithme

```pseudo
take_teacher_data(infos):
    user_id = infos.user_id
    term_id = infos.trimestre_courant

    // 1. Lire depuis PostgreSQL pour les 3 tables métiers
    eval_rows  = SELECT * FROM larcauth_evaluation WHERE teacher_id = ? AND term_id = ?
    pei_rows   = SELECT * FROM larcauth_learnerpei_has_termsubjectpei WHERE teacher_id = ?
    dp_rows    = SELECT * FROM larcauth_learnerdp_has_termsubjectdp WHERE teacher_id = ?

    // 2. Vider les tables locales
    DELETE FROM larcauth_evaluation
    DELETE FROM larcauth_learnerpei_has_termsubjectpei
    DELETE FROM larcauth_learnerdp_has_termsubjectdp

    // 3. Insérer les données
    INSERT INTO larcauth_evaluation VALUES ...
    INSERT INTO larcauth_learnerpei_has_termsubjectpei VALUES ...
    INSERT INTO larcauth_learnerdp_has_termsubjectdp VALUES ...

    // 4. Même chose pour les tables _ref
    INSERT INTO larcauth_evaluation_ref VALUES ...
    // ... idem pour pei_ref, dp_ref
```

### Décisions

- **VIDER puis INSERT** : pas de REPLACE ou UPSERT — le seed est une réinitialisation complète.
- **Tables `_ref` peuplées à l'identique** : au seed, `local = ref = serveur` → pas de diff.
- **Une seule requête par table** : pas de ligne par ligne.
- **Vérification connexion serveur avant** : si `db.server_conn` est NULL, on tente `connect_intranet()` puis `connect_cloud()`.

### Pour le portage Delphi

- `TFDQuery` avec `SELECT * FROM ... WHERE ...` puis `INSERT` en boucle.
- Attention : les schémas peuvent évoluer — ne pas hardcoder les colonnes.
- Utiliser `TFDMemTable` comme buffer intermédiaire si besoin.

---

## Itération 8 — Gestion de session

### Objectif

Maintenir l'état de la session utilisateur dans un singleton global, sauvegardé dans SQLite.

### Structure

```python
class AuthResult:
    user_id: int
    email: str
    full_name: str
    role: UserRole
    term_id: int
    term_label: str

class Session:
    user_id: int
    email: str
    full_name: str
    role: UserRole
    active_term_id: int
    active_term_label: str
    conn_mode: ConnMode   # INTRANET / CLOUD / OFFLINE
```

### Sauvegarde

```sql
INSERT INTO session_cache (user_id, email, full_name, role, pin_hash, term_id, term_label)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(email) DO UPDATE SET ...
```

### Décisions

- **Un seul singleton** `session` : importé partout comme `from common.session import session`.
- **`pin_hash` optionnel** : NULL si l'utilisateur n'a pas défini de PIN.
- **Sauvegardé à chaque auth réussie** : permet la reconnexion hors ligne.

---

## Itération 9 — Fenêtre principale (MainWindow)

### Objectif

Remplacer le popup placeholder "Phase 2 à implémenter" par un espace de travail structuré.

### Layout initial (Phase 2 - Étape 1)

```
+--------------------------------------------------------------+
| Header : Nom du prof | Année scolaire | Trimestre courant    |
+------------------+--------------------+----------+-----------+
| Matière-Classe   | Formatives F01-F12 | Sommatives S01-S12 | Filtres |
| (liste unique)   |                    |                    |         |
+------------------+--------------------+--------------------+---------+
| Grille élèves × notes (placeholder)                           |
+--------------------------------------------------------------+
| [Synchroniser]  [Enregistrer et quitter]                     |
+--------------------------------------------------------------+
```

### Sélecteur Matière-Classe (évolution importante)

**Avant (abandonné) :** deux `QComboBox` en cascade :
1. Matières → sélection → 2. Classes filtrées → sélection → workspace

**Après (retenu) :** un seul `QComboBox` avec des items `Matière - Classe`.

**Raison :** un clic suffit pour atteindre le workspace, pas de cascade.

### Requête SQL unique

```sql
SELECT cts.id AS termsubject_id,
       ls.label AS matiere,
       c.id AS class_id,
       c.label AS classe,
       c.fk_level_id
FROM larcauth_classroom_termsubject cts
JOIN larcauth_levelsubject ls ON ls.id = cts.fk_levelsubject_id
JOIN larcauth_classroom c ON c.id = cts.fk_classroom_id
WHERE cts.fk_teacher_id = ?
  AND cts.fk_term_id = ?
  AND cts.enabled = 1
  AND c.enabled = 1
ORDER BY ls.label, c.label;
```

### Structure de données

```python
self._items: list[dict] = [
    {'termsubject_id': int, 'matiere_label': str,
     'class_id': int, 'class_label': str, 'cycle': 'PEI'|'DP'},
    ...
]
self._eleves_par_classe: dict[int, list[dict]]  # class_id → élèves
self._cycle_par_classe: dict[int, str]           # class_id → 'PEI'|'DP'
```

### Cycle de vie

```pseudo
MainWindow.__init__()
├── _build_header()            → session.full_name, module_config
├── _build_matiere_classe_panel() → combo unique
├── _load_combined_data()      → requête SQL unique → peupler combo
└── si 1 seul item → auto-sélection

_on_item_selected(idx):
├── extraire class_id de l'item
├── déterminer cycle (PEI/DP)
├── basculer QStackedWidget
├── peupler panneaux F/S (future étape)
└── remplir grille élèves (future étape)
```

### Pour le portage Delphi

- Remplacer `QComboBox` par un `TComboBox`.
- Stocker les données dans des `TList` d'enregistrements ou des `TClientDataSet`.
- La requête SQL est identique.
- `QSplitter` → `TSplitter`.

---

## Itération 10 — Indicateur d'état réseau

### Objectif

Afficher en bas de la fenêtre de connexion l'état actuel de la connectivité.

### États possibles

| Valeur | Affichage | Feu |
|---|---|---|
| 0 | "Module eLarcProf non instanciée" | Noir |
| 1 | "Module eLarcProf de {Nom} {Prénom} non connecté" | Noir |
| 2 | "Module eLarcProf de {Nom} {Prénom} connecté à l'Intranet" | Vert |
| 3 | "Module eLarcProf de {Nom} {Prénom} connecté au Cloud" | Vert |

### Décisions

- **Un seul indicateur large centré** (remplace les deux indicateurs "Présence intranet ●" + "Présence cloud ●").
- **Mis à jour au démarrage** par `detect_network()` et après chaque connexion.
- **Ne pas confondre avec le statut sync** : présence réseau ≠ connexion base.

---

## Itération 11 — Changement de mot de passe et PIN

### Objectif

Permettre à l'utilisateur de modifier son mot de passe Intranet ou son PIN hors ligne.

### Password (Intranet)

```pseudo
ChangePasswordDialog:
    champs : email, ancien mot de passe, nouveau mot de passe, confirmation

    validation :
        - tous les champs obligatoires
        - nouveau mot de passe >= 6 caractères
        - confirmation identique
        - ancien mot de passe vérifié via AuthManager.auth_intranet()

    UPDATE larcauth_aecuser SET password = SHA256(new_pass)
    WHERE LOWER(email) = ?
```

### PIN (Hors ligne)

```pseudo
ChangePinDialog:
    champ : nouveau PIN (4-8 chiffres)

    validation : que des chiffres, 4-8 caractères

    sqlite_init.save_session(session, new_pin)
    // met à jour session_cache avec le nouveau pin_hash
```

### Décisions

- **Bouton dans l'onglet correspondant** : "Changer mot de passe" dans l'onglet Intranet, "Changer PIN" dans l'onglet Hors connexion.
- **Pas de bouton dans la barre d'état** (supprimé car redondant).

---

## Itération 12 — Synchronisation (architecture, non implémentée)

### Objectif (documenté, pas codé)

Définir l'algorithme de synchronisation entre SQLite device et PostgreSQL serveur.

### Pattern shadow-table

Chaque table métier a une jumelle `_ref` au schéma identique :

| Table de travail | Table de référence |
|---|---|
| `larcauth_evaluation` | `larcauth_evaluation_ref` |
| `larcauth_learnerpei_...` | `larcauth_learnerpei_..._ref` |
| `larcauth_learnerdp_...` | `larcauth_learnerdp_..._ref` |

- **Table de travail** = état local courant (saisies du prof).
- **Table `_ref`** = snapshot du dernier état serveur connu.
- Au seed, les deux sont identiques.

### Matrice de décision (par cellule)

| local vs ref | serveur vs ref | Action |
|---|---|---|
| = | = | Rien |
| = | ≠ | **Pull** : local = serveur, ref = serveur |
| ≠ | = | **Push** : serveur = local, ref = local |
| ≠ | ≠ | **Conflit** → IHM de résolution |

### Déclencheurs prévus

1. Seed initial (mode 4) — pas de diff possible.
2. Clic "Connecter" — pull/push si nécessaire.
3. Clic "Synchroniser" (tableau de bord).
4. "Enregistrer et quitter" — synchro puis fermeture.

### Règle métier fondamentale

- **Jamais de INSERT/DELETE** — que des UPDATE (gabarit pré-alloué).
- **Trimestre passé en lecture seule** : la synchro ne touche que `term_id = trimestre_courant`.
- **Ne jamais toucher au daemon serveur** (sync intranet ↔ cloud tourne séparément).

### Pour le portage Delphi

- C'est l'algorithme le plus important à coder.
- Le diff cellule par cellule peut se faire en SQL : jointure par `id`, comparaison colonne par colonne.
- La table `sync_state` (dernier timestamp par table) est essentielle.
- Les `_ref` tables sont le cœur du dispositif — ne pas les oublier.

---

## Itération 13 — Encodage et configuration

### Problème connexion PostgreSQL

**Symptôme :** `'utf-8' codec can't decode byte 0xe9`
**Cause racine :** nom de base erroné dans `config.ini` (NewLarcDB vs NewLarcLocal).
**Symptôme trompeur :** l'erreur UTF-8 faisait croire à un problème d'encodage.
**Vrai problème :** PostgreSQL renvoie des messages d'erreur en français (Windows-1252) que psycopg2 ne peut pas décoder.

### Leçon retenue

- Le serveur PostgreSQL était en **UTF8**.
- L'erreur d'encodage n'était qu'un **symptôme indirect**.
- Toujours vérifier d'abord que la base de données cible existe.

---

## Itération 14 — Correction environnement virtuel

### Problème

```
error: uv trampoline failed to spawn Python child process
Caused by: entity not found (os error 2)
```

### Cause

`uv venv` crée un `python.exe` qui est un **trampoline** (exécutable intermédiaire de 270 Ko)
qui appelle `uv` pour lancer le vrai Python. Si le Python géré par `uv` est désinstallé
(ou réinstallé ailleurs), le trampoline ne trouve plus la cible → `entity not found`.

### Solution retenue

Recréer le venv avec le vrai Python système :
```
C:\Python\Python311\python.exe -m venv .venv
```

### Alternative avec uv

Si on veut utiliser `uv`, il faut lancer avec `uv run main.py` (pas d'activation de venv).
Le trampoline ne pose pas de problème si le Python uv est toujours installé.

---

## Itération 12 — Panneaux F/S avec indicateurs et dialogue détail (25 mai 2026)

### Objectif

Remplacer les placeholders des panneaux formatives/sommatives par des slots cliquables
avec indicateurs visuels et dialogue d'édition des métadonnées (label, nature, source, critères).

### Fichiers modifiés

- `views/evaluation_panel.py` — créé (contient `EvaluationPanel`, `_SlotButton`, `EvaluationDetailDialog`)
- `views/main_window.py` — intégration des panneaux, chargement des évaluations depuis SQLite

### Dialogue de détail (`EvaluationDetailDialog`)

Fenêtre modale ouverte au clic sur un slot F/S :

```
┌──────────────────────────────────────┐
│  S01                                 │
│  Label : [Électricité - Loi d'Ohm]  │
│  Nature : [Devoir surveillé]        │
│                                      │
│  Source / Texte de l'évaluation :    │
│  ┌────────────────────────────────┐ │
│  │ (texte libre multi-lignes)     │ │
│  └────────────────────────────────┘ │
│                                      │
│  Critères :                          │
│  ┌──────────────────────────────────┐│
│  │ ☑ Critère A : label + aspects   ││
│  │ ☐ Critère B : label             ││
│  │ ☑ Critère C : label + aspects   ││
│  │ ☐ Critère D : label             ││
│  └──────────────────────────────────┘│
│                          [OK] [Cancel]│
└──────────────────────────────────────┘
```

Colonnes sauvegardées dans `larcauth_evaluation` : `label`, `nature`, `source`, `crit_a..crit_d`.

### Slot compact (`_SlotButton`)

Chaque slot dans la grille 4×3 affiche :
- Titre `F01` (8-10px bold)
- Label descriptif (9px)
- 4 critères avec ☐/☑ + label text (9px)
- Fond blanc/bordure verte si actif, gris `#f0f0f0` si inactif
- Police Roboto

Les labels des critères sont chargés depuis `larcauth_criteria_of_levelsubject` (jointure via `larcauth_classroom_termsubject.fk_levelsubject_id`).

### Barre d'indicateurs

12 petits labels `F01`..`F12` / `S01`..`S12` en haut de chaque panneau.
- Vert si actif (≥1 critère coché)
- Gris si inactif

### Interaction

- Clic sur un slot sans matière-classe sélectionnée → ignoré (vérification `self._termsubject_id is None`)
- Clic sur un slot inactif → ouvre le dialogue vide (création)
- Clic sur un slot actif → ouvre le dialogue pré-rempli
- Sauvegarde immédiate en SQLite (`UPDATE ... SET label=?, nature=?, ...`)
- Mise à jour visuelle du slot + indicateurs

---

## Itération 13 — Restructuration layout (25 mai 2026)

### Objectif

Corriger les problèmes UX identifiés : titres flottants, espace vertical gaspillé,
déséquilibre des largeurs, interligne trop grand, couleurs inactives illisibles.

### Problèmes corrigés

#### 1. Titres flottants

Chaque `EvaluationPanel` est maintenant un `QFrame` avec bordure grise et titre intégré.
Le titre est visuellement rattaché à son contenu (indicateurs + grille de slots).

#### 2. Gaspillage vertical

Suppression du `QSplitter` vertical (main_split). La zone haute prend sa hauteur
naturelle (titre + indicateurs + 2 lignes de slots, ≈190-220px). La grille élèves
prend le reste avec `stretch=1` dans le `QVBoxLayout`.

#### 3. Déséquilibre des largeurs

Suppression du `QSplitter` horizontal. Remplacement par un `QHBoxLayout` avec :
- Matière-Classe : `setFixedWidth(200)`
- Formatives : `stretch=1`
- Sommatives : `stretch=1`
- Filtres : `setFixedWidth(140)`

#### 4. Interligne et compacité

- Layout des slots : `setSpacing(0)`, marges réduites `3,1,3,1`
- Polices Roboto 8-10px pour tout le panneau
- Hauteur du scroll limitée dynamiquement à 2 lignes (`scroll.setMaximumHeight`)

#### 5. Couleurs inactives lisibles

- Titre inactif : `#555`
- Critères inactifs : `#555` (label), `#777` (checkbox ☐)
- Indicateurs inactifs : `#666` sur fond `#e0e0e0`
- Plus de `#bbb` illisible

### Fichiers modifiés

- `views/evaluation_panel.py` — restructuration complète de `EvaluationPanel` et `_SlotButton`
- `views/main_window.py` — suppression des QSplitter, layout à hauteur fixe
- `docs/16_main_window.md` — mise à jour de la documentation

---

## Itération 14 — Fenêtre de gestion EvalManagerWindow (27 mai 2026)

### Objectif

Séparer la gestion complète des évaluations de l'écran principal. Créer une fenêtre
non-modale avec grille de slots à gauche et formulaire d'édition à droite.

### Fichiers

- `views/eval_manager.py` — créé (contient `_SlotBar`, `EvalManagerWindow`)
- `views/evaluation_panel.py` — retiré `EvalManagerWindow` (déplacé), `EvaluationDetailWidget` extrait du dialog
- `views/main_window.py` — connexion des boutons Gérer → `EvalManagerWindow`

### Panneau principal : mode compact

`EvaluationPanel` supporte deux modes via `compact=True/False` :
- **compact=True** (écran principal) : seuls les slots actifs sont affichés dans la grille
- **compact=False** (manager) : les 12 slots sont dans une grille responsive

Ajout d'un bouton "Gérer" en mode compact → ouvre `EvalManagerWindow`.

### Fenêtre de gestion

Layout `QSplitter` horizontal :
- **Gauche** : `EvaluationPanel(compact=False)` avec les 12 slots + légende critères
- **Droite** : `EvaluationDetailWidget` (formulaire réutilisable)

À la fermeture du manager, `panel.load_evaluations()` recharge les données dans l'écran principal.

---

## Itération 15 — Barres horizontales et affichage progressif (27 mai 2026)

### Objectif

Remplacer la grille 4×3 par des barres horizontales empilées, avec un affichage
progressif : seuls les slots actifs + le "suivant" sont visibles.

### `_SlotBar`

Barre horizontale `QHBoxLayout` :
```
[F01] | Titre (nature, 72 chars max) ............. | ☐A ☐B ☐C ☐D
```

### Affichage progressif

```python
_update_visibility():
    for bar in bars:
        if bar._active:
            bar.set_style_active()   # vert
            bar.setVisible(True)
        elif not found_next:
            bar.set_style_next()     # grisé pointillé
            bar.setVisible(True)
            found_next = True
        else:
            bar.setVisible(False)    # masqué
```

Quand le prof enregistre un slot avec un critère coché, les données SQLite sont
mises à jour, `_update_visibility()` est rappelé → le slot devient vert et le
suivant apparaît grisé.

### `resizeEvent`

Le panneau gauche recalcule automatiquement l'affichage au redimensionnement.

---

## Itération 16 — Markdown, toolbar, correcteur orthographique, grille critères (27 mai 2026)

### Objectif

Améliorer le panneau d'édition droit avec un éditeur markdown, une barre d'outils,
un correcteur orthographique, et une grille critères compacte.

### Source en Markdown

- `QPlainTextEdit` → `QTextEdit` avec `setMarkdown()`/`toMarkdown()`
- Barre d'outils au-dessus : **B** (gras `**texte**`), *I* (italique `*texte*`),
  **H** (titre `## `), **•** (liste `- `), **🔗** (lien `[texte](url)`)
- Boutons insèrent le snippet à la position du curseur

### Correcteur orthographique (`_SpellHighlighter`)

```python
class _SpellHighlighter(QSyntaxHighlighter):
    utilise pyenchant.Dict('fr_FR') si disponible
    surligne les mots inconnus en rouge (SpellCheckUnderline)
    # Si pyenchant non installé → pas d'erreur, correcteur inactif
```

### Grille critères 4×2

Au lieu de 4 frames verticales → `QGridLayout` 4 colonnes × 2 lignes :
```
   ☐A          ☑B          ☐C          ☑D
Recherche   Développement  Création    Évaluation
et analyse  des idées      de la solution
```

Les retours à la ligne (`\n`) dans les labels critères sont nettoyés.

### Label en lecture seule

Le champ "Label" passe de `QLineEdit` → `QLabel` (affichage seul).
`get_form_data()` ne renvoie plus `label`. La sauvegarde conserve la valeur
existante.

### Fichiers modifiés

- `views/evaluation_panel.py` — `EvaluationDetailWidget` : markdown, toolbar,
  `_SpellHighlighter`, grille critères, label lecture seule, taille policies
- `views/eval_manager.py` — `_SlotBar` horizontale, `_update_visibility()`
- `docs/20_eval_manager.md` — créé

---

## Annexe A — Règles métier générales

| Règle | Détail |
|---|---|
| Gabarit pré-alloué | Rien n'est créé ni détruit — que des UPDATE |
| Trimestre courant | Toute requête filtre par `term_id = trimestre_courant` |
| Trimestres passés | Lecture seule — grisés dans l'IHM |
| Jamais de DELETE | Désactivation logique par `enabled = FALSE` |
| Notes PEI (collège) | 0-8 par critère, synthèse 0-7 |
| Notes DP (lycée) | 0-20, step 0.5 |
| 12 formatives + 12 sommatives | Par matière par trimestre — slots F13-F15 et S13-S15 réservés pour v2 |
| 4 critères (a,b,c,d) | Critères E et F existent en base mais ignorés en v1 |
| Sync déclenchée uniquement par clic | Pas de connexion automatique au démarrage |
| Daemon serveur | Ne jamais le modifier — logique de diff côté device uniquement |

## Itération 17 — Content widget, migration DDL, debug boutons Gérer (1er juin 2026)

### Objectif

Rendre le workspace utilisable : combo matière-classe toujours visible, panneaux cachés
jusqu'à sélection, correction du bug des boutons Gérer qui ne répondaient pas.

### Fichiers modifiés

- `views/main_window.py` — content widget (`_content_widget`), traces debug, `try/except`
  dans `_open_manager`
- `views/evaluation_panel.py` — empty placeholder, traces debug, `try/except` dans
  `load_evaluations`
- `views/eval_manager.py` — dead code (doublons `statusBar`), traces debug
- `views/login.py` — contournement de `take_teacher_data` pour login normal
- `common/sqlite_init.py` — méthode `_migrate_columns()` pour ALTER TABLE ADD COLUMN
- `CONTEXT.md` — mise à jour

### Détail des modifications

#### 1. Content widget (main_window.py)
- Combo matière-classe extrait dans un panneau séparé toujours visible.
- Tout le reste (panneaux F/S, filtres, grille, actions) dans `_content_widget`.
- `_content_widget.hide()` au démarrage, `show()` après sélection.
- `_on_item_selected` bascule la visibilité.

#### 2. take_teacher_data contourné (login.py)
- `_on_auth_done` appelait `take_teacher_data` après chaque connexion Intranet/Cloud.
- Problème : vidait les données locales (DELETE + réimport) à chaque démarrage.
- Solution : retiré du flux normal, réservé à `--mode4` et confirmation PIN opt-in.

#### 3. Placeholder (evaluation_panel.py)
- `_empty_placeholder` : `QLabel("Aucune évaluation active")` centré.
- `_update_layout()` : si aucun slot actif, cache la grille et montre le placeholder.
- `clear_panel()` : reset `_termsubject_id = None`, cache aussi le placeholder.

#### 4. Migration DDL automatique (sqlite_init.py)
- Nouvelle méthode `_migrate_columns(conn, table, columns)`.
- Appelée après `executescript(_DDL)` dans `init_intranet()`.
- Vérifie les colonnes existantes via `PRAGMA table_info()`, ajoute celles manquantes.
- Colonnes ajoutées : `sync_version`, `synced_at`, `synced_by`, `last_modified_at`,
  `sync_revision`, `source` sur `larcauth_evaluation` et `larcauth_evaluation_ref`.

#### 5. Bug boutons Gérer
**Cause racine :** la base SQLite existante (`elarc.db`) avait été créée sans la colonne
`source` dans `larcauth_evaluation`. La requête `SELECT ... source FROM larcauth_evaluation`
lançait `sqlite3.OperationalError: no such column: source`. L'exception dans
`load_evaluations()` déclenchait `clear_panel()` qui mettait `_termsubject_id = None`.
Quand l'utilisateur cliquait Gérer, `_open_manager()` voyait `_termsubject_id = None` et
abortait sans message visible.

**Correctifs :**
- Migration DDL automatique (voir point 4).
- `try/except` dans `load_evaluations()` avec `traceback.print_exc()`.
- `try/except` dans `_open_manager()` avec affichage du message d'erreur dans la
  statusBar et console.
- Traces `[TRACE]` ajoutées aux points clés pour faciliter le diagnostic.

#### 6. Diagnostic serveur (données réelles)
- Prof 1021 (Patrice LABONNE), trimestre 3 : 31 `classroom_termsubject`, 189 évaluations.
- **0 évaluations avec critères cochés** — toutes les colonnes `crit_a`..`crit_d` = `'0'`.
- Les 57 évaluations qui ont des critères cochés sont sur les trimestres 1 et 2.
- Conclusion : le serveur n'a pas de critères configurés pour le trimestre 3 pour ce prof.
- L'interface affiche donc "Aucune évaluation active" pour toutes les matières du T3.

### Problèmes ouverts

1. **Données trimestre 3 vides** — besoin de critères côté serveur ou d'un jeu de test.
2. **Grille élèves × notes** — pas encore implémentée (placeholder uniquement).
3. **Pas de sync** — bouton Synchroniser non branché.
4. **Correcteur orthographique** — `pyenchant` doit être installé dans le venv.

---

## Annexe B — Organisation des fichiers

```
eLarcProfPy/
├── main.py                 # Point d'entrée (QApplication + LoginWindow + CLI)
├── common/
│   ├── network.py          # detect_network()
│   ├── database.py         # Database (singleton db)
│   ├── auth.py             # AuthManager + OAuth2Manager
│   ├── session.py          # UserRole, ConnMode, Session (singleton session)
│   ├── sqlite_init.py      # SQLiteInit (DDL, seed, session, module_config)
│   └── logger.py           # log()
├── views/
│   ├── login.py            # LoginWindow (4 onglets)
│   ├── password.py         # ChangePinDialog + ChangePasswordDialog
│   ├── main_window.py      # MainWindow (espace de travail)
│   ├── evaluation_panel.py # EvaluationPanel, _SlotButton, EvaluationDetailWidget,
│   │                       # EvaluationDetailDialog, _SpellHighlighter
│   └── eval_manager.py     # _SlotBar, EvalManagerWindow
└── docs/                   # Documentation algorithmique
```

## Annexe C — Dépendances

```txt
PySide6>=6.6.0              # Qt6 bindings (remplace Delphi VCL/FireMonkey)
psycopg2-binary>=2.9.9      # PostgreSQL driver (remplace FireDAC)
pandas>=2.0.0               # Data manipulation (optionnel)
sqlalchemy>=2.0.0           # ORM (utile pour export)
pyenchant>=3.2              # Correcteur orthographique (optionnel)
```

---

## Itération 18 — Top bar refactorée avec slots scrollables actifs (1er juin 2026)

### Objectif
Remplacer les panneaux `EvaluationPanel` (grille 4×3 de slots, placeholders d'inactifs) par une top bar compacte avec 4 sections fixes, où seuls les slots actifs sont visibles.

### Problème résolu
Les panneaux F/S existants montraient tous les slots (actifs + inactifs) dans une grille 4×3. Les inactifs étaient grisés mais prenaient de la place. Sur un trimestre avec peu d'évals actives (ex: T3 = 0), l'interface était vide et déroutante.

### Layout final
```
┌──────────────┬────────────────────────────────────┬────────────────────────────────────┬──────────────┐
│ Matière-Cl.  │ Formatives (scroll, actifs seuls)  │ Sommatives (scroll, actifs seuls)  │ Jugements    │
│ fixed 210px  │ stretch                            │ stretch                            │ fixed 170px  │
├──────────────┼────────────────────────────────────┼────────────────────────────────────┼──────────────┤
│ Combo +      │ [F01] Titre...  Nature  B C D     │ [S01] Titre...  Nature  A B       │ [Jgt][Note]  │
│ Autre combo  │ [F02] Titre...  Nature  A B C     │ [S03] Titre...  Nature  D         │ [Comm]       │
│              │ (scroll si >N actifs)              │ (scroll si >N actifs)              │ Crit. A B C D│
│              │ [Toute] [Aucune] [Commentaire]     │ [Toute] [Aucune] [Commentaire]     │              │
└──────────────┴────────────────────────────────────┴────────────────────────────────────┴──────────────┘
```

### Détail des sections

#### Section Matière-Classe
- `QComboBox` avec items `Matière - Classe` (depuis `larcauth_classroom_termsubject`)
- Second combo "Autre Matière-Classe" (depuis `larcauth_classroom_termothersubject`)
- Critère A/B/C/D déplacés vers la section Jugements

#### Sections Formatives / Sommatives
- Chaque section est un `QFrame` avec `QVBoxLayout`
- Titre (bold 10px) + bouton **Gérer** → `EvalManagerWindow`
- `QScrollArea` avec `maximumHeight=160px`
- Liste de rangées `QFrame` cliquables, une par slot actif
- Chaque rangée : `F01` (26px) | Label (90px, tronqué 18→16+…) | Nature (70px, tronqué 14→12+…) | Critères actifs (ex: `B C D` en vert)
- Fond vert clair `#e8f8f0` + bordure gauche orange `#ff6b00` 3px si visible dans la grille
- Fond gris `#f9f9f9` si masqué
- Clic sur rangée → `_on_slot_icon_clicked()` bascule visibilité
- Boutons **Toute** / **Aucune** / **Commentaire** (QPushButton checkable)

#### Section Jugements
- 3 boutons toggles : **Jugement** (jgt_a..d), **Note sur 7** (note_on_7), **Commentaire** (term_observation)
- Séparateur horizontal
- 4 boutons toggles **Critère A/B/C/D** (déplacés ici depuis la section Matière)

### Grille élèves × notes
- `QTableWidget` sous la top bar, stretch=1
- Colonnes dynamiques construites dans `_fill_grille()` selon les slots visibles + critères + jugements
- Données chargées depuis la table PEI ou DP, column names dynamiques
- Étudiant = première colonne fixe (nom + prénom)

### Changements clés
- `EvaluationPanel` n'est plus utilisé par `MainWindow`
- `_build_top_panels()` supprimée
- `_db_col()`, `_on_filter_changed()`, `_set_workspace_enabled()` → dead code retiré
- `_current_ts_id` stocké directement dans `MainWindow` (plus dans `EvaluationPanel`)

### Fichiers modifiés
- `views/main_window.py` — réécriture complète de `_setup_ui`, `_build_top_bar`, `_fill_grille`
- `views/evaluation_panel.py` — plus importé par `main_window.py` (obsolète)
- `docs/16_main_window.md` — mise à jour
- `deepseek/` — snapshot + key_locations mis à jour

---

## Itération 19 — Grille fonctionnelle + édition + sauvegarde (2 juin 2026)

### Objectif
Rendre la grille élèves × notes réellement fonctionnelle : charger les notes depuis SQLite, les afficher par élève, permettre l'édition par double-clic, et sauvegarder les modifications.

### Problèmes résolus

#### 1. Matching élèves → notes
**Avant :** la requête `SELECT * FROM larcauth_learnerpei_has_termsubjectpei` chargeait toutes les lignes sans filtre CTS, et utilisait `row[0]` (l'`id` de la table learner) comme clé. Les élèves étaient keyés par `aecuser_ptr_id` → **les clés ne correspondaient jamais**, la grille affichait des cellules vides.

**Solution :** modifier les requêtes de seed dans `take_teacher_data` pour inclure `lht.fk_student_id` comme colonne supplémentaire dans les tables PEI et DP :
```sql
SELECT pei.*, lht.fk_student_id
FROM public.larcauth_learnerpei_has_termsubjectpei pei
JOIN public.larcauth_learner_has_termsubject lht ON ...
```

`_fill_grille` utilise maintenant `fk_student_id` comme clé du dictionnaire `notes[student_id]`, qui matche `eleve['id']` (= `aecuser_ptr_id`).

⚠️ Les bases existantes (seedées avant cette modification) n'ont pas la colonne `fk_student_id` → message "relancez --mode4" dans la barre d'état.

#### 2. Modification et sauvegarde des notes
- Signal `QTableWidget::cellChanged` connecté à `_on_cell_changed()`
- Les cellules modifiées sont stockées dans `_dirty_cells[(student_id, db_name)] = new_value`
- `_save_grid_edits()` itère les cellules sales et exécute `UPDATE table SET col = ? WHERE id = pei_row_id`
- Sauvegarde automatique déclenchée avant :
  - Changement de sélection de slots (`_on_selection_changed`)
  - Synchronisation (`_on_sync`)
  - Fermeture (`_on_save_and_quit`)

### Fichiers modifiés
- `common/sqlite_init.py` — requêtes PEI/DP ajoutent `lht.fk_student_id`
- `views/main_window.py` — `_fill_grille` : `SELECT id, fk_student_id, ...` ; ajout de `_on_cell_changed`, `_save_grid_edits`, `_current_table`, `_row_ids`, `_dirty_cells`
- `CONTEXT.md` — mise à jour
- `docs/etat_projet.md` — réécriture
- `docs/historique_construction.md` — présent ajout

---

## Itération 20 — Daemon LarcCloudSync (3 juin 2026)

### Objectif
Créer un daemon de synchronisation autonome entre PostgreSQL Intranet et Supabase Cloud, distinct de l'application desktop eLarcProfPy.

### Décisions clés
- **`sync_listeMAJ JSONB`** remplace les 3 colonnes (`sync_version`, `sync_aecuser`, `sync_date`) + table `sync_log`. Chaque enregistrement porte son propre historique (50 entrées max).
- **Trigger BEFORE UPDATE** : `track_sync_update()` calcule le diff NEW vs OLD, incrémente `sync_version`, append `{v, user, at, src, fields}`.
- **Conflit simplifié** : ADMIN gagne toujours (PULL forcé côté prof). Pas de conflit entre profs par conception.
- **Fréquences par niveau** : N0=1min, N1=5min, N2=1h, N3=1j.
- **Agent monoprocess** : boucle `while True` avec `time.sleep()` par niveau, pas de threading.

### Fichiers créés
```
LarcCloudSync/
├── config.json                        # Connexions + fréquences par table
├── requirements.txt                   # psycopg2-binary, python-dotenv
├── sql/
│   ├── 01_add_sync_columns.sql        # ALTER TABLE sync_version + sync_listeMAJ
│   └── 02_create_triggers.sql         # FUNCTION + TRIGGER track_sync_update
├── sync_agent/
│   ├── __init__.py
│   ├── main.py                # Boucle principale N0..N3
│   ├── sync.py                # fetch_versions, resolve (push winner → loser)
│   ├── db.py                  # Query builders PostgreSQL
│   ├── config.py              # Chargement config.json
│   └── logger.py              # Logging structuré avec rotation
└── 01_Architecture/
    └── 02_TABLE_CLASSIFICATION.md # 40 tables classées N0-N3
```

### Changements transverses
- `.gitignore` : ajout de `.obsidian/` (notes personnelles).

### Impact sur l'application desktop
- `common/sync.py` (SyncManager device) **inchangé** pour l'instant — utilise toujours le pattern shadow-table (`_ref`). Une future itération pourra aligner device sur le même système `sync_listeMAJ`.
- Les scripts SQL doivent être appliqués manuellement sur Intranet et Cloud avant la mise en route du daemon.

---

## Annexe D — Organisation des fichiers (3 juin 2026)

```
eLarcProfPy/
├── main.py                 # Point d'entrée (QApplication + LoginWindow + CLI)
├── common/
│   ├── network.py          # detect_network()
│   ├── database.py         # Database (singleton db)
│   ├── auth.py             # AuthManager + OAuth2Manager
│   ├── session.py          # UserRole, ConnMode, Session (singleton session)
│   ├── sqlite_init.py      # SQLiteInit (DDL, seed, session, module_config)
│   ├── sync.py             # SyncManager (diff, pull, push, conflict)
│   ├── theme.py            # ThemeManager (palette + font scaling)
│   ├── grid_config.py      # GridConfig loader (grid_configs/*.json)
│   └── logger.py           # log()
├── views/
│   ├── login.py            # LoginWindow (4 onglets)
│   ├── password.py         # ChangePinDialog + ChangePasswordDialog
│   ├── main_window.py      # MainWindow (top bar + grille)
│   ├── eval_manager.py     # _SlotBar, EvalManagerWindow
│   └── evaluation_panel.py # Obsolète (non importé par main_window)
├── grid_configs/
│   └── pei.json            # Configuration grille PEI
├── LarcCloudSync/          # Daemon sync Intranet ↔ Cloud
│   ├── sync_agent/         # Agent Python (boucle, diff, push/pull)
│   ├── sql/                # Scripts SQL (colonnes sync + triggers)
│   └── config.json         # Fréquences de sync par table
├── export_to_sqlite.py     # Export PostgreSQL → SQLite
└── docs/                   # Documentation algorithmique
```

---

## Itération 21 — Dashboard HomeWindow + Login refactor (9 juillet 2026)

### Contexte

L'application passait directement du login au `MainWindow` (grille de notes). Il manquait un écran intermédiaire pour orienter le professeur vers ses différentes activités.

### Réalisations

#### 1. `views/home_window.py` — Dashboard (~800 lignes)

Écran intermédiaire login → notes avec :

**Colonne gauche** :
- Carte Profil : nom, email, rôle, année, trimestre, nb classes-matières, nb élèves
- Indicateurs connexion serveur : `Intranet : ●/○`, `Cloud : ●/○`, `Hors connexion`
- Carte Synchro : date dernière sync, source, compteur modifs non synchronisées par table
- Bouton **Synchroniser** (connexion serveur auto + pull/push)

**Colonne droite** — boutons conditionnels par programme :
- Section PEI (visible si prof enseigne PEI/MYP) :
  - Unité de groupes de matières, Unités interdisciplinaires, Projet Personnel
  - **Mes classes PEI** (visible seulement si serveur connecté)
- Section DP (visible si prof enseigne DP/DPFr/DPEn) :
  - Unité de groupes de matières, TDC, CAS, Mémoire
  - **Mes classes DP** (visible seulement si serveur connecté)
- **Professeur principal** (visible si fk_headteacher_id = prof)
- **Déconnexion**

Chaque bouton a sa propre requête de visibilité dans `_detect_button_visibility()`.

#### 2. `views/login.py` — Refactor complet

- Style uniformisé avec `_STYLE` property + QSS classes (`.btn-primary`, `.btn-google`, `.panel`, etc.)
- Espacement Fibonacci via `theme_manager.phi_theme.spacing.spacing()`
- Taille fenêtre 480×780 (ratio φ ≈ 1.625)
- i18n : `Translator.instance(lang).load_dir(...)` + `_()` pour tous les textes
- 18 clés `prof_login.*` dans LarcCommon fr.json/en.json
- Indicateurs réseau dans le header, pas dans le bandeau bleu

#### 3. `common/theme.py` — Ajout phi_theme

- Property `ThemeManager.phi_theme` → `PhiTheme(ThemeConfig) + PhiScale(base_spacing=4)`
- `_M3Colors` mappe la palette eLarcProfPy → propriétés M3 (primary, surface, error, outline, etc.)
- Reset automatique au `set_active()`

#### 4. Mapping boutons → vues cibles (`_BTN_VIEW`)

```
college_notes_0    ← Unité de groupes PEI (ex-MainWindow)
college_notes_opt1 ← Unités interdisciplinaires
college_notes_opt2 ← Projet Personnel
colleges_eleves    ← Mes classes PEI (serveur direct, pas SQLite)
lycee_notes_0      ← Unité de groupes DP
lycee_notes_opt1   ← Mémoire
lycee_notes_opt2   ← TDC
lycee_notes_opt3   ← CAS
lycee_eleves       ← Mes classes DP (serveur direct)
college_bulletin   ← Professeur principal PEI (SQLite)
lycee_bulletin     ← Professeur principal DP (SQLite)
```

#### 5. Renommage global

- "eLarcProf" → "LarcProf" dans tous les titres de fenêtres
- `main_window.py` titre → "LarcProf — College Notes"

#### 6. Corrections

- `EvalManagerWindow._on_manager_closed` wrappé dans try/except RuntimeError (bug destroyed lambda)
- Ne pas utiliser `_` comme variable throwaway (écrase `_()` i18n) → `_outer`, `_ignored`

### Fichiers modifiés/créés

| Fichier | Action |
|---|---|
| `views/home_window.py` | Créé (~800 lignes) |
| `views/login.py` | Reconstruit (~1180 lignes) |
| `views/main_window.py` | Titre + fix destroyed lambda |
| `common/theme.py` | +phi_theme, +_M3Colors (~370 lignes) |
| `../LarcCommon/larccommon/l10n/fr.json` | +18 clés prof_login.* |
| `../LarcCommon/larccommon/l10n/en.json` | +18 clés prof_login.* |
| `../LarcSuperviseur/AGENTS.md` | +eLarcProfPy section complète |
| `docs/etat_projet.md` | Mis à jour |
| `docs/historique_construction.md` | Itération 21 |

---

## Itération 22 — Gradient, sauvegarde, init, sync (10/07/2026)

### Objectif
Corriger l'affichage des notes (couleurs, padding, centrage), la sauvegarde locale (nom de colonne), l'initialisation de base (take_teacher_data absent), et les performances sync.

### Réalisé

#### 1. Gradient pastel des notes
- **ColorItem** : sous-classe de QTableWidgetItem avec `_bg` et surcharge `data(UserRole+3)`
- **ColorDelegate** : delegate custom qui peint fond + texte centré (contourne le thème Windows natif qui ignore setBackground)
- Couleurs : rouge(0) → blanc(milieu) → vert(max), interpolées
- Recalcul immédiat dans `_on_cell_changed` via `ColorItem.set_bg()`

#### 2. Top bar — nature à la place du doublon label
- Supprimé `lbl_label` (redondant avec `idx_lbl`) dans `_update_icons`
- Largeur nature doublée (89→178px)
- Espace entre nature et critères

#### 3. Filtrage des critères par évaluation
- `_crit_visible()` vérifie `crit_a/b/c/d` de chaque évaluation dans `larcauth_evaluation`
- Seules les colonnes des critères activés apparaissent (pas uniquement le toggle global)

#### 4. EditTriggers Excel-like + tri + cellules centrées
- `SelectedClicked | EditKeyPressed | AnyKeyPressed`
- `setSortingEnabled(True)` + tri Nom/Prenom toggle
- `Qt.AlignCenter` partout

#### 5. Sauvegarde locale (nom de colonne)
- `learner_has_termsubject_ptr_id` accepté en plus de `fk_student_id` dans `_fill_grille`
- Tables PEI/DP utilisent ce nom de colonne pour le matching élève

#### 6. Boutons adaptatifs online/offline
- "Synchroniser" quand connecté, "Enregistrer" quand hors ligne
- Tooltips mis à jour

#### 7. Initialisation base (take_teacher_data)
- `_on_create` appelait `init()` mais pas `take_teacher_data` → base vide
- Correction : `take_teacher_data` appelé après `init()`

#### 8. sync_state migration + non-bloquant
- Migration : recrée `sync_state` si ancien schéma sans `table_name`
- `_touch_sync_state` rendu non-bloquant (try/except) — ne rollback plus la transaction

#### 9. Performance sync
- Commit unique par table (plus par cellule)
- Log verbeux retiré d'`apply_pull`
- Traces timing `[SYNC]` par table pour diagnostic

#### 10. Divers
- Fenêtre maximisée au lancement (`showMaximized`)
- `QStatusBar` import corrigé
- `disconnect` warning corrigé (connect une seule fois)
- Traces `[INIT]` dans sqlite_init
- Audit padding/margin documenté dans AGENTS.md

### Fichiers modifiés

| Fichier | Action |
|---|---|
| `views/main_window.py` | Gradient, ColorItem, ColorDelegate, tri, centrage, save fix, boutons adaptatifs, disconnect fix, showMaximized |
| `views/home_window.py` | showMaximized |
| `views/login.py` | take_teacher_data dans _on_create |
| `common/sync.py` | Commit unique par table, retrait log verbeux, traces timing |
| `common/sqlite_init.py` | Migration sync_state, _touch_sync_state non-bloquant, traces [INIT] |
| `../LarcSuperviseur/AGENTS.md` | Mise à jour 10/07/2026 |
| `docs/historique_construction.md` | Itération 22 |
