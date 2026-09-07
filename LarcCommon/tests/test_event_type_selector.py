"""Tests EventTypeSelectorWidget — arbre + confirmation partagés (création + édition)."""
import pytest

# NOTE: `larccommon` must be imported before any `phibuilder.widgets.*` submodule.
# There is a pre-existing circular import in the repo (phibuilder.widgets.__init__
# -> snackbar -> larccommon.safe_slot -> larccommon.__init__ -> larccommon.widgets
# -> larccommon.widgets.sidebar -> `from phibuilder.widgets import M3Button, ...`,
# re-entering the still-initializing phibuilder.widgets package). Importing
# larccommon first fully resolves that cycle before phibuilder.widgets starts.
import larccommon  # noqa: F401,E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from larccommon.dialogs.event_type_selector import EventTypeSelectorWidget  # noqa: E402
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
