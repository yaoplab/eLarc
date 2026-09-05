import pytest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from phibuilder import PhiBuilder
from phibuilder.theme import Theme, ThemeConfig
from phibuilder.theme.shape import M3Shape
from phibuilder.widgets import (
    ButtonVariant,
    CardVariant,
    FieldVariant,
    M3Button,
    M3Card,
    M3ComboBox,
    M3Dialog,
    M3Label,
    M3ListWidget,
    M3NavigationBar,
    M3Sidebar,
    M3TableWidget,
    M3TextField,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def theme():
    return Theme(ThemeConfig(seed_color="#6750A4", is_dark=False))


@pytest.fixture
def builder():
    return PhiBuilder()


class TestM3Button:
    def test_default_creation(self, qapp, theme):
        btn = M3Button("Click", theme)
        assert btn.text() == "Click"
        assert btn._variant == ButtonVariant.FILLED

    def test_variants(self, qapp, theme):
        for v in ButtonVariant:
            btn = M3Button(v.value, theme, v)
            assert btn._variant == v

    def test_set_variant(self, qapp, theme):
        btn = M3Button("Test", theme, ButtonVariant.FILLED)
        btn.set_variant(ButtonVariant.TEXT)
        assert btn._variant == ButtonVariant.TEXT

    def test_signal(self, qapp, theme):
        btn = M3Button("Test", theme)
        assert btn.isEnabled()


class TestM3Card:
    def test_default_creation(self, qapp, theme):
        card = M3Card(theme)
        assert card._variant == CardVariant.ELEVATED

    def test_variants(self, qapp, theme):
        for v in CardVariant:
            card = M3Card(theme, v)
            assert card._variant == v

    def test_content_layout(self, qapp, theme):
        card = M3Card(theme)
        assert card.content_layout() is card._layout

    def test_set_variant(self, qapp, theme):
        card = M3Card(theme, CardVariant.ELEVATED)
        card.set_variant(CardVariant.FILLED)
        assert card._variant == CardVariant.FILLED

    def test_set_shape(self, qapp, theme):
        card = M3Card(theme)
        card.set_shape(M3Shape.FULL)
        assert card._shape == M3Shape.FULL


class TestM3TextField:
    def test_default_creation(self, qapp, theme):
        tf = M3TextField("hello", theme)
        assert tf.text() == "hello"
        assert tf._variant == FieldVariant.OUTLINED

    def test_variants(self, qapp, theme):
        for v in FieldVariant:
            tf = M3TextField("", theme, v)
            assert tf._variant == v

    def test_placeholder(self, qapp, theme):
        tf = M3TextField("", theme, placeholder="Enter text")
        assert tf.placeholderText() == "Enter text"

    def test_set_variant(self, qapp, theme):
        tf = M3TextField("", theme, FieldVariant.OUTLINED)
        tf.set_variant(FieldVariant.FILLED)
        assert tf._variant == FieldVariant.FILLED


class TestM3Label:
    def test_default_creation(self, qapp, theme):
        lbl = M3Label("Hello", theme)
        assert lbl.text() == "Hello"

    def test_custom_style(self, qapp, theme):
        lbl = M3Label("Title", theme, "headline_large")
        assert lbl._style_name == "headline_large"

    def test_set_style(self, qapp, theme):
        lbl = M3Label("Text", theme, "body_medium")
        lbl.set_style("display_large")
        assert lbl._style_name == "display_large"


class TestM3ComboBox:
    def test_default_creation(self, qapp, theme):
        cb = M3ComboBox(["A", "B", "C"], theme)
        assert cb.count() == 3

    def test_empty(self, qapp, theme):
        cb = M3ComboBox(theme=theme)
        assert cb.count() == 0

    def test_selection(self, qapp, theme):
        cb = M3ComboBox(["X", "Y"], theme)
        cb.setCurrentIndex(1)
        assert cb.currentText() == "Y"


class TestM3ListWidget:
    def test_default_creation(self, qapp, theme):
        lw = M3ListWidget(theme)
        assert lw.count() == 0

    def test_add_item(self, qapp, theme):
        lw = M3ListWidget(theme)
        lw.add_item("Item 1")
        assert lw.count() == 1

    def test_add_item_with_subtitle(self, qapp, theme):
        lw = M3ListWidget(theme)
        item = lw.add_item("Main", subtitle="Sub")
        assert item.toolTip() == "Sub"


class TestM3TableWidget:
    def test_default_creation(self, qapp, theme):
        tw = M3TableWidget(0, 3, theme)
        assert tw.columnCount() == 3

    def test_set_headers(self, qapp, theme):
        tw = M3TableWidget(0, 0, theme)
        tw.set_headers(["Name", "Value"])
        assert tw.columnCount() == 2

    def test_add_row(self, qapp, theme):
        tw = M3TableWidget(0, 3, theme)
        tw.set_headers(["A", "B", "C"])
        r = tw.add_row(["1", "2", "3"])
        assert r == 0
        assert tw.item(0, 0).text() == "1"


class TestM3Dialog:
    def test_creation(self, qapp, theme):
        dlg = M3Dialog(title="Title", message="Message", theme=theme)
        assert dlg.windowTitle() == "Title"


class TestM3NavigationBar:
    def test_creation(self, qapp, theme):
        items = [{"label": "Tab1"}, {"label": "Tab2"}, {"label": "Tab3"}]
        nav = M3NavigationBar(items, theme)
        assert len(nav._buttons) == 3

    def test_selection(self, qapp, theme):
        items = [{"label": "A"}, {"label": "B"}]
        nav = M3NavigationBar(items, theme)
        nav.set_current(1)
        assert nav._current_index == 1


class TestM3Sidebar:
    def test_creation(self, qapp, theme):
        items = [{"label": "Item1"}, {"label": "Item2"}]
        sb = M3Sidebar(items, theme)
        assert len(sb._buttons) == 2

    def test_selection(self, qapp, theme):
        items = [{"label": "A"}, {"label": "B"}]
        sb = M3Sidebar(items, theme)
        sb.set_current(1)
        assert sb._current_index == 1


class TestBuilder:
    def test_default_init(self, builder):
        assert builder.theme is not None
        assert builder.qss != ""

    def test_toggle_dark(self, builder):
        was = builder._config.is_dark
        builder.toggle_dark_mode()
        assert builder._config.is_dark != was

    def test_set_dark(self, builder):
        builder.set_dark_mode(True)
        assert builder._config.is_dark
        builder.set_dark_mode(False)
        assert not builder._config.is_dark

    def test_set_seed(self, builder):
        builder.set_seed_color("#FF0000")
        assert builder._config.seed_color == "#FF0000"

    def test_set_font(self, builder):
        builder.set_font("Arial")
        assert builder._config.font_family == "Arial"

    def test_set_variant(self, builder):
        builder.set_variant("monochrome")
        assert builder._config.variant == "monochrome"

    def test_palette(self, builder):
        p = builder.palette
        assert "primary" in p
        assert isinstance(p["primary"], str)

    def test_apply(self, qapp, builder):
        w = QWidget()
        builder.apply(w)
        assert w.styleSheet() == builder.qss

    def test_export_qss(self, builder, tmp_path):
        p = tmp_path / "test.qss"
        builder.export_qss(str(p))
        assert p.read_text() == builder.qss

    def test_export_json(self, builder, tmp_path):
        import json

        p = tmp_path / "test.json"
        builder.export_theme_json(str(p))
        d = json.loads(p.read_text())
        assert "primary" in d


class TestIntegration:
    def test_widgets_with_builder(self, qapp, builder):
        parent = QWidget()
        layout = QVBoxLayout(parent)
        btn = M3Button("Test", builder.theme)
        card = M3Card(builder.theme)
        tf = M3TextField("text", builder.theme)
        lbl = M3Label("Label", builder.theme)
        layout.addWidget(btn)
        layout.addWidget(card)
        layout.addWidget(tf)
        layout.addWidget(lbl)
        builder.apply(parent)
        assert btn.text() == "Test"
        assert tf.text() == "text"
        assert lbl.text() == "Label"
