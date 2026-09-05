# Fenêtre de gestion des évaluations (EvalManagerWindow)

**Fichier :** `views/eval_manager.py`

## Rôle

Fenêtre non-modale de gestion complète des 12 slots d'évaluation (F ou S).
Permet de voir, activer/désactiver et éditer tous les slots d'un type donné.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Gestion des Formatives — Design - PEI-1                    │
├──────────────────────────┬──────────────────────────────────┤
│  [F01][F02][F03]... tabs │  F03 — Détails                   │
│                           │                                  │
│  A: Rech. | B: Dév. ...  │  Label : (lecture seule)         │
│                           │  Nature : [________]             │
│  ┌────────────────────┐   │                                  │
│  │ F01 | Titre... ☑A☐B│   │  Source : [B I H • 🔗]         │
│  │ F02 | Titre... ☑A☑B│   │  ┌──────────────────────────┐  │
│  │ F03 | Titre... ☐A☐B│ ← │  │ Markdown éditable        │  │
│  │  (actifs + suivante)│   │  │ scrollable               │  │
│  └────────────────────┘   │  └──────────────────────────┘  │
│  (scroll si >4 barres)    │                                  │
│                           │  ☐A  ☑B  ☐C  ☑D                │
│                           │  Rech. Dév. Créa. Éval.          │
│                           │                                  │
│                           │  [Enregistrer ce slot]            │
├──────────────────────────┴──────────────────────────────────┤
│  QSplitter redimensionnable (400 / 500)                      │
└─────────────────────────────────────────────────────────────┘
```

### Panneau gauche

- **Tabs F01-F12** : QPushButton cliquables, verts si slot actif, gris sinon. Le tab sélectionné est enfoncé (`setChecked`).
- **Légende** : texte `A: Recherche et analyse | B: ...` chargé depuis `larcauth_criteria_of_levelsubject`.
- **Barres slots (`_SlotBar`)** : layout vertical (`QVBoxLayout`) dans une `QScrollArea`.
  - Chaque barre est une `QHBoxLayout` : `[F01] | Titre (nature, 72 chars max) ...... | ☐A ☐B ☐C ☐D`
  - Actives : fond blanc, bordure verte `#27ae60`
  - "Suivante" (première inactive) : fond gris, bordure pointillée `#bbb`
  - Suivantes inactives après la suivante : masquées (`setVisible(False)`)

### Panneau droit

Utilise `EvaluationDetailWidget` (depuis `views/evaluation_panel.py`) :
- **Label** : QLabel lecture seule
- **Nature** : QLineEdit éditable
- **Source** : QTextEdit avec support Markdown + barre d'outils formatage (B/I/H/•/🔗)
- **Critères** : grille 4×2 (ligne 0 = checkboxes A/B/C/D, ligne 1 = noms des critères)
- **Bouton Enregistrer** : met à jour SQLite + rafraîchit la barre et les tabs

## Fonctionnement

### Affichage progressif des slots

Seuls les slots actifs + le premier slot inactif ("suivant") sont visibles :

```
Cas initial (aucun slot actif) :
  F01 (grisé) ← seule barre visible
  F02..F12 (masqués)

Après activation de F01 :
  F01 (vert) + F02 (grisé) ← visibles
  F03..F12 (masqués)

Après activation de F01, F02, F03 :
  F01, F02, F03 (verts) + F04 (grisé) ← visibles
  F05..F12 (masqués)
```

### Sauvegarde

```python
_on_save_slot():
    form_data = self._detail.get_form_data()
    # form_data = {nature, source, crit_a..crit_d}
    # label conservé depuis l'existant (lecture seule)

    UPDATE larcauth_evaluation
    SET label=?, nature=?, source=?,
        crit_a=?, crit_b=?, crit_c=?, crit_d=?
    WHERE id=?

    rafraîchir barre (_update_visibility)
    rafraîchir tabs (_update_tabs)
```

### Changement de sélection

Clic sur un tab F01-F12 ou sur une barre → `_on_slot_selected` :
1. Met à jour `_detail` avec les données du slot
2. Charge les labels des critères
3. Met à jour les tabs (sélection visuelle)

## Classes

### `_SlotBar(QFrame)`

Barre horizontale cliquable :
- `set_data(eval_id, data)` : remplit titre (nature[:72]), checkboxes
- `clear()` : vide le slot
- `restyle()` : applique le style visuel selon l'état (active / suivante) — réactivité thème via `_restyle()`
- Signal `clicked(int)` : émet le slot_index

### `EvalManagerWindow(ThemedDialog)`

Fenêtre principale de gestion :
- `_build_ui()` : splitter + panneaux gauche/droit
- `_load_data()` : charge les évaluations depuis SQLite
- `_update_visibility()` : filtre les barres visibles (actives + suivante)
- `_update_tabs()` : colorie les tabs (vert/gris)
- `_on_slot_selected(slot_index)` : bascule la sélection
- `_on_save_slot()` : sauvegarde et rafraîchit

## Responsive design

- Le `QSplitter` permet de redimensionner les deux panneaux
- Les barres de gauche s'étirent horizontalement (`QSizePolicy.Expanding`)
- Les champs du panneau droit (`QLineEdit`, `QTextEdit`) ont `QSizePolicy.Expanding` horizontal
- Le `QTextEdit` source a `Expanding` vertical → prend toute la hauteur disponible
- Les critères en grille 4×2 gardent une hauteur fixe (`QSizePolicy.Fixed`)

## Dépendances

- `views/evaluation_panel.py` : `EvaluationDetailWidget` (panneau droit)
- `common/database.py` : `db.local_conn` (SQLite)
