# Refonte hiérarchie types d'événements + vue arbre (LarcSuperviseur / LarcConfig)

Date : 2026-09-07
Statut : Validé par l'utilisateur (conversationnel), en attente de revue finale avant plan d'implémentation.

## Contexte et problème

Les types d'événements (`larcauth_event_type_config`) sont actuellement limités à 3 niveaux
de hiérarchie et insuffisamment déclinés pour un usage réel en école secondaire : les
enseignants manquent d'options adaptées et seraient tentés de saisir du texte libre — ce qui
est à proscrire (cohérence des données, reporting, traduction).

Le wizard de création d'événement (`EventGeneratorDialog`, LarcCommon) navigue actuellement
étape par étape (un niveau à la fois, boutons en grille) : l'enseignant ne voit jamais
l'ensemble des options disponibles pendant sa saisie.

Deux besoins distincts, validés en discussion :

1. **Contenu** : une arborescence de types à 4 niveaux, exhaustive et cohérente pour le
   contexte d'une école secondaire, incluant la distinction fondamentale entre **Absence**
   (élève non présent) et **Sortie** (élève présent puis retiré/quitte temporairement).
2. **UX** : donner à l'enseignant une **vue d'ensemble visuelle** de tous les types possibles
   pendant qu'il choisit, plutôt qu'une navigation à l'aveugle.

## Décisions actées pendant le brainstorming

- Absence ≠ Sortie : deux catégories racines distinctes (un élève peut être absent d'un cours
  sans avoir été "sorti", et peut sortir d'un cours sans être considéré absent).
- Un même comportement disciplinaire (ex. "Insolence") peut mener soit à une sortie
  (exclusion de cours), soit à un simple événement noté sans sortie. Plutôt que dupliquer via
  un flag booléen, les motifs comportementaux sont dupliqués comme feuilles sous
  `Sortie > Sortie du cours > Mauvais comportement` **et** sous
  `Événement > Comportement > Négatif` — ce sont deux actions différentes de l'enseignant,
  donc deux entrées de configuration distinctes (codes différents), pas un attribut partagé.
- La catégorie "Incident" a été supprimée : redondante avec "Comportement > Négatif"
  (Conflit élèves ≈ Violence, Dégât matériel ≈ Dégradation matériel, etc.).
- "Exclusion de cours" a été retirée de "Absence du cours" : couverte par
  "Sortie du cours > Mauvais comportement".
- "Matériel oublié" n'est pas un "manque de travail" (l'élève peut continuer à travailler en
  empruntant du matériel) : catégorie indépendante sous Comportement.
- Chaque branche feuille se termine par une option "Autre" (fallback), afin qu'aucune saisie
  libre ne soit nécessaire même dans les cas non couverts explicitement.
- Profondeur maximale : 4 niveaux (root → contexte → motif → sous-motif/Autre). Pas de retard
  avec motif implique un cas à 4 niveaux également (Retard > Contexte > Durée > Motif) pour
  rester cohérent.

## Arborescence finale des types d'événements

