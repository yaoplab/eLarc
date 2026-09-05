# Tableau de bord du professeur — Espace de travail (Phase 2)

**Fichier :** `views/main_window.py` + `views/pei_workspace.py` + `views/dp_workspace.py`

## Rôle

Offrir au professeur son espace de saisie de notes après authentification :
sélectionner une matière, une classe, puis saisir les évaluations formatives
et sommatives dans une grille élèves × notes, avec sync locale puis serveur.

---

## 1. Architecture d'ensemble

```
MainWindow  (enveloppe générique)
├── Header        : nom prof, année scolaire, trimestre
├── Selecteur     : Matière - Classe (liste combinée unique)
├── Workspace     : QStackedWidget
│   ├── page 0    : PeiWorkspace   (si classe collège)
│   └── page 1    : DpWorkspace    (si classe lycée)
├── Actions       : [Synchroniser] [Enregistrer et quitter]
└── StatusBar     : messages, état synchro
```

### Deux fichiers workspace distincts (décision `17_pei_dp_separation.md`)

| Cible | Fichier | Table métier |
|---|---|---|
| PEI (collège) | `pei_workspace.py` | `larcauth_learnerpei_has_termsubjectpei` |
| DP (lycée) | `dp_workspace.py` | `larcauth_learnerdp_has_termsubjectdp` |

Chaque workspace contient :
- **Panneau F** : 12 slots formatives (F01–F12) avec 4 critères (a, b, c, d)
- **Panneau S** : 12 slots sommatives (S01–S12) avec 4 critères (a, b, c, d)
- **Panneau filtres** : affichage, tri, masquage colonnes
- **Grille élèves × notes** : table éditable, ligne par élève

---

## 2. Flux de données — sélecteur Matière-Classe → évaluations

### 2.1 Chargement au démarrage du workspace

```
MainWindow.__init__()
├── _build_header()               → session.full_name, module_config
├── _load_combined_data()         → requête SQLite unique
│   └── items Matière-Classe      → DISTINCT (matiere_label || ' - ' || classe_label)
└── _on_selection_changed()       → QStackedWidget.setCurrentIndex()
```

Les données sont stockées en mémoire dans une liste unique :

```python
self._items: list[dict] = [
    {'id': int, 'termsubject_id': int, 'class_id': int, 'class_label': str,
     'matiere_label': str, 'cycle': 'PEI'|'DP'},
    ...
]
self._eleves: dict[int, list[dict]]      # {class_id: [{student_id, nom, prenom}]}
```

### 2.2 Requête SQLite locale

```sql
-- Items Matière-Classe pour le prof (trimestre courant)
SELECT cts.id AS termsubject_id,
       ls.label AS matiere,
       c.id AS class_id,
       c.label AS classe
FROM larcauth_classroom_termsubject cts
JOIN larcauth_levelsubject ls ON ls.id = cts.fk_levelsubject_id
JOIN larcauth_classroom c ON c.id = cts.fk_classroom_id
WHERE cts.fk_teacher_id = ?
  AND cts.fk_term_id = ?
  AND cts.enabled = 1
  AND c.enabled = 1
ORDER BY ls.label, c.label;

-- Élèves d'une classe avec leur niveau (PEI/DP)
SELECT s.aecuser_ptr_id, u.last_name, u.first_name,
       pei.note_on_7, dp.moy_on_20
FROM larcauth_student s
JOIN larcauth_aecuser u ON u.id = s.aecuser_ptr_id
LEFT JOIN larcauth_learnerpei_has_termsubjectpei pei ON ...
LEFT JOIN larcauth_learnerdp_has_termsubjectdp dp ON ...
WHERE s.fk_classroom_id = ?
  AND s.enabled = TRUE
ORDER BY u.last_name, u.first_name;
```

> Les requêtes sont fixes → seul le paramètre `term_id` varie. Principe **schéma fixe → queries fixes** (CONTEXT.md l.199).

### 2.3 Sélecteur combiné

```
[QListWidget / QComboBox Matière - Classe] ──selection──> [Workspace]
                                                                 │
                                              ┌───────────────────┘
                                              ▼
                                     filtrer évaluations pour
                                     ce termsubject_id + class_id
                                     → peupler panneaux F/S
                                     → remplir grille élèves
```

