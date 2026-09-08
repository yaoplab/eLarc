# LarcCommon UI Quality Enforcement — Design

Date: 2026-09-08

## Contexte

L'écart de qualité graphique entre `LarcCommon/larccommon/login.py` (widgets PySide6
bruts, QSS manuel, espacements en dur) et `LarcCommon/larccommon/dialogs/event_generator_dialog.py`
(phibuilder M3Card/M3Button, tokens `ds.*`, thème réactif) a révélé que la couche de
gouvernance qualité de LarcCommon (pre-commit, linters, skills de revue) ne remplit
plus son rôle : elle documente des règles qu'elle ne fait plus respecter.

Root causes identifiées (audit du 2026-09-08) :

1. **Pre-commit cassé depuis la migration C:→D:** — `.pre-commit-config.yaml` pointe
   vers `C:/projets/scripts/...`, chemin inexistant depuis le 2026-08-10. Aucun
   linter ne tourne plus au commit.
2. **CI absente** — `.github/workflows/ci.yml`, documenté dans `CLAUDE.md`, n'existe
   pas. Dérive doc/réalité.
3. **Aucun linter ne vérifie la règle la plus importante** — "toujours
   `phibuilder.widgets`, jamais PySide6 direct" (RÈGLE ABSOLUE, `CLAUDE.md`). C'est
   la cause directe de la dérive de `login.py`.
4. **Deux linters de hardcoding incohérents** — `lint_qss_hardcoding.py` rapporte 0
   violation partout ; `audit_design_system.py` en trouve 72 (dont 13 P0 + 2 P1 dans
   `login.py` lui-même). Le premier sous-détecte.
5. **Couverture pre-commit très partielle** — seuls 2 scripts sur ~13 sont branchés
   (`lint_d1_color_checker.py`, `lint_qss_hardcoding.py`). `lint_ui_quality.py`,
   `audit_design_system.py`, `lint_palette_contrast.py`, `lint_safe_slot.py`,
   `lint_file_size.py`, etc. ne tournent jamais automatiquement.
6. Un chantier fondation non committé (design_system.py, widgets phibuilder,
   `phi_scale.py`/`phi_grid.py`/`m3_phi_bridge.py`, `keyboard_navigator.py`, et 5
   nouveaux scripts `lint_accessibility.py`/`lint_focus_visible.py`/
   `lint_keyboard_nav.py`/`lint_motion.py`/`lint_phi_compliance.py`) existe déjà,
   non intégré au dispositif de contrôle. 133/133 tests LarcCommon passent avec ces
   changements — pas de régression détectée.

## Objectifs

- Les skills et linters de LarcCommon garantissent qu'un écran ne peut plus dériver
  du design system (widgets bruts, hardcoding, contraste, accessibilité) sans que
  rien ne le signale — pour tout **nouveau** code ou code **modifié**.
- La dette déjà en place (login.py et ~70 autres violations connues) reste visible
  dans les rapports d'audit mais ne bloque aucun commit tant qu'elle n'est pas
  touchée — décision utilisateur du 2026-09-08 (pas de refonte des 8 apps ici).
- Le chantier fondation (phi/accessibilité) en cours devient la base validée de ce
  dispositif renforcé, committée dans ce travail.

## Non-objectifs (hors scope explicite)

- Corriger les 72 hardcodings existants ou migrer `login.py` (ou tout autre écran
  des 8 apps) vers phibuilder. Ce travail devient une dette **visible et non
  aggravable**, à traiter au fil de l'eau, plus tard, par app.
- Remettre en place une CI GitHub Actions (`.github/workflows/ci.yml`). Signalé
  comme dérive documentaire dans `CLAUDE.md` mais pas traité ici — le pre-commit
  local est le mécanisme d'enforcement visé par cette spec.
- Toucher au contenu fonctionnel des 8 apps.

## Architecture

Cinq composants, dans l'ordre où ils doivent être livrés (chacun dépend du précédent) :

### 1. Réparation du pre-commit (bug fix, risque quasi nul)

`.pre-commit-config.yaml` : remplacer les deux occurrences de
`C:/projets/scripts/` par `D:/projets/scripts/`. Aucun changement de comportement
attendu au-delà de "les hooks recommencent à s'exécuter".

### 2. Nouveau linter `scripts/lint_widget_purity.py`

Détecte l'instanciation directe de classes PySide6 en dehors des exceptions
autorisées par `CLAUDE.md` (`QMessageBox`, `QApplication`, `QVBoxLayout`,
`QHBoxLayout`, `QGridLayout`, `QButtonGroup`, `QTableWidgetItem`), dans tout fichier
sous `views/`, `dialogs/`, `panels/` des 8 apps + LarcCommon.

- Détection statique par regex/AST sur les appels `QXxx(` importés depuis
  `PySide6.QtWidgets`, à l'exclusion de la liste blanche.
