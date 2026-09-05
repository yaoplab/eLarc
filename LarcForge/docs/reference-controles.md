# Référence des contrôles

> Généré automatiquement par `python -m larcforge docs` à partir de
> l'auto-découverte des linters (`scripts/*.py`) et des reviewers
> (`.claude/skills/*-review.md`). **Ne pas éditer à la main** — toute
> modification doit se faire dans le script/skill source puis régénérer.

## Linters (11)

### [AUTH] Authentification

- **Script** : `lint_auth_checker.py`
- **Catégorie** : `auth`
- **Skill** : `auth-intranet`
- **Description** : Credentials en dur, session contournée, mots de passe en clair

**Vérifications exactes** (docstring du linter) :

```text
Linter: vérifie les règles des skills auth (auth-oauth2, auth-intranet, auth-pin).

Détecte :
  - Credentials en dur dans le code source
  - session.is_authenticated = True hors de LoginWindow
  - Mots de passe en clair dans les logs
  - appels db.server_conn sans vérifier is_server_connected

Usage:
  python scripts/lint_auth_checker.py                      # Tous les projets
  python scripts/lint_auth_checker.py --dir .\LarcProf       # Un seul projet
  python scripts/lint_auth_checker.py --json                 # Sortie JSON
```

---

### [C] Pré-soumission

- **Script** : `lint_preflight.py`
- **Catégorie** : `checklist`
- **Skill** : `preflight`
- **Description** : Check-list mécanique C1-C13 avant soumission

**Vérifications exactes** (docstring du linter) :

```text
lint_preflight.py - Linter de pre-soumission (check-list mecanique C1-C12).

Regles verifiees automatiquement :
  C1  - on_primary_container interdit (crash runtime)
  C2  - QMessageBox + QLineEdit/QTextEdit interdit (utiliser ThemedDialog)
  C3  - QDialog direct interdit (heriter de ThemedDialog)
  C4  - Label AU-DESSUS du champ (Q8) - jamais addWidget(QLabel) apres addWidget(field)
  C5  - theme_manager.image.X restreint a logo et theme_btn
  C6  - Colonnes de tableau coherentes (max(col) < len(headers))
  C7  - @safe_slot obligatoire sur tout slot _on_*
  C9  - Tooltip obligatoire sur bouton icone-seul
  C11 - QDateEdit/QDateTimeEdit doit avoir setMinimumWidth (Q10d)
  C12 - QDateTimeEdit/QDateEdit/QComboBox QSS sans padding uniforme >= space_sm (Q10c)
  C13 - Erreurs silencieuses : except:pass, print_exc() sans QMessageBox, return muet

Usage:
  python scripts/lint_preflight.py --dir .\LarcRH
  python scripts/lint_preflight.py --json
```

---

### [COV] Couverture de tests

- **Script** : `lint_test_coverage.py`
- **Catégorie** : `tests`
- **Skill** : `larc-testing`
- **Description** : Modules common/views sans fichier de test correspondant

**Vérifications exactes** (docstring du linter) :

```text
Linter: vérifie la couverture de tests (skill testing).

Vérifie que chaque module common/ et views/ a un fichier de test correspondant.

Usage:
  python scripts/lint_test_coverage.py                        # Tous les projets
  python scripts/lint_test_coverage.py --dir .\LarcSuperviseur  # Un seul projet
  python scripts/lint_test_coverage.py --json                   # Sortie JSON
```

---

### [CTR] Contraste palette

- **Script** : `lint_palette_contrast.py`
- **Catégorie** : `theme`
- **Skill** : `color-rules`
- **Description** : Contraste texte/fond insuffisant ou inversé dans la palette (background vs text)

**Vérifications exactes** (docstring du linter) :

```text
Linter : contraste de la palette — texte vs fond (skill color-rules, règle D8).

Vérifie que les variables de TEXTE (text_strong / text_soft / text_disabled)
sont correctement contrastées vis-à-vis des variables de FOND
(surface / background / surface_variant), dans ``larccommon/theme.py`` :

  - thème clair  : texte plus FONCÉ que le fond (luminance texte < fond)
  - thème sombre : texte plus CLAIR que le fond  (luminance texte > fond)
  - ratio WCAG minimum par paire (AA 4.5:1 pour le texte normal, 3:1 seuil dur)

Lecture par AST (comme larcforge/taxonomy.py) — aucun import, donc aucun effet
de bord PySide6/phibuilder, le scan reste valide même si theme.py ne s'importe pas.

Usage:
  python scripts/lint_palette_contrast.py            # Rapport texte
  python scripts/lint_palette_contrast.py --json     # Sortie JSON (liste)
  python scripts/lint_palette_contrast.py --fix-only # Liste compacte
```

