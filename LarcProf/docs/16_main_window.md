# Fenêtre principale — Espace de travail du professeur

**Fichier :** `views/main_window.py` (~1215 lignes)

## Rôle

Présenter au professeur son espace de travail après une authentification réussie :
sélection matière-classe, gestion des évaluations (F/S), grille élèves × notes avec édition.

## Layout général

```
+------------------------------------------------------------------+
| Header : Nom du prof          | Année scolaire | Trimestre        |
+--------------------------------------------------------+---------+
| Matière-Classe  | Formatives (scroll, actifs seuls)   | Juge.    |
| (fixe 210px)    | Sommatives (scroll, actifs seuls)   |(170px)   |
+-----------------+---------------------------+---------+----------+
| Grille élèves × notes (stretch=1)                               |
| [Élève] [F01_A] [F01_B] [F01_C] [F01_D] [F02_A] ... [Jgt_A]   |
| [Nom P.] [  8  ] [  7  ] [  6  ] [  7  ]                      |
| [Nom P.] [  5  ] [  4  ] [  6  ] [  5  ]                      |
+------------------------------------------------------------------+
| [Synchroniser]                                      [Enr.&quitter]|
+------------------------------------------------------------------+
| Status bar                                                       |
+------------------------------------------------------------------+
```

### Top bar (toujours visible, 4 sections en `QHBoxLayout`)

| Section | Largeur | Contenu |
|---|---|---|
| Matière-Classe | `fixed 210px` | 2 combos (principal + autre) |
| Formatives | `stretch` | Titre + Gérer + scroll slots actifs + Toute/Aucune/Commentaire |
| Sommatives | `stretch` | Idem |
| Jugements | `fixed 170px` | 3 toggles (Jgt/Note/Commentaire) + 4 critères A/B/C/D |

### Section Formatives / Sommatives

Chaque section est un `QFrame` borduré avec :

1. **Titre** (bold 10px) + bouton **Gérer** → `EvalManagerWindow`
2. **`QScrollArea`** (maxHeight=160px) : liste de rangées cliquables, une par slot actif
3. **Boutons** Toute / Aucune / Commentaire (QPushButton checkable)

Chaque rangée de slot affiche :
```
┌─────────────────────────────────────────────┐
│ F01 │ Titre éval...  │ Nature...   │ B C D  │  ← vert si visible dans grille
├─────────────────────────────────────────────┤
│ F03 │ Autre...       │ ...         │ A B    │  ← gris si masqué
└─────────────────────────────────────────────┘
```
- Bordure gauche orange `#ff6b00` (3px) si le slot est visible dans la grille
- Seuls les slots avec ≥1 critère coché (`is_active`) sont affichés
- Clic sur une rangée → bascule la visibilité dans la grille

### Section Jugements
- **Jugement** : bascule les 4 colonnes `jgt_a..jgt_d`
- **Note sur 7** : bascule `note_on_7` (PEI) ou `moy_on_20` (DP)
- **Commentaire** : bascule `term_observation`
- **Critère A/B/C/D** : filtre les colonnes `fXX_note_{a..d}` / `sXX_note_{a..d}` affichées

## Grille élèves × notes

`QTableWidget` avec alternance de couleurs, sélection par ligne, édition par double-clic.

### Construction (`_fill_grille`)
1. Détermine les colonnes visibles selon `_visible_f`, `_visible_s`, `_visible_crits`, toggles jugements
2. Vérifie les colonnes existantes dans la table via `PRAGMA table_info()`
3. Charge les notes depuis la table PEI ou DP :
   - `SELECT id, fk_student_id, <cols> FROM larcauth_learnerpei_has_termsubjectpei`
   - Matching : `notes[student_id]` où `student_id` = `fk_student_id` (matche `eleve.aecuser_ptr_id`)
4. Pour les bases anciennes (sans `fk_student_id`) : message en barre d'état

### Édition et sauvegarde
- `cellChanged` → `_on_cell_changed()` stocke les modifs dans `_dirty_cells[(student_id, db_name)]`
- `_save_grid_edits()` : parcourt les cellules sales et exécute `UPDATE table SET col = ? WHERE id = pei_row_id`
- Appels automatiques : changement de sélection → sauvegarde, sync → sauvegarde, fermeture → sauvegarde

## Calcul des jugements et de la note /7 (PEI)

Le calcul se déclenche **à chaque saisie** (jamais au clic « Valide »), dans l'ordre imposé :

