---
name: design-tokens
description: Tokens numériques Larc — espacements Fibonacci×4, couleurs M3, typographie, hauteurs. JAMAIS de px en dur.
category: design
trigger: spacing, espacement, token, couleur, typo, font, radius, field_height, button_height, ds.space, ds.p., ds.font, Fibonacci
---

# Design Tokens — Fondation du Design System

**Règle absolue** : Aucune valeur px littérale dans le code. Tout passe par `ds.*`.

## Espacements (Fibonacci × 4)

| Token | px | Usage |
|---|---|---|
| `ds.space_xxs` | 4 | Inner padding (gap icône-texte d'un bouton = `ds.space_xs` 8px, voir sidebar-spec K26) |
| `ds.space_xs` | 8 | Padding léger |
| `ds.space_sm` | 12 | Gap standard |
| `ds.space_md` | 20 | Marges intérieures |
| `ds.space_lg` | 32 | Marges conteneurs |
| `ds.space_xl` | 52 | Grands écarts |
| `ds.space_xxl` | 84 | Très grands écarts |
| `ds.space_xxxl` | 136 | Marges page |

## Hauteurs composants

`ds.field_height=32`, `ds.button_height=52`, `ds.header_height=52`, `ds.icon_md=32`, `ds.icon_sm=18`, `ds.kpi_card_height=80`, `ds.sidebar_width=233`, `ds.table_row_min=21`

## Bordures

`ds.radius_none=0`, `ds.radius_xs=4`, `ds.radius_sm=8`, `ds.radius_md=12`, `ds.radius_lg=16`, `ds.radius_xl=28`, `ds.border_width=1`

## Typographie

`ds.font_h1=28`, `ds.font_h2=22`, `ds.font_title=16`, `ds.font_body=14`, `ds.font_small=12`

## Palette (via `ds.p.*`)

`ds.p.primary`, `ds.p.on_primary`, `ds.p.surface`, `ds.p.on_surface`, `ds.p.background`, `ds.p.error`, `ds.p.outline`, `ds.p.success`, `ds.p.text_strong`, `ds.p.text_soft`

## Golden Ratio

`ds.GOLDEN=1.618`, `ds.golden_split(total)` → (large, small), `ds.golden_width(total)`, `ds.golden_height(total)`

## QSS generators

`ds.flat_input_qss()` → style pour champs texte
`ds.table_qss()` → style pour tableaux
`ds.panel_qss()` → style pour panneaux
