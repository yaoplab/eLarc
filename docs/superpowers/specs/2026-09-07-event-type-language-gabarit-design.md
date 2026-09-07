# Types d'événements : multilingue + principe gabarit (LarcCommon / LarcConfig)

Date : 2026-09-07
Statut : Validé par l'utilisateur (conversationnel), en attente de revue finale avant plan d'implémentation.

## Contexte et problème

La hiérarchie `larcauth_event_type_config` (voir
[2026-09-07-event-type-hierarchy-and-tree-ui-design.md](2026-09-07-event-type-hierarchy-and-tree-ui-design.md))
fonctionne, mais deux limites sont apparues à l'usage réel :

1. **Aucune dimension langue** — `label` est un texte brut, non traduit. Un utilisateur en
   anglais verrait les libellés français tels quels. Or l'école (comme le reste du système,
   cf. `larcauth_program`, `larcauth_lieu`) doit pouvoir fonctionner en 1, 2 ou 3 langues selon
   le déploiement.
2. **`LarcConfig` (`TypesPanel`) est 100 % lecture seule** — impossible de désactiver un type,
   de comprendre la hiérarchie parent/enfant (aucune colonne "Parent", seule l'indentation),
   ni d'ajouter un type sans changement de code.
3. **Le principe gabarit** (déjà en place pour les élèves — jamais d'`INSERT`/`DELETE`, des
   slots pré-configurés qu'on active via `enabled`) n'est pas appliqué ici : chaque nouveau
   type nécessite une migration SQL.

## Décisions actées pendant le brainstorming

### Multilinguisme — `fk_language` directement sur la table, pas de table de traduction

Option initialement proposée (rejetée) : une table séparée `larcauth_event_type_config_i18n`
(`event_type_config_id`, `fk_language`, `label`), arbre unique, un seul `is_active` par concept.

**Rejetée** au profit du pattern déjà utilisé partout ailleurs dans cette base
(`larcauth_program` : PYP/MYP/DPEn en `fk_language_id=1`, PP/PEI/DPFr en `fk_language_id=2` —
même `s_id` conceptuel, lignes dupliquées) :

- `fk_language` ajouté directement sur `larcauth_event_type_config`.
- Contrainte `UNIQUE(code)` → `UNIQUE(code, fk_language)`. `code` sert de lien "même concept
  entre langues" (rôle équivalent au `s_id` de `larcauth_program`), mais **rien ne s'appuie
  dessus comme clé étrangère** — exactement comme `larcauth_level.fk_program_id` référence
  `larcauth_program.id` (spécifique à une langue), jamais `s_id`.
- `parent_id` reste dans la même langue (arbre entièrement dupliqué par langue).
- **`is_active` devient par langue** — décision métier explicite : un type peut être actif
  côté francophone et inactif côté anglophone (ou l'inverse), les deux arbres sont
  indépendants sur ce point.
- `student_event.event_type_config_id` / `staff_event.event_type_config_id` **ne changent
  pas** — ils référencent toujours `larcauth_event_type_config.id`, comme aujourd'hui.
- Ajouter une 3ᵉ langue plus tard = dupliquer l'arbre une fois de plus dans
  `larcauth_language`, aucun changement de schéma ni de code (`EventTypeConfigService` est déjà
  paramétré par `fk_language`).
- Pour les 105 lignes existantes (aujourd'hui en français) : `fk_language=2` (FR) reçoit le
  texte réel actuel ; `fk_language=1` (EN) reçoit une **copie provisoire** du texte français,
  à corriger ensuite dans LarcConfig (pas de logique de repli côté code — un admin traduit).

### Principe gabarit — dimensionné sur l'usage réel, pas sur une estimation abstraite

Rejeté : une grille abstraite uniforme (5 catégories × 10 × 10, ou pire ×10 à tous les
niveaux) — surdimensionnée (jusqu'à ~11 000 lignes) et déconnectée de l'usage réel.

**Retenu** : partir de la hiérarchie **réellement active aujourd'hui** et lui ajouter une
marge de "potentiel" (+2 slots par parent existant, à chaque niveau) — pas de pré-remplissage
sous des branches qui n'existent pas encore.

| Niveau | Réel (actif aujourd'hui) | + Potentiel (+2 par parent réel) | Total par langue |
|---|---|---|---|
| 1 (racines) | 4 | +2 | 6 |
| 2 | 8 (sous les 4 racines réelles) | +2 par racine réelle (+8) | 16 |
| 3 | 35 (sous les 8 nœuds niv. 2 réels) | +2 par nœud niv. 2 réel (+16) | 51 |
| 4 (feuilles) | 54 (sous les 35 nœuds niv. 3 réels) | +2 par nœud niv. 3 réel (+70) | 124 |

**Total ≈ 217 nœuds par langue, ≈ 434 pour FR+EN** (contre 105 aujourd'hui — le double, pas
50× plus).

Décision explicite actée : si une des 2 racines "potentielles" est un jour activée pour une
**vraie nouvelle catégorie de premier niveau**, ses propres niveaux 2-3-4 seront ajoutés à ce
moment-là via une migration dédiée (événement de cycle de vie produit, pas une opération
courante d'école) — ce n'est pas un défaut du principe, c'est assumé comme tel.

### Convention des lignes "potentielles" (pas de troisième état, juste `is_active`)

Chaque ligne potentielle porte un **contenu réel dès sa création** — jamais de valeur
`NULL`/vide — sous une forme systématique reconnaissable :

- `code` : `type_niv{N}_{parent_code}_{NN}` (ex. `type_niv3_absence_school_01`)
- `label` : `Type_Niv{N}_{NN}` (ex. `Type_Niv3_01`)
- `is_active = FALSE`

Il n'y a **qu'un seul état** (`is_active` true/false) — pas de distinction "vide" vs
"désactivé" à gérer à part. C'est l'exact équivalent du placeholder `'Name of %'` déjà utilisé
pour les élèves (`LarcSecretaire/views/student_form.py:2975-2996`, cf. section suivante).

### Mécanisme d'activation — reproduit le pattern élèves existant

Trouvé et vérifié dans le code réel
([`LarcSecretaire/views/student_form.py:2975-2996`](../../../LarcSecretaire/views/student_form.py)) :

```python
# Prochain slot libre (01→40) : enabled=FALSE et nom placeholder
free = None
for rid, ln, en in all_rows:
    slot = rid % 100
    if 1 <= slot <= 40 and not en and ("Name of" in (ln or "")):
        free = slot
        break
```

Nuance clé (et raison pour laquelle un simple `WHERE is_active = FALSE` ne suffit pas) : un
élève désactivé (parti de l'école) **garde son vrai nom pour toujours** — son slot ne redevient
jamais "libre", pour ne pas corrompre l'historique. Même règle ici : un type d'événement
utilisé puis désactivé par un admin (ex. `event_incident`, déjà désactivé dans la migration
précédente) **ne doit jamais redevenir réutilisable**, sous peine de faire pointer un
événement historique (`event_type_config_id`) vers un tout autre type.

**"Slot libre" = `is_active = FALSE` ET `code` correspond encore au motif placeholder**
(`code LIKE 'type_niv%'`) — jamais encore assigné à un vrai type. Une fois activé (vrai
`code`/`label` posés), la ligne ne peut plus jamais redevenir "libre", même si elle est
désactivée plus tard.

### Activation bilingue — une seule action côté LarcConfig, pas deux manipulations manuelles

Contrairement à un élève (un seul slot, une seule langue), activer un type ici implique de
trouver **le premier slot libre dans chaque langue configurée**, sous les parents
correspondants, avec le **même `code`** des deux côtés — sinon les arbres FR et EN divergent
silencieusement. C'est une seule action utilisateur dans LarcConfig ("Créer ce type"), qui
traite toutes les langues d'un coup en interne, jamais une manipulation langue par langue.

## Impact sur le code existant

### `EventTypeConfigService` (`LarcCommon/larccommon/event_type_service.py`)

- `load_hierarchy(fk_language: int, force_refresh: bool = False)` — le cache retient la
  langue chargée ; un changement de langue déclenche un rechargement transparent (pas de cache
  multi-langue simultané, inutile ici).
- Requête simplifiée par rapport à l'option "table i18n" (pas de JOIN) :
  `WHERE fk_language = %s AND is_active = TRUE`.
- `filter_applicable(member_type, fk_language)` — signature étendue, répercutée sur son seul
  appelant (`EventGeneratorDialog.__init__`, via `session.fk_language`).
- `get_by_code`, `get_by_id`, `get_path` — inchangés (opèrent sur le cache déjà chargé pour la
  langue courante).

### `LarcConfig` — `TypesPanel` devient un vrai éditeur (aujourd'hui 100 % lecture seule)

Nouveautés à construire dans `LarcConfig/views/panel_types.py` et
`LarcConfig/common/db_access.py` :

1. **Sélecteur de langue** (liste tirée de `larcauth_language`), par défaut la langue de la
   session.
2. **Colonne "Parent"** (libellé du `parent_id` résolu, langue affichée) — répond au besoin
   exprimé de comprendre "qui est le père de qui" sans dépendre de la seule indentation.
3. **"Actif" éditable** (case à cocher au lieu du texte figé "Oui"/"Non") → nouvelle fonction
   `set_event_type_active(id, enabled)`.
4. **"Libellé" éditable** en double-clic pour la langue sélectionnée → nouvelle fonction
   `set_event_type_label(id, label)`.
5. **Action "Créer ce type"** → nouvelle fonction implémentant le mécanisme d'activation
   bilingue décrit ci-dessus (trouve le premier slot libre par langue sous le parent choisi,
   pose le même `code`, les labels fournis, `is_active = TRUE`).

### Migration DB

- `ALTER TABLE larcauth_event_type_config ADD COLUMN fk_language INT REFERENCES larcauth_language(id)`.
- Reconstruire la contrainte unique : `DROP CONSTRAINT ... UNIQUE(code)` puis
  `ADD CONSTRAINT ... UNIQUE(code, fk_language)`.
- Dupliquer les 105 lignes actuelles : `fk_language=2` (FR, texte réel), `fk_language=1` (EN,
  copie provisoire du FR).
- Insérer les lignes "potentielles" (+2 par parent réel et par niveau, cf. tableau) avec la
  convention `code`/`label` placeholder, pour les 2 langues.

## Hors périmètre (explicitement écarté pendant la discussion)

- **Table de traduction séparée** (`_i18n`) — rejetée au profit de la duplication par
  `fk_language`, cohérente avec `larcauth_program`.
- **LarcForge comme outil de configuration métier** — LarcForge existe déjà mais est un poste
  de contrôle qualité (lints/tests/registre d'issues), pas un configurateur de taxonomie ou de
  langues. Le dimensionnement du gabarit (ce document) est une décision prise directement par
  l'éditeur du logiciel dans la migration, pas via un outil dédié qui n'existe pas.
- **OfflineFirst (synchronisation profs hors ligne)** — évoqué pendant la discussion comme
  illustration de la philosophie "rien ne se crée, tout se transforme", mais volontairement
  écarté de ce document : sujet indépendant (synchronisation, résolution de conflits, stockage
  local), qui mérite sa propre session de conception.
- **Activation d'un slot potentiel qui a lui-même besoin de niveaux enfants** — vaut à tous
  les niveaux, pas seulement les racines : un des 8 slots potentiels niveau 2 activé pour un
  vrai usage n'a **aucun** niveau 3 pré-créé sous lui (même règle que les racines potentielles).
  Lui donner sa propre descendance est un événement de migration produit à part entière, pas
  un correctif de ce design ni une opération courante d'école.
