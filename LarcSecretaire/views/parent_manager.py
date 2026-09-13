"""
Gestion des parents / tuteurs.

Fonctionnalités :
  - Liste des parents avec recherche
  - Détail du parent sélectionné (identité, adresse, élèves liés)
  - Création / édition d'un parent (aecuser + larcauth_parent + foyer)
  - Lien / dé lien élève ↔ parent
  - Partage d'adresse (foyer)

Architecture :
  ParentManager      : widget principal (liste + détails en cartes M3)
  ParentEditDialog   : dialogue de création/édition d'un parent
"""

from larccommon.design_system import ds
from larccommon.widgets.themed_widget import ThemedDialog
from larccommon.icons import icon as md3_icon
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from LarcSecretaire.common.audit import audit
from LarcSecretaire.common.database import db
from LarcSecretaire.common.logger import log
from LarcSecretaire.common.session import session
from LarcSecretaire.common.theme import theme_manager
from phibuilder.phi.scale import SpacingToken
from phibuilder.widgets import (
    M3Button,
    M3Card,
    M3ComboBox,
    M3DialogButtonBox,
    M3Frame,
    M3Label,
    M3ScrollArea,
    M3TableWidget,
    M3TextField,
)
from phibuilder.widgets.button import ButtonVariant
from phibuilder.widgets.card import CardVariant
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


# ── Avatar initiales (couleur stable basée sur le nom) ──

