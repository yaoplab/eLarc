"""Phase 1 — Tests unitaires du module DataLoader (DB mockée).

Ces tests ne nécessitent PAS PostgreSQL.
Ils valident la logique métier et les cas d'erreur.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestDataLoaderActiveTerm:
    """DataLoader.get_active_term() — requête terme actif."""

    def test_returns_term_id(self, mock_db):
        """get_active_term retourne l'ID du terme quand la DB répond."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        # Simuler un curseur qui retourne (1,)
        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchone.return_value = (1,)

        result = DataLoader().get_active_term()

        assert result == 1
        fake_cursor.execute.assert_called_once()

    def test_returns_zero_when_no_term(self, mock_db):
        """get_active_term retourne 0 quand la DB ne trouve rien."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchone.return_value = None

        result = DataLoader().get_active_term()

        assert result == 0

    def test_returns_zero_on_error(self, mock_db):
        """get_active_term retourne 0 quand la DB lève une exception."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.execute.side_effect = Exception("Connection refused")

        result = DataLoader().get_active_term()

        assert result == 0


class TestDataLoaderPrograms:
    """DataLoader.get_programs() — chargement des programmes."""

    def test_returns_programs_dict(self, mock_db):
        """get_programs retourne un dict {id: {sigle, label}}."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = [
            (1, "PEI", "Programme d'éducation intermédiaire"),
            (2, "MYP", "Middle Years Programme"),
        ]

        result = DataLoader().get_programs()

        assert result == {
            1: {"sigle": "PEI", "label": "Programme d'éducation intermédiaire"},
            2: {"sigle": "MYP", "label": "Middle Years Programme"},
        }

    def test_returns_empty_on_error(self, mock_db):
        """get_programs retourne {} quand la DB lève une exception."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.execute.side_effect = Exception("Timeout")

        result = DataLoader().get_programs()

        assert result == {}


class TestDataLoaderClasses:
    """DataLoader.get_classes() — chargement des classes."""

    def test_returns_class_tuples(self, mock_db):
        """get_classes retourne une liste de tuples (id, label, program_id, sigle)."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = [
            (1, "6A", 1, "PEI"),
            (2, "5A", 1, "PEI"),
            (3, "2A", 3, "DPFr"),
        ]

        result = DataLoader().get_classes()

        assert len(result) == 3
        assert result[0] == (1, "6A", 1, "PEI")

    def test_returns_empty_on_no_conn(self, mock_db):
        """get_classes retourne [] quand server_conn est None."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn = None

        result = DataLoader().get_classes()

        assert result == []


class TestDataLoaderStudents:
    """DataLoader.get_students() — chargement des élèves d'une classe."""

    def test_returns_student_list(self, mock_db):
        """get_students retourne la liste des élèves avec id/nom/prénom."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = [
            (1, "Dupont", "Jean"),
            (2, "Martin", "Sophie"),
        ]

        result = DataLoader().get_students(5)  # class_id=5

        assert result == [
            {"id": 1, "last_name": "Dupont", "first_name": "Jean"},
            {"id": 2, "last_name": "Martin", "first_name": "Sophie"},
        ]

    def test_returns_empty_when_class_empty(self, mock_db):
        """get_students retourne [] quand la classe n'a pas d'élèves."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = []

        result = DataLoader().get_students(99)

        assert result == []

    def test_returns_empty_on_error(self, mock_db):
        """get_students retourne [] quand la DB lève une exception."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.execute.side_effect = Exception("DB not reachable")

        result = DataLoader().get_students(1)

        assert result == []


class TestDataLoaderStudentInfo:
    """DataLoader.get_student_info() — infos détaillées d'un élève."""

    def test_returns_info_dict(self, mock_db):
        """get_student_info retourne un dict complet avec les infos de l'élève."""
        from datetime import date
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchone.return_value = (
            "Dupont", "Jean", "jean.dupont@ecole.org", "", "", "90000000",
            date(2020, 9, 1), "6A",
        )

        result = DataLoader().get_student_info(1)

        assert result["last_name"] == "Dupont"
        assert result["first_name"] == "Jean"
        assert result["email"] == "jean.dupont@ecole.org"
        assert result["class_label"] == "6A"
        assert result["date_entree"] == date(2020, 9, 1)

    def test_returns_empty_when_not_found(self, mock_db):
        """get_student_info retourne {} quand l'élève n'existe pas."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchone.return_value = None

        result = DataLoader().get_student_info(999)

        assert result == {}


class TestDataLoaderStudentKpis:
    """DataLoader.get_student_kpis() — KPIs d'un élève."""

    def test_returns_kpi_dict(self, mock_db):
        """get_student_kpis retourne les compteurs absences/sorties/total."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchone.return_value = (2, 1, 5)

        result = DataLoader().get_student_kpis(1, "2024-01-01", "2024-03-31")

        assert result["abs_count"] == 2
        assert result["exit_count"] == 1
        assert result["total"] == 5

    def test_returns_empty_when_no_events(self, mock_db):
        """get_student_kpis retourne {} quand la requête ne trouve rien."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchone.return_value = None

        result = DataLoader().get_student_kpis(1, "2024-01-01", "2024-03-31")

        assert result == {}


