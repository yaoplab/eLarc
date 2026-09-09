---
name: composition-principles
description: 3 principes de composition transverses (contraste de surface, états vides, espace mort) — au-delà de la conformité aux tokens
category: design
trigger: composition, écran vide, espace mort, état vide, carte invisible, hiérarchie visuelle
---

# Principes de composition — au-delà de la conformité aux tokens

Trouvé le 2026-09-08 : un écran peut utiliser 100% les bons widgets et tokens
(`phibuilder`, `ds.*`) et rester visuellement faible. La conformité au
vocabulaire du design system (`lint_widget_purity`, `audit_design_system`) ne
garantit pas la qualité de la composition — ce sont deux axes différents.
Ces 3 principes viennent de patterns déjà documentés mais jamais généralisés.

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

## Ce qui reste hors de portée d'un linter

Rien ici ne remplace l'étape de QA visuelle (`design-review`, section 4) —
l'équilibre visuel et la hiérarchie ne sont pas mécanisables. Ces 3 principes
couvrent ce qu'on a trouvé en pratique le 2026-09-08, pas une liste exhaustive :
Material Design lui-même s'appuie sur des revues humaines en plus de ses
principes documentés. Si un nouveau défaut de composition récurrent apparaît,
évaluer s'il généralise (l'ajouter ici) ou s'il est ponctuel (le corriger sur
place sans grossir cette liste indéfiniment).
