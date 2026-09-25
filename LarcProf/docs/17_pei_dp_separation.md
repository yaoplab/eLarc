# Séparation PEI / DP — deux fichiers UI distincts

_Décision prise le 22 mai 2026._

## Décision

L'espace de travail du professeur sera implémenté en **deux fichiers UI séparés** :

| Cible | Fichier prévu | Cycle | Table métier principale |
|---|---|---|---|
| PEI | `views/pei_workspace.ui` (+ `pei_workspace.py`) | Collège | `larcauth_learnerpei_has_termsubjectpei` |
| DP | `views/dp_workspace.ui` (+ `dp_workspace.py`) | Lycée | `larcauth_learnerdp_has_termsubjectdp` |

**Pas** un seul écran qui s'adapte dynamiquement selon le niveau de la classe sélectionnée.

## Pourquoi deux fichiers et pas un

- Les deux écrans ont des spécificités fonctionnelles distinctes :
  - PEI : note de synthèse trimestrielle sur 7 (`note_on_7`), critères a-d, observations par évaluation.
  - DP : note directe sur 20 (`moy_on_20`, `cc_on_20`), notes de bac blanc (`bacblanc`, `bacblanc2`), entretiens individuels (`ei_note`, `ei_observation`, `ei_objectif`), `cpei`, en plus du système critères.
- Les colonnes diffèrent significativement (228 colonnes en PEI, 269 en DP, conventions différentes).
- Une UI dédiée par cycle est plus lisible et maintenable qu'un fac-totum qui multiplie les `if cycle == 'PEI' else ...`.
- Les évolutions futures (statistiques, bac blanc, EI…) toucheront un seul fichier et pas l'autre.

## Format `.ui` Qt Designer

Les fichiers `.ui` sont des fichiers XML Qt Designer. Deux approches d'intégration possibles :

1. **Chargement dynamique** via `PySide6.QtUiTools.QUiLoader` à l'exécution.
2. **Compilation statique** via `pyside6-uic mon.ui -o mon_ui.py` puis import du module Python généré.

Le choix entre les deux sera fait à l'étape d'implémentation. L'approche 2 (compilation) est généralement préférée pour la performance au démarrage et la complétion d'IDE.

## Choix du fichier UI à charger

`MainWindow` (cf. `16_main_window.md`) reste l'enveloppe générique (header + actions). Le contenu central est remplacé selon le cycle de la classe sélectionnée par le professeur :

- Si la classe choisie est de niveau **collège** → chargement de `pei_workspace.ui`.
- Si **lycée** → chargement de `dp_workspace.ui`.

La cascade matières → classes reste partagée (au-dessus du workspace), car elle est identique dans les deux cas.

## Conséquence sur l'étape 2

