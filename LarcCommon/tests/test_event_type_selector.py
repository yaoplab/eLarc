"""Tests EventTypeSelectorWidget — arbre + confirmation partagés (création + édition)."""
import dataclasses

import pytest

# NOTE: `larccommon` must be imported before any `phibuilder.widgets.*` submodule.
# There is a pre-existing circular import in the repo (phibuilder.widgets.__init__
# -> snackbar -> larccommon.safe_slot -> larccommon.__init__ -> larccommon.widgets
# -> larccommon.widgets.sidebar -> `from phibuilder.widgets import M3Button, ...`,
# re-entering the still-initializing phibuilder.widgets package). Importing
# larccommon first fully resolves that cycle before phibuilder.widgets starts.
import larccommon  # noqa: F401,E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from larccommon.dialogs.event_type_selector import EventTypeSelectorWidget, category_color  # noqa: E402
from larccommon.event_type_service import EventTypeNode  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def make_hierarchy():
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


def make_multi_category_hierarchy():
    """Deux catégories (Absence, Sortie) pour tester les chips + le filtrage scopé."""
    absence_hierarchies, absence_root, absence_mid, absence_leaf = make_hierarchy()

    sortie_leaf = EventTypeNode(
        id=13, code="sortie_class_toilets", label="Toilettes", category="sortie",
        icon_code=None, parent_id=12, applicable_to="student,staff",
        requires_validation=True, requires_lieu=False, requires_subject=False,
    )
    sortie_mid = EventTypeNode(
        id=12, code="sortie_class", label="Sortie du cours", category="sortie",
        icon_code=None, parent_id=11, applicable_to="student,staff",
        requires_validation=True, requires_lieu=False, requires_subject=True,
        children=[sortie_leaf],
    )
    sortie_root = EventTypeNode(
        id=11, code="sortie", label="Sortie", category="sortie",
        icon_code=None, parent_id=None, applicable_to="student,staff",
        requires_validation=True, requires_lieu=False, requires_subject=False,
        children=[sortie_mid],
    )
    hierarchies = {**absence_hierarchies, "sortie": sortie_root}
    return hierarchies, absence_root, sortie_root, sortie_leaf


class TestCategoryColor:
    def test_known_categories_have_distinct_colors(self):
        colors = {category_color(c) for c in ("absence", "retard", "sortie", "evenement")}
        assert len(colors) == 4

    def test_unknown_category_degrades_to_a_default_color(self):
        assert category_color("custom") == category_color("does_not_exist")


class TestEventTypeSelectorWidgetCategoryChips:
    def test_tree_starts_scoped_to_first_category_only(self):
        hierarchies, absence_root, sortie_root, _ = make_multi_category_hierarchy()
        widget = EventTypeSelectorWidget(hierarchies)
        # _CATEGORY_ORDER place "absence" avant "sortie".
        assert widget._tree.topLevelItemCount() == 1
        assert widget._tree.topLevelItem(0).data(0, Qt.UserRole) is absence_root

    def test_switching_chip_rescopes_tree_to_other_category(self):
        hierarchies, absence_root, sortie_root, _ = make_multi_category_hierarchy()
        widget = EventTypeSelectorWidget(hierarchies)
        sortie_index = widget._roots.index(sortie_root)

        widget._chip_bar.set_current(sortie_index)

        assert widget._tree.topLevelItemCount() == 1
        assert widget._tree.current_node() is None  # sélection réinitialisée par le changement de catégorie

    def test_search_with_no_match_in_active_category_switches_and_filters(self):
        hierarchies, absence_root, sortie_root, sortie_leaf = make_multi_category_hierarchy()
        widget = EventTypeSelectorWidget(hierarchies)
        assert widget._chip_bar.current_index() == 0  # démarre sur Absence

        widget._search.setText("toilettes")  # n'existe que sous Sortie

        assert widget._chip_bar.current_index() == widget._roots.index(sortie_root)
        root_item = widget._tree.topLevelItem(0)
        # "Sortie du cours" (parent) reste visible car il contient un match ; "Toilettes" matche.
        assert root_item.child(0).isHidden() is False

    def test_preselect_switches_to_the_node_category(self):
        hierarchies, absence_root, sortie_root, sortie_leaf = make_multi_category_hierarchy()
        widget = EventTypeSelectorWidget(hierarchies)
        assert widget._chip_bar.current_index() == 0

        widget.preselect(sortie_leaf)

        assert widget._chip_bar.current_index() == widget._roots.index(sortie_root)
        assert widget._tree.current_node() is sortie_leaf


