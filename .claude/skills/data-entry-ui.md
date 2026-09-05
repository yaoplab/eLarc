---
name: data-entry-ui
description: Saisie de données dense 10/10 — angles droits, palette marque, validation in-line, AdaptiveScrollArea, PasswordLineEdit, ComboBox épurée
category: design
trigger: data entry, saisie dense, formulaire 10/10, angles droits, has_error, errorMessage, PasswordLineEdit, AdaptiveScrollArea, combo épurée, palette marque
---

# Data Entry UI — Saisie dense (skill theme.txt aligné)

## Palette marque (dans `larccommon/theme.py` `_THEME_PALETTES`)

| Rôle | Light | Dark |
|---|---|---|
| PRIMARY | `#1F4494` | `#1F4494` |
| ACCENT / active | `#24A9E1` | `#24A9E1` |
| ERROR | `#EF4444` | `#EF4444` |
| BG_APP / background | `#F0F4F8` | `#0F172A` |
| BG_PANEL / surface | `#FFFFFF` | `#1E293B` |
| BORDER / outline | `#CBD5E1` | `#334155` |
| TEXT / text_strong | `#0F172A` | `#F1F5F9` |
| TEXT_SECONDARY / text_soft | `#5B6778` | `#A5B0BF` |

`Palette.accent` = `active` = `#24A9E1` (hover + soulignements). Tout passe par
`theme_manager.palette` / `phi_theme.colors` — jamais de hex en dur.

## Rayons (skill : boutons arrondis, reste angles droits)

| Élément | Token | Valeur |
|---|---|---|
| Boutons | `ds.radius_btn` / `RADIUS_BTN` (phi) | **5px** (F₅) |
| Champs, cartes, listes | `ds.radius_xs` / `ds.radius_sm` | **0px** (angles droits) |
| Dialogues/drawers | `ds.radius_md` | 12px (inchangé) |

## Widgets data-entry (phibuilder.widgets)

| Widget | Rôle |
|---|---|
| `AdaptiveScrollArea` | Scrollbar verticale SEULEMENT si hauteur < **768px** (`resizeEvent`) ; zéro défilement visible sinon |
| `M3TextField.set_error(msg)` | Validation in-line : propriété `has_error="true"` + bordure 2px `error` ; le `QLabel#errorMessage` (11px) s'insère sous le champ par le formulaire |
| `PasswordLineEdit(eye_icon=...)` | Echo Password + action œil (TrailingPosition) ; icônes fournies par l'appelant (`md3_icon("visibility"/"visibility_off")`) — phibuilder sans dépendance icônes |
| `M3ComboBox` | **Épurée** : flèche supprimée (`::drop-down` largeur 0), soulignement inférieur 2px primary, `:hover` fond `surface_container_highest`, curseur main |

## Fragments QSS (StyleBuilder `_data_entry()`)

`QFrame#sectionCard` (aucune bordure, angles droits) · `QLabel#sectionTitle`
(13px 700 uppercase, soulignement 2px accent) · `QLabel#fieldLabel` (12px 500 text_soft) ·
`QLabel#errorMessage` (11px error) · `*[class="mono-data"]` (mono, primary).

## Pattern formulaire (avec form-pattern)

```python
field = M3TextField(theme=phi)
field.setFixedHeight(ds.field_height)
field.setStyleSheet(ds.flat_input_qss())
field.set_error("Champ requis")          # bordure rouge + has_error="true"
err = QLabel("")                          # QLabel#errorMessage (11px) sous le champ
err.setObjectName("errorMessage"); err.hide()
# à la validation : err.setText(msg); err.show() / field.set_error(None); err.hide()
```

## Checklist

- [ ] Palette marque : aucun hex hors `_THEME_PALETTES` / `theme_manager.palette`
- [ ] Champs/cartes : angles droits (radius_xs/sm = 0) ; boutons 5px (`radius_btn`)
- [ ] Formulaire dense : `AdaptiveScrollArea` (768px) en conteneur central
- [ ] Validation : `set_error(msg)` + `QLabel#errorMessage` sous le champ
- [ ] Mots de passe : `PasswordLineEdit` avec œil
- [ ] Combos : sans flèche, soulignement accent, curseur main
- [ ] `lint_all.py` : [R][D][V][C] PASS

## Références

- `[[pyside6-data-entry-ui-builder]]` — skill SOURCE complet (ex. theme.txt)
- `[[form-pattern]]` — structure sections/cards ; `[[design-tokens]]` — ds.*
- `[[theme-reactivity]]` — `_restyle_all` obligatoire (palette au runtime)
- `[[input-ergonomics]]` — garde-molette IE1/IE2 sur les champs
