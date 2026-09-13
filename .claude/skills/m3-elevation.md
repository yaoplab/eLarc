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

## Le piège inverse (2026-09-09) : ajouter `theme=` casse un style qui marchait

Corriger le bug ci-dessus sur un fichier existant en ajoutant juste `theme=`
partout **peut introduire une régression visuelle silencieuse**, pas
seulement réparer un style manquant. Trouvé sur `LarcSuperviseur/views/login.py` :

- `M3Label._update_style()` fait `self.setStyleSheet(f"M3Label {{ ... }}")`
  dès que `theme=` est posé — un style **posé directement sur le widget**.
  Un ancien QSS parent du type `QLabel#hdrTitle {{ font-weight: bold; }}`
  (souvent posé une fois sur la fenêtre via un `QssHelper.*_qss()`) est
  **écrasé** par ce style local, silencieusement — pas d'erreur, pas
  d'avertissement, juste un titre qui n'est plus en gras.
- Le style par défaut de `M3Label` est `style="body_medium"` (14px, normal) —
  si l'ancien QSS donnait un rôle typographique différent (titre, libellé),
  poser `theme=` sans `style=` fait perdre ce rôle.

**La bonne pratique — ne jamais mélanger les deux mécanismes :**
- Toujours passer `style=` (`title_large`, `body_medium`, `label_medium`...
  voir `phibuilder/theme/typo.py` pour la liste) pour le rôle typographique.
- Utiliser `.set_color(couleur)` pour la couleur sémantique (`p.text_strong`,
  `p.text_soft`, `p.error`...) — ça préserve le `style=` déjà posé,
  contrairement à un `setStyleSheet("color: ...")` qui l'écraserait à son tour.
- Ne **plus** compter sur un QSS parent par nom d'objet (`#hdrTitle`, etc.)
  pour styliser un widget `phibuilder` une fois que `theme=` lui est passé —
  ce mécanisme ne fonctionne que tant que le widget est resté sans style
  (c'est-à-dire cassé). Idem pour `M3Button` : utiliser `variant=`/
  `accent_color=`, pas un QSS `#objectName { background: ... }` sur l'ancêtre.
- **Vérifier visuellement avant/après** (capture d'écran) tout ajout de
  `theme=` sur du code existant qui avait déjà un style par QSS ancêtre —
  ce n'est jamais un changement purement mécanique.

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