class TestEventTypeSelectorWidget:
    def test_is_leaf_true_for_node_without_children(self):
        _, _, _, leaf = make_hierarchy()
        assert EventTypeSelectorWidget.is_leaf(leaf) is True

    def test_is_leaf_false_for_node_with_children(self):
        _, _, mid, _ = make_hierarchy()
        assert EventTypeSelectorWidget.is_leaf(mid) is False

    def test_confirm_button_disabled_until_selection(self):
        hierarchies, *_ = make_hierarchy()
        widget = EventTypeSelectorWidget(hierarchies)
        assert widget._confirm_btn.isEnabled() is False

    def test_selecting_node_enables_confirm_and_emits_on_click(self, qtbot=None):
        hierarchies, root, mid, leaf = make_hierarchy()
        widget = EventTypeSelectorWidget(hierarchies)
        received = []
        widget.type_confirmed.connect(received.append)

        top_item = widget._tree.topLevelItem(0)
        child_item = top_item.child(0)
        widget._tree.setCurrentItem(child_item)
        assert widget._confirm_btn.isEnabled() is True

        widget._confirm_btn.click()
        assert received == [mid]

    def test_preselect_expands_and_selects_existing_node(self):
        hierarchies, root, mid, leaf = make_hierarchy()
        widget = EventTypeSelectorWidget(hierarchies)
        widget.preselect(leaf)
        assert widget._tree.current_node() is leaf

    def test_preselect_with_id_equal_but_distinct_object_selects_tree_native_node(self):
        """Reproduit le cas réel (edit-flow) : l'appelant passe un EventTypeNode fraîchement
        construit (ex. event_type_service.get_by_id()), distinct par identité de l'objet
        attaché à l'arbre mais égal par .id. M3TreeWidget.select_node compare par identité
        (`is`) : preselect() doit donc résoudre chain[-1] (l'objet arbre-natif), pas l'objet
        passé par l'appelant, sous peine de ne rien sélectionner silencieusement."""
        hierarchies, root, mid, leaf = make_hierarchy()
        widget = EventTypeSelectorWidget(hierarchies)

        distinct_copy = dataclasses.replace(leaf)
        assert distinct_copy is not leaf
        assert distinct_copy.id == leaf.id

        widget.preselect(distinct_copy)

        assert widget._tree.current_node() is leaf
        assert widget._confirm_btn.isEnabled() is True

    def test_preselect_with_unknown_id_degrades_gracefully(self):
        """Un nœud dont l'id n'existe dans aucune branche de la hiérarchie ne doit ni lever
        d'exception, ni modifier la sélection courante de l'arbre."""
        hierarchies, root, mid, leaf = make_hierarchy()
        widget = EventTypeSelectorWidget(hierarchies)

        unknown = dataclasses.replace(leaf, id=999, code="does_not_exist")

        widget.preselect(unknown)

        assert widget._tree.current_node() is None
        assert widget._confirm_btn.isEnabled() is False

    def test_construct_no_theme_warning(self, recwarn):
        """_search (M3TextField), _badge_text (M3Label) et _confirm_btn (M3Button)
        doivent tous recevoir theme=theme_manager.phi_theme — sinon _update_style()
        n'applique aucun style et emet un warnings.warn('... cree sans theme= ...')."""
        hierarchies, *_ = make_hierarchy()
        widget = EventTypeSelectorWidget(hierarchies)

        theme_warnings = [str(w.message) for w in recwarn.list if "cree sans theme=" in str(w.message)]
        assert not theme_warnings, theme_warnings
