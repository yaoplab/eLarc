---
name: search-detail-pattern
description: Pattern canonique recherche + fiche détail — barre de recherche, tableau résultats, panneau détail à droite (ratio 3:1), skeleton loading.
category: page-pattern
trigger: recherche, search, détail, detail, fiche, formulaire recherche, search-detail
---

# Search-Detail Pattern

## Structure (ratio 3:1)

```
┌─ Titre + bouton action ─────────────────────────────────┐
├─ Barre recherche (2+ champs + bouton) ──────────────────┤
├──────────────────────┬───────────────────────────────────┤
│ Tableau résultats    │ Panneau détail                   │
│ (stretch 3)          │ (stretch 1)                      │
│ - skeleton loading   │ - photo + badges                 │
│ - état vide inline   │ - infos + bouton "Ouvrir"        │
└──────────────────────┴───────────────────────────────────┘
```

## Règles SD

| # | Règle |
|---|---|
| SD1 | Titre `title_medium`, aligné à gauche |
| SD2 | Barre recherche à 2+ champs dédiés + bouton FILLED |
| SD3 | Ratio 3:1 via `QHBoxLayout` avec stretch |
| SD4 | Tableau résultats avec colonnes + badges via `setCellWidget` |
| SD5 | Skeleton loading pendant la requête |
| SD6 | État vide inline (pas de popup) |
| SD7 | Panneau détail avec photo + badges + infos |
| SD10 | Focus initial sur le 1er champ (`QTimer.singleShot(50, ...)`) |
