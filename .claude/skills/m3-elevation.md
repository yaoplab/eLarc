---
name: m3-elevation
description: Comment M3 exprime l'élévation sans ombre (tons de surface) et pourquoi un M3Card sans theme= est invisible — correspondances web/Qt
category: design
trigger: élévation, carte invisible, M3Card, surface_container, theme=None, ombre portée
---

# Élévation M3 sans ombre — et le piège du `theme=None`

## Le principe M3

Material Design 3 exprime l'élévation d'un composant (carte, dialogue, menu)
par des **tons de surface distincts**, pas par une ombre portée. L'échelle
officielle va de `surfaceContainerLowest` (le moins élevé) à
`surfaceContainerHighest` (le plus élevé) — 5 tons entre `surface` et
`surfaceVariant`. LarcCommon expose ça via `Palette.surface_container_low`,
`.surface_container`, `.surface_container_high` (`theme.py`).

## Le bug trouvé le 2026-09-08 (et sa vraie cause)

Un `M3Card(variant=CardVariant.ELEVATED)` dans `event_generator_dialog.py`
rendait un cadre totalement invisible — pas de fond, pas de bordure, pas de
rayon. Cause réelle : **`M3Card` avait été construit sans `theme=`**, et
`_update_style()` faisait `if self._theme is None: return` — un no-op
silencieux, présent dans 22 des 25 widgets `phibuilder`. Depuis, ce cas émet
un `UserWarning` explicite (`LarcCommon/phibuilder/widgets/*.py`) — si un
écran affiche des widgets sans style, chercher ce warning en premier.

**Exception connue — `M3Dialog` (`phibuilder/widgets/dialog.py`) :** son
`__init__` garde une forme différente du garde-fou, `if theme is None: return`
directement sur le paramètre du constructeur (pas sur `self._theme` dans
`_update_style()`) — donc un `M3Dialog` construit sans `theme=` n'a ni layout
ni warning, silencieusement. Pas encore couvert par le `UserWarning`
ci-dessus ; corrigé dans un futur passage, pas dans celui du 2026-09-08.

La question des tons `surface_container` (secondaire, aussi corrigée) ne se
posait même pas ici : `M3Card.ELEVATED` utilise `c.surface`, pas
`c.surface_container` — deux bugs différents découverts dans la même session.

## Correspondances universelles (web ↔ Qt/PySide6)

| Principe | Web (CSS/JS) | Qt/PySide6 (LARC) |
|---|---|---|
| Élévation sans ombre | tons de surface M3 (Material Web) | `Palette.surface_container_*` (`theme.py`) |
| États d'interaction | `:hover` `:focus-visible` `:active` `:disabled` | QSS `:hover`/`:pressed`/`:disabled` ; `:focus` visible via `lint_focus_visible.py`/`keyboard_navigator.py` |
| Rythme d'espacement 8pt | scale `gap`/`padding` (Tailwind) | `ds.space_*` |
| États vides/skeleton | composants dédiés | voir `composition-principles` |
| Grille d'alignement | CSS Grid/Flexbox (auto) | `PhiGrid` (`phibuilder/phi/phi_grid.py`) — Qt n'aligne rien automatiquement, plus facile à louper qu'en CSS |

## Checklist avant de committer un écran avec M3Card

- [ ] `theme=theme_manager.phi_theme` passé explicitement (jamais compter sur un défaut)
- [ ] Aucun `UserWarning` de widget phibuilder dans la sortie console au lancement
- [ ] La carte reste visible à l'œil contre son fond (capture d'écran — voir `composition-principles`)
