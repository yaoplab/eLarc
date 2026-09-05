"""StaffDetail — fiche détail employé, master-detail (Q16a).

Pattern: header sticky (Q9c) + sidebar 233px (K2) + QStackedWidget workspace (Q16a).
Toutes les catégories sont visibles dans la sidebar. Le workspace garde la même taille.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QStackedWidget, QLineEdit,
    QCheckBox,
)

from larccommon.database import db
from larccommon.design_system import ds
from PySide6.QtWidgets import QHeaderView
from larccommon.icons import icon as md3_icon
from larccommon.theme import theme_manager
from larccommon.session import session
from LarcRH.views.sections_flow import SectionsFlow
from larccommon.safe_slot import safe_slot
from larccommon.widgets.themed_widget import ThemedDialog
from phibuilder.phi.scale import SpacingToken

from LarcRH.common.hr_database import HRDatabase
from LarcRH.views.staff_grid import _make_avatar, _find_photo

class _CategoryButton(QPushButton):
    """Bouton de catégorie dans la sidebar — icône + libellé, checkable."""

    def __init__(self, key: str, label: str, icon_name: str, parent=None):
        super().__init__(parent)
        self._key = key
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(ds.field_height + ds.space_sm)

        p = theme_manager.palette
        s = theme_manager.font_size
        # K26 : gap icône↔texte natif Qt (8px = ds.space_xs) via text-align: left
        # ci-dessous — pas de hack d'espaces dans le libellé.
        icon = md3_icon(icon_name, color=p.text_strong,
                        size=theme_manager.image.icon_btn)
        self.setIcon(icon)
        self.setIconSize(QSize(theme_manager.image.icon_btn,
                               theme_manager.image.icon_btn))
        self.setText(label)
        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding: {ds.space_xs}px {ds.space_sm}px;
                border: none;
                border-radius: {ds.radius_sm}px;
                color: {p.text_strong};
                font-size: {s(13)}px;
                background: transparent;
            }}
            QPushButton:checked {{
                background: {p.primary_container};
                color: {p.text_strong};
                font-weight: bold;
            }}
            QPushButton:hover:!checked {{
                background: {p.surface_variant};
            }}
        """)

    @property
    def key(self) -> str:
        return self._key


