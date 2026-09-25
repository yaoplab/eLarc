"""Tests db_access — types d'événements (lecture par langue + écriture LarcConfig)."""
from unittest.mock import MagicMock, patch

from LarcConfig.common import db_access


class FakeCursor:
    def __init__(self):
        self.executed = []
        self._next_fetchall = []
        self._next_fetchone = None

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self._next_fetchall

    def fetchone(self):
        return self._next_fetchone


class FakeConn:
    def cursor(self):
        return self._cur


class TestGetEventTypes:
    def test_filters_by_language_and_resolves_parent_label(self):
        cur = FakeCursor()
        cur._next_fetchall = [
            (1, 'absence', 'Absence', 'absence', None, 0, True, None),
            (2, 'absence_school', "Absent de l'école", 'absence', 1, 1, True, 'Absence'),
        ]
        conn = FakeConn()
        conn._cur = cur
        with patch.object(db_access, "_conn", return_value=conn):
            rows = db_access.get_event_types(fk_language=2)
        assert rows[1]['parent_label'] == 'Absence'
        assert '%s' in cur.executed[0][0]
        assert cur.executed[0][1] == (2,)


class TestSetEventTypeActive:
    def test_writes_is_active(self):
        cur = FakeCursor()
        conn = FakeConn()
        conn._cur = cur
        with patch.object(db_access, "_conn", return_value=conn),                 patch.object(db_access, "count_event_type_usage", return_value=0):
            ok = db_access.set_event_type_active(42, True)
        assert ok is True
        assert "UPDATE larcauth_event_type_config" in cur.executed[0][0]
        assert "is_active" in cur.executed[0][0]
        assert cur.executed[0][1] == (True, 42)

    def test_refuses_to_disable_a_used_type(self):
        cur = FakeCursor()
        conn = FakeConn()
        conn._cur = cur
        with patch.object(db_access, "_conn", return_value=conn),                 patch.object(db_access, "count_event_type_usage", return_value=3):
            assert db_access.set_event_type_active(42, False) is False
        assert cur.executed == []                      # aucun UPDATE

    def test_enabling_is_always_allowed(self):
        cur = FakeCursor()
        conn = FakeConn()
        conn._cur = cur
        with patch.object(db_access, "_conn", return_value=conn),                 patch.object(db_access, "count_event_type_usage", return_value=3):
            assert db_access.set_event_type_active(42, True) is True


class TestSetEventTypeLabel:
    def test_writes_label(self):
        cur = FakeCursor()
        conn = FakeConn()
        conn._cur = cur
        with patch.object(db_access, "_conn", return_value=conn),                 patch.object(db_access, "count_event_type_usage", return_value=0):
            ok = db_access.set_event_type_label(42, "Nouveau libellé")
        assert ok is True
        assert cur.executed[0][1] == ("Nouveau libellé", 42)

    def test_refuses_to_rename_a_used_type(self):
        cur = FakeCursor()
        conn = FakeConn()
        conn._cur = cur
        with patch.object(db_access, "_conn", return_value=conn),                 patch.object(db_access, "count_event_type_usage", return_value=1):
            assert db_access.set_event_type_label(42, "Autre") is False
        assert cur.executed == []


class TestActivateEventType:
    def test_activates_first_free_slot_in_both_languages(self):
        cur = FakeCursor()
        conn = FakeConn()
        conn._cur = cur

        # 1er appel (résolution parent FR), 2e (slot libre FR), 3e (résolution parent EN),
        # 4e (slot libre EN) — fetchone() successifs.
        responses = iter([(10,), (11,), (20,), (21,)])

        def fake_fetchone():
            return next(responses, None)

        cur.fetchone = fake_fetchone

        with patch.object(db_access, "_conn", return_value=conn):
            ok = db_access.activate_event_type(
                parent_code="absence_school", code_suffix="allergie",
                label_fr="Allergie", label_en="Allergy",
            )
        assert ok is True
        # 2 UPDATE (un par langue) après les 2 SELECT de résolution de slot
        update_calls = [e for e in cur.executed if e[0].strip().startswith("UPDATE")]
        assert len(update_calls) == 2

    def test_no_free_slot_in_second_language_leaves_no_update_committed(self):
        """Non-régression : slot FR trouvé mais AUCUN slot libre en EN.

        Avant le correctif (2 phases), l'UPDATE FR était exécuté avant même
        de savoir si l'EN allait réussir — et comme toutes les connexions
        sont en autocommit=True, ce UPDATE restait committé même si la
        fonction retournait False ensuite (état incohérent permanent,
        principe gabarit interdisant tout DELETE pour réparer).

        Avec le correctif, la résolution (parent + slot) se fait pour les 2
        langues AVANT tout UPDATE : si l'EN échoue à ce stade, aucun UPDATE
        n'a encore été exécuté, ni pour le FR ni pour l'EN.
        """
        cur = FakeCursor()
        conn = FakeConn()
        conn._cur = cur

        # 1er appel (résolution parent FR) -> id 10
        # 2e appel (slot libre FR) -> id 11 (trouvé)
        # 3e appel (résolution parent EN) -> id 20
        # 4e appel (slot libre EN) -> None (aucun slot libre)
        responses = iter([(10,), (11,), (20,), None])

        def fake_fetchone():
            return next(responses, None)

        cur.fetchone = fake_fetchone

        with patch.object(db_access, "_conn", return_value=conn):
            ok = db_access.activate_event_type(
                parent_code="absence_school", code_suffix="allergie",
                label_fr="Allergie", label_en="Allergy",
            )

        assert ok is False
        # Preuve qu'aucune mutation n'a eu lieu du tout — même pas le FR,
        # dont le slot avait pourtant été trouvé avec succès.
        update_calls = [e for e in cur.executed if e[0].strip().startswith("UPDATE")]
        assert update_calls == []


