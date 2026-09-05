"""Phase 1 — Tests unitaires du module EventActions (CRUD événements, DB mockée).

Ces tests ne nécessitent PAS PostgreSQL ni PySide6.
Les méthodes Qt-dépendantes (get_context_menu) ne sont pas testées ici.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestEventActionsGetById:
    """EventActions.get_event_by_id() — lecture d'un événement."""

    def test_returns_event_dict(self, mock_db, mock_session):
        """get_event_by_id retourne un dict avec les colonnes attendues."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchone.return_value = (
            42, 1, "absence", "2024-03-15 08:30",
            "Cour", "Maths", "Non justifié", None,
            None, 1, "2024-03-15 09:00", "manuel",
            "Dupont Jean",
        )
        # Simuler cursor.description pour dict(zip(cols, row))
        fake_cursor.description = [
            ("event_id",), ("student_id",), ("event_type",), ("event_at",),
            ("lieu_label",), ("subject_label",), ("note",), ("validated_by",),
            ("agenda_day_id",), ("created_by",), ("created_at",), ("source",),
            ("student_name",),
        ]

        result = EventActions().get_event_by_id(42)

        assert result is not None
        assert result["event_id"] == 42
        assert result["event_type"] == "absence"
        assert result["student_name"] == "Dupont Jean"

    def test_returns_none_when_not_found(self, mock_db, mock_session):
        """get_event_by_id retourne None quand l'événement n'existe pas."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.fetchone.return_value = None

        result = EventActions().get_event_by_id(999)

        assert result is None

    def test_returns_none_on_error(self, mock_db, mock_session):
        """get_event_by_id retourne None quand la DB lève une exception."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        fake_cursor = mock_db.server_conn.cursor.return_value
        fake_cursor.execute.side_effect = Exception("Query failed")

        result = EventActions().get_event_by_id(42)

        assert result is None


class TestEventActionsEditEvent:
    """EventActions.edit_event() — UPDATE d'un événement."""

    def test_edit_success(self, mock_db, mock_session):
        """edit_event retourne True quand l'UPDATE réussit."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        mock_cursor = mock_db.server_conn.cursor.return_value

        result = EventActions().edit_event(42, {
            "event_type": "sortie",
            "note": "Justifié",
        })

        assert result is True
        mock_db.server_conn.commit.assert_called_once()

    def test_edit_partial_fields(self, mock_db, mock_session):
        """edit_event ne modifie que les champs fournis dans data."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        mock_cursor = mock_db.server_conn.cursor.return_value

        result = EventActions().edit_event(42, {
            "note": "Nouvelle note",
        })

        assert result is True
        # Vérifier que l'UPDATE ne contient QUE note (pas event_type)
        sql = mock_cursor.execute.call_args[0][0]
        assert "note = %s" in sql
        assert "event_type" not in sql

    def test_edit_no_allowed_fields(self, mock_db, mock_session):
        """edit_event retourne False si data ne contient aucun champ autorisé."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        result = EventActions().edit_event(42, {
            "invalid_key": "value",
        })

        assert result is False
        # execute ne doit PAS être appelé
        mock_db.server_conn.cursor.return_value.execute.assert_not_called()

    def test_edit_failure_rollback(self, mock_db, mock_session):
        """edit_event retourne False et appelle rollback quand l'UPDATE échoue."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        mock_cursor = mock_db.server_conn.cursor.return_value
        mock_cursor.execute.side_effect = Exception("Update failed")

        result = EventActions().edit_event(42, {
            "event_type": "sortie",
        })

        assert result is False
        mock_db.server_conn.rollback.assert_called_once()