- Sortie dans le même format que `audit_design_system.py` (fichier, ligne, classe
  détectée, widget phibuilder suggéré si mapping connu : `QPushButton`→`M3Button`,
  `QLineEdit`→`M3TextField`, `QLabel`→`M3Label`, `QComboBox`→`M3ComboBox`, etc.)
- Mode `--baseline` (génère/actualise la baseline) et mode par défaut (compare à la
  baseline, voir composant 3).

### 3. Mécanisme de ratchet (baseline de dette connue)

Fichier `scripts/.quality_baseline.json` (ou équivalent), généré une fois par
`lint_widget_purity.py --baseline` (et étendu à `audit_design_system.py` de la même
façon), qui fige la liste des violations actuelles par `(fichier, ligne, règle)`.

Comportement en pre-commit :
- Une violation présente dans la baseline → autorisée, non bloquante (dette connue).
- Une violation absente de la baseline (nouveau fichier, ligne modifiée qui
  introduit ou déplace une violation) → bloque le commit.
- Un rapport complet (baseline + nouvelles) reste consultable via les skills
  `design-review` / `pyside6-review`, pour piloter la résorption future.

Ce même mécanisme s'applique à `audit_design_system.py` (72 violations actuelles)
et à `lint_widget_purity.py` — pas besoin de deux implémentations : une fonction
`load_baseline()` / `is_baselined(violation)` partagée, dans un module utilitaire
commun (`scripts/_baseline.py`) réutilisé par les deux linters.

### 4. Réconciliation `lint_qss_hardcoding.py` vs `audit_design_system.py`

Investiguer pourquoi `lint_qss_hardcoding.py` rapporte 0 violation alors que
`audit_design_system.py` en trouve 72. Décision attendue après investigation :
soit corriger `lint_qss_hardcoding.py` pour qu'il détecte réellement les cas
qu'`audit_design_system.py` trouve, soit le retirer du pre-commit au profit
d'`audit_design_system.py` seul (source unique de vérité pour le hardcoding). Pas
de doublon incohérent dans le dispositif final.

### 5. Câblage complet

- `.pre-commit-config.yaml` : ajouter les hooks manquants (`lint_ui_quality.py`,
  `audit_design_system.py` en mode baseline, `lint_widget_purity.py` en mode
  baseline, `lint_palette_contrast.py`, `lint_safe_slot.py`, `lint_file_size.py`,
  et les 5 scripts accessibilité/motion/phi une fois validés).
- `.claude/skills/design-review.md` et `.claude/skills/pyside6-review.md` : ajouter
  les nouveaux scripts à la procédure, et une entrée de mapping règle
  (`lint_widget_purity` → nouvelle règle, ex. `W1` — widget non-phibuilder).
- Valider et committer le chantier fondation (design_system.py, widgets, phi/*,
  keyboard_navigator.py) comme un commit distinct, avant le nouveau linter — c'est
  la base sur laquelle `lint_widget_purity.py` et les scripts accessibilité
  s'appuient.

### 6. Nettoyage annexe

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
      → lint_ui_quality.py                                  [nouvellement câblé]
      → lint_palette_contrast.py                            [nouvellement câblé]
      → lint_safe_slot.py, lint_file_size.py                [nouvellement câblé]
      → (si foundation validée) lint_accessibility.py, lint_focus_visible.py,
        lint_keyboard_nav.py, lint_motion.py, lint_phi_compliance.py
  → échec si une violation NOUVELLE (hors baseline) est détectée
  → succès sinon (dette connue tolérée, rapportée mais non bloquante)
```

## Gestion des erreurs

- Un linter qui lève une exception (fichier illisible, encodage, etc.) ne doit pas
  planter tout le pre-commit silencieusement en bloquant à tort — logguer l'erreur
  clairement et échouer explicitement sur ce fichier plutôt que de le sauter sans
  le dire.
- La baseline doit être versionnée (committée) pour que le ratchet soit reproductible
  en CI/pour tout développeur, pas seulement en local.

## Tests

- Suite `LarcCommon/tests/` existante : doit continuer à passer (133/133 aujourd'hui)
  après validation de la fondation.
- Tests unitaires pour `lint_widget_purity.py` : cas positif (widget brut détecté),
  cas négatif (widget phibuilder, exception autorisée non signalée), cas baseline
  (violation connue non bloquante) et cas régression (nouvelle violation bloquante).
- Test manuel : réparer le pre-commit, faire un commit factice introduisant une
  violation dans un fichier non-baseliné → vérifier que le commit est rejeté.

## Périmètre de livraison

Cette spec couvre un seul sous-projet cohérent : la couche de gouvernance qualité
de LarcCommon. Les sous-projets suivants (résorption de la dette par app, CI
GitHub Actions) sont explicitement différés et non spécifiés ici.
