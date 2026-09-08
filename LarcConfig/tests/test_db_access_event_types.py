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
        with patch.object(db_access, "_conn", return_value=conn):
            ok = db_access.set_event_type_active(42, True)
        assert ok is True
        assert "UPDATE larcauth_event_type_config" in cur.executed[0][0]
        assert "is_active" in cur.executed[0][0]
        assert cur.executed[0][1] == (True, 42)


class TestSetEventTypeLabel:
    def test_writes_label(self):
        cur = FakeCursor()
        conn = FakeConn()
        conn._cur = cur
        with patch.object(db_access, "_conn", return_value=conn):
            ok = db_access.set_event_type_label(42, "Nouveau libellé")
        assert ok is True
        assert cur.executed[0][1] == ("Nouveau libellé", 42)


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
