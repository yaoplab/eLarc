---
name: graphify
description: Graphe de connaissances du codebase — "cerveau Obsidian" interrogeable. 4233 nœuds, 8421 arêtes. À régénérer après refactoring.
category: infrastructure
trigger: graphify, graphe, knowledge graph, god nodes, dépendances
---

# Graphify — Graphe de Connaissances

## Commandes

```bash
graphify extract . --code-only --force
graphify cluster-only .
graphify query "Comment X se connecte a Y ?"
graphify explain "ThemeManager"
graphify god-nodes --top 20
```

## Règle

Toujours consulter le graphe AVANT une tâche touchant ≥3 fichiers. Régénérer après chaque refactoring.
