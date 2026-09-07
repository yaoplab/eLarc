"""Régression : EventTypeConfigService doit gérer 4 niveaux de hiérarchie sans changement de code.

Et : EventTypeConfigService filtre par fk_language, cache par langue.
"""
from larccommon.event_type_service import EventTypeConfigService, MemberType


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return self._rows


class FakeConn:
    closed = False

    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return FakeCursor(self._rows)


# id, code, label, category, icon_code, parent_id, applicable_to,
# requires_validation, requires_lieu, requires_subject
FOUR_LEVEL_ROWS = [
    (1, 'absence', 'Absence', 'absence', None, None, 'student,staff', True, False, False),
    (2, 'absence_school', "Absence de l'école", 'absence', None, 1, 'student,staff', True, False, False),
    (3, 'absence_school_sick', 'Maladie', 'absence', None, 2, 'student,staff', True, False, False),
    (4, 'absence_school_sick_mild', 'Légère', 'absence', None, 3, 'student,staff', True, False, False),
]


class TestEventTypeConfigServiceFourLevels:
    def setup_method(self):
        # Reset du singleton entre les tests (cache de classe partagé)
        EventTypeConfigService._instance = None

    def test_load_hierarchy_builds_four_levels(self, monkeypatch):
        service = EventTypeConfigService()
        monkeypatch.setattr(
            "larccommon.event_type_service.db",
            type("DB", (), {"server_conn": FakeConn(FOUR_LEVEL_ROWS)})(),
        )
        hierarchies = service.load_hierarchy(fk_language=1, force_refresh=True)

        assert "absence" in hierarchies
        root = hierarchies["absence"]
        level2 = root.children[0]
        level3 = level2.children[0]
        level4 = level3.children[0]
        assert level4.code == "absence_school_sick_mild"
        assert level4.children == []

    def test_get_path_four_levels(self, monkeypatch):
        service = EventTypeConfigService()
        monkeypatch.setattr(
            "larccommon.event_type_service.db",
            type("DB", (), {"server_conn": FakeConn(FOUR_LEVEL_ROWS)})(),
        )
        service.load_hierarchy(fk_language=1, force_refresh=True)
        leaf = service.get_by_code("absence_school_sick_mild")
        assert service.get_path(leaf) == "Absence > Absence de l'école > Maladie > Légère"

    def test_filter_applicable_four_levels(self, monkeypatch):
        service = EventTypeConfigService()
        monkeypatch.setattr(
            "larccommon.event_type_service.db",
            type("DB", (), {"server_conn": FakeConn(FOUR_LEVEL_ROWS)})(),
        )
        service.load_hierarchy(fk_language=1, force_refresh=True)
        result = service.filter_applicable(MemberType.STUDENT, fk_language=1)
        assert "absence" in result

    def test_get_by_id_returns_intermediate_node(self, monkeypatch):
        service = EventTypeConfigService()
        monkeypatch.setattr(
            "larccommon.event_type_service.db",
            type("DB", (), {"server_conn": FakeConn(FOUR_LEVEL_ROWS)})(),
        )
        service.load_hierarchy(fk_language=1, force_refresh=True)
        intermediate = service.get_by_id(3)  # absence_school_sick, a des enfants
        assert intermediate.code == "absence_school_sick"
        assert len(intermediate.children) == 1


class FakeLangCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        self._params = params

    def fetchall(self):
        # Filtre par fk_language (index 3 dans les rows du fixture), puis retire
        # ce champ : la vraie requête SQL ne sélectionne pas fk_language (WHERE
        # seulement), donc les rows retournées à load_hierarchy() ne l'incluent pas.
        lang = self._params[0] if self._params else None
        rows = [r for r in self._rows if r[3] == lang] if lang else self._rows
        return [r[:3] + r[4:] for r in rows]


class FakeLangConn:
    closed = False

    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return FakeLangCursor(self._rows)


# id, code, label, fk_language, category, icon_code, parent_id, applicable_to,
# requires_validation, requires_lieu, requires_subject
TWO_LANG_ROWS = [
    (1, 'absence', 'Absence', 2, 'absence', None, None, 'student,staff', True, False, False),
    (2, 'absence', 'Absence', 1, 'absence', None, None, 'student,staff', True, False, False),
]


class TestEventTypeConfigServiceLanguage:
    def setup_method(self):
        EventTypeConfigService._instance = None

    def test_load_hierarchy_filters_by_language(self, monkeypatch):
        service = EventTypeConfigService()
        monkeypatch.setattr(
            "larccommon.event_type_service.db",
            type("DB", (), {"server_conn": FakeLangConn(TWO_LANG_ROWS)})(),
        )
        fr = service.load_hierarchy(fk_language=2, force_refresh=True)
        assert fr["absence"].label == "Absence"
        assert fr["absence"].id == 1

    def test_load_hierarchy_reloads_when_language_changes(self, monkeypatch):
        service = EventTypeConfigService()
        monkeypatch.setattr(
            "larccommon.event_type_service.db",
            type("DB", (), {"server_conn": FakeLangConn(TWO_LANG_ROWS)})(),
        )
        service.load_hierarchy(fk_language=2, force_refresh=True)
        en = service.load_hierarchy(fk_language=1)  # pas de force_refresh : doit quand même recharger
        assert en["absence"].id == 2

    def test_filter_applicable_passes_language_through(self, monkeypatch):
        service = EventTypeConfigService()
        monkeypatch.setattr(
            "larccommon.event_type_service.db",
            type("DB", (), {"server_conn": FakeLangConn(TWO_LANG_ROWS)})(),
        )
        result = service.filter_applicable(MemberType.STUDENT, fk_language=1)
        assert result["absence"].id == 2