---

### [D] Couleurs palette

- **Script** : `lint_d1_color_checker.py`
- **Catégorie** : `theme`
- **Skill** : `color-rules`
- **Description** : Couleurs hex hardcodées et contrastes non conformes à la palette

**Vérifications exactes** (docstring du linter) :

```text
lint_d1_color_checker.py — Linter Design System Larc (règles D1, D3, D4, D5, J7).

Vérifications disponibles :

  D1 — setText() HTML : chaque balise (<b>, <span>, etc.) DOIT avoir
       `color:{p.text_strong}` ou `color:{p.text_soft}` explicite.
       Sans cela, le texte hérite du QPalette (NOIR) et devient illisible
       en mode dark.

  J7 — WA_StyledBackground : tout M3Frame/QWidget/QFrame avec un background
       via QSS DOIT avoir `setAttribute(Qt.WA_StyledBackground, True)`.
       Sans cela, le widget utilise son rendu interne (phibuilder / Qt natif)
       et le fond QSS est ignoré.

  D3 — Couleurs hex hardcodées : toute couleur hex (#xxxxxx) dans un
       setStyleSheet() NE réagit PAS au changement de thème.
       Remplacer par les tokens {p.primary}, {p.surface}, etc.

  D4 — Contrastes insuffisants :
       D4a : font-size < 12px AVEC color: {p.text_soft}
       D4b : background: {p.surface_variant} AVEC color: {p.text_soft}

  D5 — text_soft dans setStyleSheet() inline : toute occurrence de
       `color: {p.text_soft}` dans un setStyleSheet() avec string literal
       (pas _STYLE). Ces appels échappent à l'analyse de contexte et
       créent du "gris sur gris" en dark si le widget hérite d'un fond
       surface_variant.

  D6 — Réactivité au thème : toute classe qui utilise des tokens palette
       dans un setStyleSheet() inline DOIT avoir une connexion
       `ds.theme_changed.connect(...)` ou `theme_changed.connect(...)`
       dans son __init__ ou _build_ui. Sans cela, le widget ne réagit
       pas au changement de thème et conserve ses couleurs d'origine.
       Les classes héritant de ThemedWidget ou ThemedDialog sont exonérées.

  D7 — Complétude de _restyle() : toute classe qui a theme_changed.connect
       ET des setStyleSheet() palette-dépendants DOIT avoir une méthode
       _restyle() qui met à jour TOUS les widgets concernés.
       D7 compare les targets de setStyleSheet() dans __init__/_build_ui
       avec ceux dans _restyle(). Si un widget est stylé dans le builder
       mais PAS dans _restyle() → violation.

Usage:
    python scripts/lint_d1_color_checker.py
    python scripts/lint_d1_color_checker.py --dir .\LarcSuperviseur
    python scripts/lint_d1_color_checker.py --json
    python scripts/lint_d1_color_checker.py --fix-only
    python scripts/lint_d1_color_checker.py --rule D5       # Uniquement D5
    python scripts/lint_d1_color_checker.py --rule D1+J7+D3+D4+D5  # Tout
```

---

### [DB] Connexions DB

- **Script** : `lint_db_checker.py`
- **Catégorie** : `data`
- **Skill** : `database-operations`
- **Description** : Import psycopg2 hors database.py, singleton ignoré, credentials en dur

**Vérifications exactes** (docstring du linter) :

```text
Linter: vérifie les règles du skill database-operations.

Détecte :
  - import psycopg2 hors de database.py
  - Instanciation directe de Database() (doit utiliser le singleton db)
  - db.server_conn sans vérification is_server_connected
  - Credentials de connexion en dur

Usage:
  python scripts/lint_db_checker.py                        # Tous les projets
  python scripts/lint_db_checker.py --dir .\LarcProf         # Un seul projet
  python scripts/lint_db_checker.py --json                   # Sortie JSON
```

---

### [FS] Taille des fichiers

- **Script** : `lint_file_size.py`
- **Catégorie** : `filesize`
- **Skill** : `pyside6-wrapper`
- **Description** : Fichiers dépassant 1000 lignes — refactorisation requise

**Vérifications exactes** (docstring du linter) :

```text
Linter: vérifie la règle des 1000 lignes (skill pyside6-wrapper, sous-système F).

Usage:
  python scripts/lint_file_size.py                           # Tous les projets
  python scripts/lint_file_size.py --dir .\LarcSuperviseur     # Un seul projet
  python scripts/lint_file_size.py --threshold 500             # Seuil personnalisé
  python scripts/lint_file_size.py --json                      # Sortie JSON
```

---

### [R] Hardcoding QSS