Quand l'utilisateur sélectionne un item `Matière - Classe` :
1. Extraire `termsubject_id` et `class_id` de l'item sélectionné.
2. Déterminer le cycle (collège → PEI / lycée → DP) depuis `self._cycle_par_classe`.
3. Basculer le `QStackedWidget` sur la bonne page (PeiWorkspace / DpWorkspace).
4. Peupler les panneaux F/S avec les évaluations filtrées.
5. Remplir la grille avec les élèves + leurs notes.

Plus de cascade à deux niveaux — un seul clic suffit pour atteindre le workspace.

---

## 3. Panneaux d'évaluation (F/S)

### 3.1 Structure d'un slot d'évaluation

Chaque slot est un widget composite :

```
┌──────────────────────────────────┐
│ F03  [15/09/2026]  ☑ critère a  │
│      Observation : ___________  │
│      Note : [0-7/0-20]          │
└──────────────────────────────────┘
```

Données sous-jacentes (depuis SQLite `larcauth_evaluation`) :
```python
{
    'slot_index': 3,           # F03 → index 3 (1-based)
    'eval_id': 4512,
    'date': '2026-09-15',
    'criteria': {'a': True, 'b': False, 'c': True, 'd': False},
    'observation': '',
    'synthèse': None,          # note_on_7 ou moy_on_20
}
```

### 3.2 Algorithme de peuplement

```
_peupler_panneaux(termsubject_id, class_id):
├── évaluations = db.local_conn.execute("""
│   SELECT * FROM larcauth_evaluation
│   WHERE fk_classroom_termsubject_id = ?
│     AND fk_student_id IS NULL       -- ligne gabarit (pas par élève)
│   ORDER BY evaluation_type, slot_index
│   LIMIT 24                         -- 12F + 12S
│ """, (termsubject_id,))
│
├── pour chaque éval dans évaluations:
│   ├── si eval.type == 'FORMATIVE':
│   │     remplir le slot F[eval.slot_index]
│   └── si eval.type == 'SUMMATIVE':
│         remplir le slot S[eval.slot_index]
│
└── griser les slots vides (enabled = FALSE)
```

### 3.3 Interaction utilisateur

- **Case à cocher critère** → affiche/masque la colonne correspondante dans la grille.
- **Clic date** → sélecteur de date (`QDateEdit`).
- **Champ observation** → `QLineEdit` libre.
- **Note de synthèse** → `QSpinBox` avec validation selon cycle.

Un slot est **actif** si au moins un critère est coché.
Les colonnes de la grille sont masquées si le critère n'est coché **pour aucun élève**.

---

## 4. Grille élèves × notes

### 4.1 Structure

```
┌────────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┐
│ Élève  │F01_a │F01_b │F01_c │F01_d │F02_a │...   │Note  │
├────────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┤
│ Dupont │  5   │  6   │  4   │  7   │      │      │  5.5 │
│ Martin │  3   │  4   │  2   │  5   │      │      │  3.5 │
│ ...    │      │      │      │      │      │      │      │
└────────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┘
```

Implémentation : `QTableWidget` (ou `QTableView` + modèle personnalisé).

### 4.2 Colonnes dynamiques

Les colonnes sont générées à partir de la configuration des évaluations actives :

```
[Élève]                     (fixe)
[F01_note_a] [F01_note_b]   (si critère a ET b cochés pour F01)
[F02_note_a]                (si seulement critère a coché pour F02)
...
[S01_note_c] [S01_note_d]   (idem pour sommatives)
[Synthèse]                  (note_on_7 ou moy_on_20)
```

### 4.3 Algorithme de remplissage

