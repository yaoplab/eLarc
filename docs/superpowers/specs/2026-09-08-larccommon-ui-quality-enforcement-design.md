# LarcCommon UI Quality Enforcement — Design

Date: 2026-09-08 (révisé après inspection visuelle réelle des écrans)

## Contexte

L'écart de qualité graphique entre `LarcCommon/larccommon/login.py` (widgets PySide6
bruts, QSS manuel) et `LarcCommon/larccommon/dialogs/event_generator_dialog.py`
(construit sur `phibuilder` M3Card/M3Button, tokens `ds.*`) a d'abord semblé être un
problème de conformité au design system. Une inspection visuelle réelle (captures
d'écran des deux fenêtres lancées en direct, 2026-09-08) a renversé ce diagnostic :

- **login.py**, pourtant hors design system, est visuellement réussi : rythme
  vertical clair, carte contenue, hiérarchie nette, aucun espace mort.
- **event_generator_dialog.py**, pourtant 100% conforme (M3Card, M3Button, tokens
  `ds.*`), est visuellement faible : la carte élevée est **invisible** (aucun
  contraste avec le fond), plus de la moitié du panneau droit est un vide gris, le
  panneau de sélection est une zone blanche vide sans état vide explicite.

**Conclusion :** la conformité au vocabulaire du design system (bons widgets, bons
tokens) ne garantit pas la qualité de composition. Ce sont deux axes différents.
Cette spec traite donc deux problèmes distincts, dans cet ordre de priorité :

1. Un défaut d'implémentation du design system lui-même (haute leverage : un seul
   correctif répare toutes les cartes du projet).
2. Une absence de gouvernance empêchant la dérive de conformité (login.py face au
   design system) — la gouvernance initialement prévue dans cette spec.

## Root cause principale : système de tons M3 incomplet

`LarcCommon/larccommon/theme.py:40-41` :

```python
self.surface_container = p.surface_variant
self.surface_container_highest = p.surface_variant
```

Material Design 3 définit une échelle de 5-6 tons de surface distincts
(`surfaceContainerLowest` → `surfaceContainerLow` → `surfaceContainer` →
`surfaceContainerHigh` → `surfaceContainerHighest`) — le mécanisme officiel par
lequel M3 exprime l'élévation **sans ombre portée**. Ici, tous les rôles sont
aliasés sur la même valeur que `surface_variant`. Une `M3Card(variant=ELEVATED)`
posée sur un fond `surface_variant` devient donc invisible par construction —
partout dans le projet, pas seulement dans le générateur d'événements.

C'est le point de plus haute leverage de cette spec : corriger l'échelle de tons
une fois dans `theme.py`/`design_system.py` répare la lisibilité de toutes les
cartes élevées existantes, sans toucher au code appelant.

### Correspondances universelles (web ↔ Qt/PySide6)

Les principes de composition qui rendent un artefact web "réussi" sont
platform-agnostic ; ce qui manque n'est pas une réflexion neuve mais leur
portage/documentation côté Qt :