- **Script** : `lint_qss_hardcoding.py`
- **Catégorie** : `theme`
- **Skill** : `zero-hardcoding`
- **Description** : Valeurs px/couleurs codées en dur dans les QSS (tokens ds.* attendus)

**Vérifications exactes** (docstring du linter) :

```text
lint_qss_hardcoding.py — Linter QSS pour le Design System Larc.

Détecte les valeurs en pixels hardcodées (border-radius, padding, font-size,
setFixedHeight, etc.) qui devraient utiliser les tokens ds.space_*, ds.radius_*,
s(), ou theme_manager.image.*.

Usage:
    python scripts/lint_qss_hardcoding.py
    python scripts/lint_qss_hardcoding.py --dir .\LarcSuperviseur     # rapport détaillé par fichier
    python scripts/lint_qss_hardcoding.py --dir .\LarcCommon          # répartition larccommon vs phibuilder
    python scripts/lint_qss_hardcoding.py --dir .\LarcCommon --group-by package   # par package (ex: larccommon/widgets)
    python scripts/lint_qss_hardcoding.py --dir .\LarcCommon --group-by file      # liste plate
    python scripts/lint_qss_hardcoding.py --dir .\LarcCommon --group-by auto      # auto : package si profondeur ≥ 2, sinon subdir
    python scripts/lint_qss_hardcoding.py --fix
    python scripts/lint_qss_hardcoding.py --threshold P0
    python scripts/lint_qss_hardcoding.py --json
    python scripts/lint_qss_hardcoding.py --fix-only         # compact fichier:ligne (pre-commit, comme lint-dlinter)
    python scripts/lint_qss_hardcoding.py --rule Q2w        # audit étendu : états vides .information + .warning

Conforme au Sous-système R du skill design-system-larc.

Règle Q1+Q3 (companion des correctifs ergonomiques du Sous-système Q) :
    Toute table M3TableWidget/QTableWidget INTERACTIVE (cellDoubleClicked,
    cellClicked, itemDoubleClicked ou itemClicked connecté) doit avoir :
      • viewport().setCursor(Qt.PointingHandCursor)   (Q1 — affordance)
      • installEventFilter(self)                      (Q3 — Entrée-ouvre)
      • une méthode def eventFilter() dans le même bloc (Q3 — sinon
        l'installEventFilter est orphelin et Qt l'ignore silencieusement)

Règle Q2 (companion du Sous-système Q) :
    Tout QMessageBox.information dont le message est un état vide (zéro résultat :
    clé i18n .no_xxx (.no_users / .no_address / .no_results...), littéral FR/EN
    « aucun / rien / vide / introuvable / not found / no results / empty... »)
    DOIT être remplacé par un état vide INLINE (_empty_state : icône + message dans
    le panneau, tableau caché). Jamais de popup modale pour 0 résultat.
    Variante --rule Q2w (opt-in, audit) : étend la détection aux
    QMessageBox.warning contenant un marqueur d'état vide (ex: parent.error.no_address).
    Les validations (_selected / _available / _required) ne sont PAS des états vides.
```

---

### [REACT] Réactivité thème

- **Script** : `audit_theme_reactive.py`
- **Catégorie** : `theme`
- **Skill** : `theme-reactivity`
- **Description** : Classes non conformes à la réactivité thème (_STYLE / _restyle)

**Vérifications exactes** (docstring du linter) :

```text
Audit de réactivité au thème — LarcSuperviseur, LarcSecretaire, LarcProf.

Scanne tous les fichiers Python des répertoires views/ des 3 modules.
Pour chaque classe, détecte :
  - Les appels setStyleSheet() qui utilisent une palette dynamique
    (p.X, ds.p.X, theme_manager.palette.X)
  - La présence d'une connexion theme_changed (ds.theme_changed.connect)
  - La présence d'une méthode _restyle / restyle

Rapporte les classes non conformes sous forme de tableau.
```

---

### [S] Safe slots PySide6

- **Script** : `lint_safe_slot.py`
- **Catégorie** : `qt`
- **Skill** : `pyside6-wrapper`
- **Description** : Slots sans @safe_slot, anti-patterns Qt, variable _ écrasée

**Vérifications exactes** (docstring du linter) :

```text
Linter: vérifie les règles du skill pyside6-wrapper.

Vérifie statiquement :
  - Slots Qt sans @safe_slot
  - lambda: nu dans connect()
  - except Exception: pass muet
  - print() dans les handlers
  - Variable _ utilisée (écrase i18n)

Usage:
  python scripts/lint_safe_slot.py                           # Tous les projets
  python scripts/lint_safe_slot.py --dir .\LarcSuperviseur     # Un seul projet
  python scripts/lint_safe_slot.py --json                      # Sortie JSON
```

---

### [V] Finitions UI