class TestDataLoaderEventHistory:
    """DataLoader.get_event_history() — historique global des événements."""

    def test_events_have_expected_keys(self, mock_db):
        """Chaque événement retourné a les clés attendues."""
        from datetime import datetime
        from LarcSuperviseur.views.core.data_loader import DataLoader

        now = datetime.now()
        mock_cursor = mock_db.server_conn.cursor.return_value
        mock_cursor.fetchall.return_value = [
            (1, "Dupont Jean", "6A", "absence", now, "Cour", "Maths", "Non justifié", "Mr X", None),
        ]

        result = DataLoader().get_event_history("grp_all", "2024-01-01", "2024-03-31")

        assert len(result) == 1
        evt = result[0]
        assert "event_id" in evt
        assert "student_name" in evt
        assert "event_type" in evt
        assert "event_at" in evt
        assert "created_by" in evt

    def test_filters_by_class(self, mock_db):
        """get_event_history applique le filtre class_id."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_cursor = mock_db.server_conn.cursor.return_value
        mock_cursor.fetchall.return_value = []

        DataLoader().get_event_history("grp_all", "2024-01-01", "2024-03-31", class_id=5)

        # Vérifier que le curseur a été appelé (le filtre est passé dans la requête)
        mock_cursor.execute.assert_called_once()


class TestDataLoaderStudentsEventStats:
    """DataLoader.get_student_event_stats() — stats par élève."""

    def test_returns_stats_dict(self, mock_db):
        """get_student_event_stats retourne un dict {student_id: stats}."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = [
            (1, 0, "Présent"),
            (2, 1, "Absent"),
        ]

        result = DataLoader().get_student_event_stats([1, 2], "2024-01-01", "2024-03-31")

        assert result[1] == {"exit_count": 0, "presence": "Présent"}
        assert result[2] == {"exit_count": 1, "presence": "Absent"}

    def test_returns_empty_when_no_ids(self, mock_db):
        """get_student_event_stats retourne {} si la liste d'IDs est vide."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        result = DataLoader().get_student_event_stats([], "2024-01-01", "2024-03-31")

        assert result == {}


class TestDataLoaderInsertEvent:
    """DataLoader.insert_event() — création d'un événement."""

    def test_insert_success(self, mock_db):
        """insert_event retourne True quand l'INSERT réussit."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_cursor = mock_db.server_conn.cursor.return_value
        mock_cursor.execute.return_value = MagicMock()

        result = DataLoader().insert_event({
            "student_id": 1,
            "event_type": "absence",
            "event_at": "2024-03-15 08:30:00",
            "lieu_label": "Cour",
            "subject_label": "",
            "note": "Non justifié",
            "source": "manuel",
            "created_by": 1,
        })

        assert result is True
        # Vérifier que commit a été appelé
        mock_db.server_conn.commit.assert_called_once()

    def test_insert_failure_rollback(self, mock_db):
        """insert_event retourne False et appelle rollback quand l'INSERT échoue."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_cursor = mock_db.server_conn.cursor.return_value
        mock_cursor.execute.side_effect = Exception("Duplicate key")

        result = DataLoader().insert_event({
            "student_id": 1,
            "event_type": "absence",
            "event_at": "2024-03-15 08:30:00",
            "lieu_label": "Cour",
            "subject_label": "",
            "note": "",
            "source": "manuel",
            "created_by": 1,
        })

        assert result is False
        mock_db.server_conn.rollback.assert_called_once()