```
Absence
├─ Absence de l'école
│  ├─ Maladie
│  │  ├─ Légère (rhume, fièvre)
│  │  ├─ Grave / Hospitalisation
│  │  ├─ Chronique (suivi médical)
│  │  └─ Autre
│  ├─ Motif familial
│  │  ├─ Décès
│  │  ├─ Événement familial
│  │  ├─ Déplacement
│  │  └─ Autre
│  ├─ Rendez-vous médical
│  │  ├─ Généraliste
│  │  ├─ Spécialiste
│  │  └─ Autre
│  ├─ Motif administratif
│  │  ├─ Démarches
│  │  ├─ Convocation externe
│  │  └─ Autre
│  ├─ Justifiée (sans détail)
│  ├─ Injustifiée
│  └─ Autre
├─ Absence du cours
│  ├─ Convoqué (direction/administration)
│  ├─ Activité scolaire (sport, sortie pédagogique, compétition)
│  └─ Autre

Sortie
├─ Sortie du cours
│  ├─ Toilettes
│  ├─ Infirmerie
│  ├─ Bureau direction/vie scolaire
│  ├─ Matériel oublié
│  ├─ Mauvais comportement
│  │  ├─ Indiscipline légère
│  │  ├─ Insolence
│  │  ├─ Violence verbale
│  │  ├─ Violence physique
│  │  ├─ Fraude
│  │  ├─ Vol
│  │  ├─ Dégradation matériel
│  │  └─ Autre
│  └─ Autre
├─ Sortie de l'école
│  ├─ Récupéré par parent/tuteur
│  ├─ Rendez-vous médical
│  ├─ Malaise/renvoyé
│  ├─ Autorisation exceptionnelle
│  └─ Autre

Retard
├─ Retard à l'école
│  ├─ 5 min → Transport / Familial / Oubli-réveil / Autre
│  ├─ 15 min → Transport / Familial / Oubli-réveil / Autre
│  └─ 30 min et + → Transport / Familial / Oubli-réveil / Autre
├─ Retard au cours
│  ├─ 5 min → Transport / Familial / Oubli-réveil / Autre
│  └─ 15 min et + → Transport / Familial / Oubli-réveil / Autre

Événement
├─ Comportement
│  ├─ Positif → Mérite/Encouragement / Autre
│  ├─ Négatif
│  │  ├─ Indiscipline légère
│  │  ├─ Insolence
│  │  ├─ Violence verbale
│  │  ├─ Violence physique
│  │  ├─ Fraude
│  │  ├─ Vol
│  │  ├─ Dégradation matériel
│  │  └─ Autre
│  ├─ Matériel oublié (élève continue de travailler)
│  └─ Manque de travail → Devoirs non faits / Autre
├─ Santé → Malaise / Blessure / Urgence médicale / Suivi PAI / Autre
```

Notes d'implémentation DB :
- `applicable_to` : les branches "Retard" restent `student` uniquement (comme aujourd'hui) ;
  "Absence" et "Sortie" restent `student,staff` où pertinent (le staff n'a pas de "Sortie du
  cours > Mauvais comportement", à filtrer via `applicable_to='student'` sur ce sous-arbre).
- `requires_lieu` : Sortie du cours (Infirmerie, Bureau direction), Événement (tous) — comme
  aujourd'hui.
- `requires_subject` : conservé pour les branches déjà marquées `requires_subject=TRUE`.
- Migration additive : ne pas supprimer `larcauth_event_type_config` existant, écrire une
  nouvelle migration qui désactive (`is_active=FALSE`) les anciens codes retirés (`retard`
  reasons absent, `absence_class_*`, etc. si remplacés) et insère la nouvelle hiérarchie avec
  de nouveaux `code` uniques — pas de DELETE (principe gabarit du projet, cf. CLAUDE.md).

## UX : vue d'ensemble (Approche A retenue)

Remplacer la navigation "un niveau à la fois" de `EventGeneratorDialog` par une **vue
scindée** :

- **Panneau gauche** (~35% largeur, via `M3Splitter` déjà existant dans `phibuilder.widgets`) :
  nouveau composant **`M3TreeWidget`** (à créer sur le modèle de `M3TableWidget` :
  Phi/Fibonacci pour les hauteurs de ligne, navigation clavier flèches, focus visible,
  accessibilité `setData(Qt.AccessibleTextRole, ...)`) affichant l'intégralité de la
  hiérarchie, repliable/dépliable, avec icônes MD3 par catégorie racine
  (`larccommon.icons.icon`). Une barre de recherche (`M3TextField`) au-dessus filtre les
  libellés en temps réel (affiche uniquement les branches contenant une correspondance,
  auto-expand des parents).
- **Panneau droit** : reprend le contenu actuel de `self._final` (date/heure, lieu si
  `requires_lieu`, matière si `requires_subject`, note, boutons Annuler/Valider) + badge
  résumé coloré (`_bd_update`, logique déjà existante) affichant le chemin complet
  (`event_type_service.get_path`).
- Sélection : clic sur une feuille de l'arbre = sélection immédiate (`_on_node_selected`
  équivalent), pas de navigation multi-clic. Les nœuds non-feuilles (avec enfants) restent
  cliquables pour expand/collapse uniquement, non sélectionnables comme type final.

Composants réutilisés sans changement : `event_type_service` (le chargement hiérarchique
`EventTypeNode` fonctionne déjà pour N niveaux, aucun changement de service nécessaire),
`EventData`, `_bd_update`.

### Sélection à un niveau intermédiaire

Le prof n'est pas obligé de descendre jusqu'à la feuille : il peut **valider son choix à
n'importe quel niveau** (ex. s'arrêter à "Maladie" sans préciser Légère/Grave/Chronique/Autre).