```
_remplir_grille(termsubject_id, class_id, cycle):
├── 1. Vider la grille (supprimer toutes les lignes/colonnes)
│
├── 2. Déterminer les colonnes selon les évaluations actives
│   ├── colonne 0 : "Élève" (fixe)
│   ├── pour chaque F01..F12 active :
│   │     pour chaque critère (a,b,c,d) coché :
│   │         ajouter colonne "F{slot}_{critère}"
│   ├── pour chaque S01..S12 active : (même logique)
│   └── colonne finale : "Synthèse"
│
├── 3. Lire les notes depuis la base locale
│   ├── SELECT * FROM larcauth_learnerpei_has_termsubjectpei  (PEI)
│   │   WHERE fk_termsubjectpei_id IN (SELECT ...)
│   │     AND term_id = module_config.trimestre_courant
│   ├── ou SELECT * FROM larcauth_learnerdp_has_termsubjectdp (DP)
│   │   WHERE fk_termsubjectdp_id IN (SELECT ...)
│   │     AND term_id = module_config.trimestre_courant
│   └── transformer en dict {(student_id, slot, critère): valeur}
│
├── 4. Remplir ligne par ligne
│   ├── élèves = self._eleves[class_id]
│   ├── pour chaque élève :
│   │   ├── ligne = [élève.nom_prénom]
│   │   ├── pour chaque colonne note :
│   │   │     valeur = notes_dict.get((élève.id, slot, critère), '')
│   │   │     ligne.append(valeur)
│   │   └── grille.ajouter_ligne(ligne)
│   └── stocker id élève dans le UserRole des items
│
└── 5. Appliquer les validateurs par type de colonne
```

### 4.4 Validateurs par cycle et colonne

| Colonne | Type | Validateur |
|---|---|---|
| PEI `F{n}_note_{a,b,c,d}` | `QSpinBox` | 0–8, step 1 |
| PEI `S{n}_note_{a,b,c,d}` | `QSpinBox` | 0–8, step 1 |
| PEI note de synthèse | `QSpinBox` | 0–7, step 1 |
| DP `F{n}_note_{a,b,c,d}` | `QDoubleSpinBox` | 0–20, step 0.5 |
| DP `S{n}_note_{a,b,c,d}` | `QDoubleSpinBox` | 0–20, step 0.5 |
| DP `moy_on_20` | `QDoubleSpinBox` | 0–20, step 0.5 |
| DP `cc_on_20` | `QDoubleSpinBox` | 0–20, step 0.5 |
| DP `bacblanc` / `bacblanc2` | `QDoubleSpinBox` | 0–20, step 0.5 |
| DP `ei_note` | `QDoubleSpinBox` | 0–20, step 0.5 |

---

## 5. Sauvegarde locale (écriture immédiate)

### Principe

Toute modification dans la grille est écrite **immédiatement** en SQLite local
(dans la table de travail, pas la `_ref`). Pas de bouton "Enregistrer" local :
les données sont persistées cellule par cellule.

### Algorithme

```
_on_cell_changed(row, col):
├── élève_id   = grille.item(row, 0).data(Qt.UserRole)
├── slot_index = self._col_map[col]['slot_index']
├── critère    = self._col_map[col]['critere']
├── type_eval  = self._col_map[col]['type']    # 'F' ou 'S'
├── valeur     = grille.cellWidget(row, col).value()
│
├── nom_colonne = f"{type_eval}{slot_index:02d}_note_{critère}"
│
├── UPDATE larcauth_learnerpei_has_termsubjectpei
│   SET {nom_colonne} = ?
│   WHERE learner_has_termsubject_ptr_id IN (
│       SELECT id FROM larcauth_learner_has_termsubject
│       WHERE fk_student_id = ?
│         AND fk_classroom_termsubject_id = ?
│   )
│
└── (aucune modif de la table _ref — elle reste le snapshot serveur)
```

Pour la note de synthèse :
```sql
UPDATE larcauth_learnerpei_has_termsubjectpei
SET note_on_7 = ?
WHERE id = (
    SELECT pei.id FROM larcauth_learnerpei_has_termsubjectpei pei
    JOIN larcauth_learner_has_termsubject lht ON lht.id = pei.learner_has_termsubject_ptr_id
    WHERE lht.fk_student_id = ?
      AND lht.fk_classroom_termsubject_id = ?
)
```

### Transaction par lot