class TestDataLoaderDeleteEvent:
    """DataLoader.delete_event() — suppression d'un événement."""

    def test_delete_success(self, mock_db):
        """delete_event retourne True quand le DELETE réussit."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_cursor = mock_db.server_conn.cursor.return_value
        mock_cursor.execute.return_value = MagicMock()

        result = DataLoader().delete_event(42)

        assert result is True
        mock_db.server_conn.commit.assert_called_once()

    def test_delete_failure_rollback(self, mock_db):
        """delete_event retourne False et appelle rollback quand le DELETE échoue."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_cursor = mock_db.server_conn.cursor.return_value
        mock_cursor.execute.side_effect = Exception("Foreign key violation")

        result = DataLoader().delete_event(42)

        assert result is False
        mock_db.server_conn.rollback.assert_called_once()


class TestDataLoaderClassStats:
    """DataLoader.get_class_stats() — stats agrégées par classe (mode groupe)."""

    def test_returns_stats_for_all(self, mock_db):
        """get_class_stats('grp_all', ...) retourne les stats pour toutes les classes."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = [
            (1, "6A", 10, 2, 1, 25),
            (2, "5A", 8, 1, 0, 22),
        ]

        result = DataLoader().get_class_stats("grp_all", "2024-01-01", "2024-03-31")

        assert len(result) == 2
        assert result[0]["label"] == "6A"
        assert result[0]["abs_count"] == 2
        assert result[0]["exit_count"] == 1
        assert result[0]["student_count"] == 25

    def test_returns_stats_for_college(self, mock_db):
        """get_class_stats('grp_college', ...) filtre sur le Collège (PEI + MYP)."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = [
            (3, "6B", 5, 0, 0, 20),
        ]

        result = DataLoader().get_class_stats("grp_college", "2024-01-01", "2024-03-31")

        assert len(result) == 1
        assert result[0]["label"] == "6B"

    def test_returns_stats_for_lycee(self, mock_db):
        """get_class_stats('grp_lycee', ...) filtre sur le Lycée (DPFr + DPEn)."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = [
            (4, "2A", 15, 5, 2, 30),
        ]

        result = DataLoader().get_class_stats("grp_lycee", "2024-01-01", "2024-03-31")

        assert len(result) == 1
        assert result[0]["label"] == "2A"

    def test_returns_stats_for_program(self, mock_db):
        """get_class_stats('grp_pei', ...) filtre sur un programme spécifique."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = [
            (1, "6A", 10, 2, 1, 25),
        ]

        result = DataLoader().get_class_stats("grp_pei", "2024-01-01", "2024-03-31")

        assert result[0]["label"] == "6A"

    def test_returns_empty_when_no_data(self, mock_db):
        """get_class_stats retourne [] quand il n'y a pas de données."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = []

        result = DataLoader().get_class_stats("grp_all", "2024-01-01", "2024-03-31")

        assert result == []

    def test_returns_empty_on_error(self, mock_db):
        """get_class_stats retourne [] quand la DB lève une exception."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.execute.side_effect = Exception("Query failed")

        result = DataLoader().get_class_stats("grp_all", "2024-01-01", "2024-03-31")

        assert result == []


class TestDataLoaderPresenceRate:
    """DataLoader.get_presence_rate() — taux de présence agrégé."""

    def test_returns_present_absent_counts(self, mock_db):
        """get_presence_rate retourne les compteurs present/absent."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchone.return_value = (150, 10)

        result = DataLoader().get_presence_rate("grp_all", "2024-01-01", "2024-03-31")

        assert result["present"] == 150
        assert result["absent"] == 10

    def test_returns_zero_when_no_data(self, mock_db):
        """get_presence_rate retourne (0, 0) quand la requête ne trouve rien."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchone.return_value = None

        result = DataLoader().get_presence_rate("grp_all", "2024-01-01", "2024-03-31")

        assert result == {"present": 0, "absent": 0}

    def test_returns_zero_on_error(self, mock_db):
        """get_presence_rate retourne (0, 0) quand la DB lève une exception."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.execute.side_effect = Exception("Connection lost")

        result = DataLoader().get_presence_rate("grp_all", "2024-01-01", "2024-03-31")

        assert result == {"present": 0, "absent": 0}


class TestDataLoaderLocations:
    """DataLoader.get_locations() — chargement des lieux."""

    def test_returns_locations(self, mock_db):
        """get_locations retourne une liste de tuples (ID, s_ID, label)."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = [
            (1, "COUR", "Cour"),
            (2, "SALLE_001", "Salle 001"),
        ]

        result = DataLoader().get_locations()

        assert len(result) == 2


