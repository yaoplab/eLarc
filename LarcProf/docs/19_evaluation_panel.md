# Panneau d'évaluations F/S — Slots cliquables (Phase 2)

**Fichier :** `views/evaluation_panel.py`

## Rôle

Afficher les 12 formatives (F01-F12) et 12 sommatives (S01-S12) d'une matière-classe
sous forme de slots cliquables. Chaque slot permet d'éditer les métadonnées de l'évaluation
(label, nature, source, critères A/B/C/D).

## Classes

| Classe | Rôle |
|---|---|
| `EvaluationPanel` | Panneau complet : titre, indicateurs, grille 4×3 de slots |
| `_SlotButton` | Slot cliquable affichant le titre + critères |
| `EvaluationDetailDialog` | Dialogue d'édition des métadonnées d'un slot |

## EvaluationPanel

### Layout

```
┌──────────────────────────────────────────────────────┐
│ QFrame (fond blanc, bordure 1px, border-radius 4px)  │
│ ┌──────────────────────────────────────────────────┐ │
│ │ Titre : "Formatives (F01 — F12)" (10px Roboto) │ │
│ │                                                  │ │
│ │ Indicateurs : [F01][F02][F03]...[F12]           │ │
│ │   ← vert si actif, gris sinon (28×14px)         │ │
│ │                                                  │ │
│ │ QScrollArea (max 2 lignes visibles)              │ │
│ │ ┌──────┬──────┬──────┬──────┐                    │ │
│ │ │ F01  │ F02  │ F03  │ F04  │ ← ligne 1         │ │
│ │ │ ☑☐☐☑ │ ☐☐☐☑ │ ☑☑☐☐ │ ☐☐☐☐ │                    │ │
│ │ ├──────┼──────┼──────┼──────┤                    │ │
│ │ │ F05  │ F06  │ F07  │ F08  │ ← ligne 2         │ │
│ │ │ ☐☐☐☐ │ ☑☐☐☐ │ ☐☐☐☐ │ ☐☑☐☐ │                    │ │
│ │ ├──────┼──────┼──────┼──────┤                    │ │
│ │ │ F09  │ F10  │ F11  │ F12  │ ← ligne 3 (scroll)│ │
│ │ │ ☑☐☐☐ │ ☐☐☐☐ │ ☑☑☑☐ │ ☐☐☐☐ │                    │ │
│ │ └──────┴──────┴──────┴──────┘                    │ │
│ └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

### Hauteur

Titre (≈14px) + indicateurs (16px) + 2 lignes de slots (≈70px×2 + 2px spacing)
+ marges internes ≈ 190-220px. La hauteur est fixée par `scroll.setMaximumHeight()`
calculée dynamiquement à partir de `minimumSizeHint()` du premier slot.

### Barre d'indicateurs

12 `QLabel` côte à côte (28×14px). Mise à jour via `_update_indicators()` :
- **Vert** (#27ae60 fond, blanc texte) si `slot._active == True` et `slot.eval_id` défini
- **Gris** (#e0e0e0 fond, #666 texte) sinon

### Cycle de vie

```
MainWindow._on_item_selected()
└── eval_f.load_evaluations(termsubject_id)
    └── pour chaque slot (F01..F12) :
        ├── si ligne trouvée dans larcauth_evaluation :
        │     slot.set_data(id, {crit_a, crit_b, crit_c, crit_d, label, nature, source})
        └── sinon :
              slot.clear()
        └── _update_indicators()