L'étape 2 (cascade matières → classes) reste agnostique du cycle. L'étape 3 (panneaux d'évaluation) devra trancher : soit on duplique les panneaux F/S dans chaque UI, soit on les mutualise dans un widget partagé. Le code des `.ui` Qt Designer permet d'inclure des widgets composites, donc factorisation possible.

## Statut

**À FAIRE — étape 2+.** Le squelette de `MainWindow` ne charge pas encore de `.ui` ; les panneaux sont des placeholders.

---

## Addendum — 2026-09-17 : réaffirmation de la décision, constat du chemin réellement pris

**Ce qui s'est réellement passé depuis le 22 mai** : la décision ci-dessus n'a jamais été implémentée telle quelle (pas de `pei_workspace.ui`/`dp_workspace.ui`, pas de `QUiLoader`). Le code a pris un chemin différent : **une seule grille Python** (`views/main_notes.py::_fill_grille`, appelée depuis `MainWindow`) qui accepte un paramètre `cycle` ('PEI'/'DP') et bascule dessus — table, colonne de synthèse (`note_on_7` vs `moy_on_20`), noms de colonnes de critères. C'est exactement le pattern « fac-totum à `if cycle == 'PEI' else ...` » que ce document voulait éviter à l'origine.

Ce chemin a partiellement marché parce que les tables PEI et DP partagent par coïncidence le même nommage de colonnes par critère (`f01_note_a`..`f01_note_f`, `jgt_a`..`jgt_f`) — donc l'affichage brut des critères A-D fonctionne déjà pour DP sans code dédié. Mais ça s'arrête là : `_auto_compute_judgments_and_note()` sort immédiatement si `cycle == 'DP'` (calcul jamais implémenté), et surtout la grille ne sait pas du tout afficher la colonne `f01_note`/`s01_note` (note générale /20 par évaluation, **sans suffixe de critère** — distincte des 4 notes par critère), qui n'existe que côté DP.

**Décision reconfirmée le 2026-09-17** : oui, deux UI séparées, pour la raison originale **plus** une raison supplémentaire trouvée en pratique — `note_20` (colonne générale par évaluation) est structurellement absente du PEI et présente en DP ; la coïncidence de nommage qui permettait de partager la grille pour les critères A-D ne s'étend pas à cette colonne. Continuer à étendre la grille partagée aurait recréé exactement le fac-totum que ce document dénonçait déjà en mai.

### Règles métier confirmées par l'utilisateur (session du 2026-09-17)

- **Jugements A-D (`jgt_a`..`jgt_d`)** : même mécanisme que PEI, à l'identique — moyenne pondérée F/S par critère, arrondie à l'entier (aucun changement de logique de calcul, juste débrancher le `if cycle=='DP': return` actuel et réutiliser le code PEI existant pour cette partie).
- **Moyenne /20 (`moy_on_20`)** : `Sommative × 0.75 + Formative × 0.125 + EI × 0.125` (moyenne des notes générales, pas des critères).
- **Moyenne /7 (`moy_on_7`)** : dérivée de `moy_on_20` via une **bande de notation imposée** (table de correspondance bornes inf/sup sur 20 → entier 1-7), même principe que les bandes IB de PEI mais sur une échelle /20.
- **Paramétrable par matière** : même mécanisme que PEI — `calc_formula` JSON en base (`larcauth_classroom_termsubject.calc_formula`), lu/écrit via `CalcEngine.get_formula`/`save_formula`. Ce mécanisme existe déjà et est générique (le `type` dans le JSON distingue PEI/DP) ; pas de nouvelle table nécessaire pour la config.

### Bug confirmé (à corriger avec l'implémentation)

`common/calc_engine.py::_DEFAULT_DP` et `views/weight_dialog.py::_on_template_changed` (valeur de repli) ont tous les deux `formative_coefficient` = **1.125** au lieu de **0.125** — avec 0.75+1.125+0.125 la somme des poids fait 2.0, incohérent avec une moyenne pondérée. Doit être 0.125 (0.75+0.125+0.125=1.0), cohérent avec la règle ci-dessus.

### Ce qui existe déjà et peut être réutilisé tel quel

- `WeightDialog` (`views/weight_dialog.py`) a déjà une section DP (`_build_dp_section`) avec 3 `QDoubleSpinBox` pour les coefficients EI/Formative/Sommative — juste le bug ci-dessus à corriger.
- Le widget de tableau de bandes (`_boundaries_table`, `_fill_boundaries`, `_read_boundaries_from_table`) existe déjà côté PEI — réutilisable pour la bande /20→/7 de DP moyennant une déclinaison d'échelle.
- `CalcEngine._compute_dp()` existe (lit `ei_note`, moyenne des `f01_note`..`f12_note`/`s01_note`..`s12_note`) mais ignore les critères A-D et `jgt_a-d` — à réécrire en combinant les deux mécanismes (jugements façon PEI + moy_on_20/7 façon ci-dessus).

### Trou confirmé — aucune saisie EI dans l'UI

`ei_note`/`ei_observation`/`ei_objectif`/`cp_note*`/`bacblanc*` (colonnes réelles de `larcauth_learnerdp_has_termsubjectdp`, vérifiées en base) ne sont référencées **nulle part** dans les fichiers `views/*.py` — uniquement lues par `calc_engine.py`. Il n'existe aujourd'hui aucun écran pour saisir l'Évaluation Interne. À trancher : champ dans la nouvelle grille DP, ou écran séparé au niveau élève/matière.

### Schéma réel de `larcauth_learnerdp_has_termsubjectdp` (vérifié en base, 269 colonnes)

Par évaluation (f01..f12, s01..s12) : `{préfixe}_observation`, `{préfixe}_note` (générale /20, **absente de PEI**), `{préfixe}_note_a`..`{préfixe}_note_f` (par critère, même convention que PEI). Hors évaluations : `cp_note`/`cp_note_a-f`/`cp_observation`, `jgt_a-f`, `jgt_obsersation` (typo existante), `ei_note`/`ei_observation`/`ei_objectif`, `cpei`, `cc_on_20`, `moy_on_20`, `moy_on_7`, `bacblanc`/`bacblanc_v`/`bacblanc2`/`bacblanc_v2`, `term_observation`, `note_on_7_checked`.

### Compte de test DP créé

`olgaadja@arc-en-ciel.org` / `test123` (activé le 2026-09-17) — professeure DP existante, pour générer une instance LarcProf locale avec de vraies données DP et tester visuellement la future grille.

### Prochaines étapes (pas commencées)

1. Concevoir l'écran DP dédié (pas nécessairement des fichiers `.ui` Qt Designer comme prévu en mai — un module Python séparé à la `main_notes.py` mais propre au DP est plus cohérent avec le reste du code actuel, à trancher à l'implémentation).
2. Grille DP : critères A-D (réutilisables tels quels) + colonne note/20 générale (nouvelle).
3. Moteur de calcul DP complet (jugements + moy_on_20 + moy_on_7 via bande), corriger le bug de coefficient au passage.
4. `WeightDialog` : ajouter la bande /20→/7 côté DP.
5. Décider où saisir l'EI.
