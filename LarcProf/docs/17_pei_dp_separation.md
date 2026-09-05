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