class TestGetEventTypeTree:
    ROWS = [
        (21000, 'absence_school', "Absent de l'école", None, True),
        (21100, 'absence_school_justified', 'Justifiée', 21000, True),
        (21200, 'absence_school_old', 'Ancien motif', 21000, False),        # désactivé, libellé réel
        (21300, 'type_niv2_11300', 'Categorie_Niv21000_Level_3', 21000, False),   # emplacement libre
        (22000, 'absence_class', 'Absent du cours', None, True),
        (28000, 'type_niv1_01', 'Categorie_Niv20000_Level_8', None, False),
    ]

    def _run(self, **kw):
        cur = FakeCursor()
        cur._next_fetchall = self.ROWS
        conn = FakeConn()
        conn._cur = cur
        with patch.object(db_access, "_conn", return_value=conn):
            return db_access.get_event_type_tree(2, **kw), cur

    def test_default_hides_only_free_slots_and_keeps_disabled_types(self):
        rows, cur = self._run()
        assert [r['id'] for r in rows] == [21000, 21100, 21200, 22000]
        assert {r['id']: r['enabled'] for r in rows}[21200] is False    # visible, désactivé
        assert [r['depth'] for r in rows] == [0, 1, 1, 0]
        assert cur.executed[0][1] == (2,)

    def test_include_free_adds_the_categorie_slots(self):
        rows, _ = self._run(include_free=True)
        assert [r['id'] for r in rows] == [21000, 21100, 21200, 21300, 22000, 28000]
        assert {r['id'] for r in rows if r['is_free']} == {21300, 28000}

    def test_disabled_real_type_is_not_a_free_slot(self):
        rows, _ = self._run()
        assert not {r['id']: r['is_free'] for r in rows}[21200]



class TestEventTypeUsage:
    def test_branch_ranges_follow_the_hierarchical_id(self):
        # niveau 1 : 1000 IDs ; niveau 2 : 100 ; niveau 3 : 10 ; niveau 4 : 1 — dans les 2 langues
        assert db_access._branch_ranges(25000) == [(15000, 15999), (25000, 25999)]
        assert db_access._branch_ranges(21300) == [(11300, 11399), (21300, 21399)]
        assert db_access._branch_ranges(25210) == [(15210, 15219), (25210, 25219)]
        assert db_access._branch_ranges(25331) == [(15331, 15331), (25331, 25331)]

    def test_count_sums_both_tables_over_both_languages(self):
        class Cur(FakeCursor):
            def fetchone(self):
                return (2,)
        cur = Cur()
        conn = FakeConn()
        conn._cur = cur
        with patch.object(db_access, "_conn", return_value=conn):
            assert db_access.count_event_type_usage(21300) == 4    # 2 tables x 2
        assert cur.executed[0][1] == (11300, 11399, 21300, 21399)

    def test_tree_reports_usage_per_branch(self):
        class Cur(FakeCursor):
            def __init__(self):
                super().__init__()
                self.queue = [
                    [(21000, 'a', 'Absence', None, True), (21300, 'b', 'Injustifiée', 21000, True),
                     (22000, 'c', 'Cours', None, True)],
                    [(21300, 2), (11300, 1)],          # student_event
                    [],                                # staff_event
                ]
            def fetchall(self):
                return self.queue.pop(0)
        cur = Cur()
        conn = FakeConn()
        conn._cur = cur
        with patch.object(db_access, "_conn", return_value=conn):
            rows = db_access.get_event_type_tree(2)
        usage = {r['id']: r['usage'] for r in rows}
        assert usage == {21000: 3, 21300: 3, 22000: 0}
