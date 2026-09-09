import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from lint_widget_purity import ALLOWED, ROOT, find_violations


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


def test_file_field_is_relative_to_root_for_files_under_root():
    """Regression pour la CRITIQUE de la review finale : les cles de baseline
    doivent survivre un deplacement du repo (worktree -> chemin final), donc
    'file' doit etre relatif a ROOT, jamais absolu, pour un fichier sous ROOT."""
    real_file = ROOT / "LarcCommon" / "larccommon" / "_tmp_widget_purity_test.py"
    real_file.write_text("btn = QPushButton('Go')\n", encoding="utf-8")
    try:
        results = find_violations(real_file)
        assert len(results) == 1
        expected = str(Path("LarcCommon") / "larccommon" / "_tmp_widget_purity_test.py")
        assert results[0]["file"] == expected
        assert not Path(results[0]["file"]).is_absolute()
    finally:
        real_file.unlink()


def test_file_field_falls_back_to_original_path_outside_root(tmp_path):
    """Un fichier hors ROOT (ex: tmp_path de pytest) ne doit pas lever -- on
    retombe simplement sur le chemin d'origine (comportement historique)."""
    f = tmp_path / "sample.py"
    f.write_text("btn = QPushButton('Go')\n", encoding="utf-8")
    results = find_violations(f)
    assert len(results) == 1
    assert results[0]["file"] == str(f)


def test_allowed_exceptions_never_flagged_even_if_hypothetically_matchable():
    """Finding 2 (IMPORTANT) : ALLOWED doit etre un vrai garde-fou dans
    find_violations, pas seulement une consequence implicite de l'absence de
    ces noms dans SUGGESTIONS. On le verifie en tapant directement dans le
    dict interne des resultats bruts avant filtrage pour s'assurer que le
    filtre explicite existe (et pas seulement l'absence de correspondance)."""
    import lint_widget_purity as lwp

    assert ALLOWED == {
        "QMessageBox", "QApplication", "QVBoxLayout", "QHBoxLayout",
        "QGridLayout", "QButtonGroup", "QTableWidgetItem", "QWidget",
    }

    # Simule un SUGGESTIONS temporaire qui contiendrait par erreur une
    # exception CLAUDE.md, pour prouver que le garde-fou ALLOWED filtre bien
    # meme si SUGGESTIONS venait a en contenir une (protection en profondeur).
    original_suggestions = dict(lwp.SUGGESTIONS)
    original_re = lwp.INSTANTIATION_RE
    try:
        lwp.SUGGESTIONS["QWidget"] = "N/A"
        lwp.INSTANTIATION_RE = lwp.re.compile(
            r'\b(' + '|'.join(lwp.SUGGESTIONS) + r')\s*\('
        )

        def _write_and_scan(tmp_path, code):
            f = tmp_path / "sample.py"
            f.write_text(code, encoding="utf-8")
            return lwp.find_violations(f)

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            results = _write_and_scan(Path(tmpdir), "w = QWidget()\n")
            assert results == [], "QWidget (ALLOWED) ne doit jamais etre signale"
    finally:
        lwp.SUGGESTIONS.clear()
        lwp.SUGGESTIONS.update(original_suggestions)
        lwp.INSTANTIATION_RE = original_re
