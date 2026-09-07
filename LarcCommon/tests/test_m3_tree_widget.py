"""Tests M3TreeWidget — arbre générique (hiérarchie, filtre, sélection)."""
import pytest

# NOTE: `larccommon` must be imported before any `phibuilder.widgets.*` submodule.
# There is a pre-existing circular import in the repo (phibuilder.widgets.__init__
# -> snackbar -> larccommon.safe_slot -> larccommon.__init__ -> larccommon.widgets
# -> larccommon.widgets.sidebar -> `from phibuilder.widgets import M3Button, ...`,
# re-entering the still-initializing phibuilder.widgets package). Importing
# larccommon first fully resolves that cycle before phibuilder.widgets starts.
# This also reproduces on the untouched tests/tests/test_widgets.py — unrelated
# to M3TreeWidget itself.
import larccommon  # noqa: F401,E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from phibuilder.widgets.tree import M3TreeWidget  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class Node:
    def __init__(self, code, label, children=None):
        self.code = code
        self.label = label
        self.children = children or []


def make_tree():
    leaf_a = Node("a", "Alpha")
    leaf_b = Node("b", "Beta")
    root = Node("root", "Racine", [leaf_a, leaf_b])
    return root, leaf_a, leaf_b


class TestM3TreeWidget:
    def test_set_data_builds_items(self):
        widget = M3TreeWidget()
        root, leaf_a, leaf_b = make_tree()
        widget.set_data([root], children_fn=lambda n: n.children, label_fn=lambda n: n.label)
        assert widget.topLevelItemCount() == 1
        assert widget.topLevelItem(0).childCount() == 2

    def test_current_node_returns_underlying_object(self):
        widget = M3TreeWidget()
        root, leaf_a, leaf_b = make_tree()
        widget.set_data([root], children_fn=lambda n: n.children, label_fn=lambda n: n.label)
        item = widget.topLevelItem(0).child(0)
        widget.setCurrentItem(item)
        assert widget.current_node() is leaf_a

    def test_filter_text_hides_non_matching_leaves(self):
        widget = M3TreeWidget()
        root, leaf_a, leaf_b = make_tree()
        widget.set_data([root], children_fn=lambda n: n.children, label_fn=lambda n: n.label)
        widget.filter_text("alpha")
        root_item = widget.topLevelItem(0)
        assert root_item.child(0).isHidden() is False  # Alpha matches
        assert root_item.child(1).isHidden() is True   # Beta hidden

    def test_filter_text_empty_shows_everything(self):
        widget = M3TreeWidget()
        root, leaf_a, leaf_b = make_tree()
        widget.set_data([root], children_fn=lambda n: n.children, label_fn=lambda n: n.label)
        widget.filter_text("alpha")
        widget.filter_text("")
        root_item = widget.topLevelItem(0)
        assert root_item.child(0).isHidden() is False
        assert root_item.child(1).isHidden() is False

    def test_select_node_by_path_expands_and_selects(self):
        widget = M3TreeWidget()
        root, leaf_a, leaf_b = make_tree()
        widget.set_data([root], children_fn=lambda n: n.children, label_fn=lambda n: n.label)
        widget.select_node(leaf_a, path=[root, leaf_a])
        assert widget.current_node() is leaf_a
        assert widget.topLevelItem(0).isExpanded()
