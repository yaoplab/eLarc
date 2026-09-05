---
name: input-ergonomics
description: Saisie sûre — garde-molette, composants bornés, SectionsFlow, tableaux bornés/triables, dialogues stylés par widget, ligne retrouvée par ID
category: design
trigger: molette, wheel, spinbox, combo, saisie, scroll, WheelGuard, SectionsFlow, setStretchLastSection, field_max_width, tableau borné
---

# Input Ergonomics — Saisie sûre & composants bornés

Deux fragilités : la **molette** change une valeur au survol pendant le scroll (donnée altérée sans clic), et la **responsivité appliquée au composant** (champ/combo immense sur écran large) au lieu du conteneur. Le composant atomique n'a ni comportement de molette implicite, ni taille propre — la **section sémantique** est le seul point de responsivité.

## Règles IE

| # | Règle | ❌ Anti-pattern | ✅ Obligatoire |
|---|---|---|---|
| IE1 | **Garde-molette** | Molette qui change spin/date/combo au survol sans focus | `install_wheel_guard(app)` dans chaque `main.py` — `Wheel` ignoré sauf si le widget a le focus |
| IE2 | **Combo au clic** | Combo qui change au passage de la molette | Sélection modifiée UNIQUEMENT par clic ou clavier |
| IE3 | **Sections en onglets** | Formulaire à défilement unique, scrolls imbriqués | Une section par onglet tenant à l'écran ; ≤ 1 QScrollArea par écran |
| IE4 | **Erreur sur l'onglet** | Champ invalide caché dans un onglet sans indice | Pastille d'erreur sur le libellé de l'onglet |
| IE5 | **Responsivité au conteneur** | `setMinimumWidth`/`Expanding` sur un champ/combo | Composant sans taille propre ; la section décide largeur et colonnes |
| IE6 | **Largeur plafonnée** | Combo/champ pleine largeur sur écran large | `ds.field_max_width` (360) sur les composants ; `ds.form_max_width` (720) sur le contenu des POPUPS uniquement ; plein écran = la grille adapte ses colonnes |
| IE7 | **SectionsFlow** | Sections empilées en pleine largeur ; largeurs dictées par les sizeHint (colonnes inégales) | Colonnes ÉGALES : `N = max(1, largeur // (min_width + espacement))`, `setFixedWidth(col_w)` sur chaque carte, reflow **différé** (`QTimer.singleShot(0)`) |
| IE7e | **Remplissage vertical** | `fill_vertical=True` quand les cartes côte à côte doivent remplir la page | `Expanding` sur flux ET cartes, stretch sur les lignes occupées, **sans `AlignTop`**, `grid.activate()` — uniquement quand toutes les cartes sont sur UNE ligne |
| IE8 | **Tableaux bornés** | `setStretchLastSection(True)` (colonne d'action qui s'étire sans fin) ; tableau débordant de sa section | Colonnes fixées au contenu ; SEULE la 1ʳᵉ colonne `QHeaderView.Stretch` + `setStretchLastSection(False)` |
| IE8d | **Réglables + triables** | Tri jamais activé | `setSortingEnabled(False)` PENDANT le remplissage puis `(True)` à la fin — sur TOUS les tableaux |
| IE9 | **Boutons de dialogue stylés par widget** | Bouton sans style dans un dialogue (QSS global inefficace → blanc sur blanc) | `setStyleSheet()` explicite par bouton ; QMessageBox patchées via `larccommon/msgbox.py` |
| IE10 | **Ligne par ID** | Handler qui ouvre `self._liste[row]` (après un tri, l'index ne correspond plus) | ID stocké via `item.setData(Qt.UserRole, id)` — insensible au tri |

## Code clé

```python
# main.py — brancher une fois par app
from larccommon.ergonomics import install_wheel_guard
install_wheel_guard(app)   # WheelGuard : QAbstractSpinBox/QComboBox sans focus → molette ignorée

# IE5/IE6 — composant borné
combo.setMaximumWidth(ds.field_max_width)

# IE8 — tableau borné
h = table.horizontalHeader()
h.setSectionResizeMode(0, QHeaderView.Stretch)     # 1ʳᵉ colonne extensible
h.setStretchLastSection(False)
table.setColumnWidth(3, ds.field_height + ds.space_xs)  # colonne action

# IE7 — SectionsFlow (composant partagé : LarcRH/views/sections_flow.py)
layout.addWidget(SectionsFlow([card1, card2], min_width=610))

# IE10 — retrouver l'enregistrement par ID
item.setData(Qt.UserRole, record_id)
```

## Checklist

- [ ] `install_wheel_guard(app)` dans chaque `main.py` ; molette ignorée sans focus
- [ ] Sections en onglets ; ≤ 1 QScrollArea par écran ; pastille d'erreur sur l'onglet
- [ ] Aucune taille propre sur les composants ; plafonds `ds.field_max_width` / `ds.form_max_width`
- [ ] Sections de page dans `SectionsFlow` (colonnes égales, reflow différé)
- [ ] Tableaux : 1ʳᵉ colonne Stretch, jamais `setStretchLastSection(True)`, tri activé en fin de remplissage
- [ ] Boutons de dialogue stylés par widget ; ligne retrouvée par ID jamais par index
- [ ] Linters verts : `lint_qss_hardcoding.py`, `lint_ui_quality.py`

## Références croisées

- design-tokens (`ds.field_max_width`, `ds.form_max_width`), zero-hardcoding, ergonomics (fenêtres de liste), form-pattern, ui-quality (V8)