- Chaque nœud de l'arbre (feuille ou non) porte une action "Confirmer ce choix" (bouton
  visible dès qu'un nœud est sélectionné/surligné dans `M3TreeWidget`, qu'il ait des enfants
  ou non). Aucune règle ne force à atteindre la feuille.
- Le `type_code` stocké est alors celui du nœud intermédiaire (ex. `absence_school_sick`)
  plutôt qu'un descendant précis — la table `larcauth_event_type_config` supporte déjà cela
  nativement (chaque nœud, quel que soit son niveau, est un `id` valide et référençable).
- **Champ note conditionnel** : si le choix s'arrête à un niveau intermédiaire (nœud avec
  enfants, non déplié jusqu'à une feuille), le panneau de droite n'affiche **que la date et
  l'heure** — pas de champ note. Si le choix atteint une feuille (y compris "Autre"
  explicite), le champ note redevient disponible. Objectif : empêcher que la note serve de
  contournement à l'imprécision (cohérent avec l'interdiction de saisie libre du motif).
- Le nœud est ensuite **éditable avant validation** par le flux déjà existant
  (`validated_by IS NULL` → `EventActions.edit_event` / `toggle_validation`,
  `LarcSuperviseur/views/core/event_actions.py`) : un superviseur (ou le prof lui-même avant
  validation) peut rouvrir l'événement et préciser le type jusqu'à une feuille, ce qui
  débloque alors le champ note.

### Écart constaté à corriger dans le flux d'édition existant

`LarcSuperviseur/views/main_events.py:_edit_event` et `LarcSuperviseur/views/core/event_dialog.py`
(`EventEditDialog`, utilisé par `views/panels/student_detail.py`) utilisent encore l'**ancien
système** : un `M3ComboBox` peuplé par `SELECT DISTINCT event_type FROM student_event` (valeurs
texte historiques), sans lien avec `larcauth_event_type_config`. Ce flux d'édition doit être
refondu pour réutiliser le même sélecteur hiérarchique (`M3TreeWidget`) que la création, avec la
même règle de note conditionnelle — sinon l'édition réintroduit la déconnexion que le refactor
"EventGenerator polymorphe" (session précédente) visait justement à éliminer.

### Correctif découvert lors de la mise en plan : liaison fiable événement ↔ nœud

