---
name: ui-quality
description: Finition visuelle professionnelle — icônes, tailles, câblage, labels, tooltips, états vides, messages d'erreur.
category: design
trigger: UI, finition, icône, tooltip, état vide, erreur, label, visuel, professionnel
---

# UI Quality — Finition Professionnelle

## Check-list

1. **Icônes** : chaque bouton a une icône via `icon()` (pas de texte seul)
2. **Labels** : chaque champ a un label visible (au-dessus ou placeholder)
3. **Tooltips** : boutons d'action avec `setToolTip()`
4. **État vide** : liste vide → message "Aucun élément" avec icône
5. **Erreurs** : messages d'erreur rouges (`ds.p.error`), pas de popup brut
6. **Tailles** : fenêtres ≥ 987×610 (golden ratio minimum)
7. **Alignement** : boutons d'action en bas à droite
8. **Désactivé** : boutons grisés quand l'action est impossible
9. **Gap icône↔texte (V8)** : bouton icône+texte → `text-align: left` dans son QSS (K26 sidebar-spec) → gap natif 8px = `ds.space_xs` ; détecté par `lint_ui_quality.py`

## Règles de style des tableaux — OBLIGATOIRES

Tout tableau de données DOIT respecter ces règles :

### Structure
| Colonne | Règle |
|---|---|
| **ID** | Centré horizontalement (`Qt.AlignCenter`) |
| **Nom / Libellé** | Gras (`QFont` avec `setBold(True)`) |
| **Code** | Centré, largeur fixe (60-80px) |
| **Valeurs numériques** | Centrées, formatées (séparateur de milliers) |
| **Couleur** | Pastille colorée via `setCellWidget(QLabel)` avec `background:{hex}` — JAMAIS le code hex en texte |
| **Actions** | `setCellWidget(QWidget)` contenant des `QPushButton` en ligne avec espacement `ds.space_xxs` |
| **Dernière colonne** | `setStretchLastSection(True)` — pas d'espace vide à droite |

### Style de base
```python
table = M3TableWidget()                    # via phibuilder — JAMAIS QTableWidget brut
table.setStyleSheet(ds.table_qss())        # QSS standard
table.setSelectionBehavior(QAbstractItemView.SelectRows)
table.setEditTriggers(QAbstractItemView.NoEditTriggers)
table.verticalHeader().setVisible(False)
```

### Pastille de couleur
```python
color_widget = QLabel()
color_widget.setFixedSize(32, 20)
color_widget.setStyleSheet(
    f"background:{color_hex};border-radius:{ds.radius_xs}px;"
    f"border:1px solid {theme_manager.palette.outline};")
table.setCellWidget(row, col, color_widget)
```

### État vide
```python
if not data:
    table.setRowCount(0)
    empty = QLabel("Aucune donnée")
    empty.setAlignment(Qt.AlignCenter)
    empty.setStyleSheet(f"color:{p.text_soft};font-size:{ds.font_title}px;")
    layout.addWidget(empty)
```

### Ratio Golden Ratio
La table ne doit pas occuper >62% de la largeur si un panneau de détail est présent à droite (split 62/38 via `ds.golden_split`).

## Icônes disponibles (~45)

`person, add, edit, delete, save, close, check, search, filter_list, refresh, settings, dashboard, event, calendar_today, schedule, contract, description, folder, receipt_long, work, group, badge, print, download, upload_file, attach_money, warning, error, info, school, home`

Usage : `icon('save', color=ds.p.primary, size=ds.icon_sm)`
