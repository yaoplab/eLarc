---
name: dashboard-pattern
description: Pattern canonique de page tableau de bord — KPIs, graphiques, tableaux avec totaux. Structure : KPI row → charts → detail table.
category: feature
trigger: dashboard, KPI, tableau de bord, statistiques, graphique, indicateur, bar chart, donut
---

# Dashboard Pattern — Pattern Canonique

## Structure standard

```
┌─────────────────────────────────────────────┐
│  KPI Row (4-6 cards)                        │
│  [Effectif] [Contrats] [Masse salariale]    │
├────────────────────┬────────────────────────┤
│  Chart Left        │  Chart Right           │
│  (bar/donut)       │  (trend/line)          │
├────────────────────┴────────────────────────┤
│  Detail Table (with totals row)             │
│  Colonnes | Total                           │
└─────────────────────────────────────────────┘
```

## KPI Cards

```python
kpi = M3Card(theme=phi, variant=ds.CARD_ELEVATED)
kpi.setFixedHeight(ds.kpi_card_height)
# label AU-DESSUS, valeur en grand, variation en petit
```

## Graphiques

Utiliser `charts.py` — QPainter widgets (HBarCell, RingChart, StatChange).
Couleurs depuis `ds.p.*` et `theme_manager.palette.*`.

## Tableau avec totaux

Dernière ligne en gras avec fond `ds.p.surface_variant`.
Colonnes numériques alignées à droite.
