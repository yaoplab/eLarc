import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from larccommon.design_system import ds
from larccommon.widgets.file_viewer import FileViewer
from larccommon.safe_slot import safe_slot


class FilePanel(QWidget):
    """Panneau de gestion de fichiers avec liste, ajout, aperçu, suppression."""

    file_added = Signal(str)
    file_deleted = Signal(str)

    def __init__(self, directory: str = "", parent=None):
        super().__init__(parent)
        self._directory = directory
        self._build()

    def set_directory(self, directory: str):
        self._directory = directory
        os.makedirs(directory, exist_ok=True)
        self._refresh()

    def directory(self) -> str:
        return self._directory

    def files(self) -> list[str]:
        try:
            return sorted(os.listdir(self._directory))
        except Exception:
            return []

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.space_xxs + ds.space_xxs // 2)  # 6px = 4+2

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.itemDoubleClicked.connect(self._on_preview)
        layout.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(ds.space_xxs + ds.space_xxs // 2)  # 6px = 4+2

        self._btn_add = QPushButton("➕ Ajouter")
        self._btn_add.clicked.connect(self._add_files)
        btn_row.addWidget(self._btn_add)

        self._btn_preview = QPushButton("👁 Aperçu")
        self._btn_preview.clicked.connect(self._on_preview)
        btn_row.addWidget(self._btn_preview)

        self._btn_open = QPushButton("📂 Dossier")
        self._btn_open.clicked.connect(self._open_folder)
        btn_row.addWidget(self._btn_open)

        self._btn_del = QPushButton("🗑 Supprimer")
        self._btn_del.clicked.connect(self._delete_file)
        btn_row.addWidget(self._btn_del)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _refresh(self):
        self._list.clear()
        if not self._directory:
            return
        try:
            for f in sorted(os.listdir(self._directory)):
                self._list.addItem(f)
        except Exception:
            pass

    @safe_slot("FilePanel._add_files")
    def _add_files(self):
        if not self._directory:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Ajouter des fichiers", "")
        if not paths:
            return
        import shutil

        for p in paths:
            name = os.path.basename(p)
            shutil.copy2(p, os.path.join(self._directory, name))
            self.file_added.emit(name)
        self._refresh()

    @safe_slot("FilePanel._delete_file")
    def _delete_file(self):
        item = self._list.currentItem()
        if not item:
            return
        name = item.text()
        path = os.path.join(self._directory, name)
        r = QMessageBox.question(
            self, "Confirmation", f"Supprimer {name} ?", QMessageBox.Yes | QMessageBox.No
        )
        if r != QMessageBox.Yes:
            return
        try:
            os.remove(path)
            self.file_deleted.emit(name)
            self._refresh()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

    @safe_slot("FilePanel._on_preview")
    def _on_preview(self, _=None):
        item = self._list.currentItem()
        if not item:
            return
        path = os.path.join(self._directory, item.text())
        dlg = FileViewer(path, self)
        dlg.exec()

    @safe_slot("FilePanel._open_folder")
    def _open_folder(self):
        if not self._directory:
            return
        import subprocess

        subprocess.Popen(["explorer", self._directory])
