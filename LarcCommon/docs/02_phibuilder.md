
# PhiBuilder — UI Toolkit M3 + Fibonacci

## Principes

### Proportions d'or (φ = 1.618)

Toutes les dimensions suivent la suite de Fibonacci ou le nombre d'or :

- Espacements : 0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144 (Fibonacci × base=4px)
- Typographie : 11, 12, 14, 16, 22, 24, 28, 32, 36, 45, 57 (M3 spec)
- Angle d'or : 137° pour dispositions radiales

### Material Design 3

Les couleurs sont générées dynamiquement via le HCT color engine
de `materialyoucolor` (port officiel du Material Color Utilities Google).

## Architecture du thème

```
Seed Color (#6750A4)
    ↓
Hct.from_int(argb)
    ↓
SchemeTonalSpot (ou variant)
    ↓
MaterialDynamicColors
    ↓
60+ rôles de couleur (primary, on_primary, primary_container, ...)
```

### Variants supportés

| Variant | Description |
|---|---|
| `tonal_spot` | Standard M3 (défaut) |
| `expressive` | Plus saturé |
| `fidelity` | Fidèle à la source |
| `monochrome` | Monochrome |
| `neutral` | Neutre |
| `vibrant` | Vibrant |
| `rainbow` | Arc-en-ciel |
| `fruit_salad` | Coloré |
| `content` | Basé sur contenu |

## Widgets

| Widget | Variants | Usage |
|---|---|---|
| `M3Button` | filled, tonal, outlined, text | Boutons d'action |
| `M3Card` | elevated, filled, outlined | Conteneurs |
| `M3TextField` | filled, outlined | Saisie texte |
| `M3Label` | 15 styles M3 | Texte typographié |
| `M3ComboBox` | — | Listes déroulantes |
| `M3ListWidget` | single/two/three line | Listes |
| `M3TableWidget` | — | Tableaux |
| `M3Dialog` | confirm/alert | Boîtes de dialogue |
| `M3Snackbar` | — | Notifications temporaires |
| `M3BottomSheet` | — | Panneau latéral bas |
| `M3NavigationBar` | — | Barre de navigation basse |
| `M3Sidebar` | — | Panneau de navigation latéral |

## PhiBuilder facade

```python
builder = PhiBuilder(seed_color="#6750A4", is_dark=False)
builder.apply(widget)           # Appliquer le QSS
builder.set_dark_mode(True)     # Mode sombre
builder.toggle_dark_mode()      # Basculer
builder.set_seed_color("#FF0000")
builder.set_font("Roboto")
builder.set_variant("monochrome")
builder.export_qss("theme.qss")
builder.export_theme_json("theme.json")
builder.palette                 # → dict[str, str] des couleurs
```