class TestDataLoaderClassFilter:
    """DataLoader._build_class_filter() — construction des filtres SQL."""

    def test_build_class_filter_all(self, mock_db):
        """_build_class_filter('grp_all') retourne le filtre toutes classes."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        dl = DataLoader()
        result = dl._build_class_filter("grp_all")

        assert "PEI" in result
        assert "MYP" in result
        assert "DPFr" in result

    def test_build_class_filter_college(self, mock_db):
        """_build_class_filter('grp_college') retourne le filtre Collège."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        dl = DataLoader()
        result = dl._build_class_filter("grp_college")

        assert "PEI" in result
        assert "MYP" in result
        assert "DPFr" not in result


class TestDataLoaderAttendanceTrend:
    """DataLoader.get_attendance_trend() — tendance des absences sur la période."""

    def test_returns_trend_list(self, mock_db):
        """get_attendance_trend retourne la liste {date, count}."""
        from datetime import date
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = [
            (date(2024, 1, 5), 3),
            (date(2024, 1, 6), 5),
            (date(2024, 1, 7), 1),
        ]

        result = DataLoader().get_attendance_trend("grp_all", "2024-01-01", "2024-03-31")

        assert len(result) == 3
        assert result[0]["count"] == 3
        assert result[1]["count"] == 5

    def test_returns_empty_when_no_data(self, mock_db):
        """get_attendance_trend retourne [] quand il n'y a pas de données."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = []

        result = DataLoader().get_attendance_trend("grp_all", "2024-01-01", "2024-03-31")

        assert result == []

    def test_returns_empty_on_error(self, mock_db):
        """get_attendance_trend retourne [] quand la DB lève une exception."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.execute.side_effect = Exception("Query timeout")

        result = DataLoader().get_attendance_trend("grp_all", "2024-01-01", "2024-03-31")

        assert result == []


class TestDataLoaderEventTypesTree:
    """DataLoader.get_event_types_tree() — arbre hiérarchique des types d'événements."""

    def test_returns_tree_structure(self, mock_db, mock_session):
        """get_event_types_tree retourne un dict {catégorie: {niveau2: [niveau3]}}."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = [
            (1, "Absence", "Matin", "Retard"),
            (2, "Absence", "Matin", "Non justifié"),
            (3, "Absence", "Après-midi", ""),
            (4, "Sortie", "", ""),
        ]

        result = DataLoader().get_event_types_tree()

        assert "Absence" in result
        assert "Matin" in result["Absence"]
        assert len(result["Absence"]["Matin"]) == 2
        assert "Retard" in result["Absence"]["Matin"]
        assert "Après-midi" in result["Absence"]
        assert result["Absence"]["Après-midi"] == []  # pas de niveau 3
        assert "Sortie" in result
        assert result["Sortie"] == {}  # pas de niveau 2

    def test_returns_empty_on_error(self, mock_db, mock_session):
        """get_event_types_tree retourne {} quand la DB lève une exception."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.execute.side_effect = Exception("Connection lost")

        result = DataLoader().get_event_types_tree()

        assert result == {}


class TestDataLoaderUpdateEvent:
    """DataLoader.update_event() — UPDATE d'un événement (type + note)."""

    def test_update_success(self, mock_db):
        """update_event retourne True quand l'UPDATE réussit."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_cursor = mock_db.server_conn.cursor.return_value

        result = DataLoader().update_event(42, "sortie", "Justifié")

        assert result is True
        mock_db.server_conn.commit.assert_called_once()
        # Vérifier les paramètres SQL : event_type, note, event_id
        call_params = mock_cursor.execute.call_args[0][1]
        assert call_params[0] == "sortie"
        assert call_params[1] == "Justifié"
        assert call_params[2] == 42

    def test_update_failure_rollback(self, mock_db):
        """update_event retourne False et appelle rollback quand l'UPDATE échoue."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_cursor = mock_db.server_conn.cursor.return_value
        mock_cursor.execute.side_effect = Exception("Update failed")

        result = DataLoader().update_event(42, "sortie", "")

        assert result is False
        mock_db.server_conn.rollback.assert_called_once()