| Principe | Web (CSS/JS) | État LARC/Qt |
|---|---|---|
| Élévation sans ombre | tons de surface M3 (Material Web) | cassé (voir ci-dessus) |
| États d'interaction | `:hover` `:focus-visible` `:active` `:disabled` | QSS `:hover`/`:pressed`/`:disabled` OK ; `:focus` visible en chantier (`lint_focus_visible.py`, `keyboard_navigator.py`) |
| Rythme d'espacement 8pt | scale `gap`/`padding` (Tailwind) | `ds.space_*`, bien posé |
| États vides/skeleton | composants dédiés | ad hoc, un seul pattern le documente (SD6) |
| Grille d'alignement | CSS Grid/Flexbox (auto-align) | `PhiGrid` en chantier, pas validé ; Qt n'aligne rien automatiquement (plus facile à louper qu'en CSS) |

## Objectifs

1. Le système de tons M3 est complet et correct — toute carte élevée reste lisible
   contre son fond, partout dans le projet.
2. Cette correspondance web↔Qt et le principe d'élévation M3 sont documentés une
   fois, dans un skill, pour ne plus être redécouverts à la main.
3. Un petit nombre de principes de composition transverses (pas une liste
   illimitée) sont extraits des patterns existants (`_section_card` de
   `form-pattern`, `SD6` de `search-detail-pattern`) et généralisés à tout écran,
   pas seulement aux patterns qui les documentaient déjà.
4. Une vérification visuelle (capture d'écran réelle, pas seulement les linters)
   devient une étape du processus de revue — filet de sécurité pour tout ce qui
   n'est pas mécanisable.
5. Les skills et linters de LarcCommon empêchent qu'un écran dérive du design
   system (widgets bruts, hardcoding) sans que rien ne le signale — pour tout
   **nouveau** code ou code **modifié** (objectif de gouvernance initial, conservé).
6. La dette déjà en place (login.py et ~70 violations connues) reste visible dans
   les rapports d'audit mais ne bloque aucun commit tant qu'elle n'est pas touchée.

## Non-objectifs (hors scope explicite)

- Corriger les 72 hardcodings existants ou migrer `login.py` (ou tout autre écran
  des 8 apps) vers phibuilder. Dette visible et non aggravable, traitée plus tard.
- Remettre en place une CI GitHub Actions (`.github/workflows/ci.yml`) — dérive
  documentaire signalée mais non traitée ici.
- Toucher au contenu fonctionnel des 8 apps.
- Produire une liste exhaustive de principes de composition à la manière d'un
  design system complet (Material Design a mis des années, avec une équipe dédiée
  et des revues humaines constantes — non réaliste ici). On corrige la cause
  racine trouvée (tons M3) et on documente 3-4 principes généralisables trouvés en
  pratique ; le reste reste couvert par la QA visuelle, pas par des règles ad hoc.

## Architecture

### Phase 0 — Corriger le système de tons M3 (priorité 1, plus haute leverage)

- `theme.py` : donner à `surface_container`, `surface_container_low`,
  `surface_container_high`, `surface_container_highest` des valeurs de ton
  distinctes (pas d'alias sur `surface_variant`) pour chacune des 5 palettes de
  thème (océan, forêt, nuit, lave, sable), en respectant le contraste WCAG déjà
  vérifié par `lint_palette_contrast.py`.
- Revalider visuellement `event_generator_dialog.py` (et d'autres écrans utilisant
  `M3Card` ELEVATED/FILLED) après correctif — capture d'écran avant/après.
- Documenter le principe d'élévation M3 et la table de correspondance web↔Qt dans
  un skill (`color-rules.md` étendu, ou nouveau `m3-elevation.md`).

### Phase 1 — Gouvernance anti-dérive (scope initial, conservé)

1. **Réparer le pre-commit** — `.pre-commit-config.yaml` pointe encore vers
   `C:/projets/scripts/...` (cassé depuis la migration C:→D: du 2026-08-10).
   Remplacer par `D:/projets/scripts/...`.
2. **Nouveau linter `scripts/lint_widget_purity.py`** — détecte l'instanciation de
   widgets PySide6 bruts hors exceptions autorisées par `CLAUDE.md`
   (`QMessageBox`, `QApplication`, `QVBoxLayout`, `QHBoxLayout`, `QGridLayout`,
   `QButtonGroup`, `QTableWidgetItem`), avec suggestion du widget phibuilder
   correspondant (`QPushButton`→`M3Button`, `QLineEdit`→`M3TextField`,
   `QLabel`→`M3Label`, `QComboBox`→`M3ComboBox`...).
3. **Mécanisme de ratchet (baseline)** — `scripts/_baseline.py` partagé par
   `lint_widget_purity.py` et `audit_design_system.py` : les violations connues au
   moment de la génération de la baseline ne bloquent pas ; toute violation
   nouvelle (fichier neuf ou ligne modifiée qui en introduit une) bloque le commit.
   Rapport complet (baseline + nouvelles) toujours consultable via `design-review`.
4. **Réconcilier `lint_qss_hardcoding.py` (0 violation) vs `audit_design_system.py`
   (72 violations)** — investiguer pourquoi le premier sous-détecte, puis soit le
   corriger, soit le retirer au profit d'`audit_design_system.py` comme source
   unique de vérité sur le hardcoding.
5. **Câblage** — brancher dans `.pre-commit-config.yaml` et dans les procédures
   `design-review.md`/`pyside6-review.md` : `lint_ui_quality.py`,
   `audit_design_system.py --check-baseline`, `lint_widget_purity.py
   --check-baseline`, `lint_palette_contrast.py`, `lint_safe_slot.py`,
   `lint_file_size.py`, et les 5 scripts accessibilité/motion/phi non committés
   (`lint_accessibility.py`, `lint_focus_visible.py`, `lint_keyboard_nav.py`,
   `lint_motion.py`, `lint_phi_compliance.py`) une fois validés.
6. Valider et committer le chantier fondation non committé (`design_system.py`,
   widgets phibuilder, `phi_scale.py`/`phi_grid.py`/`m3_phi_bridge.py`,
   `keyboard_navigator.py`) — base sur laquelle s'appuient les phases 0 et 1.
   133/133 tests LarcCommon passent déjà avec ces changements (vérifié 2026-09-08).

### Phase 2 — Principes de composition généralisés (priorité 2)

Extraire et généraliser 3 principes déjà présents dans des patterns isolés, pour
qu'ils s'appliquent à **tout** écran, pas seulement au pattern qui les documentait :

1. **Contraste de surface obligatoire** — tout usage de `M3Card`
   (`_section_card` de `form-pattern` le fait déjà, à généraliser) doit rester
   visuellement distinct de son parent. Avec la Phase 0 corrigée, ce principe est
   déjà largement acquis par construction ; garder une vérification légère (lint
   ou check visuel) pour éviter une régression future (ex. si quelqu'un force un
   `background` custom qui recrée le bug).
2. **États vides/chargement/erreur obligatoires** — généraliser SD6
   (`search-detail-pattern`, aujourd'hui limité à ce pattern) à toute liste/arbre
   pouvant être vide (ex. `EventTypeSelectorWidget` sans données).
3. **Pas d'espace mort non borné** — un panneau ne doit pas se terminer par un
   `addStretch()` qui absorbe plus qu'une fraction raisonnable de l'espace
   disponible sans contenu qui la justifie (ex. centrer le contenu plutôt que
   l'ancrer en haut avec du vide en dessous).

Documentés dans un skill (`composition-principles.md`), avec statut par principe :
mécanisable via lint (1, partiellement 3) vs vérifiable seulement à l'œil (2, 3).

### Phase 3 — QA visuelle (filet de sécurité)

Ajouter à la procédure `design-review` une étape obligatoire pour tout écran
neuf/modifié significativement : lancer l'écran isolément (pattern des scripts
`show_*.py` utilisés pour le diagnostic du 2026-09-08, éventuellement formalisé en
petit utilitaire réutilisable dans `scripts/` ou `tools/`), capturer une image
(`horizon-mcp` ou équivalent), et la comparer visuellement aux principes des
Phases 0/2 avant de considérer l'écran terminé. Ce n'est pas mécanisable —
certains défauts de composition ne le seront jamais — donc ce n'est pas une étape
optionnelle : c'est ce qui rattrape tout ce que les linters ne peuvent pas voir.

### Annexe — Nettoyage

`git worktree remove` sur `.claude/worktrees/event-type-hierarchy-tree-ui`
(branche déjà entièrement fusionnée dans `main`, 0 commit divergent — vérifié
2026-09-08).

## Flux (au commit)

```
git commit
  → pre-commit
      → lint_d1_color_checker.py (D1+J7+D3+D4+D5+D6+D7)   [existant, réparé]
      → audit_design_system.py --check-baseline            [nouveau mode]
      → lint_widget_purity.py --check-baseline              [nouveau script]
      → lint_ui_quality.py, lint_palette_contrast.py        [nouvellement câblés]
      → lint_safe_slot.py, lint_file_size.py                [nouvellement câblés]
      → (si fondation validée) lint_accessibility.py, lint_focus_visible.py,
        lint_keyboard_nav.py, lint_motion.py, lint_phi_compliance.py
  → échec si une violation NOUVELLE (hors baseline) est détectée
  → succès sinon (dette connue tolérée, rapportée mais non bloquante)
```

La QA visuelle (Phase 3) n'est pas dans ce flux automatique — c'est une étape
humaine/agent dans la procédure `design-review`, avant de clore une tâche d'écran.

## Gestion des erreurs

- Un linter qui lève une exception ne doit pas planter le pre-commit
  silencieusement — logguer clairement et échouer explicitement sur le fichier
  concerné plutôt que de le sauter sans le dire.
- La baseline doit être versionnée (committée) pour être reproductible par tout
  développeur.

## Tests

- Suite `LarcCommon/tests/` existante : doit continuer à passer (133/133
  aujourd'hui) après validation de la fondation et du correctif de tons M3.
- Test visuel avant/après pour la Phase 0 : capture de `event_generator_dialog.py`
  (et au moins un autre écran utilisant M3Card) avant et après le correctif de
  tons, pour confirmer que la carte redevient visible.
- Tests unitaires pour `lint_widget_purity.py` : cas positif (widget brut
  détecté), cas négatif (widget phibuilder, exception autorisée), cas baseline
  (violation connue non bloquante), cas régression (nouvelle violation bloquante).
- Test manuel pre-commit : commit factice introduisant une violation dans un
  fichier non-baseliné → doit être rejeté.

## Périmètre de livraison

Cette spec couvre un seul sous-projet cohérent : la fondation du design system
(tons M3) et la couche de gouvernance/QA de LarcCommon. Les sous-projets suivants
(résorption de la dette par app, CI GitHub Actions, principes de composition
au-delà des 3 identifiés ici) sont explicitement différés et non spécifiés ici.