Si l'utilisateur colle des données ou fait une modification rapide,
les UPDATE sont regroupés en une transaction toutes les 2 secondes
(`QTimer` avec accumulation de requêtes). Pas de transaction par cellule.

---

## 6. Synchronisation device → serveur

### 6.1 Principe (rappel CONTEXT.md §Architecture de synchronisation)

La synchro utilise le pattern shadow-table : comparaison cellule par cellule
entre la table de travail et la table `_ref` (snapshot du dernier état serveur).

### 6.2 Algorithme `SyncManager.pull_push`

```
SyncManager.pull_push(table_name, term_id):
├── conn = db.local_conn
│
├── Pour chaque ligne de la table de travail (WHERE term_id = trimestre_courant):
│   ├── ref_row = jointure par id avec {table_name}_ref
│   ├── Pour chaque colonne métier (notes, observations) :
│   │   ├── local = travail[col], ref = ref_row[col], serveur = NULL (après pull)
│   │   │
│   │   ├── Matrice de décision :
│   │   │   local vs ref  |  serveur vs ref  |  Action
│   │   │   ──────────────┼──────────────────┼─────────
│   │   │        =        │        =         │  rien
│   │   │        =        │        ≠         │  PULL  ← serveur → local + ref
│   │   │        ≠        │        =         │  PUSH  ← local → serveur + ref
│   │   │        ≠        │        ≠         │  CONFLIT (IHM dédiée)
│   │   │
│   │   └── Appliquer l'action
│   │
│   └── Mettre à jour {table_name}_ref avec le nouvel état
│
├── UPDATE sync_state SET last_sync = now(), last_source = ?
│   WHERE table_name = ?
│
└── Log dans sync_log
```

### 6.3 Pull (données serveur → local)

```sql
-- Exemple PEI
UPDATE larcauth_learnerpei_has_termsubjectpei AS local
SET col_notes = serveur.col_notes
FROM (
    SELECT * FROM postgres_query(...)
) AS serveur
WHERE local.id = serveur.id;

-- Puis mettre à jour _ref
UPDATE larcauth_learnerpei_has_termsubjectpei_ref AS ref
SET col_notes = serveur.col_notes
FROM (
    SELECT * FROM postgres_query(...)
) AS serveur
WHERE ref.id = serveur.id;
```

### 6.4 Push (local → serveur)

```sql
-- Via connexion PostgreSQL
SET LOCAL app.sync_source = 'intranet';
SET LOCAL app.modified_by = <user_id>;

UPDATE public.larcauth_learnerpei_has_termsubjectpei
SET col_notes = ?
WHERE id = ?;
```

Puis mise à jour de `_ref` en local :
```sql
UPDATE larcauth_learnerpei_has_termsubjectpei_ref
SET col_notes = ?
WHERE id = ?;
```

### 6.5 Conflit

Si `local ≠ ref` ET `serveur ≠ ref`, la cellule est en conflit.
Ajoutée à une liste interne `self._conflits: list[Conflit]`.

À la fin de `pull_push()` :
- Si aucun conflit → tout commit, tout OK.
- Si conflits → ouvrir `ConflictResolutionDialog` (Phase 2).

Structure d'un conflit :
```python
@dataclass
class Conflit:
    table: str
    row_id: int
    colonne: str
    local: Any
    serveur: Any
```

L'utilisateur choisit pour chaque cellule : **Garder ma version** (push) ou **Prendre celle du serveur** (pull).

---

## 7. Déclencheurs de la synchro (recontextualisation)

