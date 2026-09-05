"""StaffFormDialog — formulaire enrichi multi-sections (ThemedDialog)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QCheckBox,
    QPushButton, QDateEdit, QComboBox, QFileDialog, QScrollArea, QWidget, QFrame,
)

from larccommon.database import db
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.icons import icon as md3_icon
from larccommon.safe_slot import safe_slot
from larccommon.widgets.themed_widget import ThemedDialog
from phibuilder.phi.scale import SpacingToken

from LarcRH.common.hr_database import HRDatabase

STAFF_ROLES = [
    ('type_DRH', 'DRH'),
    ('type_Comptable', 'Comptable'),
    ('type_ressources_Humaines', 'Ress. Humaines'),
    ('type_Bulletin_Releves', 'Bulletins / Relevés'),
]
TEACHADM_ROLES = [
    ('is_teacher', 'Enseignant'),
    ('is_coordonator', 'Coordinateur'),
    ('is_adm', 'Admin'),
]
CIVILITIES = ['M.', 'Mme', 'Mlle']
MARITAL_STATUSES = ['célibataire', 'marié(e)', 'divorcé(e)', 'veuf/veuve']
EMP_STATUSES = ['actif', 'suspendu', 'en_préavis', 'parti']
PROFICIENCIES = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
ID_TYPES = ['CNI', 'Passeport', 'Carte de séjour', 'Permis de conduire']


class StaffFormDialog(ThemedDialog):
    """Dialogue d'édition enrichi d'un membre du personnel."""

    def __init__(self, id_lo: int, id_hi: int,
                 staff_data: dict | None = None, parent=None,
                 scope: str | None = None):
        super().__init__(parent)
        self._id_lo = id_lo
        self._id_hi = id_hi
        self._staff_data = staff_data
        self._is_new = staff_data is None
        self._scope = scope  # "identity" | "degrees" | None (tout)
        self._is_staff = (staff_data.get("is_staff") if staff_data else id_lo >= 4001)
        self._new_id: int | None = None
        self._checkboxes: dict[str, QCheckBox] = {}
        self._photo_path: str | None = None
        self._degrees: list[dict] = []
        self._languages: list[dict] = []

        title = "Ajouter un employé" if self._is_new else "Modifier l'employé"
        if scope == "identity":
            title = "Modifier la fiche personnelle"
        elif scope == "degrees":
            title = "Modifier diplômes & langues"
        self.setWindowTitle(title)
        _w = ds.sidebar_width + ds.golden_width(ds.sidebar_width)  # 610
        self.setMinimumSize(_w, ds.sp(SpacingToken.XXXL) * 5 + ds.sp(SpacingToken.MD))
        self.setStyleSheet(f"background: {theme_manager.palette.surface};")
        self._setup_ui()
        if not self._is_new and staff_data:
            self._load_data()

    # ------------------------------------------------------------------
    # UI — structure
    # ------------------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_sm)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        sw = QWidget()
        sw.setAttribute(Qt.WA_StyledBackground, True)
        # PAS « transparent » : palette noire héritée (bug contraste 2026-08-16)
        sw.setStyleSheet(f"background: {theme_manager.palette.surface};")
        sl = QVBoxLayout(sw)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(ds.space_sm)

        if self._scope != "degrees":
            sl.addWidget(self._section_identity())
            sl.addWidget(self._section_contact())
            sl.addWidget(self._section_professional())
        if self._scope != "identity":
            sl.addWidget(self._section_degrees())
            sl.addWidget(self._section_languages())
        sl.addStretch()

        scroll.setWidget(sw)
        layout.addWidget(scroll, 1)
        layout.addLayout(self._buttons())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _section_card(self, title: str, icon_name: str) -> tuple[QWidget, QVBoxLayout]:
        p = theme_manager.palette
        card = QWidget()
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet(f"""
            QWidget {{
                background: {p.surface};
                border: 1px solid {p.outline_variant};
                border-radius: {ds.radius_sm}px;
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(ds.space_md, ds.space_sm, ds.space_md, ds.space_md)
        cl.setSpacing(ds.space_sm)

        # Header
        hdr = QHBoxLayout()
        try:
            icon_lbl = QLabel()
            icon_lbl.setPixmap(md3_icon(icon_name, color=p.primary, size=18).pixmap(18, 18))
            hdr.addWidget(icon_lbl)
        except (ValueError, RuntimeError):
            pass
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-weight: bold; font-size: {theme_manager.font_size(14)}px; color: {p.text_strong}; border: none;")
        hdr.addWidget(title_lbl, 1)
        cl.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {p.outline_variant}; border: none;")
        cl.addWidget(sep)

        return card, cl

    def _field_row(self, label: str, widget: QWidget, parent_layout) -> None:
        p = theme_manager.palette
        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-size: {theme_manager.font_size(11)}px; color: {p.text_soft}; border: none;")
        parent_layout.addWidget(lbl)
        parent_layout.addWidget(widget)

    def _make_field(self, placeholder: str = "") -> QLineEdit:
        f = QLineEdit()
        f.setPlaceholderText(placeholder)
        f.setFixedHeight(ds.field_height)
        f.setStyleSheet(ds.flat_input_qss())
        return f

    def _make_combo(self, items: list[str]) -> QComboBox:
        cb = QComboBox()
        cb.addItems(items)
        cb.setFixedHeight(ds.field_height)
        p = theme_manager.palette
        cb.setStyleSheet(f"""
            QComboBox {{
                background: transparent; border: 1px solid {p.outline};
                border-radius: {ds.radius_xs}px; padding: {ds.space_xs}px;
                color: {p.text_strong}; font-size: {theme_manager.font_size(13)}px;
            }}
            QComboBox:focus {{ border-color: {p.primary}; }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
        """)
        return cb

    # ------------------------------------------------------------------
    # Section 1 — Identité
    # ------------------------------------------------------------------
    def _section_identity(self):
        p = theme_manager.palette
        card, cl = self._section_card("Identité", "person")
        grid = QGridLayout()
        grid.setSpacing(ds.space_xs)

        self._f_civility = self._make_combo(CIVILITIES)
        self._field_row("Civilité", self._f_civility, grid)

        self._f_first = self._make_field("Prénom")
        self._field_row("Prénom *", self._f_first, grid)

        self._f_last = self._make_field("Nom")
        self._field_row("Nom *", self._f_last, grid)

        self._f_birth = QDateEdit()
        self._f_birth.setCalendarPopup(True)
        self._f_birth.setDate(QDate(1980, 1, 1))
        self._f_birth.setFixedHeight(ds.field_height)
        self._f_birth.setStyleSheet(ds.flat_input_qss())
        self._field_row("Date de naissance", self._f_birth, grid)

        self._f_nationality = self._make_field("Nationalité")
        self._field_row("Nationalité", self._f_nationality, grid)

        self._f_marital = self._make_combo(MARITAL_STATUSES)
        self._field_row("Situation familiale", self._f_marital, grid)

        self._f_children = self._make_field("Nombre")
        self._field_row("Enfants à charge", self._f_children, grid)

        self._f_blood = self._make_field("A+, A-, B+, B-, AB+, AB-, O+, O-")
        self._field_row("Groupe sanguin", self._f_blood, grid)

        # ID document
        self._f_id_type = self._make_combo(ID_TYPES)
        self._field_row("Type pièce identité", self._f_id_type, grid)

        self._f_id_number = self._make_field("N° document")
        self._field_row("N° pièce identité", self._f_id_number, grid)

        self._f_id_expiry = QDateEdit()
        self._f_id_expiry.setCalendarPopup(True)
        self._f_id_expiry.setDate(QDate.currentDate().addYears(5))
        self._f_id_expiry.setFixedHeight(ds.field_height)
        self._f_id_expiry.setStyleSheet(ds.flat_input_qss())
        self._field_row("Date expiration", self._f_id_expiry, grid)

        # Photo
        self._photo_btn = QPushButton("  Photo d'identité...")
        self._photo_btn.setCursor(Qt.PointingHandCursor)
        self._photo_btn.setFixedHeight(ds.field_height)
        self._photo_btn.setStyleSheet(f"""
            QPushButton {{ border: 1px dashed {p.outline}; border-radius: {ds.radius_xs}px;
            color: {p.text_soft}; font-size: {theme_manager.font_size(12)}px; background: transparent; }}
            QPushButton:hover {{ border-color: {p.primary}; }}
        """)
        self._photo_btn.clicked.connect(self._on_upload_photo)
        self._field_row("Photo d'identité", self._photo_btn, grid)

        cl.addLayout(grid)
        return card

    # ------------------------------------------------------------------
    # Section 2 — Contact
    # ------------------------------------------------------------------
    def _section_contact(self):
        card, cl = self._section_card("Contact", "location_on")
        grid = QGridLayout()
        grid.setSpacing(ds.space_xs)

        self._f_email = self._make_field("email@ecole.org")
        self._field_row("Email professionnel", self._f_email, grid)

        self._f_email_perso = self._make_field("email.perso@exemple.com")
        self._field_row("Email personnel", self._f_email_perso, grid)

        self._f_tel_home = self._make_field("Téléphone fixe")
        self._field_row("Téléphone fixe", self._f_tel_home, grid)

        self._f_tel_mobile = self._make_field("Téléphone portable")
        self._field_row("Téléphone portable", self._f_tel_mobile, grid)

        self._f_emergency_name = self._make_field("Nom du contact")
        self._field_row("Contact urgence", self._f_emergency_name, grid)

        self._f_emergency_phone = self._make_field("Téléphone urgence")
        self._field_row("Tél. urgence", self._f_emergency_phone, grid)

        cl.addLayout(grid)
        return card

    # ------------------------------------------------------------------
    # Section 3 — Professionnel
    # ------------------------------------------------------------------
    def _section_professional(self):
        card, cl = self._section_card("Professionnel", "work")
        grid = QGridLayout()
        grid.setSpacing(ds.space_xs)

        self._f_matricule = self._make_field("Matricule interne")
        self._field_row("Matricule", self._f_matricule, grid)

        pro_cats = HRDatabase.get_professional_categories()
        self._f_pro_cat = self._make_combo(pro_cats or ["cadre", "agent de maîtrise", "employé"])
        self._field_row("Catégorie professionnelle", self._f_pro_cat, grid)

        self._f_emp_status = self._make_combo(EMP_STATUSES)
        self._field_row("Statut", self._f_emp_status, grid)

        # Campus — loaded from DB
        p = theme_manager.palette
        combo_style = f"""
            QComboBox {{
                background: transparent; border: 1px solid {p.outline};
                border-radius: {ds.radius_xs}px; padding: {ds.space_xs}px;
                color: {p.text_strong}; font-size: {theme_manager.font_size(13)}px;
            }}
            QComboBox:focus {{ border-color: {p.primary}; }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
        """
        self._f_campus = QComboBox()
        self._f_campus.setFixedHeight(ds.field_height)
        self._f_campus.setStyleSheet(combo_style)
        self._load_campuses()
        self._field_row("Campus", self._f_campus, grid)

        # Supervisor
        self._f_supervisor = QComboBox()
        self._f_supervisor.setFixedHeight(ds.field_height)
        self._f_supervisor.setStyleSheet(combo_style)
        self._load_supervisors()
        self._field_row("Supérieur hiérarchique", self._f_supervisor, grid)

        self._f_hire = QDateEdit()
        self._f_hire.setCalendarPopup(True)
        self._f_hire.setDate(QDate.currentDate())
        self._f_hire.setFixedHeight(ds.field_height)
        self._f_hire.setStyleSheet(ds.flat_input_qss())
        self._field_row("Date d'embauche", self._f_hire, grid)

        self._f_cnss = self._make_field("N° sécurité sociale")
        self._field_row("N° CNSS", self._f_cnss, grid)

        self._f_tax = self._make_field("N° identification fiscale")
        self._field_row("N° fiscal", self._f_tax, grid)

        # Roles
        role_set = STAFF_ROLES if self._is_staff else TEACHADM_ROLES
        role_grid = QGridLayout()
        role_grid.setSpacing(ds.space_xs)
        p = theme_manager.palette
        for i, (key, label) in enumerate(role_set):
            cb = QCheckBox(label)
            cb.setStyleSheet(f"color: {p.text_strong}; font-size: {theme_manager.font_size(12)}px;")
            role_grid.addWidget(cb, i // 3, i % 3)
            self._checkboxes[key] = cb
        cl.addWidget(QLabel("Postes / Rôles :"))
        style_role_lbl = cl.itemAt(cl.count() - 1).widget()
        if style_role_lbl:
            style_role_lbl.setStyleSheet(f"font-weight: bold; color: {p.text_strong}; border: none;")
        cl.addLayout(role_grid)

        cl.addLayout(grid)
        return card

    # ------------------------------------------------------------------
    # Section 4 — Diplômes
    # ------------------------------------------------------------------
    def _section_degrees(self):
        card, cl = self._section_card("Diplômes", "school")
        self._degree_layout = QVBoxLayout()
        self._degree_layout.setSpacing(ds.space_xxs)
        cl.addLayout(self._degree_layout)

        add_btn = QPushButton("+ Ajouter un diplôme")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setFlat(True)
        p = theme_manager.palette
        add_btn.setStyleSheet(f"color: {p.primary}; font-size: {theme_manager.font_size(12)}px; border: none;")
        add_btn.clicked.connect(self._add_degree_row)
        cl.addWidget(add_btn)
        return card

    def _add_degree_row(self, data: dict | None = None):
        row = QHBoxLayout()
        row.setSpacing(ds.space_xs)
        f_type = self._make_field("Type (ex: Licence, Master)")
        if data:
            f_type.setText(data.get("degree_type", ""))
        f_inst = self._make_field("Établissement")
        if data:
            f_inst.setText(data.get("institution", ""))
        f_year = self._make_field("Année")
        if data and data.get("year_obtained"):
            f_year.setText(str(data["year_obtained"]))
        del_btn = QPushButton("×")
        del_btn.setFixedSize(ds.icon_btn_size, ds.field_height)
        del_btn.setCursor(Qt.PointingHandCursor)
        p = theme_manager.palette
        del_btn.setStyleSheet(f"color: {p.error}; border: none; font-weight: bold; font-size: {theme_manager.font_size(16)}px;")
        del_btn.clicked.connect(lambda checked: self._remove_degree_row(row))
        for w in (f_type, f_inst, f_year):
            row.addWidget(w)
        row.addWidget(del_btn)
        self._degree_layout.addLayout(row)

    def _remove_degree_row(self, row: QHBoxLayout):
        while row.count():
            item = row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._degree_layout.removeItem(row)

    # ------------------------------------------------------------------
    # Section 5 — Langues
    # ------------------------------------------------------------------
    def _section_languages(self):
        card, cl = self._section_card("Langues", "language")
        self._lang_layout = QVBoxLayout()
        self._lang_layout.setSpacing(ds.space_xxs)
        cl.addLayout(self._lang_layout)

        add_btn = QPushButton("+ Ajouter une langue")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setFlat(True)
        p = theme_manager.palette
        add_btn.setStyleSheet(f"color: {p.primary}; font-size: {theme_manager.font_size(12)}px; border: none;")
        add_btn.clicked.connect(self._add_language_row)
        cl.addWidget(add_btn)
        return card

    def _add_language_row(self, data: dict | None = None):
        row = QHBoxLayout()
        row.setSpacing(ds.space_xs)
        f_lang = self._make_field("Langue (ex: Anglais, Français)")
        if data:
            f_lang.setText(data.get("language", ""))
        f_level = self._make_combo(PROFICIENCIES)
        if data and data.get("proficiency"):
            idx = PROFICIENCIES.index(data["proficiency"]) if data["proficiency"] in PROFICIENCIES else 2
            f_level.setCurrentIndex(idx)
        del_btn = QPushButton("×")
        del_btn.setFixedSize(ds.icon_btn_size, ds.field_height)
        del_btn.setCursor(Qt.PointingHandCursor)
        p = theme_manager.palette
        del_btn.setStyleSheet(f"color: {p.error}; border: none; font-weight: bold; font-size: {theme_manager.font_size(16)}px;")
        del_btn.clicked.connect(lambda checked: self._remove_lang_row(row))
        for w in (f_lang, f_level):
            row.addWidget(w)
        row.addWidget(del_btn)
        self._lang_layout.addLayout(row)

    def _remove_lang_row(self, row: QHBoxLayout):
        while row.count():
            item = row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._lang_layout.removeItem(row)

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def _buttons(self):
        p = theme_manager.palette
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel = QPushButton("Annuler")
        cancel.setFixedHeight(ds.button_height)
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {p.text_strong};
            border: 1px solid {p.outline}; border-radius: {ds.radius_sm}px;
            padding: {ds.space_xs}px {ds.space_md}px; font-size: {theme_manager.font_size(13)}px; }}
            QPushButton:hover {{ background: {p.surface_variant}; }}
        """)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        save = QPushButton("Enregistrer")
        save.setFixedHeight(ds.button_height)
        save.setCursor(Qt.PointingHandCursor)
        save.setStyleSheet(f"""
            QPushButton {{ background: {p.primary}; color: white; border: none;
            border-radius: {ds.radius_sm}px; padding: {ds.space_xs}px {ds.space_md}px;
            font-size: {theme_manager.font_size(13)}px; font-weight: bold; }}
            QPushButton:hover {{ background: {p.primary}; }}
        """)
        save.clicked.connect(self._on_save)
        btn_row.addWidget(save)

        return btn_row

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def _load_campuses(self):
        self._f_campus.clear()
        self._f_campus.addItem("—", None)
        for c in HRDatabase.get_campuses():
            self._f_campus.addItem(c["label"], c["id"])

    def _load_supervisors(self):
        self._f_supervisor.clear()
        self._f_supervisor.addItem("—", None)
        for s in HRDatabase.get_available_supervisors():
            self._f_supervisor.addItem(s["full_name"], s["id"])

    def _load_data(self):
        d = self._staff_data or {}
        self._f_first.setText(d.get("first_name", ""))
        self._f_last.setText(d.get("last_name", ""))
        self._f_email.setText(d.get("email", ""))
        self._f_tel_home.setText(d.get("tel_maison", "") or "")
        self._f_tel_mobile.setText(d.get("tel_smartphone_1", "") or "")
        self._f_email_perso.setText(d.get("emailperso", "") or "")
        if d.get("date_of_birth"):
            self._f_birth.setDate(d["date_of_birth"])
        if d.get("civility") and d["civility"] in CIVILITIES:
            self._f_civility.setCurrentIndex(CIVILITIES.index(d["civility"]))
        if d.get("nationality"):
            self._f_nationality.setText(d["nationality"])
        if d.get("marital_status") and d["marital_status"] in MARITAL_STATUSES:
            self._f_marital.setCurrentIndex(MARITAL_STATUSES.index(d["marital_status"]))
        if d.get("children_count"):
            self._f_children.setText(str(d["children_count"]))
        if d.get("blood_type"):
            self._f_blood.setText(d["blood_type"])
        if d.get("id_document_type") and d["id_document_type"] in ID_TYPES:
            self._f_id_type.setCurrentIndex(ID_TYPES.index(d["id_document_type"]))
        if d.get("id_document_number"):
            self._f_id_number.setText(d["id_document_number"])
        if d.get("id_document_expiry"):
            self._f_id_expiry.setDate(d["id_document_expiry"])
        if d.get("emergency_contact_name"):
            self._f_emergency_name.setText(d["emergency_contact_name"])
        if d.get("emergency_contact_phone"):
            self._f_emergency_phone.setText(d["emergency_contact_phone"])
        if d.get("matricule"):
            self._f_matricule.setText(d["matricule"])
        if d.get("professional_category"):
            idx = self._f_pro_cat.findText(d["professional_category"])
            if idx >= 0:
                self._f_pro_cat.setCurrentIndex(idx)
        if d.get("emp_status") and d["emp_status"] in EMP_STATUSES:
            self._f_emp_status.setCurrentIndex(EMP_STATUSES.index(d["emp_status"]))
        if d.get("cnss_number"):
            self._f_cnss.setText(d["cnss_number"])
        if d.get("tax_id"):
            self._f_tax.setText(d["tax_id"])
        if d.get("hire_date"):
            self._f_hire.setDate(d["hire_date"])

        # Campus + Supervisor
        if d.get("fk_campus_id"):
            for i in range(self._f_campus.count()):
                if self._f_campus.itemData(i) == d["fk_campus_id"]:
                    self._f_campus.setCurrentIndex(i)
                    break
        if d.get("fk_supervisor_id"):
            for i in range(self._f_supervisor.count()):
                if self._f_supervisor.itemData(i) == d["fk_supervisor_id"]:
                    self._f_supervisor.setCurrentIndex(i)
                    break

        for key, cb in self._checkboxes.items():
            cb.setChecked(d.get(key, False))

        staff_id = d.get("id", 0)
        if staff_id:
            for deg in HRDatabase.get_degrees(staff_id):
                self._add_degree_row(deg)
            for lang in HRDatabase.get_languages(staff_id):
                self._add_language_row(lang)

    # ------------------------------------------------------------------
    # Photo upload
    # ------------------------------------------------------------------
    @safe_slot("StaffFormDialog._on_upload_photo")
    def _on_upload_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner une photo", "",
            "Images (*.png *.jpg *.jpeg)")
        if path:
            self._photo_path = path
            self._photo_btn.setText(f"  Photo: {path.split('/')[-1]}")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    def _show_error(self, message: str):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Erreur", message)

    def _show_success(self, message: str):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Succès", message)

    @safe_slot("StaffFormDialog._on_save")
    def _on_save(self):
        first = self._f_first.text().strip()
        last = self._f_last.text().strip()
        if not last or not first:
            self._show_error("Le nom et le prénom sont obligatoires.")
            return

        data = {
            "first_name": first,
            "last_name": last,
            "email": self._f_email.text().strip(),
            "tel_maison": self._f_tel_home.text().strip(),
            "tel_smartphone_1": self._f_tel_mobile.text().strip(),
            "emailperso": self._f_email_perso.text().strip(),
            "date_of_birth": self._f_birth.date().toPython(),
            "civility": self._f_civility.currentText(),
            "nationality": self._f_nationality.text().strip(),
            "marital_status": self._f_marital.currentText(),
            "children_count": int(self._f_children.text().strip()) if self._f_children.text().strip() else 0,
            "blood_type": self._f_blood.text().strip(),
            "id_document_type": self._f_id_type.currentText(),
            "id_document_number": self._f_id_number.text().strip(),
            "id_document_expiry": self._f_id_expiry.date().toPython(),
            "emergency_contact_name": self._f_emergency_name.text().strip(),
            "emergency_contact_phone": self._f_emergency_phone.text().strip(),
            "matricule": self._f_matricule.text().strip(),
            "professional_category": self._f_pro_cat.currentText(),
            "emp_status": self._f_emp_status.currentText(),
            "cnss_number": self._f_cnss.text().strip(),
            "tax_id": self._f_tax.text().strip(),
            "hire_date": self._f_hire.date().toPython(),
            "fk_campus_id": self._f_campus.currentData(),
            "fk_supervisor_id": self._f_supervisor.currentData(),
            "is_staff": self._is_staff,
        }

        for key, cb in self._checkboxes.items():
            data[key] = cb.isChecked()

        try:
            if self._is_new:
                new_id = HRDatabase.create_staff(self._id_lo, self._id_hi, data)
                if new_id is None:
                    self._show_error(
                        "Aucun emplacement libre trouvé dans la plage "
                        f"{self._id_lo}–{self._id_hi}.\n"
                        "Contactez un administrateur pour étendre la plage.")
                    return
                self._new_id = new_id
                data["id"] = new_id
                HRDatabase.save_staff(new_id, data)
            else:
                staff_id = self._staff_data["id"]
                HRDatabase.save_staff(staff_id, data)

            # Degrees & languages — only for existing staff
            staff_id = data.get("id", self._staff_data.get("id") if self._staff_data else self._new_id)
            if staff_id:
                if self._scope != "identity":
                    self._save_degrees(staff_id)
                    self._save_languages(staff_id)

            # Photo — sauvegarde dans LarcRH/photos/ (dossier prioritaire)
            if self._photo_path and staff_id:
                import shutil
                photo_dir = os.path.normpath(
                    os.path.join(os.path.dirname(__file__), "..", "..",
                                 "LarcRH", "photos"))
                os.makedirs(photo_dir, exist_ok=True)
                dest = os.path.join(photo_dir, f"{staff_id}.png")
                shutil.copy2(self._photo_path, dest)

            self.accept()

        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            self._show_error(
                "Une erreur est survenue lors de l'enregistrement.\n"
                "Vérifiez les logs pour plus de détails.")

    def _save_degrees(self, staff_id: int):
        for i in range(self._degree_layout.count()):
            item = self._degree_layout.itemAt(i)
            if not item:
                continue
            row = item.layout()
            if not row or row.count() < 3:
                continue
            f_type = row.itemAt(0).widget()
            f_inst = row.itemAt(1).widget()
            f_year = row.itemAt(2).widget()
            if isinstance(f_type, QLineEdit) and f_type.text().strip():
                HRDatabase.save_degree(staff_id, {
                    "degree_type": f_type.text().strip(),
                    "institution": f_inst.text().strip() if isinstance(f_inst, QLineEdit) else "",
                    "year_obtained": int(f_year.text().strip()) if isinstance(f_year, QLineEdit) and f_year.text().strip() else None,
                })

    def _save_languages(self, staff_id: int):
        for i in range(self._lang_layout.count()):
            item = self._lang_layout.itemAt(i)
            if not item:
                continue
            row = item.layout()
            if not row or row.count() < 2:
                continue
            f_lang = row.itemAt(0).widget()
            f_level = row.itemAt(1).widget()
            if isinstance(f_lang, QLineEdit) and f_lang.text().strip():
                HRDatabase.save_language(staff_id, {
                    "language": f_lang.text().strip(),
                    "proficiency": f_level.currentText() if isinstance(f_level, QComboBox) else "B1",
                })