1. **Jugements d'abord** : `jgt_a..jgt_d` — moyenne pondérée des notes du critère
   (F × 0,4 + S × 0,6, arrondie à l'entier ; un seul type de notes compte seul à 100 %).
2. **Note /7 ensuite** : `CalcEngine.compute_note()` → somme des moyennes par critère
   (critères effectifs = critères visibles du top bar « Affichage colonnes ») → bandes IB.

La saisie en cours (non encore enregistrée) alimente le calcul via un *override* :
`_dirty_cells` remplace la base, puis la grille est rafraîchie sans redéclencher
`cellChanged` (`blockSignals`). Le clic « Enregistrer » ne persiste que les saisies ;
le recalcul lui, est immédiat et visible.

### Validation de la note

La case « Valide » (`_note_validated` → `note_on_7_checked`) signifie que le
professeur **valide le calcul** ou qu'il a **lui-même corrigé des calculs faits
préalablement** (saisie manuelle d'un jugement ou de la note /7).

- **Clic sur la case** → `note_on_7_checked = 1` (sauvegarde immédiate, pas de recalcul).
- **Toute modification ultérieure** — note (`*_note_*`), jugement (`jgt_*`) ou note /7
  (`note_on_7` / `moy_on_20`) — **invalide la validation** : `note_on_7_checked`
  repasse à `0` (le calcul a été redéclenché ou corrigé) et la case se décoche.
- La saisie manuelle d'un jugement **n'est jamais écrasée** par le recalcul (seules
  les cellules de notes déclenchent le recalcul).

### Fiche élève (`StudentCardView`, double-clic colonne élève)

Fenêtre non modale **agrandie** (`window_width + sidebar_width` × `window_height`),
ouverte par double-clic sur la colonne élève de la grille (`_open_student_card`).

- **Gauche** : liste des élèves de la classe (tri alphabétique).
- **Droite** :
  - **Sections Formatives | Sommatives en parallèle** (`QSplitter` horizontal,
    sans arrondis) : une `QTableWidget` par section, une ligne par évaluation en
    lecture seule, en-têtes **Label | Nature | A | B | C | D** — label (fallback
    F01/S01, tooltip = observation d'évaluation), nature, 4 notes colorées
    (vert ≥ 4, rouge < 4, « — » si vide, 0 ou critère inactif).
  - **Bas** : photo **grande** (`header_height × 4` ≈ 208px, placeholder
    initiales si absente) centrée avec **nom + matière** dessous en colonne
    gauche ; **Jugements** + **note /7 prévue** + case « Validée »
    (`note_on_7_checked`, écriture immédiate) + **commentaire général**
    (`term_observation`, bouton « Enregistrer le commentaire ») avec surligneur
    orthographique — correcteur (spylls) à brancher plus tard, actuellement
    silencieux si pyenchant absent, en colonne droite.

### Données chargées
- **Élèves** : `larcauth_student` JOIN `larcauth_aecuser`, par `s_classroom_id`
- **Notes PEI** : `larcauth_learnerpei_has_termsubjectpei` (colonnes dynamiques `f01_note_a`..`f15_note_f`, `note_on_7`, `jgt_a..d`, etc.)
- **Notes DP** : `larcauth_learnerdp_has_termsubjectdp` (idem + `moy_on_20`, `cc_on_20`, `bacblanc`)

## Boutons d'action

| Bouton | Action |
|---|---|
| **Synchroniser** | `_save_grid_edits()` → `sync.pull_push()` → rapport en statusBar |
| **Enregistrer et quitter** | `_save_grid_edits()` → `sync.pull_push()` → `self.close()` |

## Cycle de vie

```
LoginWindow → auth OK → MainWindow()
  ├── __init__()
  │   ├── _setup_ui()          → header + top bar + workspace
  │   ├── _load_combined_data() → requête CTS, élèves, peuplement combos
  │   └── auto-sélection si 1 seul item
  │
  └── _on_item_selected(idx)   → charge évaluations, affiche workspace
      ├── _load_evaluations_from_db(ts_id)
      ├── _fill_grille()       → colonnes dynamiques + notes
      └── _update_top_bar()    → slots actifs, toggles
```

## Dépendances
- `PySide6.QtWidgets`, `PySide6.QtGui`, `PySide6.QtCore`
- `common.session.session`
- `common.database.db`
- `common.sync.sync`
- `views.eval_manager.EvalManagerWindow`

## Fichiers liés
- `views/eval_manager.py` — `EvalManagerWindow` (gestion détaillée des évaluations)
- `docs/20_eval_manager.md` — documentation
- `docs/historique_construction.md` — itérations 18-19