```

## _SlotButton

### Affichage compact

```
┌─────────────────────┐
│        F03          │  titre 10px bold
│   Électricité       │  label 9px (optionnel, caché si absent ou = "F03")
│ ☑ Recherche et      │  critères : ☐/☑ + label (checkbox 9px, label 8px)
│ ☐ Développement     │
│ ☑ Création          │
│ ☐ Évaluation        │
└─────────────────────┘
```

### États visuels

| État | Fond | Bordure | Texte |
|---|---|---|---|
| Inactif (vide) | `#f0f0f0` | `#e0e0e0` | `#555` (titre), `#777` (☐) |
| Actif (≥1 critère coché) | blanc | `#27ae60` | `#2c3e50` (titre), `#27ae60` (☑) |
| Hover (n'importe) | `#ecf0f1` | `#3498db` | — |

### Chargement des labels des critères

À l'appel de `set_data()`, le slot charge les labels A/B/C/D depuis
`larcauth_criteria_of_levelsubject` via la jointure :

```
slot._ts_id (= data._termsubject_id)
    → larcauth_classroom_termsubject.fk_levelsubject_id
        → larcauth_criteria_of_levelsubject.criteria_label
```

Requête :
```sql
SELECT criteria_letter, criteria_label
FROM larcauth_criteria_of_levelsubject
WHERE fk_levelsubject_id = ?
  AND criteria_letter IN ('A','B','C','D')
ORDER BY criteria_letter;
```

Les labels avec sauts de ligne (`\n`) sont normalisés en espaces.

### Sauvegarde

Les critères cochés sont persistés dans `larcauth_evaluation` (colonnes `crit_a`..`crit_d`).
Les labels/nature/source sont persistés dans `label`, `nature`, `source`.

## EvaluationDetailDialog

### Ouverture

`EvaluationPanel._on_slot_clicked(slot_index)` :
```python
dlg = EvaluationDetailDialog(slot_index, eval_type, slot._data,
                             termsubject_id, subject_label, parent)
if dlg.exec() == QDialog.Accepted:
    form_data = dlg.get_form_data()
    panel._save_criteria(slot, form_data)
```

### Formulaire

```
┌──────────────────────────────────────────────┐
│ F01                                          │
│ Label : [_____Électricité - Loi d'Ohm_____]  │
│ Nature : [______Devoir surveillé________]    │
│                                              │
│ Source / Texte de l'évaluation :             │
│ ┌──────────────────────────────────────────┐│
│ │ 1. Calculer le courant dans...           ││
│ │ 2. Déterminer la tension aux bornes...   ││
│ └──────────────────────────────────────────┘│
│                                              │
│ Critères :                                   │
│ ┌──────────────────────────────────────────┐│
│ │ ☑ Critère A : Recherche et analyse      ││
│ │    · aspect 1 · aspect 2                ││
│ │ ☐ Critère B : Développement des idées   ││
│ │ ☑ Critère C : Création de la solution   ││
│ │    · aspect 1                           ││
│ │ ☐ Critère D : Évaluation                ││
│ └──────────────────────────────────────────┘│
│                                 [OK] [Cancel]│
└──────────────────────────────────────────────┘
```

### Champs

| Champ | Widget | Colonne SQLite |
|---|---|---|
| Label | `QLineEdit` | `larcauth_evaluation.label` |
| Nature | `QLineEdit` | `larcauth_evaluation.nature` |
| Source | `QPlainTextEdit` | `larcauth_evaluation.source` |
| Critère A | `QCheckBox` | `larcauth_evaluation.crit_a` |
| Critère B | `QCheckBox` | `larcauth_evaluation.crit_b` |
| Critère C | `QCheckBox` | `larcauth_evaluation.crit_c` |
| Critère D | `QCheckBox` | `larcauth_evaluation.crit_d` |

### Chargement des labels et aspects des critères

Même mécanisme que `_SlotButton` : requête vers `larcauth_criteria_of_levelsubject`
avec JOIN via `larcauth_classroom_termsubject.fk_levelsubject_id`.

Les aspects (7 max par critère) sont affichés en `• texte` sous chaque critère,
dans une police plus petite (9px).

### get_form_data()

```python
def get_form_data(self) -> dict:
    return {
        'label': self._label_edit.text().strip(),
        'nature': self._nature_edit.text().strip(),
        'source': self._source_edit.toPlainText().strip(),
        'crit_a': '1' if crits['a'] else '0',
        'crit_b': '1' if crits['b'] else '0',
        'crit_c': '1' if crits['c'] else '0',
        'crit_d': '1' if crits['d'] else '0',
    }
```

## Intégration dans MainWindow

### Chargement initial

```python
MainWindow._build_top_panels()
├── self._eval_f = EvaluationPanel('F', 'Formatives  (F01 — F12)')
└── self._eval_s = EvaluationPanel('S', 'Sommatives  (S01 — S12)')

MainWindow._on_item_selected(idx)
├── self._eval_f.load_evaluations(termsubject_id)
└── self._eval_s.load_evaluations(termsubject_id)
```

### Nettoyage

```python
MainWindow._on_item_selected(idx)  # idx invalide (class_id is None)
├── self._eval_f.clear_panel()
└── self._eval_s.clear_panel()
```

`clear_panel()` vide tous les slots (`slot.clear()`) et remet les indicateurs en gris.

## Données

### Lecture depuis SQLite

```sql
SELECT id, index_eval,
       crit_a, crit_b, crit_c, crit_d,
       label, nature, source
FROM larcauth_evaluation
WHERE fk_classroom_termsubject_id = ?
  AND type_evaluation = ?           -- 'F' ou 'S'
  AND CAST(index_eval AS INTEGER) BETWEEN 1 AND 12
ORDER BY CAST(index_eval AS INTEGER);
```

### Écriture

```sql
UPDATE larcauth_evaluation
SET label=?, nature=?, source=?,
    crit_a=?, crit_b=?, crit_c=?, crit_d=?
WHERE id=?;
```

## Dépendances

- `common.database.db` — connexion SQLite locale
- `PySide6.QtWidgets`, `PySide6.QtCore` — widgets Qt
- `PySide6.QtCore.Signal` — signal `clicked` du slot