1. **Seed initial** (mode 4 / première connexion) : `local = ref = serveur` — pas de diff possible.
2. **Clic "Connecter"** (onglet Intranet ou Cloud) : après auth, si `local ≠ ref` → pull/push.
3. **Clic "Synchroniser"** (barre d'actions) : déclenche `SyncManager.pull_push()` pour les 3 tables.
4. **Clic "Enregistrer et quitter"** : synchro puis fermeture.

---

## 8. Règles métier appliquées dans l'IHM

| Règle | Implémentation |
|---|---|
| Trimestre courant uniquement | Toute requête filtre par `term_id = module_config.trimestre_courant` |
| Trimestres passés en lecture seule | Si `trimestre sélectionné < trimestre courant` → `table.setEditTriggers(NoEditTriggers)` |
| Notes 0-8 PEI (collège) | `QSpinBox(range(0,9))` + classe CSS si valeur hors limite |
| Notes 0-20 DP (lycée) | `QDoubleSpinBox(0.0, 20.0, 0.5)` |
| 12 slots F + 12 slots S max | Les colonnes `f13..f15` et `s13..s15` existent en base mais sont ignorées par l'IHM v1 |
| 4 critères affichés (a,b,c,d) | `crit_e` et `crit_F` existent en base mais ignorés par l'IHM v1 |
| Jamais de DELETE | Pas de bouton supprimer ; désactivation logique uniquement |
| Pas de connexion auto au démarrage | Sync déclenchée uniquement par clic explicite |
| Ne jamais toucher au daemon serveur | Toute la logique de diff vit côté device |

---

## 9. Cycle de vie du workspace

```
MainWindow.show()
├── _load_combined_data()
├── _auto_select_first()
│   └── si un seul item Matière-Classe : le sélectionner
│       └── _on_item_selected()
│           ├── _switch_workspace(cycle)
│           ├── _peupler_panneaux()
│           └── _remplir_grille()
│
└── statusBar().showMessage(f"Dernière synchro : {sync_state.last_sync}")

┌─ Boucle d'événements Qt ─────────────────────────────┐
│  • Changement item Matière-Classe → workspace         │
│  • Clic case critère → masquer/afficher colonne       │
│  • Édition cellule → save locale (timer 2s)          │
│  • Clic Synchroniser → SyncManager.pull_push()       │
│  • Clic Enregistrer et quitter → save + sync + close │
└──────────────────────────────────────────────────────┘

MainWindow.closeEvent()
├── si modifications non sauvegardées :
│   └── QMessageBox.YesNo → Save now?
│       ├── Yes → SyncManager.pull_push() + close
│       └── No  → close (perte des modifications locales)
└── accept()
```

---

## 10. Dépendances

- `PySide6.QtWidgets` : `QMainWindow`, `QStackedWidget`, `QTableWidget`, `QSplitter`, `QComboBox`, `QSpinBox`, `QDoubleSpinBox`, `QDateEdit`, `QCheckBox`, `QLineEdit`, `QPushButton`, `QStatusBar`, `QMessageBox`
- `PySide6.QtCore` : `QTimer`, `Qt`, `Signal`, `Slot`
- `common.database.db` : connexions PostgreSQL + SQLite
- `common.session.session` : session active
- `common.sqlite_init.sqlite_init` : `read_cursor`, `update_cursor`
- `common.logger.log` : journalisation

---

## 11. Numérotation des colonnes notes (rappel)

Convention de nommage côté `larcauth_learnerpei_has_termsubjectpei` et `larcauth_learnerdp_has_termsubjectdp` :

```
formatives  :  f01_note_a, f01_note_b, f01_note_c, f01_note_d
               f02_note_a … f12_note_d
sommatives  :  s01_note_a … s12_note_d
synthèse    :  note_on_7 (PEI)  ou  moy_on_20 (DP)
observation :  fXX_observation, sXX_observation, cp_observation, term_observation
jugement    :  jgt_a..jgt_d
```

L'IHM v1 expose uniquement `f01_note_a..f12_note_d` et `s01_note_a..s12_note_d`.
Les colonnes `_e`, `_f`, `f13..f15`, `s13..s15` sont réservées pour v2.

---

## 12. États du workspace

| État | Condition | Affichage |
|---|---|---|
| Aucun item | Prof sans affectation matière-classe | Message "Aucune matière-classe assignée" |
| Aucun élève | Classe vide | Grille vide avec message |
| Aucune évaluation | Pas d'éval créée | Panneaux F/S vides (grisés) |
| Données présentes | Tout OK | Grille remplie, prête pour édition |
| Hors ligne | Pas de connexion serveur | Sync désactivée, bouton grisé |
| Synchro en cours | Pendant pull/push | Barre de progression + status |
| Conflit | Détecté pendant synchro | Boîte de dialogue de résolution |
