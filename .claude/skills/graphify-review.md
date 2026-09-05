---
name: graphify-review
description: Audit du graphe de connaissances — fraîcheur, complétude, god nodes, communautés
category: quality
trigger: audit graphe, vérifie graphe, check graphify, revue graphe, knowledge graph, god nodes
---

# Graphify Review — Audit du Graphe de Connaissances Larc

Vérifier que le graphe de connaissances est à jour et cohérent avec le codebase.

## Procédure

1. Vérifier la fraîcheur du graphe :
```bash
graphify god-nodes --top 10 --graph graphify-out/graph.json
```

2. Comparer avec les fichiers récemment modifiés :
```bash
git diff --name-only HEAD~1 | head -20
graphify query "Quels fichiers sont impactés par les derniers changements ?"
```

3. Vérifier les god nodes attendus :
```bash
graphify god-nodes --top 20 --json
```

4. Tracer un chemin entre deux modules clés :
```bash
graphify path LarcCommon LarcSuperviseur
graphify path LarcCommon LarcProf
```

5. Régénérer si nécessaire :
```bash
graphify extract . --code-only --force
graphify cluster-only .
```

## Checklist

### Fraîcheur
- [ ] graph.json modifié après le dernier refactoring
- [ ] Nombre de nœuds stable (pas de chute >10%)
- [ ] Pas de fichiers .py absents du graphe
- [ ] Communautés nommées (ou --no-label assumé)

### Complétude
- [ ] God nodes couvrent les modules principaux (DataLoader, ThemeManager, MainWindow, LoginWindow)
- [ ] Tous les modules Larc* ont au moins 1 nœud
- [ ] Les imports inter-modules sont capturés
- [ ] Les fichiers SQL sont parsés (tree-sitter-sql installé)

### Cohérence
- [ ] God nodes cohérents avec l'architecture documentée
- [ ] Pas de communautés orphelines (1-2 nœuds isolés)
- [ ] Les dépendances LarcCommon → apps sont visibles

## Skills de référence

- `graphify` — graphe de connaissances du codebase
- `database-operations` — connexions DB
- `toolkit-reference` — architecture phibuilder
