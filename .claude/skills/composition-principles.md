---
name: composition-principles
description: 4 principes de composition transverses (contraste de surface, états vides, espace mort, taille fixe mesurée) — au-delà de la conformité aux tokens
category: design
trigger: composition, écran vide, espace mort, état vide, carte invisible, hiérarchie visuelle, chevauchement, overlap, setFixedSize, taille fixe
---

# Principes de composition — au-delà de la conformité aux tokens

Trouvé le 2026-09-08 : un écran peut utiliser 100% les bons widgets et tokens
(`phibuilder`, `ds.*`) et rester visuellement faible. La conformité au
vocabulaire du design system (`lint_widget_purity`, `audit_design_system`) ne
garantit pas la qualité de la composition — ce sont deux axes différents.
Ces 4 principes viennent de patterns déjà documentés mais jamais généralisés
(les 3 premiers), plus un trouvé en corrigeant un écran existant (le 4e).

## 1. Contraste de surface obligatoire

Toute carte/panneau élevé doit rester visuellement distinct de son parent.
Voir `m3-elevation` pour le mécanisme (`theme=`, tons `surface_container`).
Déjà appliqué dans `form-pattern` (`_section_card` avec `border` + `background`
explicites) — généraliser ce réflexe à tout usage de `M3Card`.

## 2. États vides/chargement/erreur obligatoires

Déjà documenté comme règle **SD6** dans `search-detail-pattern`
("État vide inline, pas de popup") — mais limité à ce seul pattern. Toute
liste/arbre pouvant légitimement être vide (aucune donnée chargée, aucun
résultat de recherche) doit afficher un message explicite à la place d'une
zone blanche silencieuse. Exemple concret trouvé : `EventTypeSelectorWidget`
sans données ne montre rien — un utilisateur ne peut pas distinguer "en cours
de chargement" de "cassé".

## 3. Pas d'espace mort non borné

Un panneau ne doit pas se terminer par un `addStretch()` qui absorbe plus
qu'une fraction raisonnable de l'espace disponible sans contenu qui la
justifie. Trouvé dans `event_generator_dialog.py` : plus de la moitié du
panneau droit était vide après le champ Note, à cause de deux `addStretch()`
successifs (`cl.addStretch()` puis `fl.addStretch()`). Alternative : centrer
le contenu verticalement plutôt que l'ancrer en haut avec du vide en dessous,
ou dimensionner le conteneur à son contenu plutôt que l'inverse.

## 4. Une taille fixe doit être mesurée, pas héritée d'une ancienne formule

Trouvé le 2026-09-09 sur `login.py` : une fenêtre `setFixedSize()` calculée
par une formule (ex. ratio doré `H = W * 1.618`) au moment où les widgets
n'avaient pas encore de vrai style peut devenir trop petite une fois `theme=`
correctement posé — le padding/min-height réel des widgets M3 (souvent plus
généreux qu'un `QLineEdit`/`QLabel` nu) fait grossir le contenu. Une fenêtre
trop petite avec un layout `Qt.AlignCenter` ne se comprime pas proprement :
**les widgets se chevauchent visuellement**, sans erreur ni avertissement.

Avant de figer une taille (`setFixedSize`, `setFixedHeight`...) sur un écran
qui vient de recevoir `theme=` pour la première fois, mesurer le besoin réel
plutôt que réutiliser l'ancienne valeur :
```python
win.show(); app.processEvents()
print(win.layout().sizeHint())  # taille réellement nécessaire
```
Si la taille fixe existante est inférieure à ce `sizeHint()`, l'agrandir
(avec une marge de confort) plutôt que de laisser un chevauchement.

## Ce qui reste hors de portée d'un linter

Rien ici ne remplace l'étape de QA visuelle (`design-review`, section 4) —
l'équilibre visuel et la hiérarchie ne sont pas mécanisables. Ces 3 principes
couvrent ce qu'on a trouvé en pratique le 2026-09-08, pas une liste exhaustive :
Material Design lui-même s'appuie sur des revues humaines en plus de ses
principes documentés. Si un nouveau défaut de composition récurrent apparaît,
évaluer s'il généralise (l'ajouter ici) ou s'il est ponctuel (le corriger sur
place sans grossir cette liste indéfiniment).
