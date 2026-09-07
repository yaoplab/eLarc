"""Tests smoke — EventGeneratorDialog en vue scindée (Task 7).

Ne remplace PAS la vérification manuelle GUI décrite dans le brief (lancement réel de
LarcSuperviseur, clic dans l'arbre, layout visuel) : celle-ci nécessite une connexion
PostgreSQL et un affichage, indisponibles pour un test automatisé. Ce test couvre la
logique la plus risquée du refactor — la visibilité du champ note qui doit suivre
EventTypeSelectorWidget.is_leaf(node), quel que soit le niveau de confirmation — sans
jamais appeler .exec() (qui bloquerait en attente d'un utilisateur réel).
"""
from unittest.mock import PropertyMock, patch

import pytest

# NOTE: `larccommon` must be imported before any `phibuilder.widgets.*` submodule.
# Cf. test_event_type_selector.py / test_m3_tree_widget.py pour le détail du cycle
# d'import préexistant que cet ordre résout.
import larccommon  # noqa: F401,E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from larccommon.database import db  # noqa: E402
from larccommon.dialogs.event_generator_dialog import EventGeneratorDialog  # noqa: E402
from larccommon.event_type_service import EventTypeNode, MemberType, event_type_service  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def make_hierarchy():
    """Hiérarchie à 2 niveaux : root (Absence) -> mid (Maladie, intermédiaire) -> leaf (Légère)."""
    leaf = EventTypeNode(
        id=3, code="absence_school_sick_mild", label="Légère", category="absence",
        icon_code=None, parent_id=2, applicable_to="student,staff",
        requires_validation=True, requires_lieu=False, requires_subject=False,
    )
    mid = EventTypeNode(
        id=2, code="absence_school_sick", label="Maladie", category="absence",
        icon_code=None, parent_id=1, applicable_to="student,staff",
        requires_validation=True, requires_lieu=False, requires_subject=False,
        children=[leaf],
    )
    root = EventTypeNode(
        id=1, code="absence", label="Absence", category="absence",
        icon_code=None, parent_id=None, applicable_to="student,staff",
        requires_validation=True, requires_lieu=False, requires_subject=False,
        children=[mid],
    )
    return {"absence": root}, root, mid, leaf


@pytest.fixture
def dialog():
    hierarchies, root, mid, leaf = make_hierarchy()
    # server_conn est une @property sans setter : on la patch au niveau classe pour
    # que _load_locations / _check_working_day / _check_active_term dégradent comme
    # prévu en environnement sans DB (leur propre code gère déjà conn is None).
    with patch.object(type(db), "server_conn", new_callable=PropertyMock, return_value=None), \
            patch.object(event_type_service, "filter_applicable", return_value=hierarchies), \
            patch.object(event_type_service, "get_path", return_value="Absence > Maladie"):
        dlg = EventGeneratorDialog(member_id=1, member_type=MemberType.STUDENT)
        yield dlg, root, mid, leaf
        dlg.deleteLater()


class TestEventGeneratorDialogSmoke:
    def test_constructs_without_crashing(self, dialog):
        dlg, root, mid, leaf = dialog
        assert dlg._selector is not None
        assert dlg._detail_panel is not None
        # Aucun type confirmé encore : Valider doit rester désactivé.
        assert dlg._validate_btn.isEnabled() is False
        # Note masquée par défaut (aucune sélection).
        assert dlg._note_label.isHidden() is True
        assert dlg._note_input.isHidden() is True

    def test_confirming_intermediate_node_hides_note_and_enables_validate(self, dialog):
        dlg, root, mid, leaf = dialog
        assert mid.children  # précondition : mid est bien un nœud intermédiaire

        dlg._on_type_confirmed(mid)

        assert dlg._selected_node is mid
        assert dlg._validate_btn.isEnabled() is True
        assert dlg._note_label.isHidden() is True
        assert dlg._note_input.isHidden() is True

    def test_confirming_leaf_node_shows_note(self, dialog):
        dlg, root, mid, leaf = dialog
        assert not leaf.children  # précondition : leaf est bien une feuille

        dlg._on_type_confirmed(mid)  # d'abord un choix intermédiaire (masque la note)
        dlg._on_type_confirmed(leaf)  # puis redescente jusqu'à la feuille

        assert dlg._selected_node is leaf
        assert dlg._validate_btn.isEnabled() is True
        assert dlg._note_label.isHidden() is False
        assert dlg._note_input.isHidden() is False

    def test_type_confirmed_signal_from_selector_drives_the_dialog(self, dialog):
        """Vérifie le câblage réel selector.type_confirmed -> dialog._on_type_confirmed
        (et pas seulement un appel direct de méthode)."""
        dlg, root, mid, leaf = dialog
        dlg._selector.type_confirmed.emit(leaf)
        assert dlg._selected_node is leaf
        assert dlg._note_input.isHidden() is False

    def test_validate_intermediate_choice_saves_empty_note_even_if_field_had_stale_text(self, dialog):
        """Un choix intermédiaire doit être sauvegardé avec note vide, même si le champ
        note contient un texte périmé au moment de la validation.

        `_on_type_confirmed` vide déjà le champ note quand le nœud confirmé n'est pas
        une feuille (`self._note_input.clear()`) — cela ne suffit pas à prouver que
        `_on_validate` a son propre garde-fou : si ce test se contentait d'appeler
        `_on_type_confirmed(mid)` puis d'asserter `note == ""`, il passerait même en
        supprimant entièrement la vérification `is_leaf` dans `_on_validate` (puisque
        le champ serait déjà vide de toute façon). Pour isoler et prouver le
        garde-fou de `_on_validate` lui-même, on réinjecte du texte dans le widget
        APRÈS la confirmation — simulant un futur bug hypothétique dans le clear-on-
        confirm, ou une race condition — puis on vérifie que `_on_validate` force
        quand même `note == ""` malgré un champ non vide au moment de l'appel.
        """
        dlg, root, mid, leaf = dialog

        dlg._on_type_confirmed(mid)  # choix intermédiaire : _note_input.clear() a déjà tourné
        # Réinjection délibérée : le widget contient du texte périmé au moment de valider,
        # indépendamment de ce que _on_type_confirmed a fait — isole le garde-fou de _on_validate.
        dlg._note_input.setText("stale text that should never be saved")

        received = []
        dlg.event_created.connect(received.append)
        dlg._on_validate()

        assert len(received) == 1
        event_data = received[0]
        assert event_data.type_id == mid.id
        assert event_data.type_code == mid.code
        assert event_data.note == ""

    def test_validate_leaf_choice_includes_note_and_type_id(self, dialog):
        dlg, root, mid, leaf = dialog

        dlg._on_type_confirmed(leaf)
        dlg._note_input.setText("Fièvre depuis ce matin")

        received = []
        dlg.event_created.connect(received.append)
        dlg._on_validate()

        assert len(received) == 1
        event_data = received[0]
        assert event_data.type_id == leaf.id
        assert event_data.type_code == leaf.code
        assert event_data.note == "Fièvre depuis ce matin"
        assert event_data.member_id == 1
        assert event_data.member_type == MemberType.STUDENT
