# Plan d'Amélioration et d'Audit de LarcForge : Gardien de Build et de Qualité

Ce document présente l'analyse stratégique et le plan d'action technique pour renforcer **LarcForge**, notre pipeline d'automatisation critique. L'objectif est de transformer LarcForge en un "gardien" intraitable capable de bloquer toute régression de code, tout défaut de design et toute anomalie avant la compilation et la génération des setups.

---

## 1. Diagnostic de l'État Actuel et Faiblesses Identifiées

* **Linters trop permissifs :** Les outils actuels se limitent souvent à des vérifications de syntaxe basiques, laissant passer des erreurs de typage, des fuites de ressources ou des incohérences logiques entre Larcommon et les applications clientes.
* **Absence de validation visuelle et structurelle :** Aucun mécanisme automatisé ne garantit le respect de la charte graphique, de l'ergonomie ou de la structure des interfaces graphiques (notamment pour les composants partagés).
* **Pipeline de build non bloquant :** Le processus de compilation et de génération du setup peut parfois s'exécuter même si des avertissements ou des erreurs mineures ont été ignorés, créant de la dette technique en production.

---

## 2. Axes Stratégiques pour un LarcForge Infaillible

### A. Renforcement du Pipeline de Vérification Statique
- **Intégration d'analyses rigoureuses :** Configurer des linters stricts (type `ruff`, `flake8` ou équivalents selon l'écosystème Python) avec un niveau de tolérance zéro pour les erreurs.
- **Vérification des contrats d'interface :** S'assurer que chaque modification de `Larcommon` est automatiquement testée vis-à-vis de tous les logiciels de l'écosystème avant le build.

### B. Intégration d'un Contrôle de Design et de Présentation
- **Audits visuels automatisés :** Mettre en place des scripts de vérification des feuilles de style, des thèmes et des composants graphiques.
- **Conformité UI :** Valider que les éléments respectent les grilles de design et les règles d'accessibilité et d'espacement de l'ERP.

### C. Automatisation du Cycle de Vie Bloquant (Fail-Fast)
Le pipeline de LarcForge doit impérativement respecter l'ordre d'exécution suivant, chaque étape étant un prérequis bloquant pour la suivante :

```
[ 1. Synchronisation & Nettoyage ] 
                │
                ▼
      [ 2. Analyse Statique ] ──(Erreur ?)──> [ 🛑 ARRÊT DU BUILD ]
                │
                ▼
       [ 3. Tests Unitaires ] ──(Échec ?)──> [ 🛑 ARRÊT DU BUILD ]
                │
                ▼
     [ 4. Validation Design ] ──(Non-conforme ?)──> [ 🛑 ARRÊT DU BUILD ]
                │
                ▼
       [ 5. Compilation ] ──(Échec ?)──> [ 🛑 ARRÊT DU BUILD ]
                │
                ▼
     [ 6. Génération du Setup ] ──(Succès Final ✅)
```

---

## 3. Plan d'Action Technique

1. **Étape 1 : Audit du script de build principal**
   - Isoler les points d'entrée de LarcForge qui gèrent le déclenchement des tâches.
   - Implémenter des codes de retour stricts (`sys.exit(1)`) à chaque étape en cas d'anomalie.

2. **Étape 2 : Durcissement des règles de linting et de typage**
   - Centraliser les fichiers de configuration des linters pour qu'ils soient appliqués uniformément à travers tout l'ERP et `Larcommon`.

3. **Étape 3 : Mise en place du mode "Dry-Run / Strict Check"**
   - Permettre de lancer LarcForge en mode vérification seule pour auditer l'état actuel de l'application sans lancer la lourde phase de compilation des setups.