def _make_avatar(last_name: str, first_name: str, size: int = 80) -> QPixmap:
    initials = (last_name[:1] + first_name[:1]).upper() or "?"
    p = theme_manager.palette
    roles = ["primary", "secondary", "tertiary", "error"]
    seed = sum(ord(c) for c in last_name + first_name)
    bg_role = roles[seed % len(roles)]
    bg = getattr(p, bg_role)
    fg = getattr(p, "on_" + bg_role)
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(bg))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)
    painter.setPen(QColor(fg))
    f = painter.font()
    f.setPixelSize(size // 3)
    f.setBold(True)
    painter.setFont(f)
    painter.drawText(px.rect(), Qt.AlignCenter, initials)
    painter.end()
    return px


# ──────────────────────────────────────────────
#   ParentManager — widget principal
# ──────────────────────────────────────────────


class ParentManager(QWidget):
    def __init__(self):
        super().__init__()
        self._parents: list[dict] = []
        self._students: list[dict] = []
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_md)

        # ── Titre ──
        title = M3Label(_("parent.title"), style="title_medium")
        layout.addWidget(title)

        # ── Barre de recherche + Ajouter ──
        search_row = QHBoxLayout()
        search_row.setSpacing(ds.space_sm)
        self._search_input = M3TextField(placeholder=_("parent.search_placeholder"))
        self._search_input.setFixedHeight(ds.field_height)
        self._search_input.setStyleSheet(ds.flat_input_qss())
        self._search_input.textChanged.connect(self._filter_parents)
        search_row.addWidget(self._search_input, 1)

        self._add_btn = M3Button("+ " + _("parent.add_button"), variant=ButtonVariant.FILLED)
        self._add_btn.setMinimumHeight(ds.field_height + ds.space_xs)
        self._add_btn.clicked.connect(self._on_add_parent)
        search_row.addWidget(self._add_btn)
        layout.addLayout(search_row)

        # ── Contenu : liste (gauche) + détail (droite) ──
        content = QHBoxLayout()
        content.setSpacing(ds.space_md)

        # ● Gauche : liste des parents
        left_card, left_cl = self._section_card(_("parent.list_title"), "person")
        self._parent_table = M3TableWidget()
        self._parent_table.set_headers([
            _("parent.table_headers"), _("parent.table_headers_email"),
            _("parent.table_headers_phone"), _("parent.table_headers_city"),
            _("parent.table_headers_id"),
        ])
        self._parent_table.setColumnHidden(4, True)
        self._parent_table.horizontalHeader().setStretchLastSection(True)
        self._parent_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._parent_table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._parent_table.setShowGrid(True)
        self._parent_table.setAlternatingRowColors(False)
        hh = self._parent_table.horizontalHeader()
        hh.setFixedHeight(ds.field_height)
        self._parent_table.verticalHeader().setDefaultSectionSize(ds.table_row_min)
        self._parent_table.setStyleSheet(ds.table_qss())
        self._parent_table.viewport().setCursor(Qt.PointingHandCursor)
        self._parent_table.itemSelectionChanged.connect(self._on_parent_selected)
        left_cl.addWidget(self._parent_table)
        content.addWidget(left_card, 3)

        # ● Droite : détail du parent sélectionné
        self._detail_card, self._detail_cl = self._section_card(
            _("parent.select_prompt"), "info")
        self._detail_body = QVBoxLayout()
        self._detail_body.setSpacing(ds.space_md)
        self._detail_cl.addLayout(self._detail_body)
        self._detail_card.hide()
        content.addWidget(self._detail_card, 2)

        layout.addLayout(content, 1)
        ds.theme_changed.connect(self._restyle)

    # ── Helpers de carte ──

    def _section_card(self, title: str, icon_name: str):
        card = M3Card(theme=theme_manager.phi_theme, variant=CardVariant.ELEVATED)
        card.setStyleSheet(
            f"M3Card {{ background: {ds.p.surface}; "
            f"border: 1px solid {ds.p.outline_variant}; "
            f"border-radius: {ds.radius_md}px; }}")
        cl = card.content_layout()
        cl.setSpacing(ds.space_sm)
        cl.setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
        hdr = QHBoxLayout()
        hdr.setSpacing(ds.space_xs)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(md3_icon(icon_name, color=ds.p.primary, size=20).pixmap(20, 20))
        hdr.addWidget(icon_lbl)
        title_lbl = M3Label(title, style="title_medium")
        title_lbl.setStyleSheet(f"color: {ds.p.text_strong}; font-weight: bold;")
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        cl.addLayout(hdr)
        sep = M3Frame()
        sep.setAttribute(Qt.WA_StyledBackground, True)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {ds.p.outline_variant};")
        cl.addWidget(sep)
        return card, cl

    @safe_slot("ParentManager._restyle")
    def _restyle(self):
        # Cartes
        card_style = (f"M3Card {{ background: {ds.p.surface}; "
                      f"border: 1px solid {ds.p.outline_variant}; "
                      f"border-radius: {ds.radius_md}px; }}")
        self._parent_table.setStyleSheet(ds.table_qss())
        if hasattr(self, "_student_table") and self._student_table:
            self._student_table.setStyleSheet(ds.table_qss())
        if hasattr(self, "_linked_title") and self._linked_title:
            self._linked_title.setStyleSheet(f"color: {ds.p.text_strong}; font-weight: bold;")
        if hasattr(self, "_share_status") and self._share_status:
            self._share_status.setStyleSheet(f"color: {ds.p.text_disabled};")
        self._search_input.setStyleSheet(ds.flat_input_qss())

    # ── Données ──

    def _load_data(self):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT aec.id, aec.last_name, aec.first_name, aec.email,
                       COALESCE(aec.tel_smartphone_1, aec.tel_maison, '') AS tel,
                       par.nature, foyer.city, foyer.address_line1
                FROM larcauth_aecuser aec
                JOIN larcauth_parent par ON par.aecuser_ptr_id = aec.id
                LEFT JOIN foyer ON foyer.id = aec.fk_foyer_id
                WHERE aec.type_parentutor = TRUE AND aec.is_active = TRUE
                  AND par.enabled = TRUE
                ORDER BY aec.last_name, aec.first_name
            """)
            self._parents = [
                {"id": r[0], "last_name": r[1], "first_name": r[2],
                 "email": r[3], "tel": r[4], "nature": r[5],
                 "city": r[6] or "", "address": r[7] or ""}
                for r in cur.fetchall()
            ]
            cur.execute("""
                SELECT s.aecuser_ptr_id, aec.last_name, aec.first_name,
                       c.label AS classroom
                FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program pr ON pr.id = l.fk_program_id
                WHERE s.enabled = TRUE AND pr.sigle IN ('PEI','MYP','DPEn','DPFr')
                ORDER BY aec.last_name, aec.first_name
            """)
            self._students = [
                {"id": r[0], "last_name": r[1], "first_name": r[2],
                 "classroom": r[3]} for r in cur.fetchall()
            ]
            self._populate_parents()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"ParentManager._load_data: {e}")

    def _populate_parents(self, filter_text: str = ""):
        self._parent_table.setRowCount(0)
        ft = filter_text.lower()
        for p in self._parents:
            if ft and ft not in p["last_name"].lower() and ft not in p["first_name"].lower() and ft not in p["email"].lower():
                continue
            row = self._parent_table.rowCount()
            self._parent_table.insertRow(row)
            self._parent_table.setItem(row, 0, QTableWidgetItem(f"{p['last_name']} {p['first_name']}"))
            self._parent_table.setItem(row, 1, QTableWidgetItem(p["email"]))
            self._parent_table.setItem(row, 2, QTableWidgetItem(p["tel"]))
            self._parent_table.setItem(row, 3, QTableWidgetItem(p.get("city", "")))
            self._parent_table.setItem(row, 4, QTableWidgetItem(str(p["id"])))
        self._parent_table.resizeColumnsToContents()

    @safe_slot("ParentManager.filter_parents")
    def _filter_parents(self, text: str):
        self._populate_parents(text)

    # ── Sélection d'un parent → détail à droite ──

    @safe_slot("ParentManager.on_parent_selected")
    def _on_parent_selected(self):
        if not db.is_server_connected:
            return
        rows = self._parent_table.selectedItems()
        if not rows:
            self._detail_card.hide()
            return
        parent_id = int(self._parent_table.item(rows[0].row(), 4).text())
        parent = next((p for p in self._parents if p["id"] == parent_id), None)
        if not parent:
            return

        # Charger les infos foyer
        conn = db.server_conn
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT f.address_line1, f.address_line2, f.postal_code,
                           f.city, f.country, aec.fk_foyer_id
                    FROM larcauth_aecuser aec
                    LEFT JOIN foyer f ON f.id = aec.fk_foyer_id
                    WHERE aec.id = %s
                """, (parent_id,))
                r = cur.fetchone()
                if r:
                    parent["address"] = r[0] or ""
                    parent["address2"] = r[1] or ""
                    parent["postal_code"] = r[2] or ""
                    parent["city"] = r[3] or ""
                    parent["country"] = r[4] or "France"
                    parent["fk_foyer_id"] = r[5]
            except Exception as e:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                log(f"ParentManager._on_parent_selected: {e}")

        self._build_detail(parent)
        self._load_links(parent_id)
        self._populate_student_combo(parent_id)
        self._detail_card.show()

    def _build_detail(self, parent: dict):
        """Construit le panneau de detail du parent. La section liens est preservee."""
        p = ds.p

        # Vider uniquement le header, pas les liens
        if hasattr(self, "_detail_header_widget") and self._detail_header_widget:
            hl = self._detail_header_widget.layout()
            if hl:
                self._clear_layout(hl)
        else:
            self._detail_header_widget = QWidget()
            self._detail_body.addWidget(self._detail_header_widget)

        hlayout = QVBoxLayout(self._detail_header_widget)
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.setSpacing(ds.space_sm)

        # ── Avatar + Nom ──
        avatar_row = QHBoxLayout()
        avatar_row.setSpacing(ds.space_md)
        avatar_lbl = QLabel()
        avatar_lbl.setPixmap(_make_avatar(parent["last_name"], parent["first_name"], ds.icon_md * 2))
        avatar_lbl.setFixedSize(ds.icon_md * 2, ds.icon_md * 2)
        avatar_row.addWidget(avatar_lbl)

        name_col = QVBoxLayout()
        name_col.setSpacing(ds.space_xxs)
        name = M3Label(f"{parent['first_name']} {parent['last_name']}", style="title_medium")
        name.setStyleSheet(f"font-weight: bold; color: {p.text_strong};")
        name_col.addWidget(name)
        nature_lbl = M3Label(parent.get("nature", ""), style="body_medium")
        nature_lbl.setStyleSheet(f"color: {p.primary}; font-weight: bold;")
        name_col.addWidget(nature_lbl)
        avatar_row.addLayout(name_col, 1)
        hlayout.addLayout(avatar_row)

        # ── Contact ──
        email = parent.get("email", "")
        tel = parent.get("tel", "")
        if email or tel:
            contact_row = QHBoxLayout()
            contact_row.setSpacing(ds.space_md)
            if email:
                em = M3Label(email, style="body_small")
                em.setStyleSheet(f"color: {p.text_strong};")
                contact_row.addWidget(em)
            if tel:
                ph = M3Label(tel, style="body_small")
                ph.setStyleSheet(f"color: {p.text_strong};")
                contact_row.addWidget(ph)
            contact_row.addStretch()
            hlayout.addLayout(contact_row)

        # ── Séparateur ──
        sep = M3Frame()
        sep.setAttribute(Qt.WA_StyledBackground, True)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {p.outline_variant};")
        hlayout.addWidget(sep)

        # ── Adresse ──
        addr_parts = []
        if parent.get("address"):
            addr_parts.append(parent["address"])
        if parent.get("address2"):
            addr_parts.append(parent["address2"])
        cp_city = f"{parent.get('postal_code', '')} {parent.get('city', '')}".strip()
        if cp_city:
            addr_parts.append(cp_city)
        if parent.get("country", "France") != "France":
            addr_parts.append(parent["country"])

        addr_title = M3Label(_("parent.address_group"), style="label_small")
        addr_title.setStyleSheet(f"color: {p.text_strong}; font-weight: bold;")
        hlayout.addWidget(addr_title)

        if addr_parts:
            addr_text = M3Label("\n".join(addr_parts), style="body_medium")
            addr_text.setStyleSheet(f"color: {p.text_strong};")
            addr_text.setWordWrap(True)
            hlayout.addWidget(addr_text)

            foyer_btn_row = QHBoxLayout()
            foyer_btn_row.setSpacing(ds.space_sm)
            edit_f_btn = M3Button(_("parent.edit_address"), variant=ButtonVariant.TONAL)
            edit_f_btn.clicked.connect(self._on_edit_foyer)
            foyer_btn_row.addWidget(edit_f_btn)
            share_btn = M3Button(_("parent.share_address"), variant=ButtonVariant.OUTLINED)
            share_btn.clicked.connect(self._on_share_foyer)
            foyer_btn_row.addWidget(share_btn)
            foyer_btn_row.addStretch()
            hlayout.addLayout(foyer_btn_row)
        else:
            no_addr = M3Label(_("parent.no_address"), style="body_small")
            no_addr.setStyleSheet(f"color: {p.text_disabled}; font-style: italic;")
            hlayout.addWidget(no_addr)

        # ── Statut partage ──
        self._share_status = M3Label("", style="body_small")
        self._share_status.setWordWrap(True)
        self._share_status.setStyleSheet(f"color: {p.text_disabled};")
        self._share_status.hide()
        hlayout.addWidget(self._share_status)

        # ── Fin header ──

        # ── Lier / Délier (persistant, creé une seule fois) ──
        # Ces widgets survivent aux appels de _build_detail
        self._links_section = QWidget()
        ls_layout = QVBoxLayout(self._links_section)
        ls_layout.setContentsMargins(0, 0, 0, 0)
        ls_layout.setSpacing(ds.space_sm)

        self._linked_title = M3Label(_("parent.linked_students"), style="label_small")
        self._linked_title.setStyleSheet(f"color: {p.text_strong}; font-weight: bold;")
        ls_layout.addWidget(self._linked_title)

        self._student_table = M3TableWidget()
        self._student_table.set_headers([
            _("parent.linked_students"), _("parent.linked_students_class"),
            _("parent.linked_students_nature"),
        ])
        self._student_table.horizontalHeader().setStretchLastSection(True)
        self._student_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._student_table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._student_table.setShowGrid(True)
        self._student_table.setAlternatingRowColors(False)
        self._student_table.horizontalHeader().setFixedHeight(ds.field_height)
        self._student_table.verticalHeader().setDefaultSectionSize(ds.table_row_min)
        self._student_table.setMaximumHeight(ds.space_xxxl)
        self._student_table.setStyleSheet(ds.table_qss())
        ls_layout.addWidget(self._student_table)

        link_row = QHBoxLayout()
        link_row.setSpacing(ds.space_sm)
        self._link_student_combo = M3ComboBox()
        self._link_student_combo.setFixedHeight(ds.field_height)
        link_row.addWidget(self._link_student_combo, 1)
        self._nature_combo = M3ComboBox([""] + _("parent.nature_items").split(","))
        self._nature_combo.setFixedHeight(ds.field_height)
        link_row.addWidget(self._nature_combo)
        self._link_btn = M3Button(_("parent.link_button"), variant=ButtonVariant.FILLED)
        self._link_btn.setMinimumHeight(ds.field_height + ds.space_xs)
        self._link_btn.clicked.connect(self._on_link)
        link_row.addWidget(self._link_btn)
        self._unlink_btn = M3Button(_("parent.unlink_button"), variant=ButtonVariant.OUTLINED)
        self._unlink_btn.setMinimumHeight(ds.field_height + ds.space_xs)
        self._unlink_btn.clicked.connect(self._on_unlink)
        link_row.addWidget(self._unlink_btn)
        ls_layout.addLayout(link_row)

        self._detail_body.addWidget(self._links_section)
        self._detail_body.addStretch()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _load_links(self, parent_id: int):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT s.aecuser_ptr_id, aec.last_name, aec.first_name,
                       c.label, sp.nature
                FROM larcauth_student_parent sp
                JOIN larcauth_student s ON s.aecuser_ptr_id = sp.student_id
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                WHERE sp.parent_id = %s
                ORDER BY aec.last_name, aec.first_name
            """, (parent_id,))
            rows = cur.fetchall()
            self._student_table.setRowCount(len(rows))
            for i, (sid, ln, fn, cls, nature) in enumerate(rows):
                self._student_table.setItem(i, 0, QTableWidgetItem(f"{ln} {fn}"))
                self._student_table.setItem(i, 1, QTableWidgetItem(cls))
                self._student_table.setItem(i, 2, QTableWidgetItem(nature or ""))
            self._student_table.resizeColumnsToContents()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"ParentManager._load_links: {e}")

    def _populate_student_combo(self, parent_id: int):
        if not db.is_server_connected:
            return
        self._link_student_combo.clear()
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT s.aecuser_ptr_id, aec.last_name, aec.first_name, c.label
                FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                WHERE s.enabled = TRUE
                  AND NOT EXISTS (
                      SELECT 1 FROM larcauth_student_parent sp
                      WHERE sp.student_id = s.aecuser_ptr_id AND sp.parent_id = %s)
                ORDER BY aec.last_name, aec.first_name
            """, (parent_id,))
            for sid, ln, fn, cls in cur.fetchall():
                self._link_student_combo.addItem(f"{ln} {fn} ({cls})", sid)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"ParentManager._populate_student_combo: {e}")

    # ── Lien / Délien ──

    @safe_slot("ParentManager.on_link")
    def _on_link(self):
        if not db.is_server_connected:
            return
        rows = self._parent_table.selectedItems()
        if not rows:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("parent.error.no_parent_selected"))
            return
        parent_id = int(self._parent_table.item(rows[0].row(), 4).text())
        student_id = self._link_student_combo.currentData()
        if not student_id:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("parent.error.no_student_available"))
            return
        nature = self._nature_combo.currentText() or None
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO larcauth_student_parent (student_id, parent_id, nature) VALUES (%s, %s, %s)",
                        (student_id, parent_id, nature))
            cur.execute("SET LOCAL app.sync_source = 'intranet'")
            cur.execute(f"SET LOCAL app.modified_by = {session.user_id}")
            audit.update_parent(parent_id, f"Lié à l'élève #{student_id}")
            conn.commit()
            self._load_links(parent_id)
            self._populate_student_combo(parent_id)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            conn.rollback()
            log(f"ParentManager._on_link: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    @safe_slot("ParentManager.on_unlink")
    def _on_unlink(self):
        if not db.is_server_connected:
            return
        rows = self._parent_table.selectedItems()
        if not rows:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("parent.error.no_parent_selected"))
            return
        parent_id = int(self._parent_table.item(rows[0].row(), 4).text())
        srow = self._student_table.currentRow()
        if srow < 0:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("parent.error.select_to_unlink"))
            return
        name = self._student_table.item(srow, 0).text()
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT s.aecuser_ptr_id FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                WHERE aec.last_name || ' ' || aec.first_name = %s
                AND s.s_classroom_id IN (
                    SELECT c.id FROM larcauth_classroom c
                    JOIN larcauth_level l ON l.id = c.fk_level_id
                    JOIN larcauth_program pr ON pr.id = l.fk_program_id
                    WHERE pr.sigle IN ('PEI','MYP','DPEn','DPFr'))
                LIMIT 1
            """, (name,))
            r = cur.fetchone()
            if not r:
                return
            student_id = r[0]
            cur.execute("DELETE FROM larcauth_student_parent WHERE student_id=%s AND parent_id=%s",
                        (student_id, parent_id))
            cur.execute("SET LOCAL app.sync_source = 'intranet'")
            cur.execute(f"SET LOCAL app.modified_by = {session.user_id}")
            audit.update_parent(parent_id, f"Délié de l'élève #{student_id}")
            conn.commit()
            self._load_links(parent_id)
            self._populate_student_combo(parent_id)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            conn.rollback()
            log(f"ParentManager._on_unlink: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    # ── Création / Édition ──

    @safe_slot("ParentManager.on_add_parent")
    def _on_add_parent(self):
        dlg = ParentEditDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._load_data()

    @safe_slot("ParentManager.on_edit_foyer")
    def _on_edit_foyer(self):
        rows = self._parent_table.selectedItems()
        if not rows:
            return
        parent_id = int(self._parent_table.item(rows[0].row(), 4).text())
        dlg = ParentEditDialog(self, parent_id=parent_id)
        if dlg.exec() == QDialog.Accepted:
            self._load_data()

    @safe_slot("ParentManager.on_share_foyer")
    def _on_share_foyer(self):
        if not db.is_server_connected:
            return
        rows = self._parent_table.selectedItems()
        if not rows:
            return
        parent_id = int(self._parent_table.item(rows[0].row(), 4).text())
        parent = next((p for p in self._parents if p["id"] == parent_id), None)
        if not parent:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("SELECT fk_foyer_id FROM larcauth_aecuser WHERE id=%s", (parent_id,))
            r = cur.fetchone()
            if not r or not r[0]:
                if hasattr(self, "_share_status") and self._share_status:
                    self._share_status.setText(_("parent.error.no_address"))
                    self._share_status.show()
                return
            source_foyer_id = r[0]
            cur.execute("""
                SELECT aec.id, aec.last_name, aec.first_name, aec.email,
                       aec.fk_foyer_id
                FROM larcauth_aecuser aec
                WHERE aec.id != %s
                  AND (aec.type_parentutor = TRUE OR aec.type_student = TRUE)
                  AND aec.is_active = TRUE
                  AND (aec.fk_foyer_id IS NULL OR aec.fk_foyer_id != %s)
                ORDER BY aec.last_name LIMIT 100
            """, (parent_id, source_foyer_id))
            candidates = cur.fetchall()
            if not candidates:
                self._share_status.setText(_("parent.error.share_no_users"))
                self._share_status.show()
                return
            self._share_status.hide()
            items = [f"{r[1]} {r[2]} ({r[3]}) {'⚠️ foyer#' + str(r[4]) if r[4] else '📭'}" for r in candidates]
            ids = [r[0] for r in candidates]
            chosen, ok = QInputDialog.getItem(
                self, _("parent.share_address_title"),
                _("parent.share_address_prompt"), items, 0, False)
            if ok and chosen:
                idx = items.index(chosen)
                target_id = ids[idx]
                cur.execute("UPDATE larcauth_aecuser SET fk_foyer_id=%s WHERE id=%s",
                            (source_foyer_id, target_id))
                cur.execute("SET LOCAL app.sync_source = 'intranet'")
                cur.execute(f"SET LOCAL app.modified_by = {session.user_id}")
                audit.update_foyer(target_id, f"Foyer partagé avec #{source_foyer_id}")
                conn.commit()
                QMessageBox.information(self, _("parent.share_address"), _("parent.share_success"))
                self._on_parent_selected()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            conn.rollback()
            log(f"ParentManager._on_share_foyer: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    def reload(self):
        self._load_data()


# ──────────────────────────────────────────────
#   ParentEditDialog — Création / édition
# ──────────────────────────────────────────────


class ParentEditDialog(ThemedDialog):

    NEXT_PARENT_ID = 10001

    def __init__(self, parent=None, parent_id: int | None = None):
        super().__init__(parent)
        self._parent_id = parent_id
        self._existing_data: dict | None = None
        self.setWindowTitle(_("parent.edit_dialog_title") if parent_id else _("parent.add_dialog_title"))
        self.setMinimumWidth(ds.golden_width(500))
        self._init_ui()
        if parent_id:
            self._load_existing(parent_id)

    def _init_ui(self):
        p = ds.p
        layout = QVBoxLayout(self)
        layout.setSpacing(ds.space_md)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)

        title = M3Label(
            _("parent.edit_title") if self._parent_id else _("parent.add_title"),
            style="title_medium")
        layout.addWidget(title)

        # ── Carte Identité ──
        id_card, id_cl = self._section_card(_("parent.identity_group"), "person")
        id_grid = QGridLayout()
        id_grid.setSpacing(ds.space_md)
        id_grid.setColumnStretch(0, 1); id_grid.setColumnStretch(1, 1)
        id_grid.addLayout(self._field_row(_("parent.last_name_label"), self._inp("_dlg_nom", _("parent.last_name_placeholder"))), 0, 0)
        id_grid.addLayout(self._field_row(_("parent.first_name_label"), self._inp("_dlg_prenom", _("parent.first_name_placeholder"))), 0, 1)
        id_grid.addLayout(self._field_row(_("parent.email_label"), self._inp("_dlg_email", _("parent.email_placeholder"))), 1, 0)
        id_grid.addLayout(self._field_row(_("parent.phone_label"), self._inp("_dlg_tel", _("parent.phone_placeholder"))), 1, 1)
        id_cl.addLayout(id_grid)

        self._dlg_nature = M3ComboBox(_("parent.nature_items").split(","))
        self._dlg_nature.setFixedHeight(ds.field_height)
        nature_row = self._field_row(_("parent.nature_label_form"), self._dlg_nature)
        id_cl.addLayout(nature_row)
        layout.addWidget(id_card)

        # ── Carte Adresse ──
        addr_card, addr_cl = self._section_card(_("parent.address_group"), "home")
        addr_grid = QGridLayout()
        addr_grid.setSpacing(ds.space_md)
        addr_grid.setColumnStretch(0, 1); addr_grid.setColumnStretch(1, 1)
        addr_grid.addLayout(self._field_row(_("parent.street_label"), self._inp("_dlg_addr1", _("parent.street_placeholder"))), 0, 0)
        addr_grid.addLayout(self._field_row(_("parent.complement_label"), self._inp("_dlg_addr2", _("parent.complement_placeholder"))), 0, 1)
        addr_grid.addLayout(self._field_row(_("parent.zip_label"), self._inp("_dlg_cp", _("parent.zip_placeholder"))), 1, 0)
        addr_grid.addLayout(self._field_row(_("parent.city_label"), self._inp("_dlg_ville", _("parent.city_placeholder"))), 1, 1)
        addr_cl.addLayout(addr_grid)
        self._dlg_pays = M3TextField(_("parent.default_country"))
        self._dlg_pays.setFixedHeight(ds.field_height)
        self._dlg_pays.setStyleSheet(ds.flat_input_qss())
        pays_row = self._field_row(_("parent.country_label"), self._dlg_pays)
        addr_cl.addLayout(pays_row)
        layout.addWidget(addr_card)

        layout.addStretch()

        # Boutons
        buttons = M3DialogButtonBox(M3DialogButtonBox.Ok | M3DialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        ds.theme_changed.connect(self._restyle)

    # ── Helpers ──

    def _section_card(self, title: str, icon_name: str):
        card = M3Card(theme=theme_manager.phi_theme, variant=CardVariant.ELEVATED)
        card.setStyleSheet(
            f"M3Card {{ background: {ds.p.surface}; "
            f"border: 1px solid {ds.p.outline_variant}; "
            f"border-radius: {ds.radius_md}px; }}")
        cl = card.content_layout()
        cl.setSpacing(ds.space_sm)
        cl.setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
        hdr = QHBoxLayout()
        hdr.setSpacing(ds.space_xs)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(md3_icon(icon_name, color=ds.p.primary, size=20).pixmap(20, 20))
        hdr.addWidget(icon_lbl)
        title_lbl = M3Label(title, style="title_medium")
        title_lbl.setStyleSheet(f"color: {ds.p.text_strong}; font-weight: bold;")
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        cl.addLayout(hdr)
        sep = M3Frame()
        sep.setAttribute(Qt.WA_StyledBackground, True)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {ds.p.outline_variant};")
        cl.addWidget(sep)
        return card, cl

    def _field_row(self, label: str, widget):
        row = QVBoxLayout()
        row.setSpacing(ds.space_xxs)
        lbl = M3Label(label, style="label_small")
        lbl.setStyleSheet(f"color: {ds.p.text_strong}; font-weight: bold;")
        row.addWidget(lbl)
        widget.setMinimumHeight(ds.field_height)
        row.addWidget(widget)
        return row

    def _inp(self, attr: str, placeholder: str = ""):
        """Crée un M3TextField et le stocke comme attribut."""
        w = M3TextField(placeholder=placeholder)
        w.setFixedHeight(ds.field_height)
        w.setStyleSheet(ds.flat_input_qss())
        setattr(self, attr, w)
        return w

    @safe_slot("ParentEditDialog._restyle")
    def _restyle(self):
        card_style = (f"M3Card {{ background: {ds.p.surface}; "
                      f"border: 1px solid {ds.p.outline_variant}; "
                      f"border-radius: {ds.radius_md}px; }}")
        for attr in ("_dlg_nom", "_dlg_prenom", "_dlg_email", "_dlg_tel",
                     "_dlg_addr1", "_dlg_addr2", "_dlg_cp", "_dlg_ville",
                     "_dlg_pays"):
            w = getattr(self, attr, None)
            if w:
                try:
                    w.setStyleSheet(ds.flat_input_qss())
                except RuntimeError:
                    from larccommon.error_reporting import get_reporter
                    get_reporter().report_exception()
                    pass

    # ── Données ──

    def _load_existing(self, parent_id: int):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT aec.last_name, aec.first_name, aec.email,
                       aec.tel_smartphone_1, par.nature,
                       f.address_line1, f.address_line2, f.postal_code,
                       f.city, f.country
                FROM larcauth_aecuser aec
                JOIN larcauth_parent par ON par.aecuser_ptr_id = aec.id
                LEFT JOIN foyer f ON f.id = aec.fk_foyer_id
                WHERE aec.id = %s
            """, (parent_id,))
            row = cur.fetchone()
            if not row:
                return
            d = {"last_name": row[0], "first_name": row[1], "email": row[2],
                 "tel": row[3], "nature": row[4], "addr1": row[5],
                 "addr2": row[6], "cp": row[7], "city": row[8], "country": row[9]}
            self._existing_data = d
            self._dlg_nom.setText(d["last_name"] or "")
            self._dlg_prenom.setText(d["first_name"] or "")
            self._dlg_email.setText(d["email"] or "")
            self._dlg_tel.setText(d["tel"] or "")
            idx = self._dlg_nature.findText(d["nature"] or "")
            if idx >= 0:
                self._dlg_nature.setCurrentIndex(idx)
            self._dlg_addr1.setText(d["addr1"] or "")
            self._dlg_addr2.setText(d["addr2"] or "")
            self._dlg_cp.setText(d["cp"] or "")
            self._dlg_ville.setText(d["city"] or "")
            self._dlg_pays.setText(d["country"] or _("parent.default_country"))
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"ParentEditDialog._load_existing: {e}")

    @safe_slot("ParentEditDialog.validate_and_save")
    def _validate_and_save(self):
        if not db.is_server_connected:
            return
        nom = self._dlg_nom.text().strip()
        prenom = self._dlg_prenom.text().strip()
        nature = self._dlg_nature.currentText().strip()
        if not nom or not prenom or not nature:
            QMessageBox.warning(self, _("parent.validation_title"), _("parent.validation_required"))
            return
        conn = db.server_conn
        if not conn:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("parent.error.no_connection"))
            return
        try:
            cur = conn.cursor()
            cur.execute("SET LOCAL app.sync_source = 'intranet'")
            cur.execute(f"SET LOCAL app.modified_by = {session.user_id}")
            if self._parent_id:
                self._save_existing(cur, nom, prenom, nature)
            else:
                self._create_new(cur, nom, prenom, nature)
            conn.commit()
            audit.update_parent(self._parent_id or cur.lastrowid,
                                f"{'Création' if not self._parent_id else 'Modification'} parent {nom} {prenom}")
            self.accept()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            conn.rollback()
            log(f"ParentEditDialog._validate_and_save: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    def _save_existing(self, cur, nom, prenom, nature):
        pid = self._parent_id
        email = self._dlg_email.text().strip() or None
        tel = self._dlg_tel.text().strip() or None
        cur.execute(
            "UPDATE larcauth_aecuser SET last_name=%s, first_name=%s, "
            "email=COALESCE(%s, email), tel_smartphone_1=COALESCE(%s, tel_smartphone_1) "
            "WHERE id=%s", (nom, prenom, email, tel, pid))
        cur.execute("UPDATE larcauth_parent SET nature=%s WHERE aecuser_ptr_id=%s", (nature, pid))
        self._save_foyer(cur, pid)

    PARENT_SLOT_MIN = 10000
    PARENT_SLOT_MAX = 12000

    def _create_new(self, cur, nom, prenom, nature):
        email = self._dlg_email.text().strip() or _("parent.default_email").format(l=nom.lower(), f=prenom.lower())
        tel = self._dlg_tel.text().strip() or None
        from datetime import datetime
        now = datetime.now().isoformat()
        # Trouver le premier slot libre : parent avec enabled = FALSE
        cur.execute("""
            SELECT aecuser_ptr_id FROM larcauth_parent
            WHERE aecuser_ptr_id BETWEEN %s AND %s AND enabled = FALSE
            ORDER BY aecuser_ptr_id LIMIT 1
        """, (self.PARENT_SLOT_MIN, self.PARENT_SLOT_MAX))
        row = cur.fetchone()
        if not row:
            raise Exception(_("parent.limit_reached"))
        next_id = row[0]
        cur.execute("""
            UPDATE larcauth_aecuser SET
                first_name=%s, last_name=%s, email=%s, username=%s,
                tel_smartphone_1=%s, date_joined=%s, password='',
                type_parentutor=TRUE, is_active=TRUE
            WHERE id=%s
        """, (prenom, nom, email, email, tel, now, next_id))
        cur.execute("UPDATE larcauth_parent SET enabled=TRUE, nature=%s WHERE aecuser_ptr_id=%s",
                    (nature, next_id))
        log(f"ParentEditDialog: activated parent #{next_id}")
        self._save_foyer(cur, next_id)

    def _save_foyer(self, cur, aecuser_id: int):
        addr1 = self._dlg_addr1.text().strip() or None
        addr2 = self._dlg_addr2.text().strip() or None
        cp = self._dlg_cp.text().strip() or None
        city = self._dlg_ville.text().strip() or None
        country = self._dlg_pays.text().strip() or _("parent.default_country")
        cur.execute("""
            SELECT id FROM foyer
            WHERE address_line1 IS NOT DISTINCT FROM %s
              AND postal_code IS NOT DISTINCT FROM %s
              AND city IS NOT DISTINCT FROM %s
              AND enabled = TRUE LIMIT 1
        """, (addr1, cp, city))
        existing_addr = cur.fetchone()
        if existing_addr:
            foyer_id = existing_addr[0]
        else:
            cur.execute("SELECT id FROM foyer WHERE id=%s", (aecuser_id,))
            existing = cur.fetchone()
            if existing:
                foyer_id = aecuser_id
                cur.execute("""
                    UPDATE foyer SET address_line1=%s, address_line2=%s,
                    postal_code=%s, city=%s, country=%s, enabled=TRUE
                    WHERE id=%s
                """, (addr1, addr2, cp, city, country, foyer_id))
            else:
                foyer_id = aecuser_id
                cur.execute("""
                    INSERT INTO foyer (id, address_line1, address_line2,
                    postal_code, city, country, enabled)
                    VALUES (%s,%s,%s,%s,%s,%s,TRUE)
                """, (foyer_id, addr1, addr2, cp, city, country))
        cur.execute("UPDATE larcauth_aecuser SET fk_foyer_id=%s WHERE id=%s",
                    (foyer_id, aecuser_id))
