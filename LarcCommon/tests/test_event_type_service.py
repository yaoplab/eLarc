"""Régression : EventTypeConfigService doit gérer 4 niveaux de hiérarchie sans changement de code."""
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
        hierarchies = service.load_hierarchy(force_refresh=True)

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
        service.load_hierarchy(force_refresh=True)
        leaf = service.get_by_code("absence_school_sick_mild")
        assert service.get_path(leaf) == "Absence > Absence de l'école > Maladie > Légère"

    def test_filter_applicable_four_levels(self, monkeypatch):
        service = EventTypeConfigService()
        monkeypatch.setattr(
            "larccommon.event_type_service.db",
            type("DB", (), {"server_conn": FakeConn(FOUR_LEVEL_ROWS)})(),
        )
        service.load_hierarchy(force_refresh=True)
        result = service.filter_applicable(MemberType.STUDENT)
        assert "absence" in result

    def test_get_by_id_returns_intermediate_node(self, monkeypatch):
        service = EventTypeConfigService()
        monkeypatch.setattr(
            "larccommon.event_type_service.db",
            type("DB", (), {"server_conn": FakeConn(FOUR_LEVEL_ROWS)})(),
        )
        service.load_hierarchy(force_refresh=True)
        intermediate = service.get_by_id(3)  # absence_school_sick, a des enfants
        assert intermediate.code == "absence_school_sick"
        assert len(intermediate.children) == 1