class TestEventActionsToggleValidation:
    """EventActions.toggle_validation() — valider/invalider un événement."""

    def test_validate_success(self, mock_db, mock_session):
        """toggle_validation(validate=True) met validated_by = session.user_id."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        mock_cursor = mock_db.server_conn.cursor.return_value

        result = EventActions().toggle_validation(42, validate=True)

        assert result is True
        mock_db.server_conn.commit.assert_called_once()
        # Vérifier que l'UPDATE utilise session.user_id
        call_args = mock_cursor.execute.call_args[0]
        assert "validated_by" in call_args[0]
        assert 1 in call_args[1]  # session.user_id = 1

    def test_invalidate_success(self, mock_db, mock_session):
        """toggle_validation(validate=False) met validated_by = NULL."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        mock_cursor = mock_db.server_conn.cursor.return_value

        result = EventActions().toggle_validation(42, validate=False)

        assert result is True
        mock_db.server_conn.commit.assert_called_once()
        call_args = mock_cursor.execute.call_args[0][0]
        assert "NULL" in call_args.upper()

    def test_toggle_failure_rollback(self, mock_db, mock_session):
        """toggle_validation retourne False et rollback quand l'UPDATE échoue."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        mock_cursor = mock_db.server_conn.cursor.return_value
        mock_cursor.execute.side_effect = Exception("Update failed")

        result = EventActions().toggle_validation(42, validate=True)

        assert result is False
        mock_db.server_conn.rollback.assert_called_once()


class TestEventActionsDeleteEvent:
    """EventActions.delete_event() — DELETE d'un événement."""

    def test_delete_success(self, mock_db, mock_session):
        """delete_event retourne True quand le DELETE réussit."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        mock_cursor = mock_db.server_conn.cursor.return_value

        result = EventActions().delete_event(42)

        assert result is True
        mock_db.server_conn.commit.assert_called_once()

    def test_delete_failure_rollback(self, mock_db, mock_session):
        """delete_event retourne False et appelle rollback quand le DELETE échoue."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        mock_cursor = mock_db.server_conn.cursor.return_value
        mock_cursor.execute.side_effect = Exception("Foreign key violation")

        result = EventActions().delete_event(42)

        assert result is False
        mock_db.server_conn.rollback.assert_called_once()


class TestEventActionsGetEventIdFromTable:
    """EventActions.get_event_id_from_table() — méthode statique, sans DB."""

    def test_returns_id_from_selected_row(self):
        """get_event_id_from_table retourne l'ID de la ligne sélectionnée."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        table = MagicMock()
        table.currentRow.return_value = 0
        item = MagicMock()
        item.text.return_value = "42"
        table.item.return_value = item

        result = EventActions.get_event_id_from_table(table)

        assert result == 42
        table.item.assert_called_once_with(0, 0)

    def test_returns_none_when_no_selection(self):
        """get_event_id_from_table retourne None si aucune ligne sélectionnée."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        table = MagicMock()
        table.currentRow.return_value = -1

        result = EventActions.get_event_id_from_table(table)

        assert result is None

    def test_returns_none_when_invalid_data(self):
        """get_event_id_from_table retourne None si l'item n'est pas un int."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        table = MagicMock()
        table.currentRow.return_value = 0
        table.item.return_value = None  # pas d'item à cette position

        result = EventActions.get_event_id_from_table(table)

        assert result is None


class TestEventActionsGetEventIdFromRow:
    """EventActions.get_event_id_from_row() — méthode statique, sans DB."""

    def test_returns_id_from_row(self):
        """get_event_id_from_row retourne l'ID de la ligne donnée."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        table = MagicMock()
        item = MagicMock()
        item.text.return_value = "77"
        table.item.return_value = item

        result = EventActions.get_event_id_from_row(table, 3)

        assert result == 77
        table.item.assert_called_once_with(3, 0)

    def test_returns_none_when_no_item(self):
        """get_event_id_from_row retourne None si l'item n'existe pas."""
        from LarcSuperviseur.views.core.event_actions import EventActions

        table = MagicMock()
        table.item.return_value = None

        result = EventActions.get_event_id_from_row(table, 99)

        assert result is None
