---
name: design-system-larc
description: Design System Larc — ds singleton (Fibonacci×4, Golden Ratio, tokens spacing/couleurs/typo), ThemeManager (5 thèmes M3), QSS generators.
category: design
trigger: design system, ds., theme_manager, phi, Fibonacci, golden ratio, M3
---

# Design System Larc

## Singleton ds

```python
from larccommon.design_system import ds
# Tokens : ds.space_sm, ds.space_md, ds.field_height, ds.kpi_card_height
# Couleurs : ds.p.primary, ds.p.surface, ds.p.error, ds.p.success
# Générateurs QSS : ds.flat_input_qss(), ds.table_qss(), ds.panel_qss()
# Golden Ratio : ds.golden_split(total) → (62%, 38%)
```

## 5 Thèmes

`océan` (clair/bleu), `forêt` (clair/vert), `nuit` (sombre/violet), `lave` (sombre/rouge), `sable` (clair/ambre)

```python
theme_manager.set_active("nuit")
```

Voir aussi `theme-reactivity` (pattern _STYLE + _restyle_all) et `design-tokens` (table complète).
