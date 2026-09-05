"""Fixtures partagées — les tests tournent SANS PostgreSQL réelle.

FakeConn/FakeCursor simulent la connexion : chaque execute() consomme le plan
de réponses fourni au cursor (fetchone), les requêtes sont enregistrées.
"""

from __future__ import annotations

import json
from collections import deque

import pytest


class FakeCursor:
    """Cursor simulé : execute() enregistre la requête et consomme le plan."""

    def __init__(self, plan: list | None = None, description: list | None = None):
        self.plan = deque(plan or [])
        self.calls: list[tuple[str, tuple]] = []
        self.rowcount = 0
        # colonnes retournées (utile pour les fonctions qui lisent cur.description)
        self.description = description or []

    def execute(self, query: str, params=()):
        self.calls.append((query, tuple(params)))
        if "RETURNING id" in query:
            # start_run : le plan fournit la valeur à renvoyer
            pass

    def fetchone(self):
        if self.plan:
            return self.plan.popleft()
        return None

    def fetchall(self):
        out = list(self.plan)
        self.plan.clear()
        return out

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConn:
    """Connexion simulée : chaque curseur reçoit un plan de réponses.

    Les curseurs créés sont conservés dans `cursors` pour inspection
    (requêtes exécutées, rowcount).
    """

    def __init__(self, plans: list | None = None, rowcounts: list | None = None,
                 description: list | None = None):
        # plans : liste de listes (un plan par cursor() appelé, dans l'ordre)
        # rowcounts : valeurs de rowcount à affecter aux curseurs (parallèle)
        # description : colonnes retournées par chaque curseur (cur.description)
        self._plans = deque(plans or [])
        self._rowcounts = deque(rowcounts or [])
        self._desc = description
        self.cursors: list[FakeCursor] = []
        self.closed = False

    def cursor(self):
        plan = self._plans.popleft() if self._plans else []
        cur = FakeCursor(plan, description=getattr(self, "_desc", None))
        if self._rowcounts:
            cur.rowcount = self._rowcounts.popleft()
        self.cursors.append(cur)
        return cur

    def close(self):
        self.closed = True


@pytest.fixture
def fake_conn():
    return FakeConn


@pytest.fixture
def scope_lints():
    from larcforge.models import RunScope

    return RunScope(command="lints", linters=["R", "D"], projects=["LarcCommon"])