class TestDataLoaderClassroomSubjects:
    """DataLoader.get_classroom_subjects() — matières d'une classe."""

    def test_returns_subjects_with_term(self, mock_db):
        """get_classroom_subjects retourne les matières pour un terme donné."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = [
            (1, "Maths", 10, "M. Dupont"),
            (2, "Français", 11, "Mme Martin"),
        ]

        result = DataLoader().get_classroom_subjects(5, term_id=1)

        assert len(result) == 2
        assert result[0][1] == "Maths"
        assert result[1][1] == "Français"

    def test_fallback_when_term_not_found(self, mock_db):
        """get_classroom_subjects retente sans terme si la 1ère requête échoue."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        # 1ère tentative : lève une exception → fallback
        fake_cursor.fetchall.side_effect = [
            Exception("empty"),         # 1er appel -> raise
            [(1, "Anglais", 12, "M. Smith")],  # 2e appel -> donnée
        ]

        result = DataLoader().get_classroom_subjects(5, term_id=1)

        assert len(result) == 1
        assert result[0][1] == "Anglais"
        # execute doit être appelé 2 fois (1er échec + fallback)
        assert fake_cursor.execute.call_count == 2

    def test_returns_empty_on_error(self, mock_db):
        """get_classroom_subjects retourne [] quand la DB lève une exception."""
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.execute.side_effect = Exception("DB error")

        result = DataLoader().get_classroom_subjects(5)

        assert result == []


