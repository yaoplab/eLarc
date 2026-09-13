import pytest
from PySide6.QtWidgets import QApplication
from phibuilder.widgets.card import M3Card, CardVariant
from phibuilder.widgets.button import M3Button
from phibuilder.widgets.textfield import M3TextField


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_m3card_without_theme_warns():
    with pytest.warns(UserWarning, match="theme="):
        M3Card(variant=CardVariant.ELEVATED)


def test_m3button_without_theme_warns():
    with pytest.warns(UserWarning, match="theme="):
        M3Button("test")


def test_m3textfield_without_theme_warns():
    with pytest.warns(UserWarning, match="theme="):
        M3TextField(placeholder="test")