- **Script** : `lint_ui_quality.py`
- **Catégorie** : `ui`
- **Skill** : `ui-quality`
- **Description** : Emojis, tooltips manquants, layouts sans stretch, gaps icône-texte

**Vérifications exactes** (docstring du linter) :

```text
lint_ui_quality.py — Linter de qualité visuelle et finition UI.

Détecte les défauts de finition que les linters de tokens (D-linter, R-linter)
ne voient pas : emojis, widgets orphelins, tooltips manquants, layouts sans stretch.

Règles couvertes :
  V1 — Emojis dans l'UI (doit utiliser md3_icon())
  V2 — Tailles codées en dur sans token ds.*
  V6 — Boutons icône-seuls sans setToolTip()
  V7 — Layouts sans addStretch()
  V8 — Boutons icône+texte sans text-align: left (gap icône↔texte, sidebar-spec K26)

Usage:
  python scripts/lint_ui_quality.py                      # Tous les projets
  python scripts/lint_ui_quality.py --dir .\LarcRH        # Un seul projet
  python scripts/lint_ui_quality.py --json                 # Sortie JSON
  python scripts/lint_ui_quality.py --fix                  # Rapport avec suggestions
```

---

## Reviewers (9)

### auth-review

- **Catégorie** : `quality`
- **Déclencheur** : audit auth, vérifie auth, check auth, revue auth, authentification, login, OAuth
- **Description** : Audit de l'authentification — OAuth2 Google, PostgreSQL local, PIN hors connexion

**Procédure et vérifications exactes** :

### Auth Review — Audit Authentification Larc

Vérifier la configuration et la sécurité des 3 modes d'authentification.

#### Procédure

1. Lancer les linters :
```bash
python D:/projets/scripts/lint_auth_checker.py
python D:/projets/scripts/lint_db_checker.py
```

2. Vérifier la configuration :
```bash
grep -A2 "\[OAuth2\]" LarcCommon/config.ini
grep -A5 "\[IntranetDatabase\]" LarcCommon/config.ini
```

3. Tester la connexion :
```bash
python -c "from larccommon.database import db; print('INTRANET OK' if db.connect_intranet() else 'INTRANET FAIL')"
```

#### Checklist

##### OAuth2
- [ ] [OAuth2] ClientID et ClientSecret dans config.ini
- [ ] URI http://localhost:8765/callback autorisée Google Console
- [ ] Domaine arc-en-ciel.org (hd)
- [ ] Timeout 120s
- [ ] Utilisateur dans larcauth_aecuser
- [ ] Flag role non NULL

##### Intranet
- [ ] [IntranetDatabase] Host/Port/DB/User/Pass dans config.ini
- [ ] db.connect_intranet() → True
- [ ] Password hash = SHA-256
- [ ] session.conn_mode = ConnMode.INTRANET

##### PIN
- [ ] session_cache.db existe
- [ ] Premier login Intranet/OAuth2 AVANT PIN
- [ ] PIN = 4-8 chiffres, isdigit()
- [ ] pin_hash = SHA-256
- [ ] session.conn_mode = ConnMode.OFFLINE

#### Skills de référence

- `auth-oauth2` — Google OAuth2 PKCE
- `auth-intranet` — PostgreSQL local SHA-256
- `auth-pin` — PIN hors connexion
- `database-operations` — connexions DB

---

### design-review

- **Catégorie** : `quality`
- **Déclencheur** : audit design, vérifie le design, check design, revue design, design review
- **Description** : Audit complet du design system Larc - tokens, couleurs, hardcoding, réactivité au thème

**Procédure et vérifications exactes** :

### Design Review — Audit Design System Larc

Lancer les 3 linters design et produire un rapport consolidé.

#### Procédure

1. Lancer les linters :
```bash
python D:/projets/scripts/lint_d1_color_checker.py --rule D1+J7+D3+D4+D5+D6+D7 --fix-only
python D:/projets/scripts/lint_qss_hardcoding.py --fix-only
python D:/projets/scripts/audit_theme_reactive.py
python D:/projets/scripts/lint_ui_quality.py
```

2. Pour chaque violation, mapper vers la règle du skill :
   - D1 → color-rules : couleur explicite manquante
   - D3 → color-rules : hex hardcodé
   - R1-R16 → zero-hardcoding : px en dur
   - J1-J7 → theme-reactivity : thème non réactif
   - K1-K26 → sidebar-spec : sidebar non conforme
   - V1-V8 → ui-quality : finition UI (V8 = gap icône↔texte des boutons, 8px = ds.space_xs)

3. Proposer la correction en citant la règle.

#### Skills de référence