class TestDataLoaderConnectionHelpers:
    """DataLoader.conn / _cursor — accès connexion."""

    def test_conn_property(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        assert DataLoader().conn is mock_db.server_conn

    def test_cursor_raises_without_connection(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn = None
        with pytest.raises(ConnectionError):
            DataLoader()._cursor()


class TestDataLoaderTermId:
    """DataLoader.get_term_id() — résolution trim → id du terme actif."""

    def test_returns_term_id(self, mock_db, mock_session):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchone.return_value = (7,)

        result = DataLoader().get_term_id()

        assert result == 7
        fake_cursor.execute.assert_called_once()

    def test_returns_zero_when_none(self, mock_db, mock_session):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchone.return_value = None
        assert DataLoader().get_term_id() == 0

    def test_returns_zero_on_error(self, mock_db, mock_session):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().get_term_id() == 0


class TestDataLoaderCurrentTermLabel:
    """DataLoader.get_current_term_label() — libellé du terme actif."""

    def test_returns_label(self, mock_db, mock_session):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchone.return_value = ("T1 2027",)
        assert DataLoader().get_current_term_label() == "T1 2027"

    def test_returns_empty_when_none(self, mock_db, mock_session):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchone.return_value = None
        assert DataLoader().get_current_term_label() == ""

    def test_returns_empty_on_error(self, mock_db, mock_session):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().get_current_term_label() == ""


class TestDataLoaderUnitPeriods:
    """DataLoader.get_unit_periods() — périodes d'unités, préférence langue."""

    def test_prefers_user_language(self, mock_db, mock_session):
        from datetime import date

        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = [
            (1, 1, "U1 EN", date(2026, 9, 1), date(2026, 10, 9), 1),
            (2, 1, "U1 FR", date(2026, 9, 1), date(2026, 10, 9), 2),
            (3, 2, "U2 FR", date(2026, 10, 12), date(2026, 11, 27), 2),
        ]

        result = DataLoader().get_unit_periods()

        assert [p["label"] for p in result] == ["U1 FR", "U2 FR"]
        assert all(p["start_date"] for p in result)

    def test_returns_empty_on_error(self, mock_db, mock_session):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().get_unit_periods() == []


class TestDataLoaderAllClassrooms:
    """DataLoader.get_all_classrooms() — toutes les classes actives."""

    def test_returns_rows(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchall.return_value = [(1, "PP-1"), (2, "PEI-2")]
        assert DataLoader().get_all_classrooms() == [(1, "PP-1"), (2, "PEI-2")]

    def test_returns_empty_on_error(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().get_all_classrooms() == []


class TestDataLoaderStudentClassroom:
    """DataLoader.get_student_classroom() — classe d'un élève."""

    def test_returns_dict(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchone.return_value = (5, "PEI-1")
        assert DataLoader().get_student_classroom(123) == {"classroom_id": 5, "label": "PEI-1"}

    def test_returns_empty_when_none(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchone.return_value = None
        assert DataLoader().get_student_classroom(999) == {}

    def test_returns_empty_on_error(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().get_student_classroom(123) == {}


class TestDataLoaderAllEventTypes:
    """DataLoader.get_all_event_types() — liste des types d'événements."""

    def test_returns_list(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchall.return_value = [("absence",), ("sortie",)]
        assert DataLoader().get_all_event_types() == ["absence", "sortie"]

    def test_returns_empty_on_error(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().get_all_event_types() == []


class TestDataLoaderStudentAbsenceTrend:
    """DataLoader.get_student_absence_trend() — tendance d'absences élève."""

    def test_returns_trend(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchall.return_value = [("2026-07-08", 2)]
        result = DataLoader().get_student_absence_trend(123, "2026-01-01", "2026-08-14")
        assert result == [{"date": "2026-07-08", "count": 2}]

    def test_returns_empty_on_error(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().get_student_absence_trend(123, "", "") == []


class TestDataLoaderStudentEvents:
    """DataLoader.get_student_events() — événements d'un élève (limite + dates)."""

    def test_returns_events_with_dates(self, mock_db):
        from datetime import datetime

        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = [
            (51, "Absence cours", datetime(2026, 7, 8, 8, 30), "Salle de cours", "Maths", "", None, None)
        ]

        result = DataLoader().get_student_events(123, date_from="2026-01-01", date_to="2026-08-14")

        assert result[0]["event_id"] == 51
        assert result[0]["event_type"] == "Absence cours"
        assert result[0]["creator"] is None
        # Paramètres : student_id, date_from, date_to, limit
        assert fake_cursor.execute.call_args[0][1] == [123, "2026-01-01", "2026-08-14", 20]

    def test_returns_events_without_dates(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchall.return_value = []
        DataLoader().get_student_events(123)
        assert fake_cursor.execute.call_args[0][1] == [123, 20]

    def test_returns_empty_on_error(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().get_student_events(123) == []


class TestDataLoaderEventDetails:
    """DataLoader.get_event_details() — détail d'un événement."""

    def test_returns_details(self, mock_db):
        from datetime import datetime

        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchone.return_value = (
            "Absence cours",
            datetime(2026, 7, 8, 8, 30),
            "Salle de cours",
            "Maths",
            "",
            "Dupont Jean",
        )
        result = DataLoader().get_event_details(51)
        assert result["event_type"] == "Absence cours"
        assert result["student_name"] == "Dupont Jean"

    def test_returns_empty_when_none(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchone.return_value = None
        assert DataLoader().get_event_details(999) == {}

    def test_returns_empty_on_error(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().get_event_details(51) == {}


class TestDataLoaderCheckEventValidated:
    """DataLoader.check_event_validated() — qui a validé l'événement."""

    def test_returns_validator(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchone.return_value = (5,)
        assert DataLoader().check_event_validated(51) == 5

    def test_returns_none_when_not_validated(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchone.return_value = None
        assert DataLoader().check_event_validated(51) is None

    def test_returns_none_on_error(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().check_event_validated(51) is None


class TestDataLoaderToggleEventValidation:
    """DataLoader.toggle_event_validation() — invalider/valider un événement."""

    def test_unvalidates_when_validated(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchone.return_value = (5,)

        result = DataLoader().toggle_event_validation(42, user_id=7)

        assert result is True
        updates = [c.args for c in fake_cursor.execute.call_args_list if "UPDATE" in c.args[0]]
        assert "NULL" in updates[0][0]
        assert mock_db.server_conn.commit.called

    def test_validates_when_not_validated(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchone.return_value = None

        result = DataLoader().toggle_event_validation(42, user_id=7)

        assert result is True
        updates = [c.args for c in fake_cursor.execute.call_args_list if "UPDATE" in c.args[0]]
        assert updates[0][1] == (7, 42)

    def test_rollback_on_error(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        result = DataLoader().toggle_event_validation(42, user_id=7)
        assert result is False
        assert mock_db.server_conn.rollback.called


class TestDataLoaderClassroomTimeperiods:
    """DataLoader.get_classroom_timeperiods() — créneaux d'une classe."""

    def test_returns_slots(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchall.return_value = [
            (11, "08:00:00", "08:55:00", 3)
        ]
        result = DataLoader().get_classroom_timeperiods(5, 1, 7)
        assert result == [{"id": 11, "debut": "08:00", "fin": "08:55", "timetable_id": 3}]

    def test_returns_empty_on_error(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().get_classroom_timeperiods(5, 1, 7) == []


class TestDataLoaderTimeperiods:
    """DataLoader.get_timeperiods() — créneaux horaires généraux."""

    def test_returns_rows(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchall.return_value = [(1, "08:00", "08:55", 1)]
        assert DataLoader().get_timeperiods() == [(1, "08:00", "08:55", 1)]

    def test_returns_empty_on_error(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().get_timeperiods() == []


class TestDataLoaderClassroomTimetable:
    """DataLoader.get_classroom_timetable() — grille EDT d'une classe."""

    def test_maps_slots(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchall.return_value = [(11, 3, 1, "Maths")]
        result = DataLoader().get_classroom_timetable(5, 7)
        assert result == {"cht_map": {(1, 3): "Maths"}, "cht_id_map": {(1, 3): 11}}

    def test_returns_empty_maps_on_error(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().get_classroom_timetable(5, 7) == {"cht_map": {}, "cht_id_map": {}}


class TestDataLoaderAvailableSubjects:
    """DataLoader.get_available_subjects() — matières disponibles (option vide)."""

    def test_returns_with_empty_option(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchall.return_value = [("Maths",), ("Anglais",)]
        assert DataLoader().get_available_subjects(5) == ["", "Maths", "Anglais"]

    def test_returns_empty_option_on_error(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().get_available_subjects(5) == [""]


class TestDataLoaderSubjectIdByLabel:
    """DataLoader.get_subject_id_by_label() — id d'une matière par libellé."""

    def test_returns_id(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchone.return_value = (9,)
        assert DataLoader().get_subject_id_by_label("Maths") == 9

    def test_returns_none_when_missing(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchone.return_value = None
        assert DataLoader().get_subject_id_by_label("Nope") is None

    def test_returns_none_on_error(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().get_subject_id_by_label("Maths") is None


class TestDataLoaderUpdateTimetableSlot:
    """DataLoader.update_timetable_slot() — affectation d'une matière à un créneau."""

    def test_assign_subject(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        result = DataLoader().update_timetable_slot(11, subj_id=9)
        assert result is True
        assert fake_cursor.execute.call_args[0][1] == (9, 11)
        assert mock_db.server_conn.commit.called

    def test_clear_subject(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        fake_cursor = mock_db.server_conn.cursor.return_value
        result = DataLoader().update_timetable_slot(11, subj_id=None)
        assert result is True
        assert "NULL" in fake_cursor.execute.call_args[0][0]
        assert fake_cursor.execute.call_args[0][1] == (11,)

    def test_rollback_on_error(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        result = DataLoader().update_timetable_slot(11, subj_id=9)
        assert result is False
        assert mock_db.server_conn.rollback.called


class TestDataLoaderFindUserByEmail:
    """DataLoader.find_user_by_email() — recherche d'utilisateur (auth DB)."""

    def test_returns_user(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchone.return_value = (
            1, "Jean", "Dupont", "j@x.fr", "h4sh", True, False, True,
        )
        result = DataLoader().find_user_by_email("j@x.fr")
        assert result["user_id"] == 1
        assert result["password_hash"] == "h4sh"
        assert result["is_director"] is True
        assert result["is_coord"] is False
        assert result["is_supervisor"] is True

    def test_returns_none_when_missing(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchone.return_value = None
        assert DataLoader().find_user_by_email("x@x.fr") is None

    def test_returns_none_on_error(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().find_user_by_email("j@x.fr") is None


class TestDataLoaderGetStudentName:
    """DataLoader.get_student_name() — nom complet d'un élève."""

    def test_returns_name(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchone.return_value = ("Dupont Jean",)
        assert DataLoader().get_student_name(123) == "Dupont Jean"

    def test_returns_empty_when_missing(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.fetchone.return_value = None
        assert DataLoader().get_student_name(999) == ""

    def test_returns_empty_on_error(self, mock_db):
        from LarcSuperviseur.views.core.data_loader import DataLoader

        mock_db.server_conn.cursor.return_value.execute.side_effect = Exception("DB down")
        assert DataLoader().get_student_name(123) == ""
