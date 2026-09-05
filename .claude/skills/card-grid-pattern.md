---
name: card-grid-pattern
description: Grille de vignettes responsive — QScrollArea + QGridLayout adaptatif, cartes avec photo + badges, skeleton loading, clic → détail. Pattern canonique Larc.
category: page-pattern
trigger: grille, carte, vignette, grid, card, responsive, photo, StaffGrid, StudentCard, reflow
---

# Card Grid Pattern — Grille Responsive

## Structure obligatoire

```
QScrollArea (M3ScrollArea, widgetResizable=True)
└── QWidget container
    └── QGridLayout (spacing=ds.space_xs)
        └── Cards (minWidth=CARD_W, fixedHeight=CARD_H)
```

## Règles CG

| # | Règle | Obligatoire |
|---|---|---|
| CG1 | Header avec titre + compteur + boutons action | Oui |
| CG2 | `cols = max(1, viewport.width() // (card_w + spacing))` au resize | Oui |
| CG3 | Skeleton loading via QStackedWidget | Oui |
| CG4 | État vide "Aucun élément" si liste vide | Oui |
| CG5 | Chaque carte = widget réutilisable (pas de QFrame custom) | Oui |
| CG10 | Clic carte → détail (signal ou QStackedWidget) | Oui |
| CG12 | `resizeEvent` recalcule les colonnes et repositionne | Oui |

## Code canonique

```python
scroll = M3ScrollArea()
scroll.setWidgetResizable(True)
container = QWidget()
grid = QGridLayout(container)
grid.setSpacing(ds.space_xs)
scroll.setWidget(container)

def _reflow(self):
    cols = max(1, scroll.viewport().width() // (CARD_W + SPACING))
    for i, card in enumerate(self._cards):
        grid.addWidget(card, i // cols, i % cols)
```