- `design-tokens` — tokens numériques
- `color-rules` — palette et règles couleur
- `zero-hardcoding` — règle absolue tokens
- `theme-reactivity` — pattern _STYLE + _restyle_all
- `sidebar-spec` — spécification visuelle sidebar
- `ergonomics` — patterns de composition M3+Fibonacci
- `card-dashboard` — vignettes KPI
- `student-record` — dossier élève

#### Format du rapport

```markdown
#### Rapport design-review : `fichier.py`

##### ❌ Violations (P0)
| Ligne | Règle | Code actuel | Correction |
|---|---|---|---|
| 45 | R7 | setContentsMargins(6,6,6,6) | setContentsMargins(ds.space_sm, ds.space_sm, ds.space_sm, ds.space_sm) |

##### ✅ Conforme
- Utilise ds.flat_input_qss() pour les champs

##### 📊 Progression
X violations → 0 cible
```

---

### feature-review

- **Catégorie** : `quality`
- **Déclencheur** : audit feature, vérifie feature, check feature, revue feature, événements, event generator, vignettes, card dashboard, dossier élève
- **Description** : Audit des fonctionnalités — événements, vignettes, dossier élève, widgets

**Procédure et vérifications exactes** :

### Feature Review — Audit Fonctionnalités Larc

Vérifier la conformité design des fonctionnalités métier.

#### Procédure

1. Lancer les linters design :
```bash
python D:/projets/scripts/lint_d1_color_checker.py --rule D1+J7+D3+D4+D5+D6+D7 --fix-only
python D:/projets/scripts/lint_qss_hardcoding.py --fix-only
```

2. Audit spécifique :
```bash
### Event Generator
grep -rn "event_color\|event_icon" views/ | grep -v test_
### Card Dashboard
grep -rn "CardFields\|CARD_SECRETAIRE\|CARD_SUPERVISEUR\|CARD_PROF" views/
### Student Record
grep -rn "notes_json\|dossier_panel\|student_form" views/
### Widgets bruts (dette technique)
grep -rn "QPushButton\|QLineEdit\|QComboBox\|QTableWidget" --include="*.py" views/
```

#### Checklist (toutes features)
- [ ] 0 couleur hex hardcodée
- [ ] 0 px en dur
- [ ] theme_changed → _restyle_all() dans chaque classe
- [ ] @safe_slot sur tous les handlers
- [ ] ThemedWidget pour conteneurs avec QSS background
- [ ] Traductions i18n pour tous les textes

#### Skills de référence

- `[[event-generator]]` — wizard événements élèves
- `[[card-dashboard]]` — vignettes KPI configurables
- `[[student-record]]` — dossier élève par catégories
- `[[toolkit-reference]]` — catalogue widgets phibuilder
- `[[dashboard-pattern]]` — pattern canonique tableau de bord
- `[[search-detail-pattern]]` — pattern recherche + fiche détail
- `[[form-pattern]]` — pattern formulaire par sections
- `[[card-grid-pattern]]` — pattern grille responsive

---

### graphify-review

- **Catégorie** : `quality`
- **Déclencheur** : audit graphe, vérifie graphe, check graphify, revue graphe, knowledge graph, god nodes
- **Description** : Audit du graphe de connaissances — fraîcheur, complétude, god nodes, communautés

**Procédure et vérifications exactes** :

### Graphify Review — Audit du Graphe de Connaissances Larc

Vérifier que le graphe de connaissances est à jour et cohérent avec le codebase.

#### Procédure

1. Vérifier la fraîcheur du graphe :
```bash
graphify god-nodes --top 10 --graph graphify-out/graph.json
```

2. Comparer avec les fichiers récemment modifiés :
```bash
git diff --name-only HEAD~1 | head -20
graphify query "Quels fichiers sont impactés par les derniers changements ?"
```

3. Vérifier les god nodes attendus :
```bash
graphify god-nodes --top 20 --json
```

4. Tracer un chemin entre deux modules clés :
```bash
graphify path LarcCommon LarcSuperviseur
graphify path LarcCommon LarcProf
```

5. Régénérer si nécessaire :
```bash
graphify extract . --code-only --force
graphify cluster-only .
```

#### Checklist

##### Fraîcheur
- [ ] graph.json modifié après le dernier refactoring
- [ ] Nombre de nœuds stable (pas de chute >10%)
- [ ] Pas de fichiers .py absents du graphe
- [ ] Communautés nommées (ou --no-label assumé)

##### Complétude
- [ ] God nodes couvrent les modules principaux (DataLoader, ThemeManager, MainWindow, LoginWindow)
- [ ] Tous les modules Larc* ont au moins 1 nœud
- [ ] Les imports inter-modules sont capturés
- [ ] Les fichiers SQL sont parsés (tree-sitter-sql installé)

