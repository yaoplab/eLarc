---
name: testing-review
description: Audit de la couverture de tests — infrastructure, Phase 1 (mock), Phase 2 (réel)
category: quality
trigger: audit tests, vérifie les tests, check tests, revue tests, couverture tests, test coverage
---

# Testing Review — Audit des Tests Larc

Vérifier l'infrastructure de test et la couverture.

## Procédure

1. Vérifier l'infrastructure :
```bash
ls tests/conftest.py
grep "mock_db\|mock_session" tests/conftest.py
```

2. Lancer les tests Phase 1 (mock) :
```bash
pytest tests/ -v -m "not integration"
```

3. Lancer les tests Phase 2 (réel, si DB dispo) :
```bash
pytest tests/ -v -m integration
```

4. Vérifier la couverture :
```bash
pytest tests/ --cov=. --cov-report=term
python D:/projets/scripts/lint_test_coverage.py --dir . --stats
```

5. Vérifier les règles spécifiques :
```bash
python D:/projets/scripts/lint_safe_slot.py --dir .
```

## Checklist

### Phase 1 — Infrastructure
- [ ] `tests/conftest.py` avec `mock_db` et `mock_session`
- [ ] `pytest` et `pytest-qt` dans `pyproject.toml`
- [ ] `pytest tests/ -v -m "not integration"` → 100% vert
- [ ] Marqueur `integration` dans `pyproject.toml`

### Phase 1 — Couverture
- [ ] Chaque module `common/` a un `test_<module>.py`
- [ ] Chaque `except Exception:` a un test mocké
- [ ] Chaque dialogue modal a un test
- [ ] ≥ 1 test de slot @safe_slot (H)
- [ ] ≥ 1 test de QThread (I)
- [ ] ≥ 1 test de theme reactivity (J)

### Phase 2 — Tests réels
- [ ] `tests/test_integration_*.py` existe
- [ ] Tests marqués `@pytest.mark.integration`
- [ ] `pytest tests/ -v -m integration` → vert
- [ ] Requêtes critiques (INSERT/UPDATE/DELETE) ont un test réel

### En cas d'échec
1. `pytest` non trouvé → `pip install pytest pytest-qt`
2. `qtbot` non trouvé → `pip install pytest-qt`
3. Tests Phase 2 échouent → `pg_isready` (PostgreSQL)
4. `mock_db` ne fonctionne pas → vérifier le path dans `patch()`

## Skills de référence

- `larc-testing` — stratégie 2 phases
- `pyside6-wrapper` — tests @safe_slot (sous-système H)
- `theme-reactivity` — tests restyle (sous-système J)
