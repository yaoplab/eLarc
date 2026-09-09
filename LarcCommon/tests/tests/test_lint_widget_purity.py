import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from lint_widget_purity import find_violations


def test_flags_raw_qpushbutton(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("btn = QPushButton('Go')\n", encoding="utf-8")
    results = find_violations(f)
    assert len(results) == 1
    assert results[0]["widget"] == "QPushButton"
    assert "M3Button" in results[0]["suggestion"]


def test_allows_m3button(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("btn = M3Button('Go', theme=phi)\n", encoding="utf-8")
    assert find_violations(f) == []


def test_allows_qwidget_and_layouts(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text(
        "class Foo(QWidget):\n"
        "    def __init__(self):\n"
        "        layout = QVBoxLayout(self)\n"
        "        box = QHBoxLayout()\n",
        encoding="utf-8",
    )
    assert find_violations(f) == []


def test_class_inheritance_not_flagged_as_instantiation(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("class MyDialog(QDialog):\n    pass\n", encoding="utf-8")
    assert find_violations(f) == []


def test_qcheckbox_flagged_with_no_suggestion_note(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text("cb = QCheckBox('x')\n", encoding="utf-8")
    results = find_violations(f)
    assert len(results) == 1
    assert "aucun widget phibuilder" in results[0]["suggestion"]