##### Cohérence
- [ ] God nodes cohérents avec l'architecture documentée
- [ ] Pas de communautés orphelines (1-2 nœuds isolés)
- [ ] Les dépendances LarcCommon → apps sont visibles

#### Skills de référence

- `graphify` — graphe de connaissances du codebase
- `database-operations` — connexions DB
- `toolkit-reference` — architecture phibuilder

---

### infra-review

- **Catégorie** : `quality`
- **Déclencheur** : audit infra, vérifie infra, check infra, revue infra, base de données, synchronisation, sync, graphify, graphe
- **Description** : Audit de l'infrastructure — base de données, synchronisation, graphe de connaissances

**Procédure et vérifications exactes** :

### Infra Review — Audit Infrastructure Larc

Vérifier les connexions PostgreSQL, la synchronisation, et le graphe de connaissances.

#### Procédure

1. Lancer les linters :
```bash
python D:/projets/scripts/lint_db_checker.py --json
python D:/projets/scripts/lint_auth_checker.py --json
python D:/projets/scripts/lint_file_size.py --stats
```

2. Tester les connexions :
```bash
python -c "from larccommon.database import db; print('INTRANET OK' if db.connect_intranet() else 'FAIL')"
```

3. Vérifier le graphe de connaissances :
```bash
graphify god-nodes --top 10 --graph graphify-out/graph.json
graphify query "Quelles sont les connexions principales entre les modules ?"
```

4. Tester la synchronisation (si LarcCloudSync) :
```bash
python -c "from thothcommon.sync import sync_manager; print(sync_manager.sync_table('larcauth_aecuser'))"
```

#### Checklist Database
- [ ] [IntranetDatabase] et [SupabaseDatabase] dans config.ini
- [ ] db.connect_intranet() → True
- [ ] 0 import psycopg2 hors de database.py
- [ ] 0 psycopg2.connect() direct
- [ ] is_server_connected vérifié avant requête
- [ ] disconnect_all() à la fermeture

#### Checklist Sync
- [ ] Connexion locale + cloud OK
- [ ] sync_version présent
- [ ] ON CONFLICT DO NOTHING sur INSERT
- [ ] sslmode=require sur cloud
- [ ] Mode dégradé si cloud inaccessible

#### Checklist Graphify
- [ ] Graphe à jour : `graphify god-nodes --top 5`
- [ ] graphify-out/graph.json < 7 jours
- [ ] God nodes cohérents avec l'architecture
- [ ] Pas de fichiers critiques absents du graphe
- [ ] Régénération après changement structurel

#### Skills de référence

- `database-operations` — connexions DB
- `sync` — synchronisation local↔cloud
- `auth-intranet` — auth PostgreSQL
- `graphify` — graphe de connaissances du codebase

---

### pyside6-review

- **Catégorie** : `quality`
- **Déclencheur** : audit pyside6, vérifie pyside6, check pyside6, revue pyside6, vérifie les slots, vérifie safe_slot
- **Description** : Audit du code PySide6 — @safe_slot, anti-patterns Qt, règle des 1000 lignes

**Procédure et vérifications exactes** :

### PySide6 Review — Audit PySide6 Larc

Lancer les linters PySide6 et vérifier les règles manuelles.

#### Procédure

1. Lancer les linters :
```bash
python D:/projets/scripts/lint_safe_slot.py --dir .
python D:/projets/scripts/lint_file_size.py --dir . --stats
```

2. Vérifier manuellement les règles sans linter :
   - **D1** : `widget.update()` sur widget pas monté → `try: except RuntimeError: pass`
   - **D2** : Signaux cross-thread → `Signal` + `@Slot()` avec `QThread`
   - **B3** : Dialogue fermé avant d'en ouvrir un nouveau
   - **B4** : Dialogues en lazy init (pas dans `__init__`)

3. Vérifier la règle "pas de `theme=phi`" :
```bash
grep -rn "theme=phi" --include="*.py" . | grep -v test_ | grep -v __pycache__
```

#### Skills de référence

- `pyside6-wrapper` — @safe_slot, anti-patterns, 1000 lignes
- `theme-reactivity` — règle G (pas de theme=phi)

#### Format du rapport

```
#### PySide6 Review : `fichier.py`

##### Bloquant (P0)
- Ligne 45 : lambda nu → slot nommé + @safe_slot
- Ligne 67 : variable `_` → renommer en `_outer`

##### Recommandé (P1)
- Ligne 120 : dialogue dans __init__ → lazy init

##### Stats
- lint_safe_slot.py : X violations
- lint_file_size.py : X fichiers > 1000 lignes
```

---

### scolarite-review