class CategoryManageDialog(ThemedDialog):
    """Dialogue de gestion des catégories (ajout / suppression)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._categories = HRDatabase.get_detail_categories()
        self._deleted: set[str] = set()
        self._added: list[dict] = []

        self.setWindowTitle("Gérer les catégories")
        _w = ds.sidebar_width + ds.golden_width(ds.sidebar_width)
        self.setMinimumSize(ds.golden_width(ds.sidebar_width), ds.sp(SpacingToken.XXXL) * 2 + ds.space_xxl)
        self._setup_ui()

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        return f"""
            CategoryManageDialog {{ background: {p.surface}; }}
        """

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_sm)

        head = QLabel("Gérer les catégories")
        head.setStyleSheet(
            f"font-size: {s(16)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        layout.addWidget(head)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {p.outline_variant}; border: none;")
        layout.addWidget(sep)

        # ── Existing categories ──
        lbl = QLabel("Catégories existantes")
        lbl.setStyleSheet(
            f"font-size: {s(11)}px; color: {p.text_soft}; font-weight: bold; border: none;")
        layout.addWidget(lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setMaximumHeight(ds.sp(SpacingToken.XXXL) * 2)
        scroll_w = QWidget()
        scroll_w.setAttribute(Qt.WA_StyledBackground, True)
        # PAS « transparent » : palette noire héritée sinon (bug contraste 2026-08-16)
        scroll_w.setStyleSheet(f"background: {p.surface};")
        self._list_layout = QVBoxLayout(scroll_w)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(ds.space_xxs)
        scroll.setWidget(scroll_w)

        self._build_category_list()
        layout.addWidget(scroll)

        # ── Add form ──
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"color: {p.outline_variant}; border: none;")
        layout.addWidget(sep2)

        add_lbl = QLabel("Ajouter une catégorie")
        add_lbl.setStyleSheet(
            f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        layout.addWidget(add_lbl)

        grid = QGridLayout()
        grid.setSpacing(ds.space_sm)

        for col, (l, ph) in enumerate([
            ("Clé", "ex: trainings"),
            ("Label", "Formations"),
            ("Icône", "school"),
        ]):
            lbl_w = QLabel(l)
            lbl_w.setStyleSheet(
                f"font-size: {s(11)}px; color: {p.text_soft}; font-weight: bold; border: none;")
            grid.addWidget(lbl_w, 0, col)

        self._add_key = QLineEdit()
        self._add_key.setPlaceholderText("ex: trainings")
        self._add_key.setFixedHeight(ds.field_height)
        self._add_key.setStyleSheet(ds.flat_input_qss())
        grid.addWidget(self._add_key, 1, 0)

        self._add_label = QLineEdit()
        self._add_label.setPlaceholderText("Formations")
        self._add_label.setFixedHeight(ds.field_height)
        self._add_label.setStyleSheet(ds.flat_input_qss())
        grid.addWidget(self._add_label, 1, 1)

        self._add_icon = QLineEdit()
        self._add_icon.setPlaceholderText("school")
        self._add_icon.setFixedHeight(ds.field_height)
        self._add_icon.setStyleSheet(ds.flat_input_qss())
        grid.addWidget(self._add_icon, 1, 2)

        add_btn = QPushButton("+ Ajouter")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setFixedHeight(ds.field_height + ds.space_xs)
        add_btn.setStyleSheet(f"""
            QPushButton {{ background: {p.primary}; color: white; border: none;
            border-radius: {ds.radius_xs}px; padding: {ds.space_xxs}px {ds.space_sm}px;
            font-size: {s(12)}px; font-weight: bold; }}
            QPushButton:hover {{ background: {p.primary}; }}
        """)
        add_btn.clicked.connect(self._on_add)
        grid.addWidget(add_btn, 1, 3)

        layout.addLayout(grid)

        self._add_error = QLabel("")
        self._add_error.setStyleSheet(
            f"font-size: {s(11)}px; color: {p.error}; border: none;")
        self._add_error.hide()
        layout.addWidget(self._add_error)

        layout.addStretch()

        # ── Actions ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Fermer")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedHeight(ds.field_height + ds.space_xs)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: {p.primary}; color: white; border: none;
            border-radius: {ds.radius_sm}px; padding: {ds.space_xs}px {ds.space_md}px;
            font-size: {s(13)}px; font-weight: bold; }}
            QPushButton:hover {{ background: {p.primary}; }}
        """)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.setStyleSheet(self._STYLE)

    def _build_category_list(self):
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        p = theme_manager.palette
        s = theme_manager.font_size
        for cat in HRDatabase.get_detail_categories():
            if cat["key"] in self._deleted:
                continue

            row = QWidget()
            row.setStyleSheet("border: none;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(ds.space_xs)

            icon_lbl = QLabel()
            icon_lbl.setPixmap(md3_icon(cat["icon"], color=p.text_soft, size=16).pixmap(16, 16))
            icon_lbl.setStyleSheet("border: none;")
            rl.addWidget(icon_lbl)

            name = QLabel(f"{cat['label']}")
            name.setStyleSheet(
                f"font-size: {s(13)}px; color: {p.text_strong}; border: none;")
            rl.addWidget(name, 1)

            key_lbl = QLabel(cat["key"])
            key_lbl.setStyleSheet(
                f"font-size: {s(10)}px; color: {p.text_soft}; border: none;")
            rl.addWidget(key_lbl)

            del_btn = QPushButton()
            del_btn.setIcon(md3_icon("delete", color=p.error, size=16))
            del_btn.setFixedSize(ds.icon_btn_size, ds.icon_btn_size)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setToolTip(f"Supprimer {cat['label']}")
            del_btn.setStyleSheet("QPushButton { border: none; background: transparent; }")
            del_btn.clicked.connect(lambda checked, ck=cat["key"]: self._on_delete(ck))
            rl.addWidget(del_btn)

            self._list_layout.addWidget(row)

    @safe_slot("CategoryManageDialog._on_delete")
    def _on_delete(self, category_key: str):
        ok, msg = HRDatabase.delete_detail_category(category_key)
        if not ok:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Suppression impossible", msg)
        else:
            self._deleted.add(category_key)
            self._build_category_list()

    @safe_slot("CategoryManageDialog._on_add")
    def _on_add(self):
        key = self._add_key.text().strip().lower().replace(" ", "_")
        label = self._add_label.text().strip()
        icon = self._add_icon.text().strip() or "folder"

        if not key or not label:
            self._add_error.setText("La cle et le label sont obligatoires.")
            self._add_error.show()
            return

        self._add_error.hide()
        if HRDatabase.add_detail_category(key, label, icon):
            self._added.append({"key": key, "label": label, "icon": icon})
            self._add_key.clear()
            self._add_label.clear()
            self._add_icon.clear()
            self._build_category_list()


class StaffDetail(QWidget):
    """Fiche détail employé — sidebar gauche + workspace droit (Q16a)."""

    def __init__(self, staff_data: dict, on_back=None, parent=None):
        super().__init__(parent)
        self._staff = staff_data
        self._on_back = on_back
        self._full: dict | None = None
        self._value_labels: dict[str, QLabel] = {}
        self._cat_buttons: dict[str, _CategoryButton] = {}
        # Vérification du dossier (« Vérifié et Validé » — port Blado)
        self._check_boxes: dict[str, QCheckBox] = {}
        self._check_details: dict[str, QLabel] = {}
        self._check_progress: QLabel | None = None
        self._loading_checks = False

        ds.theme_changed.connect(self._restyle)
        self._setup_ui()
        self._load_full()

    # ── QSS ──

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        return f"""
            StaffDetail {{ background: {p.background}; color: {p.text_strong}; }}
            QWidget#sticky_header {{
                background: {p.surface};
                border-bottom: 1px solid {p.outline_variant};
            }}
            QWidget#category_sidebar {{
                background: {p.surface};
                border-right: 1px solid {p.outline_variant};
                border-radius: {ds.radius_sm}px;
            }}
            QWidget#workspace_page {{
                background: {p.background};
            }}
            QFrame#info_card {{
                background: {p.surface};
                border: 1px solid {p.outline_variant};
                border-radius: {ds.radius_sm}px;
            }}
            QFrame#check_card {{
                background: {p.primary_container};
                border: 1px solid {p.outline};
                border-radius: {ds.radius_sm}px;
            }}
        """

    @safe_slot("StaffDetail._restyle")
    def _restyle(self):
        try:
            self.setStyleSheet(self._STYLE)
            for page in self._workspace_pages:
                if page and hasattr(page, "viewport"):
                    try:
                        # PAS « transparent » : palette noire héritée (bug contraste)
                        page.viewport().setStyleSheet(
                            f"background: {theme_manager.palette.background};")
                        page_w = page.widget()
                        if page_w:
                            page_w.setStyleSheet(
                                f"background: {theme_manager.palette.background};")
                    except RuntimeError:
                        from larccommon.error_reporting import get_reporter
                        get_reporter().report_exception()
                        pass
            # J8 : le contenu chargé est stylé à la construction — le
            # REBÂTIR à chaque changement de thème, sinon les textes gardent
            # les couleurs de l'ancien thème (illisible en dark). On conserve
            # la catégorie courante. Le bandeau et la sidebar sont hors des
            # pages : les reconstruire aussi.
            _cur = self._workspace.currentIndex()
            self._reload_all()
            if 0 <= _cur < self._workspace.count():
                self._switch_category(_cur)
            _main = self.layout()
            if _main is not None and _main.count() > 0:
                _old_h = _main.itemAt(0).widget()
                if _old_h is not None:
                    _main.removeWidget(_old_h)
                    _old_h.deleteLater()
                _main.insertWidget(0, self._build_header())
            _content = _main.itemAt(1) if _main is not None else None
            if _content is not None and _content.layout() is not None                     and _content.layout().count() >= 2:
                _cl = _content.layout()
                _old_s = _cl.itemAt(0).widget()
                if _old_s is not None:
                    _cl.removeWidget(_old_s)
                    _old_s.deleteLater()
                self._sidebar_widget = self._build_sidebar()
                _cl.insertWidget(0, self._sidebar_widget)
        except RuntimeError:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass

    # ═══════════════════════════════════════════════════════
    # UI — Structure (Q16a)
    # ═══════════════════════════════════════════════════════

    def _setup_ui(self):
        self.setObjectName("StaffDetail")
        self.setStyleSheet(self._STYLE)

        self._categories = HRDatabase.get_detail_categories()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header sticky (Q9c + Q22) ──
        layout.addWidget(self._build_header())

        # ── Master-Detail (Q16a) ──
        content = QHBoxLayout()
        content.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        content.setSpacing(ds.space_md)

        # Sidebar gauche — 233px fixe (K2)
        self._sidebar_widget = self._build_sidebar()
        content.addWidget(self._sidebar_widget)

        # Workspace droit — QStackedWidget (stretch 1, ratio φ)
        self._workspace = QStackedWidget()
        self._workspace_pages: list[QScrollArea | None] = []

        for cat in self._categories:
            page = QScrollArea()
            page.setWidgetResizable(True)
            page.setFrameShape(QScrollArea.NoFrame)
            # PAS « transparent » : palette noire héritée (bug contraste 2026-08-16)
            page.viewport().setStyleSheet(
                f"background: {theme_manager.palette.background};")
            page_w = QWidget()
            page_w.setAttribute(Qt.WA_StyledBackground, True)
            page_w.setObjectName("workspace_page")
            page_w.setStyleSheet(f"background: {theme_manager.palette.background};")
            page.setWidget(page_w)
            key = cat["key"]
            setattr(self, f"_{key}_layout", QVBoxLayout(page_w))
            getattr(self, f"_{key}_layout").setContentsMargins(0, 0, 0, 0)
            getattr(self, f"_{key}_layout").setSpacing(ds.space_sm)
            self._workspace.addWidget(page)
            self._workspace_pages.append(page)

        content.addWidget(self._workspace, 1)
        layout.addLayout(content, 1)

    # ── Header (Q9c + Q22) ──

    def _build_header(self) -> QWidget:
        p = theme_manager.palette
        s = theme_manager.font_size
        header = QWidget()
        header.setObjectName("sticky_header")
        header.setFixedHeight(ds.header_height + ds.space_xl)

        hl = QHBoxLayout(header)
        hl.setContentsMargins(ds.space_md, ds.space_xs, ds.space_md, ds.space_xs)
        hl.setSpacing(ds.space_md)

        if self._on_back:
            back = QPushButton()
            back.setIcon(md3_icon("arrow_back", color=p.primary, size=20))
            back.setFlat(True)
            back.setCursor(Qt.PointingHandCursor)
            back.setToolTip("Retour")
            back.setStyleSheet("QPushButton { border: none; }")
            back.clicked.connect(self._on_back)
            hl.addWidget(back)

        # Photo Q22a
        photo_id = self._staff.get("id", 0)
        photo_path = _find_photo(photo_id)
        self._photo_lbl = QLabel()
        self._photo_lbl.setFixedSize(theme_manager.image.logo, theme_manager.image.logo)
        self._photo_lbl.setAlignment(Qt.AlignCenter)
        if photo_path:
            pix = QPixmap(photo_path).scaled(theme_manager.image.logo, theme_manager.image.logo,
                                              Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            pix = _make_avatar(self._staff.get("full_name", ""), theme_manager.image.logo)
        self._photo_lbl.setPixmap(pix)
        self._photo_lbl.setStyleSheet(
            f"border-radius: {ds.radius_sm}px; background: {p.primary_container}; border: none;")
        hl.addWidget(self._photo_lbl)

        identity = QVBoxLayout()
        identity.setSpacing(ds.space_xxs)

        self._name_lbl = QLabel(self._staff.get("full_name", "—"))
        self._name_lbl.setStyleSheet(
            f"font-size: {s(18)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        identity.addWidget(self._name_lbl)

        self._role_lbl = QLabel(self._build_roles_text())
        self._role_lbl.setStyleSheet(
            f"font-size: {s(13)}px; color: {p.text_soft}; border: none;")
        identity.addWidget(self._role_lbl)

        self._status_line = QLabel("")
        self._status_line.setStyleSheet(
            f"font-size: {s(11)}px; color: {p.primary}; border: none;")
        identity.addWidget(self._status_line)

        hl.addLayout(identity, 1)

        return header

    # ── Sidebar (K2) ──

    def _build_sidebar(self) -> QWidget:
        p = theme_manager.palette
        s = theme_manager.font_size

        sidebar = QWidget()
        sidebar.setObjectName("category_sidebar")
        sidebar.setAttribute(Qt.WA_StyledBackground, True)
        sidebar.setFixedWidth(ds.sidebar_width)

        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(ds.space_sm, ds.space_sm, ds.space_sm, ds.space_sm)
        sl.setSpacing(ds.space_xxs)

        title = QLabel("Catégories")
        title.setStyleSheet(
            f"font-size: {s(12)}px; font-weight: bold; color: {p.text_soft}; "
            f"border: none; padding: {ds.space_xxs}px {ds.space_xs}px;")
        sl.addWidget(title)

        for i, cat in enumerate(self._categories):
            btn = _CategoryButton(cat["key"], cat["label"], cat["icon"])
            btn.clicked.connect(lambda checked, idx=i: self._switch_category(idx))
            self._cat_buttons[cat["key"]] = btn
            sl.addWidget(btn)

        sl.addStretch()

        manage_btn = QPushButton("Gérer les catégories")
        manage_btn.setCursor(Qt.PointingHandCursor)
        manage_btn.setFixedHeight(ds.field_height)
        manage_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {p.text_soft};
            border: 1px solid {p.outline}; border-radius: {ds.radius_xs}px;
            padding: {ds.space_xxs}px {ds.space_sm}px;
            font-size: {s(11)}px; }}
            QPushButton:hover {{ background: {p.surface_variant}; color: {p.text_strong}; }}
        """)
        manage_btn.clicked.connect(self._on_manage_categories)
        sl.addWidget(manage_btn)

        return sidebar

    @safe_slot("StaffDetail._switch_category")
    def _switch_category(self, idx: int):
        for btn in self._cat_buttons.values():
            btn.setChecked(False)
        if 0 <= idx < len(self._categories):
            key = self._categories[idx]["key"]
            if key in self._cat_buttons:
                self._cat_buttons[key].setChecked(True)
        self._workspace.setCurrentIndex(idx)

    # ═══════════════════════════════════════════════════════
    # Data loading
    # ═══════════════════════════════════════════════════════

    def _load_full(self):
        staff_id = self._staff.get("id", 0)
        self._full = HRDatabase.get_staff_full(staff_id) or self._staff
        d = self._full

        self._status_line.setText(
            f"Statut : {d.get('emp_status', 'actif')}  |  "
            f"Matricule : {d.get('matricule', '—')}  |  "
            f"ID : {staff_id}")

        for cat in self._categories:
            key = cat["key"]
            loader = getattr(self, f"_load_{key}", None)
            if loader:
                loader()

        # Select first category
        self._switch_category(0)

    # ── Helpers ──

    def _field_cell(self, label: str, value) -> QVBoxLayout:
        """Pattern Q8 : label AU-DESSUS + valeur (la valeur domine visuellement)."""
        p = theme_manager.palette
        s = theme_manager.font_size
        cell = QVBoxLayout()
        cell.setSpacing(ds.space_xxs)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"font-size: {s(11)}px; color: {p.text_soft}; border: none;")
        cell.addWidget(lbl)
        val = str(value) if value is not None else "—"
        vl = QLabel(val)
        vl.setWordWrap(True)
        vl.setStyleSheet(
            f"font-size: {s(14)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        cell.addWidget(vl)
        return cell

    def _info_card(self, title: str, icon_name: str,
                    action_label: str = "", action_slot=None) -> tuple[QFrame, QVBoxLayout]:
        """Carte d'info avec header icône + titre + séparateur + bouton optionnel."""
        p = theme_manager.palette
        s = theme_manager.font_size
        card = QFrame()
        card.setObjectName("info_card")
        card.setAttribute(Qt.WA_StyledBackground, True)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(ds.space_md, ds.space_m3, ds.space_md, ds.space_md)
        cl.setSpacing(ds.space_sm)

        hdr = QHBoxLayout()
        hdr.setSpacing(ds.space_xs)
        ic = QLabel()
        ic.setPixmap(md3_icon(icon_name, color=p.primary, size=20).pixmap(20, 20))
        ic.setStyleSheet("border: none;")
        hdr.addWidget(ic)
        tl = QLabel(title)
        tl.setStyleSheet(
            f"font-size: {s(16)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        hdr.addWidget(tl)
        hdr.addStretch()

        if action_label and action_slot:
            btn = QPushButton(action_label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(ds.field_height + ds.space_xs)
            btn.setStyleSheet(f"""
                QPushButton {{ background: {p.primary}; color: white; border: none;
                border-radius: {ds.radius_xs}px; padding: {ds.space_xxs}px {ds.space_sm}px;
                font-size: {s(12)}px; font-weight: bold; }}
                QPushButton:hover {{ background: {p.primary}; }}
            """)
            btn.clicked.connect(action_slot)
            hdr.addWidget(btn)

        cl.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {p.outline_variant}; border: none;")
        cl.addWidget(sep)

        body = QVBoxLayout()
        body.setSpacing(ds.space_sm)
        cl.addLayout(body)
        return card, body

    def _section_action_btn(self, label: str, slot) -> QPushButton:
        p = theme_manager.palette
        s = theme_manager.font_size
        btn = QPushButton(label)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(ds.field_height + ds.space_xs)
        btn.setStyleSheet(f"""
            QPushButton {{ background: {p.primary}; color: white; border: none;
            border-radius: {ds.radius_xs}px; padding: {ds.space_xxs}px {ds.space_sm}px;
            font-size: {s(12)}px; font-weight: bold; }}
            QPushButton:hover {{ background: {p.primary}; }}
        """)
        btn.clicked.connect(slot)
        return btn

    def _empty_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {theme_manager.palette.text_soft}; "
            f"font-size: {theme_manager.font_size(12)}px; border: none;")
        return lbl

    def _add_stretch(self, layout: QVBoxLayout):
        layout.addStretch()

    # ── Page 0 : Fiche personnelle (Identité + Contact + Pro) ──

    def _load_personal(self):
        d = self._full or {}
        layout = self._personal_layout

        # --- Identité ---
        card1, body1 = self._info_card("Identité", "person",
                                       action_label="Modifier",
                                       action_slot=self._on_edit_identity)
        grid1 = QGridLayout()
        grid1.setSpacing(ds.space_sm)
        for i in range(3):
            grid1.setColumnStretch(i, 1)

        id_vals = [
            ("Nom", d.get("last_name")),
            ("Prénom", d.get("first_name")),
            ("Civilité", d.get("civility")),
            ("Nationalité", d.get("nationality")),
            ("Date de naissance", d.get("date_of_birth")),
            ("Situation familiale", d.get("marital_status")),
            ("Enfants à charge", d.get("children_count", 0)),
            ("Groupe sanguin", d.get("blood_type")),
            ("Pièce d'identité",
             f"{d.get('id_document_type','')} {d.get('id_document_number','')}".strip()),
            ("Expiration pièce ID", d.get("id_document_expiry")),
        ]
        for col, (lbl, val) in enumerate(id_vals):
            row, c = divmod(col, 3)
            grid1.addLayout(self._field_cell(lbl, val or "—"), row, c)
        body1.addLayout(grid1)

        # --- Contact ---
        card2, body2 = self._info_card("Contact", "mail")
        grid2 = QGridLayout()
        grid2.setSpacing(ds.space_sm)
        for i in range(2):
            grid2.setColumnStretch(i, 1)

        ct_vals = [
            ("Email professionnel", d.get("email")),
            ("Email personnel", d.get("emailperso")),
            ("Téléphone fixe", d.get("tel_maison")),
            ("Téléphone portable", d.get("tel_smartphone_1")),
            ("Contact d'urgence", d.get("emergency_contact_name")),
            ("Téléphone urgence", d.get("emergency_contact_phone")),
        ]
        for col, (lbl, val) in enumerate(ct_vals):
            row, c = divmod(col, 2)
            grid2.addLayout(self._field_cell(lbl, val or "—"), row, c)
        body2.addLayout(grid2)

        # --- Professionnel ---
        card3, body3 = self._info_card("Professionnel", "work")
        grid3 = QGridLayout()
        grid3.setSpacing(ds.space_sm)
        for i in range(3):
            grid3.setColumnStretch(i, 1)

        pro_vals = [
            ("Matricule", d.get("matricule")),
            ("Catégorie pro.", d.get("professional_category")),
            ("Statut", d.get("emp_status")),
            ("Date d'embauche", d.get("hire_date") or d.get("date_entree")),
            ("Date d'entrée école", d.get("date_entree")),
            ("N° CNSS", d.get("cnss_number")),
            ("N° fiscal", d.get("tax_id")),
        ]
        for col, (lbl, val) in enumerate(pro_vals):
            row, c = divmod(col, 3)
            grid3.addLayout(self._field_cell(lbl, val or "—"), row, c)
        body3.addLayout(grid3)

        # --- Vérification du dossier (checkboxes « Vérifié et Validé ») ---
        check_card = self._build_check_card()
        self._refresh_verification_checks()

        # Sections responsives (IE7) : côte à côte sur écran large,
        # empilées sur écran étroit — largeurs égales par ligne.
        layout.addWidget(SectionsFlow(
            [check_card, card1, card2, card3],
            min_width=ds.sidebar_width + ds.golden_width(ds.sidebar_width)))

        self._add_stretch(layout)

    # ── Vérification du dossier (port Blado) ──

    def _build_check_card(self) -> QFrame:
        """Carte « Vérification du dossier — Vérifié et Validé » : une
        checkbox par item indispensable, légende accolée, progression."""
        p = theme_manager.palette
        s = theme_manager.font_size
        card = QFrame()
        card.setObjectName("check_card")
        card.setAttribute(Qt.WA_StyledBackground, True)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        cl.setSpacing(ds.space_xs)

        title = QLabel("Vérification du dossier — Vérifié et Validé")
        title.setStyleSheet(
            f"font-size: {s(14)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        cl.addWidget(title)

        self._check_progress = QLabel("")
        self._check_progress.setStyleSheet(
            f"font-size: {s(12)}px; color: {p.text_strong}; border: none;")
        cl.addWidget(self._check_progress)

        for key, label in HRDatabase.DOSSIER_CHECK_ITEMS:
            row = QHBoxLayout()
            row.setSpacing(ds.space_xs)
            cb = QCheckBox(label)
            # Pas de QSS local : le rendu QSS ferait disparaître la case
            # native (contour invisible, 2026-08-14).
            cb.toggled.connect(lambda checked, k=key: self._on_check_toggled(k, checked))
            row.addWidget(cb)
            info = QLabel("")
            info.setStyleSheet(
                f"color: {p.text_strong}; font-size: {s(12)}px; border: none;")
            row.addWidget(info)
            row.addStretch()
            cl.addLayout(row)
            self._check_boxes[key] = cb
            self._check_details[key] = info
        cl.addStretch()
        return card

    def _refresh_verification_checks(self):
        staff_id = self._staff.get("id", 0)
        checks = HRDatabase.get_dossier_checks(staff_id)
        self._loading_checks = True
        try:
            for key, _label in HRDatabase.DOSSIER_CHECK_ITEMS:
                cb = self._check_boxes.get(key)
                if not cb:
                    continue
                c = checks.get(key, {})
                cb.setChecked(bool(c.get("validated")))
                if c.get("validated"):
                    when = ""
                    if c.get("validated_at"):
                        try:
                            when = c["validated_at"].strftime("%d/%m/%Y")
                        except Exception:
                            from larccommon.error_reporting import get_reporter
                            get_reporter().report_exception()
                            when = ""
                    self._check_details[key].setText(
                        f"Vérifié et Validé le {when} par {c.get('validated_by') or '—'}")
                else:
                    self._check_details[key].setText("Non vérifié")
        finally:
            self._loading_checks = False
        self._update_check_progress()

    def _update_check_progress(self):
        progress = HRDatabase.dossier_validation_progress(self._staff.get("id", 0))
        done, total = progress["validated"], progress["total"]
        if done >= total and total > 0:
            self._check_progress.setStyleSheet(
                f"font-size: {theme_manager.font_size(12)}px; font-weight: bold; "
                f"color: {theme_manager.palette.success}; border: none;")
            self._check_progress.setText(f"Dossier COMPLET — {done}/{total} items vérifiés ✓")
        else:
            self._check_progress.setStyleSheet(
                f"font-size: {theme_manager.font_size(12)}px; "
                f"color: {theme_manager.palette.text_strong}; border: none;")
            self._check_progress.setText(f"{done}/{total} items vérifiés — dossier incomplet")

    @safe_slot("StaffDetail._on_check_toggled")
    def _on_check_toggled(self, item_key: str, checked: bool):
        if self._loading_checks:
            return
        by = session.full_name or session.email or "—"
        HRDatabase.set_dossier_check(self._staff.get("id", 0), item_key, checked, by)
        info = self._check_details.get(item_key)
        if info is not None:
            if checked:
                row = HRDatabase.get_dossier_checks(
                    self._staff.get("id", 0)).get(item_key, {})
                when = ""
                if row.get("validated_at"):
                    try:
                        when = row["validated_at"].strftime("%d/%m/%Y")
                    except Exception:
                        from larccommon.error_reporting import get_reporter
                        get_reporter().report_exception()
                        when = ""
                info.setText(f"Vérifié et Validé le {when} par {by}")
            else:
                info.setText("Non vérifié")
        self._update_check_progress()

    # ── Page 1 : Diplômes & Langues ──

    def _load_degrees(self):
        layout = self._degrees_layout
        p = theme_manager.palette
        s = theme_manager.font_size

        card, body = self._info_card("Diplômes & Langues", "school",
                                     action_label="Modifier",
                                     action_slot=self._on_edit_degrees)

        cols = QHBoxLayout()
        cols.setSpacing(ds.space_md)

        # Diplômes
        deg_col = QVBoxLayout()
        deg_col.setSpacing(ds.space_xxs)
        deg_title = QLabel("Diplômes")
        deg_title.setStyleSheet(
            f"font-size: {s(13)}px; font-weight: bold; color: {p.text_soft}; border: none;")
        deg_col.addWidget(deg_title)

        degrees = HRDatabase.get_degrees(self._staff.get("id", 0))
        if not degrees:
            deg_col.addWidget(self._empty_label("Aucun diplôme"))
        else:
            for deg in degrees:
                text = f"{deg['degree_type']} — {deg.get('institution','')} ({deg.get('year_obtained','')})"
                item = QLabel(text)
                item.setWordWrap(True)
                item.setStyleSheet(
                    f"font-size: {s(12)}px; color: {p.text_strong}; border: none;")
                deg_col.addWidget(item)
        deg_col.addStretch()
        cols.addLayout(deg_col, 1)

        # Langues
        lang_col = QVBoxLayout()
        lang_col.setSpacing(ds.space_xxs)
        lang_title = QLabel("Langues")
        lang_title.setStyleSheet(
            f"font-size: {s(13)}px; font-weight: bold; color: {p.text_soft}; border: none;")
        lang_col.addWidget(lang_title)

        languages = HRDatabase.get_languages(self._staff.get("id", 0))
        if not languages:
            lang_col.addWidget(self._empty_label("Aucune langue"))
        else:
            for lang in languages:
                text = f"{lang['language']} — {lang.get('proficiency','')}"
                item = QLabel(text)
                item.setStyleSheet(
                    f"font-size: {s(12)}px; color: {p.text_strong}; border: none;")
                lang_col.addWidget(item)
        lang_col.addStretch()
        cols.addLayout(lang_col, 1)

        body.addLayout(cols)
        layout.addWidget(card)
        self._add_stretch(layout)

    # ── Page 4 : Contrats ──

    def _load_contracts(self):
        from LarcRH.views.contract_list import ContractList
        layout = self._contracts_layout

        hdr = QHBoxLayout()
        title = QLabel("Contrats")
        p = theme_manager.palette
        s = theme_manager.font_size
        title.setStyleSheet(
            f"font-size: {s(14)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(self._section_action_btn("+ Nouveau contrat", self._on_add_contract))
        layout.addLayout(hdr)

        self._contract_widget = ContractList(self._staff, parent=self)
        layout.addWidget(self._contract_widget, 1)

    @safe_slot("StaffDetail._on_add_contract")
    def _on_add_contract(self):
        from LarcRH.views.contract_form import ContractFormDialog
        dlg = ContractFormDialog(self._staff.get("id", 0), parent=self)
        if dlg.exec() and hasattr(self, "_contract_widget"):
            self._contract_widget.refresh()

    # ── Page 5 : Congés ──

    def _load_leave(self):
        from LarcRH.views.leave_balance import LeaveBalanceWidget, LeaveRequestHistory
        layout = self._leave_layout

        hdr = QHBoxLayout()
        title = QLabel("Congés")
        p = theme_manager.palette
        s = theme_manager.font_size
        title.setStyleSheet(
            f"font-size: {s(14)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(self._section_action_btn("+ Nouvelle demande", self._on_add_leave))
        layout.addLayout(hdr)

        self._leave_balance = LeaveBalanceWidget(self._staff, parent=self)
        layout.addWidget(self._leave_balance)

        self._leave_history = LeaveRequestHistory(self._staff, parent=self)
        self._leave_history.leave_validated.connect(
            lambda: self._leave_balance.refresh() if hasattr(self, "_leave_balance") else None)
        layout.addWidget(self._leave_history, 1)

    @safe_slot("StaffDetail._on_add_leave")
    def _on_add_leave(self):
        from LarcRH.views.leave_request import LeaveRequestDialog
        dlg = LeaveRequestDialog(self._staff.get("id", 0), parent=self)
        if dlg.exec():
            if hasattr(self, "_leave_balance"):
                self._leave_balance.refresh()
            if hasattr(self, "_leave_history"):
                self._leave_history.refresh()

    # ── Page 6 : Documents ──

    def _load_documents(self):
        from LarcRH.views.document_manager import DocumentManager
        layout = self._documents_layout

        self._doc_manager = DocumentManager(self._staff, parent=self)
        self._doc_manager.setMinimumHeight(ds.workspace_min_height * 3 + ds.space_xxl)
        layout.addWidget(self._doc_manager, 1)

    # ── Page 6 : Courriers ──

    def _load_letters(self):
        from LarcRH.views.letter_manager import LetterManager
        layout = self._letters_layout

        self._letter_manager = LetterManager(parent=self)
        self._letter_manager.set_staff(self._staff)
        self._letter_manager.setMinimumHeight(ds.workspace_min_height * 3 + ds.space_xxl)
        layout.addWidget(self._letter_manager, 1)

    # ── Page 7 : Événements ──

    def _load_events(self):
        if not db.is_server_connected:
            return
        """Page Evenements — 2 tableaux (absences + retards) avec edition inline."""
        layout = self._events_layout
        p = theme_manager.palette
        s = theme_manager.font_size

        conn = db.server_conn
        if not conn:
            layout.addWidget(self._empty_label("Base de donnees indisponible"))
            self._add_stretch(layout)
            return

        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT se.event_id, se.event_type, COALESCE(se.event_at, se.created_at) AS evt_at,
                       se.note,
                       COALESCE(u.last_name || ' ' || u.first_name, '—') AS created_by_name
                FROM staff_event se
                LEFT JOIN larcauth_aecuser u ON u.id = se.created_by
                WHERE se.staff_id = %s
                ORDER BY se.event_at DESC LIMIT 200
            """, (self._staff["id"],))
            all_rows = cur.fetchall()

            absences = [r for r in all_rows if r[1] and r[1].startswith("Absence")]
            retards  = [r for r in all_rows if r[1] and r[1].startswith("Retard")]

            if not all_rows:
                layout.addWidget(self._empty_label("Aucun evenement enregistre"))
                self._add_stretch(layout)
                return

            # ── ABSENCES ──
            abs_lbl = QLabel("Absences")
            abs_lbl.setStyleSheet(
                f"font-size: {s(13)}px; font-weight: bold; color: {p.error}; "
                f"border: none; padding-left: {ds.space_xs}px;")
            abs_table = self._build_event_table(absences, p.error)

            # ── RETARDS ──
            ret_lbl = QLabel("Retards")
            ret_lbl.setStyleSheet(
                f"font-size: {s(13)}px; font-weight: bold; color: {p.tertiary}; "
                f"border: none; padding-left: {ds.space_xs}px;")
            ret_table = self._build_event_table(retards, p.tertiary)

            # Sections responsives : Absences et Retards côte à côte sur
            # écran large, empilés sinon — remplissent la page côte à côte.
            def _section_with_label(lbl, tbl):
                w = QWidget()
                v = QVBoxLayout(w)
                v.setContentsMargins(0, 0, 0, 0)
                v.setSpacing(ds.space_xs)
                v.addWidget(lbl)
                v.addWidget(tbl, 1)
                return w
            layout.addWidget(SectionsFlow(
                [_section_with_label(abs_lbl, abs_table),
                 _section_with_label(ret_lbl, ret_table)],
                min_width=ds.sidebar_width + ds.golden_width(ds.sidebar_width),
                fill_vertical=True))

        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            layout.addWidget(self._empty_label("Erreur de chargement"))

        self._add_stretch(layout)

    def _build_event_table(self, rows, accent_color):
        from phibuilder.widgets import M3TableWidget
        from PySide6.QtWidgets import QTableWidgetItem, QPushButton
        from PySide6.QtCore import Qt as QtCore

        p = theme_manager.palette

        table = M3TableWidget()
        table.setEditTriggers(M3TableWidget.DoubleClicked | M3TableWidget.EditKeyPressed)
        table.setSelectionBehavior(M3TableWidget.SelectRows)
        table.verticalHeader().setDefaultSectionSize(ds.table_row_min)
        table.setStyleSheet(ds.table_qss())
        table.setColumnCount(5)
        table.set_headers(["Date", "Motif", "Note", "Créé par", ""])

        table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            evt_id   = row[0]
            evt_type = row[1] or ""
            evt_at   = row[2]
            note     = row[3] or ""
            by_name  = row[4] if len(row) > 4 else "—"

            motif = evt_type.split(" — ", 1)[-1] if " — " in evt_type else evt_type
            if evt_at:
                date_str = evt_at.strftime("%d/%m/%Y %H:%M") if hasattr(evt_at, 'strftime') else str(evt_at)[:16]
            else:
                date_str = ""

            # Date (non editable)
            date_item = QTableWidgetItem(date_str)
            date_item.setFlags(date_item.flags() & ~QtCore.ItemIsEditable)
            date_item.setData(QtCore.UserRole, evt_id)
            table.setItem(r_idx, 0, date_item)

            # Motif (editable)
            table.setItem(r_idx, 1, QTableWidgetItem(motif))

            # Note (editable)
            table.setItem(r_idx, 2, QTableWidgetItem(note))

            # Créé par (nom — audit trail, non editable)
            by_item = QTableWidgetItem(by_name)
            by_item.setFlags(by_item.flags() & ~QtCore.ItemIsEditable)
            table.setItem(r_idx, 3, by_item)

            # Save button
            save_btn = QPushButton()
            save_btn.setIcon(md3_icon("save", color=p.primary, size=14))
            save_btn.setFixedSize(ds.icon_btn_size, ds.icon_btn_size)
            save_btn.setCursor(QtCore.PointingHandCursor)
            save_btn.setToolTip("Enregistrer")
            save_btn.setStyleSheet(
                "QPushButton { border: none; background: transparent; } "
                "QPushButton:hover { background: %s; }" % p.surface_variant)
            save_btn.clicked.connect(
                lambda checked, ridx=r_idx, tid=evt_id, tbl=table:
                self._on_save_event(tid, tbl, ridx))
            table.setCellWidget(r_idx, 4, save_btn)

        h = table.horizontalHeader()
        # IE8 : seule la Date s'étire ; les autres au contenu
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setStretchLastSection(False)
        h.resizeSection(1, ds.sp(SpacingToken.HUGE) - ds.sp(SpacingToken.MD))
        h.resizeSection(2, ds.sp(SpacingToken.XXXL) + ds.sp(SpacingToken.SM))
        table.setColumnWidth(3, ds.field_height + ds.space_xs)
        table.setSortingEnabled(True)  # IE8d : tri par clic

        n = max(len(rows), 2)
        table.setMinimumHeight(ds.table_row_min * n)
        return table

    @safe_slot("StaffDetail._on_save_event")
    def _on_save_event(self, event_id: int, table, row_idx: int):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return
        cur = conn.cursor()
        cur.execute("SELECT event_type FROM staff_event WHERE event_id = %s", (event_id,))
        r = cur.fetchone()
        if not r:
            return
        old_type = r[0] or ""
        prefix = old_type.split(" — ")[0] if " — " in old_type else old_type
        motif = table.item(row_idx, 1).text().strip()
        note  = table.item(row_idx, 2).text().strip()
        new_type = f"{prefix} — {motif}" if motif else prefix
        cur.execute(
            "UPDATE staff_event SET event_type=%s, note=%s WHERE event_id=%s",
            (new_type, note or None, event_id))
        conn.commit()
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Modification", "Evenement mis a jour.")

    # ── Rôles ──

    def _build_roles_text(self) -> str:
        d = self._staff
        if d.get("is_staff"):
            roles = []
            for k, lbl in [("type_DRH", "DRH"), ("type_Comptable", "Comptable"),
                           ("type_ressources_Humaines", "RH"), ("type_Bulletin_Releves", "Bull")]:
                if d.get(k):
                    roles.append(lbl)
            return " · ".join(roles) if roles else "Staff non enseignant"
        roles = []
        if d.get("is_teacher"):
            roles.append("Enseignant")
        if d.get("is_coordonator"):
            roles.append("Coordinateur")
        if d.get("is_adm"):
            roles.append("Administrateur")
        return " · ".join(roles) if roles else "Rôle non défini"

    # ── Edit (scoped) ──

    def _edit_staff(self, scope: str | None):
        if not self._full:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Données non disponibles",
                "Les données de l'employé n'ont pas pu être chargées.\n"
                "Vérifiez la connexion à la base de données.")
            return

        from LarcRH.views.staff_form import StaffFormDialog
        staff_id = self._staff.get("id", 0)
        cat_lo = (staff_id // 1000) * 1000 + 1
        cat_hi = ((staff_id // 1000) + 1) * 1000
        dlg = StaffFormDialog(cat_lo, cat_hi, staff_data=self._full, parent=self,
                              scope=scope)
        if dlg.exec():
            self._reload_all()

    @safe_slot("StaffDetail._on_edit_identity")
    def _on_edit_identity(self):
        self._edit_staff("identity")

    @safe_slot("StaffDetail._on_edit_degrees")
    def _on_edit_degrees(self):
        self._edit_staff("degrees")

    @safe_slot("StaffDetail._on_manage_categories")
    def _on_manage_categories(self):
        dlg = CategoryManageDialog(parent=self)
        if dlg.exec():
            self._rebuild_from_db()

    def _rebuild_from_db(self):
        """Reconstruit completement le sidebar et les pages workspace depuis la DB."""
        self._categories = HRDatabase.get_detail_categories()

        # Reconstruire sidebar : remplacer le widget
        main_layout = self.layout()
        content_layout = main_layout.itemAt(1)  # layout contenant sidebar + workspace
        if content_layout:
            content = content_layout.layout()
            if content and content.count() >= 2:
                # Retirer l'ancien sidebar
                old_sidebar = content.itemAt(0).widget()
                if old_sidebar:
                    old_sidebar.deleteLater()
                content.takeAt(0)
                # Recreer
                self._sidebar_widget = self._build_sidebar()
                content.insertWidget(0, self._sidebar_widget)

        # Recreer les pages workspace
        while self._workspace.count():
            w = self._workspace.widget(0)
            self._workspace.removeWidget(w)
            if w:
                w.deleteLater()
        self._workspace_pages.clear()

        for cat in self._categories:
            page = QScrollArea()
            page.setWidgetResizable(True)
            page.setFrameShape(QScrollArea.NoFrame)
            # PAS « transparent » : palette noire héritée (bug contraste 2026-08-16)
            page.viewport().setStyleSheet(
                f"background: {theme_manager.palette.background};")
            page_w = QWidget()
            page_w.setAttribute(Qt.WA_StyledBackground, True)
            page_w.setObjectName("workspace_page")
            page_w.setStyleSheet(f"background: {theme_manager.palette.background};")
            page.setWidget(page_w)
            key = cat["key"]
            setattr(self, f"_{key}_layout", QVBoxLayout(page_w))
            getattr(self, f"_{key}_layout").setContentsMargins(0, 0, 0, 0)
            getattr(self, f"_{key}_layout").setSpacing(ds.space_sm)
            self._workspace.addWidget(page)
            self._workspace_pages.append(page)

        self._load_full()

    def _reload_all(self):
        self._full = None
        for cat in self._categories:
            key = cat["key"]
            layout = getattr(self, f"_{key}_layout")
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    while item.layout().count():
                        si = item.layout().takeAt(0)
                        if si.widget():
                            si.widget().deleteLater()
        self._load_full()