Investigation complémentaire (2026-09-07, avant écriture du plan d'implémentation) : il existe
**deux hiérarchies de types concurrentes et non reliées** dans le monorepo :

1. `larcauth_event_type_config` (migration 2026-09-05) + `EventTypeConfigService` — utilisée par
   `EventGeneratorDialog`. Elle n'écrit que le **texte** du chemin
   (`evt.type_path`, ex. `"Absence > Absence de l'école > Maladie"`) dans la colonne TEXT
   `student_event.event_type` / `staff_event.event_type` — aucun identifiant n'est conservé.
2. `larcauth_type_event` (migration `LarcSuperviseur/sql/migration_20260830_event_type_tree.sql`)
   + `student_event.event_type_id` (FK, avec trigger d'immutabilité) + `EventTypeRepo` — un arbre
   **distinct**, utilisé uniquement par le backfill historique et par
   `LarcConfig/common/db_access.py:get_event_types()` (via ses anciennes colonnes plates
   `Event_Niveau2`/`Event_Niveau3`, sans exploiter l'arbre `parent_id` qu'il porte pourtant déjà).

Le texte initial de cette section (et la ligne "hors scope" ci-dessous) supposait à tort que
`event_type_id` référençait déjà `larcauth_event_type_config` — ce n'est pas le cas. Sans
correctif, le flux d'édition ne peut retrouver le nœud exact choisi par l'enseignant que par
correspondance de texte sur le libellé, ce qui casse silencieusement le lien si un libellé est
renommé dans LarcConfig — inacceptable pour la règle "sélection à un niveau intermédiaire,
précisable plus tard" (point g/h validé).

**Décision validée** : ajouter une colonne FK dédiée et fiable, migration additive (principe
gabarit — aucune suppression) :
- `student_event.event_type_config_id` et `staff_event.event_type_config_id`, nullable,
  `REFERENCES larcauth_event_type_config(id)`.
- `EventGeneratorDialog` / `_insert_student_event` / `_insert_staff_event` renseignent cette
  colonne en plus du texte `event_type` (conservé pour affichage/historique).
- Le flux d'édition refondu recharge le nœud via `event_type_service.get_by_id(event_type_config_id)`
  — fiable, insensible aux renommages de libellé.
- `LarcConfig/views/panel_types.py` et `LarcConfig/common/db_access.py:get_event_types()`
  basculent sur `larcauth_event_type_config` (au lieu de `larcauth_type_event`), pour gérer la
  même table que celle utilisée par la création d'événement.
- `larcauth_type_event`, `student_event.event_type_id` et `EventTypeRepo` restent inchangés
  (aucune suppression) : ils continuent de porter l'historique déjà backfillé, mais ne reçoivent
  plus de nouvelles écritures depuis ce flux.

## Fichiers impactés

| Fichier | Changement |
|---|---|
| `LarcCommon/migrations/2026_09_07_event_type_hierarchy_v2.sql` (nouveau) | Nouvelle arborescence complète, désactivation des anciens codes remplacés, colonnes `event_type_config_id` sur `student_event`/`staff_event` |
| `LarcCommon/phibuilder/widgets/tree.py` (nouveau) | `M3TreeWidget` : arbre M3 générique avec recherche, clavier, accessibilité |
| `LarcCommon/phibuilder/widgets/__init__.py` | Export `M3TreeWidget` |
| `LarcCommon/larccommon/dialogs/event_type_selector.py` (nouveau) | `EventTypeSelectorWidget` : composant partagé (arbre + confirmation + badge résumé) réutilisé par la création et les deux flux d'édition |
| `LarcCommon/larccommon/dialogs/event_generator_dialog.py` | Refonte vue scindée (`M3Splitter` + `EventTypeSelectorWidget` + panneau date/lieu/matière/note) |
| `LarcCommon/larccommon/dialogs/__init__.py` | Export `EventTypeSelectorWidget` |
| `LarcSuperviseur/views/main_events.py` | `_insert_student_event` renseigne `event_type_config_id` ; `_edit_event` refondu sur `EventTypeSelectorWidget` |
| `LarcSuperviseur/views/core/event_dialog.py` (`EventEditDialog`) | Refonte sur `EventTypeSelectorWidget`, lecture/écriture `event_type_config_id` |
| `LarcRH/views/staff_events.py` | `_insert_staff_event` renseigne `event_type_config_id` |
| `LarcConfig/views/panel_types.py` | Affichage hiérarchique sur `larcauth_event_type_config` (au lieu de l'ancien `larcauth_type_event` plat) |
| `LarcConfig/common/db_access.py` (`get_event_types`) | Requête récursive sur `larcauth_event_type_config` (remplace la requête sur `larcauth_type_event`) |

## Tests / validation

- Test unitaire `EventTypeConfigService.load_hierarchy` : vérifier chargement 4 niveaux sans
  régression sur `filter_applicable` et `get_path`.
- Test manuel LarcSuperviseur : ouvrir `EventGeneratorDialog` pour un élève, vérifier que
  chaque branche de l'arbre est sélectionnable et que le formulaire de droite s'adapte
  (`requires_lieu`, `requires_subject`).
- Lint : `python scripts/lint_qss_hardcoding.py`, `lint_d1_color_checker.py`,
  `lint_accessibility.py`, `lint_focus_visible.py`, `lint_keyboard_nav.py` sur le nouveau
  `M3TreeWidget`.
- `graphify extract . --code-only --force && graphify cluster-only .` après ajout du nouveau
  widget et de la migration (changement structurel).

## Hors scope

- Pas de champ de saisie libre "Autre + texte" — validé explicitement par l'utilisateur : le
  prof ne doit jamais saisir de texte libre pour le motif. "Autre" reste un type fermé sans
  texte associé (le champ `note` existant reste disponible pour un commentaire optionnel,
  séparé du type).
- Pas de changement des colonnes `student_event`/`staff_event` existantes (`created_location`,
  `event_type_id`/`larcauth_type_event` legacy laissés tels quels) — seul un ajout additif
  (`event_type_config_id`) est fait, cf. section "Correctif découvert..." ci-dessus.
- Pas de migration rétroactive des événements déjà créés vers `event_type_config_id` (seuls les
  nouveaux événements et les événements rouverts en édition le renseignent) — un backfill des
  anciens événements par correspondance de texte serait un chantier séparé, hors scope ici.