- **Catégorie** : `build`
- **Déclencheur** : construit LarcScolarité, crée page compta, vérifie scolarité, audit compta, build dashboard scolarité
- **Description** : Construction des pages LarcScolarité — règles métier + design system M3 Fibonacci

**Procédure et vérifications exactes** :

### Scolarité Review — Construction LarcScolarité

Agent spécialisé pour construire les pages de LarcScolarité. Vérifie les règles métier (scolarite-finance) et les 6 skills design avec le skeleton M3 Fibonacci.

#### Procédure

1. Lire la skill métier :
```bash
cat .claude/skills/scolarite-finance.md
```

2. Construire la page avec le skeleton M3 :
```python
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot

class MaPage(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setObjectName("ma_page")
        ds.theme_changed.connect(self._restyle)
        self._restyle()
        # ds.theme_changed.connect(self._restyle) dans __init__
        # Zéro hex, zéro px, WA_StyledBackground sur QFrame
```

3. Vérifier les règles métier : SF1-SF6, S1a-S1g, S2a-S2e, S3a-S3d, S4a-S4e, S5a-S5c

4. Lancer les linters :
```bash
python scripts/lint_qss_hardcoding.py --dir LarcCompta
python scripts/lint_d1_color_checker.py --dir LarcCompta
python scripts/lint_safe_slot.py --dir LarcCompta
```

#### Règles absolues
- Zéro hardcoding — tout passe par ds.*, s(), theme_manager.image.*
- Zéro hex — ds.p.* pour toutes les couleurs
- WA_StyledBackground sur tout QFrame avec background QSS
- @safe_slot sur tous les handlers
- theme_changed.connect sur toute classe avec QSS palette
- setObjectName() sur le widget principal

#### Skills de référence
- scolarite-finance, design-tokens, color-rules, zero-hardcoding
- theme-reactivity, ergonomics, dashboard-pattern, card-grid-pattern

---

### telemetry-review

- **Catégorie** : `quality`
- **Déclencheur** : audit télémétrie, audit erreurs, audit error_log, audit audit_log, audit mise à jour, revue télémetry, revue telemetry, check erreurs
- **Description** : Audit des 3 capacités télémétrie LARC — erreurs centralisées (R1), journal d'audit (R2), mise à jour douce (R3)

**Procédure et vérifications exactes** :

### Telemetry Review — Audit R1 + R2 + R3

Vérifier l'enregistrement centralisé des erreurs, le journal d'audit et la mise à jour douce.

#### Procédure

1. Lancer les linters :
```bash
python D:/projets/scripts/lint_safe_slot.py
python D:/projets/scripts/lint_file_size.py --stats
python D:/projets/scripts/lint_db_checker.py --json
python D:/projets/scripts/lint_qss_hardcoding.py
```

2. Vérifier le schéma déployé :
```bash
python -c "from larccommon.database import db; db.connect_intranet(); c=db.server_conn.cursor(); \
c.execute('SELECT count(*) FROM error_log'); print('error_log', c.fetchone()[0]); \
c.execute('SELECT count(*) FROM audit_log'); print('audit_log', c.fetchone()[0]); \
c.execute('SELECT count(*) FROM app_version'); print('app_version', c.fetchone()[0])"
```

3. Tester le reporter en réel :
```bash
python -c "from larccommon.error_reporting import get_reporter; r=get_reporter(); \
r and r.report('ERROR', 'test telemetry-review', context={'probe': True})"
```

#### Checklist R1 — Erreurs centralisées
- [ ] `report()` = `put_nowait` uniquement — aucun I/O, aucun raise sur le thread appelant
- [ ] Chaîne de dégradation complète : PG → spool SQLite → JSONL → compteur dropped
- [ ] Rejeu spool idempotent (`spool_id UNIQUE` + `ON CONFLICT DO NOTHING`)
- [ ] Flush par lot actif (5 s OU 100 événements), une seule INSERT multi-VALUES
- [ ] Connexion PG dédiée au reporter (pas de `db.server_conn` partagé entre threads)
- [ ] `sys.excepthook` + `threading.excepthook` installés par bootstrap
- [ ] `qInstallMessageHandler` : Fatal re-call l'ancien handler (jamais d'abort avalé)
- [ ] `@safe_slot` reporte (contexte `slot_label`), `log_error` alias fonctionnel
- [ ] Rotation fichier plat > 5 Mo (`.1/.2/.3`)
- [ ] `init_app` présent dans les 7 main.py, avant QApplication
- [ ] `stop()` via atexit + aboutToQuit, flush ≤ 2 s
- [ ] Tests Phase 1 (mock) verts : `pytest LarcCommon/tests/test_error_reporting.py test_error_spool.py -v`

