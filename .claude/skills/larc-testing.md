---
name: larc-testing
description: Stratégie de test 2 phases — Phase 1: mock (offline, rapide), Phase 2: réel (DB, UI). pytest avec conftest.
category: infrastructure
trigger: test, pytest, conftest, mock, couverture, TDD
---

# Testing — Stratégie 2 Phases

## Phase 1 : Mock

- Mock `db.server_conn` → pas de DB nécessaire
- Tests rapides (< 1s)
- Couvre la logique métier

## Phase 2 : Réel

- Connexion DB réelle (test database)
- Tests UI avec QtTest
- Couvre l'intégration

```bash
pytest tests/ -v
```
