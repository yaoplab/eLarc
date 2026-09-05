import os
import tempfile

from larccommon.widgets.file_panel import FilePanel


class TestFilePanel:
    def test_empty_panel(self, qtbot):
        panel = FilePanel()
        assert panel.files() == []

    def test_set_directory(self, qtbot):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Créer quelques fichiers
            open(os.path.join(tmpdir, "a.txt"), "w").close()
            open(os.path.join(tmpdir, "b.pdf"), "w").close()

            panel = FilePanel()
            panel.set_directory(tmpdir)
            assert sorted(panel.files()) == ["a.txt", "b.pdf"]

    def test_files_empty_dir(self, qtbot):
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = FilePanel()
            panel.set_directory(tmpdir)
            assert panel.files() == []

    def test_directory(self, qtbot):
        panel = FilePanel("/some/path")
        assert panel.directory() == "/some/path"

    def test_file_added_signal(self, qtbot):
        with tempfile.TemporaryDirectory() as tmpdir:
            panel = FilePanel(tmpdir)
            signals = []
            panel.file_added.connect(lambda name: signals.append(name))

            # Copy a file manually to simulate add
            src = os.path.join(tmpdir, "test_file.txt")
            open(src, "w").close()
            panel._refresh()
            assert "test_file.txt" in panel.files()

    def test_file_deleted_signal(self, qtbot):
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "to_delete.txt"), "w").close()
            panel = FilePanel(tmpdir)
            assert "to_delete.txt" in panel.files()

            signals = []
            panel.file_deleted.connect(lambda name: signals.append(name))

            os.remove(os.path.join(tmpdir, "to_delete.txt"))
            panel._refresh()
            assert "to_delete.txt" not in panel.files()