#### Checklist R2 — Journal d'audit
- [ ] **Aucun `SET LOCAL`** sous autocommit (no-op silencieux) — `set_config(..., false)` partout
- [ ] `audit_context.attach(conn)` dans `connect_intranet` ET `connect_cloud`
- [ ] `refresh()` appelé aux points de login (LarcSecretaire, LarcProf)
- [ ] UPDATE : 1 ligne par champ modifié, champs inchangés ignorés, colonnes `sync_*` exclues
- [ ] `sync_source = 'daemon'` → aucune ligne d'audit
- [ ] INSERT/DELETE → `field = '*'` avec JSON complet
- [ ] `REVOKE INSERT, UPDATE, DELETE ON audit_log FROM PUBLIC` appliqué
- [ ] Index : `(ts DESC)`, `(user_id)`, `(table_name, ts DESC)`, `(table_name, row_id)`
- [ ] `row_id TEXT` (PK TEXT possible — `larcauth_evaluation`)
- [ ] `audit_trail` intact en archive ; `LarcSecretaire/common/audit.py` → `audit_log` (EVENT)
- [ ] Test intégration (si `LARC_PG_TEST=1`) : UPDATE avec `set_config('app.modified_by')` → lignes attendues

#### Checklist R3 — Mise à jour douce
- [ ] `check()` ne lève jamais (offline → None), channel filtré
- [ ] `--ff-only` partout ; retry ×3 ; worktree sale → refus propre
- [ ] Verrous `runtime/locks/<app>.pid` créés/supprimés (init_app/atexit)
- [ ] Mode silencieux : update au quit, aucun dialogue
- [ ] Mode informé : dialogue seulement si aucun modal ouvert
- [ ] Résultat (succès ET échec) journalisé dans `error_log`
- [ ] `pending_update.json` persistant → re-tentative au prochain démarrage
- [ ] Relance avec argv d'origine préservé

#### Skills de référence

- `error-reporting` — R1, `audit-log` — R2, `soft-update` — R3
- `sync` — sync/daemon exclus de l'audit ; `database-operations` — connexions DB

---

### testing-review

- **Catégorie** : `quality`
- **Déclencheur** : audit tests, vérifie les tests, check tests, revue tests, couverture tests, test coverage
- **Description** : Audit de la couverture de tests — infrastructure, Phase 1 (mock), Phase 2 (réel)

**Procédure et vérifications exactes** :

### Testing Review — Audit des Tests Larc

Vérifier l'infrastructure de test et la couverture.

#### Procédure

1. Vérifier l'infrastructure :
```bash
ls tests/conftest.py
grep "mock_db\|mock_session" tests/conftest.py
```

2. Lancer les tests Phase 1 (mock) :
```bash
pytest tests/ -v -m "not integration"
```

3. Lancer les tests Phase 2 (réel, si DB dispo) :
```bash
pytest tests/ -v -m integration
```

4. Vérifier la couverture :
```bash
pytest tests/ --cov=. --cov-report=term
python D:/projets/scripts/lint_test_coverage.py --dir . --stats
```

5. Vérifier les règles spécifiques :
```bash
python D:/projets/scripts/lint_safe_slot.py --dir .
```

#### Checklist

##### Phase 1 — Infrastructure
- [ ] `tests/conftest.py` avec `mock_db` et `mock_session`
- [ ] `pytest` et `pytest-qt` dans `pyproject.toml`
- [ ] `pytest tests/ -v -m "not integration"` → 100% vert
- [ ] Marqueur `integration` dans `pyproject.toml`

##### Phase 1 — Couverture
- [ ] Chaque module `common/` a un `test_<module>.py`
- [ ] Chaque `except Exception:` a un test mocké
- [ ] Chaque dialogue modal a un test
- [ ] ≥ 1 test de slot @safe_slot (H)
- [ ] ≥ 1 test de QThread (I)
- [ ] ≥ 1 test de theme reactivity (J)

##### Phase 2 — Tests réels
- [ ] `tests/test_integration_*.py` existe
- [ ] Tests marqués `@pytest.mark.integration`
- [ ] `pytest tests/ -v -m integration` → vert
- [ ] Requêtes critiques (INSERT/UPDATE/DELETE) ont un test réel

##### En cas d'échec
1. `pytest` non trouvé → `pip install pytest pytest-qt`
2. `qtbot` non trouvé → `pip install pytest-qt`
3. Tests Phase 2 échouent → `pg_isready` (PostgreSQL)
4. `mock_db` ne fonctionne pas → vérifier le path dans `patch()`

#### Skills de référence

- `larc-testing` — stratégie 2 phases
- `pyside6-wrapper` — tests @safe_slot (sous-système H)
- `theme-reactivity` — tests restyle (sous-système J)

---
