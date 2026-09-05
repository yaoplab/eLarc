---
name: sidebar-spec
description: Spécification visuelle exacte du sidebar — 233px, logo, catégories, compteurs, thème réactif.
category: design
trigger: sidebar, barre latérale, navigation, menu gauche
---

# Sidebar — Spécification

| Propriété | Valeur |
|---|---|
| Largeur | 233px (`ds.sidebar_width`) |
| Fond | `surface_variant` |
| Bordure droite | 1px `border` |
| Logo | centré, max 55px haut |
| Boutons | `_CategoryButton`, icône + label + compteur |
| Espacement | `ds.space_xs` |
| Gap icône↔texte (K26) | `text-align: left` dans le QSS du bouton + `setIconSize(theme_manager.image.icon_btn)` → gap natif Qt 8px = `ds.space_xs` |

## Pattern

```python
sidebar = QWidget()
sidebar.setFixedWidth(ds.sidebar_width)
sidebar.setStyleSheet(f"background:{p.surface_variant};border-right:1px solid {p.border};")
```
