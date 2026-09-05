"""DocumentManager — coffre-fort documentaire par employé.

Chaque fichier a un label + description (stockés en DB via staff_document).
"""
from __future__ import annotations

import os
import shutil

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFileDialog, QMessageBox, QLineEdit, QTextEdit, QFrame,
)

from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.icons import icon as md3_icon
from larccommon.safe_slot import safe_slot
from larccommon.widgets.themed_widget import ThemedDialog
from phibuilder.phi.scale import SpacingToken

from LarcRH.common.hr_database import HRDatabase

# Fallback hors ligne — les catégories dynamiques viennent de staff_detail_category
# via HRDatabase.get_detail_categories() (gérées par CategoryManageDialog).
DOC_CATEGORIES = [
    ('identity', 'Identité'),
    ('diplomas', 'Diplômes'),
    ('contracts', 'Contrats'),
    ('pay', 'Paie'),
    ('leave', 'Congés'),
    ('evaluations', 'Évaluations'),
    ('training', 'Formations'),
    ('other', 'Divers'),
]


class DocumentMetaDialog(ThemedDialog):
    """Dialogue d'édition du label et de la description d'un document."""

    def __init__(self, fname: str, label: str, description: str, parent=None):
        super().__init__(parent)
        self._fname = fname
        self._label_text = label
        self._description = description

        self.setWindowTitle("Métadonnées du document")
        _w = ds.sidebar_width + ds.golden_width(ds.sidebar_width)
        self.setMinimumSize(ds.golden_width(ds.sidebar_width), ds.sp(SpacingToken.XXXL) * 2)
        self._setup_ui()

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        s = theme_manager.font_size
        return f"""
            DocumentMetaDialog {{ background: {p.surface}; }}
        """

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_sm)

        # ── Header: filename ──
        head = QLabel("Métadonnées du document")
        head.setStyleSheet(
            f"font-size: {s(16)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        layout.addWidget(head)

        fn_lbl = QLabel(self._fname)
        fn_lbl.setStyleSheet(
            f"font-size: {s(12)}px; color: {p.text_soft}; border: none;")
        layout.addWidget(fn_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {p.outline_variant}; border: none;")
        layout.addWidget(sep)

        # ── Label field (Q8: label AU-DESSUS) ──
        lbl1 = QLabel("Label")
        lbl1.setStyleSheet(
            f"font-size: {s(11)}px; color: {p.text_soft}; font-weight: bold; border: none;")
        layout.addWidget(lbl1)

        self._label_field = QLineEdit(self._label_text)
        self._label_field.setPlaceholderText("Titre ou label du document")
        self._label_field.setFixedHeight(ds.field_height)
        self._label_field.setStyleSheet(ds.flat_input_qss())
        layout.addWidget(self._label_field)

        # ── Description field (Q8: label AU-DESSUS) ──
        lbl2 = QLabel("Description")
        lbl2.setStyleSheet(
            f"font-size: {s(11)}px; color: {p.text_soft}; font-weight: bold; border: none;")
        layout.addWidget(lbl2)

        self._desc_field = QTextEdit()
        self._desc_field.setPlainText(self._description)
        self._desc_field.setFixedHeight(ds.kpi_card_height)
        self._desc_field.setStyleSheet(f"""
            QTextEdit {{ background: {p.background}; border: 1px solid {p.outline};
            border-radius: {ds.radius_xs}px; padding: {ds.space_xs}px;
            color: {p.text_strong}; font-size: {s(13)}px; }}
            QTextEdit:focus {{ border-color: {p.primary}; }}
        """)
        layout.addWidget(self._desc_field)

        layout.addStretch()

        # ── Actions (Q19b: secondaire gauche, primaire droite) ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel = QPushButton("Annuler")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setFixedHeight(ds.field_height + ds.space_xs)
        cancel.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {p.text_strong};
            border: 1px solid {p.outline}; border-radius: {ds.radius_sm}px;
            padding: {ds.space_xs}px {ds.space_md}px; font-size: {s(13)}px; }}
            QPushButton:hover {{ background: {p.surface_variant}; }}
        """)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        save = QPushButton("Enregistrer")
        save.setCursor(Qt.PointingHandCursor)
        save.setFixedHeight(ds.field_height + ds.space_xs)
        save.setStyleSheet(f"""
            QPushButton {{ background: {p.primary}; color: white; border: none;
            border-radius: {ds.radius_sm}px; padding: {ds.space_xs}px {ds.space_md}px;
            font-size: {s(13)}px; font-weight: bold; }}
            QPushButton:hover {{ background: {p.primary}; }}
        """)
        save.clicked.connect(self.accept)
        btn_row.addWidget(save)

        layout.addLayout(btn_row)
        self.setStyleSheet(self._STYLE)

    def result(self) -> tuple[str, str]:
        return (
            self._label_field.text().strip(),
            self._desc_field.toPlainText().strip(),
        )


class DocumentManager(QWidget):
    """Coffre-fort documentaire — sidebar catégories + grille fichiers avec métadonnées."""

    def __init__(self, staff_data: dict, parent=None):
        super().__init__(parent)
        self._staff = staff_data
        self._staff_id = staff_data.get("id", 0)
        self._categories = self._load_categories()
        self._current_category = self._categories[0]["key"] if self._categories else 'identity'
        self._doc_dir = self._ensure_doc_dir()

        self._setup_ui()
        self.refresh()

    def _load_categories(self) -> list[dict]:
        """Catégories dynamiques (staff_detail_category) — fallback : DOC_CATEGORIES."""
        cats = HRDatabase.get_detail_categories()
        if not cats:
            return [
                {"key": k, "label": lbl, "icon": "folder", "order": i}
                for i, (k, lbl) in enumerate(DOC_CATEGORIES)
            ]
        return cats

    def _ensure_doc_dir(self) -> str:
        base = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "staff",
                         str(self._staff_id), "documents"))
        for cat in self._categories:
            os.makedirs(os.path.join(base, cat["key"]), exist_ok=True)
        return base

    def _setup_ui(self):
        p = theme_manager.palette
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar: categories ──
        sidebar = QWidget()
        sidebar.setFixedWidth(ds.sp(SpacingToken.XXXL) + ds.space_sm * 2)
        sidebar.setAttribute(Qt.WA_StyledBackground, True)
        sidebar.setStyleSheet(
            f"background: {p.surface_variant}; border-right: 1px solid {p.outline_variant};")
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(ds.space_xs, ds.space_sm, ds.space_xs, ds.space_sm)
        sl.setSpacing(ds.space_xxs)
        self._sidebar_layout = sl

        title = QLabel("Catégories")
        title.setStyleSheet(
            f"font-weight: bold; font-size: {theme_manager.font_size(12)}px; "
            f"color: {p.text_strong}; border: none; padding: 0 5px;")
        sl.addWidget(title)

        self._cat_buttons: dict[str, QPushButton] = {}
        self._build_category_buttons()

        sl.addStretch()

        manage_btn = QPushButton("Gérer les catégories")
        manage_btn.setCursor(Qt.PointingHandCursor)
        manage_btn.setFixedHeight(ds.field_height)
        manage_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {p.text_soft};
            border: 1px solid {p.outline}; border-radius: {ds.radius_xs}px;
            padding: {ds.space_xxs}px {ds.space_sm}px;
            font-size: {theme_manager.font_size(11)}px; }}
            QPushButton:hover {{ background: {p.surface_variant}; color: {p.text_strong}; }}
        """)
        manage_btn.clicked.connect(self._on_manage_categories)
        sl.addWidget(manage_btn)

        layout.addWidget(sidebar)

        # ── Content: header (titre + « + Ajouter ») + file list ──
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(ds.space_md, ds.space_sm, ds.space_md, ds.space_sm)
        cl.setSpacing(ds.space_sm)

        hdr = QHBoxLayout()
        hdr.setSpacing(ds.space_sm)
        self._cat_title = QLabel("")
        self._cat_title.setStyleSheet(
            f"font-weight: bold; font-size: {theme_manager.font_size(14)}px; "
            f"color: {p.text_strong}; border: none;")
        hdr.addWidget(self._cat_title)
        hdr.addStretch()
        upload_btn = QPushButton("+ Ajouter")
        upload_btn.setCursor(Qt.PointingHandCursor)
        upload_btn.setFixedHeight(ds.field_height)
        upload_btn.setStyleSheet(f"""
            QPushButton {{ background: {p.primary}; color: white; border: none;
            border-radius: {ds.radius_xs}px;
            font-size: {theme_manager.font_size(12)}px; font-weight: bold; }}
            QPushButton:hover {{ background: {p.primary}; }}
        """)
        upload_btn.clicked.connect(self._on_upload)
        hdr.addWidget(upload_btn)
        cl.addLayout(hdr)

        self._files_scroll = QScrollArea()
        self._files_scroll.setWidgetResizable(True)
        self._files_scroll.setFrameShape(QScrollArea.NoFrame)
        self._files_widget = QWidget()
        self._files_widget.setAttribute(Qt.WA_StyledBackground, True)
        self._files_widget.setStyleSheet("background: transparent;")
        self._files_layout = QVBoxLayout(self._files_widget)
        self._files_layout.setContentsMargins(0, 0, 0, 0)
        self._files_layout.setSpacing(ds.space_xs)
        self._files_scroll.setWidget(self._files_widget)
        cl.addWidget(self._files_scroll, 1)

        layout.addWidget(content, 1)

        self._switch_category(self._current_category)

    def _make_category_button(self, cat: dict) -> QPushButton:
        """Bouton de catégorie (text-only, checkable) — pattern sidebar K26."""
        key, label = cat["key"], cat["label"]
        p = theme_manager.palette
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(ds.field_height)
        btn.setStyleSheet(f"""
            QPushButton {{ text-align: left;
            padding: {ds.space_xxs}px {ds.space_xs}px; border: none;
            border-radius: {ds.radius_xs}px;
            color: {p.text_strong}; font-size: {theme_manager.font_size(12)}px;
            background: transparent; }}
            QPushButton:checked {{ background: {p.primary_container};
            color: {p.primary}; font-weight: bold; }}
            QPushButton:hover {{ background: {p.surface}; }}
        """)
        btn.clicked.connect(lambda checked, k=key: self._switch_category(k))
        return btn

    def _build_category_buttons(self):
        """Construit les boutons de catégories dans la sidebar (après le titre)."""
        self._cat_buttons.clear()
        for i, cat in enumerate(self._categories):
            btn = self._make_category_button(cat)
            self._sidebar_layout.insertWidget(1 + i, btn)
            self._cat_buttons[cat["key"]] = btn

    def _rebuild_categories(self):
        """Relit les catégories en base et reconstruit la sidebar (après gestion)."""
        self._categories = self._load_categories()
        current = self._current_category
        for btn in list(self._cat_buttons.values()):
            self._sidebar_layout.removeWidget(btn)
            btn.deleteLater()
        self._build_category_buttons()
        if current not in self._cat_buttons and self._categories:
            current = self._categories[0]["key"]
        self._ensure_doc_dir()
        self._switch_category(current)

    @safe_slot("DocumentManager._on_manage_categories")
    def _on_manage_categories(self):
        from LarcRH.views.staff_detail import CategoryManageDialog  # paresseux (cycle d'imports)
        dlg = CategoryManageDialog(parent=self)
        if dlg.exec():
            self._rebuild_categories()

    def _switch_category(self, cat_key: str):
        self._current_category = cat_key
        for k, btn in self._cat_buttons.items():
            btn.setChecked(k == cat_key)
        cat_label = next((c["label"] for c in self._categories if c["key"] == cat_key), cat_key)
        self._cat_title.setText(cat_label)
        self.refresh()

    def refresh(self):
        while self._files_layout.count():
            item = self._files_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cat_dir = os.path.join(self._doc_dir, self._current_category)
        if not os.path.isdir(cat_dir):
            self._files_layout.addWidget(self._empty_label("Aucun fichier"))
            self._files_layout.addStretch()
            return

        files = sorted(os.listdir(cat_dir))
        if not files:
            self._files_layout.addWidget(self._empty_label("Aucun fichier"))
            self._files_layout.addStretch()
            return

        # Load metadata from DB
        meta = HRDatabase.get_document_meta(self._staff_id, self._current_category)

        p = theme_manager.palette
        s = theme_manager.font_size
        for fname in files:
            fpath = os.path.join(cat_dir, fname)
            fsize = os.path.getsize(fpath)
            size_str = f"{fsize:,} o" if fsize < 1024 else f"{fsize/1024:.1f} Ko"
            doc_meta = meta.get(fname, {})
            label = doc_meta.get("label", "") or ""
            description = doc_meta.get("description", "") or ""

            card = QFrame()
            card.setAttribute(Qt.WA_StyledBackground, True)
            card.setCursor(Qt.PointingHandCursor)
            card.setStyleSheet(f"""
                QFrame {{ background: {p.surface};
                border: 1px solid {p.outline_variant};
                border-radius: {ds.radius_sm}px; }}
                QFrame:hover {{ background: {p.surface_variant}; }}
            """)
            crd_layout = QVBoxLayout(card)
            crd_layout.setContentsMargins(ds.space_sm, ds.space_xs, ds.space_sm, ds.space_xs)
            crd_layout.setSpacing(ds.space_xxs)

            # Row 1: icon + label (or filename) + size + delete
            row1 = QHBoxLayout()
            row1.setSpacing(ds.space_sm)

            icon_lbl = QLabel()
            icon_lbl.setPixmap(md3_icon("description", color=p.text_soft, size=20).pixmap(20, 20))
            icon_lbl.setStyleSheet("border: none;")
            row1.addWidget(icon_lbl)

            display = label if label else fname
            name_lbl = QLabel(display)
            name_lbl.setStyleSheet(
                f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong}; border: none;")
            row1.addWidget(name_lbl, 1)

            size_lbl = QLabel(size_str)
            size_lbl.setStyleSheet(
                f"font-size: {s(11)}px; color: {p.text_soft}; border: none;")
            row1.addWidget(size_lbl)

            crd_layout.addLayout(row1)

            # Row 2: description or filename detail
            row2 = QHBoxLayout()
            row2.setSpacing(ds.space_sm)
            row2.setContentsMargins(ds.space_lg, 0, 0, 0)  # indent under icon

            if description:
                desc_lbl = QLabel(description)
                desc_lbl.setWordWrap(True)
                desc_lbl.setStyleSheet(
                    f"font-size: {s(11)}px; color: {p.text_soft}; border: none;")
                row2.addWidget(desc_lbl, 1)

            if label:
                fname_lbl = QLabel(fname)
                fname_lbl.setStyleSheet(
                    f"font-size: {s(10)}px; color: {p.text_soft}; border: none;")
                row2.addWidget(fname_lbl, 1)

            crd_layout.addLayout(row2)

            # Actions
            actions = QHBoxLayout()
            actions.setSpacing(ds.space_xxs)
            actions.addStretch()

            edit_btn = QPushButton()
            edit_btn.setIcon(md3_icon("edit", color=p.primary, size=14))
            edit_btn.setFixedSize(ds.icon_btn_size, ds.icon_btn_size)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setToolTip("Modifier le label / description")
            edit_btn.setStyleSheet("QPushButton { border: none; background: transparent; }")
            edit_btn.clicked.connect(
                lambda checked, fp=fpath, fn=fname, lb=label, ds_=description:
                self._on_edit_meta(fp, fn, lb, ds_))
            actions.addWidget(edit_btn)

            del_btn = QPushButton()
            del_btn.setIcon(md3_icon("delete", color=p.error, size=14))
            del_btn.setFixedSize(ds.icon_btn_size, ds.icon_btn_size)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setToolTip("Supprimer")
            del_btn.setStyleSheet("QPushButton { border: none; background: transparent; }")
            del_btn.clicked.connect(lambda checked, fp=fpath, fn=fname: self._on_delete(fp, fn))
            actions.addWidget(del_btn)

            crd_layout.addLayout(actions)

            self._files_layout.addWidget(card)

        self._files_layout.addStretch()

    def _empty_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {theme_manager.palette.text_soft}; "
            f"font-size: {theme_manager.font_size(12)}px; border: none;")
        return lbl

    @safe_slot("DocumentManager._on_upload")
    def _on_upload(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Ajouter des documents", "",
            "Tous (*.pdf *.png *.jpg *.jpeg *.doc *.docx *.xlsx *.txt)")
        if not paths:
            return
        cat_dir = os.path.join(self._doc_dir, self._current_category)
        os.makedirs(cat_dir, exist_ok=True)  # catégorie ajoutée après coup
        for src in paths:
            fname = os.path.basename(src)
            shutil.copy2(src, os.path.join(cat_dir, fname))
            # Prompt for label/description
            self._edit_meta_dialog(os.path.join(cat_dir, fname), fname, "", "")
        self.refresh()

    @safe_slot("DocumentManager._on_edit_meta")
    def _on_edit_meta(self, fpath: str, fname: str, label: str, description: str):
        self._edit_meta_dialog(fpath, fname, label, description)
        self.refresh()

    def _edit_meta_dialog(self, fpath: str, fname: str,
                          label: str, description: str):
        """Dialogue d'édition label + description (ThemedDialog, pattern Q7+Q8+Q19b)."""
        dlg = DocumentMetaDialog(fname, label, description, parent=self)
        if dlg.exec():
            new_label, new_desc = dlg.result()
            HRDatabase.save_document_meta(
                self._staff_id, self._current_category, fname, new_label, new_desc)

    @safe_slot("DocumentManager._on_delete")
    def _on_delete(self, fpath: str, fname: str):
        reply = QMessageBox.question(
            self, "Confirmation", f"Supprimer {fname} ?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                os.remove(fpath)
                HRDatabase.delete_document_meta(
                    self._staff_id, self._current_category, fname)
                self.refresh()
            except OSError:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                pass
