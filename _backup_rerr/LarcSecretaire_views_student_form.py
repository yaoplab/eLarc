"""
Fiche élève — recherche, consultation et édition des informations élèves.

Architecture :
  - StudentForm       : widget principal (barre recherche + contenu)
  - _StudentSearch    : zone de recherche + résultats
  - _StudentDetail    : onglets Coordonnées / Adresse / Parents + mode édition

Dépendances :
  - LarcSecretaire.common.database  (db.server_conn)
  - LarcSecretaire.common.theme     (theme_manager)
  - LarcSecretaire.common.session   (session)
"""

import json as _json
import os

from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from larccommon.widgets.skeleton import M3Skeleton
from larccommon.widgets.themed_widget import ThemedDialog, ThemedWidget
from LarcSecretaire.common.audit import audit
from LarcSecretaire.common.database import db
from LarcSecretaire.common.logger import log
from LarcSecretaire.common.photos import get_photo_path
from LarcSecretaire.common.session import session
from LarcSecretaire.common.theme import theme_manager
from LarcSecretaire.views.supervisor_panel import _event_color, _event_label
from phibuilder.phi.scale import SpacingToken
from phibuilder.widgets import (
    M3Button,
    M3Card,
    M3ComboBox,
    M3DateEdit,
    M3Dialog,
    M3DialogButtonBox,
    M3Frame,
    M3HeaderView,
    M3Label,
    M3ListWidget,
    M3ScrollArea,
    M3TableWidget,
    M3TextEdit,
    M3TextField,
)
from phibuilder.widgets.button import ButtonVariant
from phibuilder.widgets.card import CardVariant
from PySide6.QtCore import QDate, QEvent, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
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

# ──────────────────────────────────────────────
#   Classe utilitaire : cercle avatar initiales
# ──────────────────────────────────────────────


def _make_avatar(last_name: str, first_name: str, size: int = 120) -> QPixmap:
    """Génère un avatar rond avec les initiales (couleurs M3 de la palette active)."""
    initials = (last_name[:1] + first_name[:1]).upper() or "?"
    p = theme_manager.palette
    roles = ["primary", "secondary", "tertiary", "error"]
    # Hash STABLE (pas hash() : randomisé par processus PYTHONHASHSEED)
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
#   StudentForm — widget principal
# ──────────────────────────────────────────────


class StudentForm(ThemedWidget):
    """
    Page de gestion des fiches eleves.

    Recherche par nom et/ou prenom via deux champs dedies.
    Les resultats affichent les badges de validation D/M/P/E.
    Utilise M3Skeleton pendant le chargement.
    """

    # ── Colonnes du tableau de resultats ──
    _COL_NOM, _COL_PRENOM, _COL_CLASSE, _COL_NAISSANCE = range(4)
    _COL_D, _COL_M, _COL_P, _COL_E = range(4, 8)  # badges validation
    _COL_ID = 8  # cachee

    def __init__(self):
        super().__init__()
        self._current_student: dict | None = None
        self._results: list[dict] = []
        self._init_ui()
        ds.theme_changed.connect(self._restyle)

    # ──────────── Construction UI ────────────

    def _init_ui(self):
        p = ds.p
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_md)

        # ── Titre ──
        title = M3Label(_("student_form.title"), style="title_medium")
        layout.addWidget(title)

        # ── Barre de recherche (2 champs + bouton) ──
        search_row = QHBoxLayout()
        search_row.setSpacing(ds.space_sm)

        self._inp_nom = M3TextField(placeholder=_("student_form.last_name_placeholder"))
        self._inp_nom.setFixedHeight(ds.field_height)
        self._inp_nom.setStyleSheet(ds.flat_input_qss())
        self._inp_nom.returnPressed.connect(self._on_search)
        search_row.addWidget(self._inp_nom, 2)

        self._inp_prenom = M3TextField(placeholder=_("student_form.first_name_placeholder"))
        self._inp_prenom.setFixedHeight(ds.field_height)
        self._inp_prenom.setStyleSheet(ds.flat_input_qss())
        self._inp_prenom.returnPressed.connect(self._on_search)
        search_row.addWidget(self._inp_prenom, 2)

        self._search_btn = M3Button(_("student_form.search_button"), variant=ButtonVariant.FILLED)
        self._search_btn.setMinimumHeight(ds.field_height)
        self._search_btn.clicked.connect(self._on_search)
        search_row.addWidget(self._search_btn)
        layout.addLayout(search_row)

        # ── Zone de contenu : tableau (gauche) + detail (droite) ──
        content = QHBoxLayout()
        content.setSpacing(ds.space_md)

        # ── Panneau gauche : tableau des resultats ──
        self._results_card = M3Card(variant=CardVariant.ELEVATED, parent=self)
        rc_layout = self._results_card.content_layout()
        rc_layout.setContentsMargins(ds.space_xs, ds.space_xs, ds.space_xs, ds.space_xs)

        self._results_label = M3Label(_("student_form.results_label").format(count=0), style="label_small")
        self._results_label.setStyleSheet(f"font-weight: bold; color: {p.text_strong};")
        rc_layout.addWidget(self._results_label)

        # Tableau : Nom | Prenom | Classe | Date naiss. | D | M | P | E | ID(cache)
        self._results_table = M3TableWidget()
        self._results_table.set_headers([
            _("student_form.col_last_name"), _("student_form.col_first_name"),
            _("student_form.col_class"), _("student_form.col_birth"),
            "D", "M", "P", "E",
            "ID",
        ])
        self._results_table.setColumnHidden(self._COL_ID, True)
        self._results_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._results_table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._results_table.setAlternatingRowColors(False)
        self._results_table.verticalHeader().setDefaultSectionSize(ds.table_row_min)
        self._results_table.setStyleSheet(ds.table_qss())
        self._results_table.viewport().setCursor(Qt.PointingHandCursor)
        self._results_table.itemSelectionChanged.connect(self._on_result_selected)
        self._results_table.installEventFilter(self)
        # Reduire les colonnes badges
        hh = self._results_table.horizontalHeader()
        badge_w = 28
        for col in (self._COL_D, self._COL_M, self._COL_P, self._COL_E):
            hh.setSectionResizeMode(col, M3HeaderView.Fixed)
            self._results_table.setColumnWidth(col, badge_w)
        hh.setSectionResizeMode(self._COL_NOM, M3HeaderView.Interactive)
        hh.setSectionResizeMode(self._COL_PRENOM, M3HeaderView.Interactive)
        hh.setSectionResizeMode(self._COL_CLASSE, M3HeaderView.Interactive)
        hh.setSectionResizeMode(self._COL_NAISSANCE, M3HeaderView.Interactive)
        rc_layout.addWidget(self._results_table, 1)

        # Skeleton loading pendant la requete
        self._search_skeleton = M3Skeleton.table(self, rows=6, cols=5)
        self._search_skeleton.set_label(_("student_form.searching"))
        self._search_skeleton.hide()
        rc_layout.addWidget(self._search_skeleton)

        # Etat vide
        self._empty_state = M3Frame()
        self._empty_state.setAttribute(Qt.WA_StyledBackground, True)
        self._empty_state.setStyleSheet(f"background: transparent;")
        es_layout = QVBoxLayout(self._empty_state)
        es_layout.setSpacing(ds.space_sm)
        es_icon = QLabel()
        es_icon.setPixmap(md3_icon("search_off", color=p.text_disabled,
            size=theme_manager.image.logo_small).pixmap(
            theme_manager.image.logo_small, theme_manager.image.logo_small))
        es_icon.setAlignment(Qt.AlignCenter)
        es_layout.addWidget(es_icon)
        self._empty_state_label = M3Label(_("student_form.search_no_results"), style="body_medium")
        self._empty_state_label.setStyleSheet(f"color: {p.text_disabled};")
        self._empty_state_label.setAlignment(Qt.AlignCenter)
        self._empty_state_label.setWordWrap(True)
        es_layout.addWidget(self._empty_state_label)
        self._empty_state.hide()
        rc_layout.addWidget(self._empty_state, 1)

        content.addWidget(self._results_card, 3)

        # ── Panneau droit : detail eleve ──
        self._detail_panel = M3Card(variant=CardVariant.ELEVATED, parent=self)
        dp_layout = self._detail_panel.content_layout()
        dp_layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        dp_layout.setSpacing(ds.space_md)

        # Photo + Badges + Identité — Q22
        info_row = QHBoxLayout()
        info_row.setSpacing(ds.space_md)

        # Photo — Q22a
        self._detail_photo = QLabel()
        self._detail_photo.setFixedSize(theme_manager.image.logo, theme_manager.image.logo)  # 89×89
        self._detail_photo.setStyleSheet(
            f"background: {p.primary_container}; border-radius: {ds.radius_sm}px;")
        self._detail_photo.setAlignment(Qt.AlignCenter)
        self._detail_photo.setCursor(Qt.PointingHandCursor)
        self._detail_photo.setToolTip(_("student_form.open_file"))
        self._detail_photo.installEventFilter(self)
        info_row.addWidget(self._detail_photo)

        # Badges D/M/P/E (spécifique LarcSecretaire)
        self._detail_badges: dict[str, QLabel] = {}
        badges_layout = QVBoxLayout()
        badges_layout.setSpacing(ds.space_xxs - 1)
        _badge_size = 24
        for badge_key, letter, tooltip in [
            ("dossier_valid", "D", _("student_form.badge_dossier")),
            ("parent_valid",  "M", _("student_form.badge_medical")),
            ("photo_valid",   "P", _("student_form.badge_photo")),
            ("email_valid",   "E", _("student_form.badge_email")),
        ]:
            circle = QLabel(letter)
            circle.setFixedSize(_badge_size, _badge_size)
            circle.setAlignment(Qt.AlignCenter)
            circle.setToolTip(tooltip)
            circle.setStyleSheet(
                f"background: {p.surface}; color: {p.error}; "
                f"border: {ds.border_width * 2}px solid {p.error}; "
                f"font-weight: bold; font-size: {ds.font_label_sm}px; "
                f"border-radius: {ds.radius_md}px;")
            badges_layout.addWidget(circle)
            self._detail_badges[badge_key] = circle
        info_row.addLayout(badges_layout)

        # Identité — Q22b, Q22c, Q22d, Q22e, Q22f
        s = theme_manager.font_size
        text_col = QVBoxLayout()
        text_col.setSpacing(ds.space_xxs)  # 4px — Q22f

        self._detail_nom_lbl = M3Label("—")
        self._detail_nom_lbl.setStyleSheet(
            f"font-size: {s(18)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        text_col.addWidget(self._detail_nom_lbl)  # Q22c

        self._detail_classe_label = M3Label("", style="body_medium")
        self._detail_classe_label.setStyleSheet(f"color: {p.text_strong};")
        text_col.addWidget(self._detail_classe_label)  # Q22d

        self._detail_id_label = M3Label("", style="body_medium")
        self._detail_id_label.setStyleSheet(f"color: {p.text_strong};")
        text_col.addWidget(self._detail_id_label)  # Q22e

        text_col.addStretch()
        info_row.addLayout(text_col, 1)
        dp_layout.addLayout(info_row)

        self._open_btn = M3Button(_("student_form.open_file"), variant=ButtonVariant.FILLED)
        self._open_btn.clicked.connect(self._open_edit_dialog)
        self._open_btn.setMinimumWidth(ds.sp(SpacingToken.XXL) + ds.sp(SpacingToken.XL) + 9)
        dp_layout.addWidget(self._open_btn, 0, Qt.AlignCenter)
        dp_layout.addStretch()

        self._detail_panel.hide()
        content.addWidget(self._detail_panel, 1)

        layout.addLayout(content, 1)
        self._restyle()

    @safe_slot("StudentForm._restyle")
    def _restyle(self):
        p = ds.p
        if hasattr(self, "_results_table") and self._results_table:
            self._results_table.setStyleSheet(ds.table_qss())
        if hasattr(self, "_detail_photo") and self._detail_photo:
            self._detail_photo.setStyleSheet(f"background: {p.primary_container}; border-radius: {ds.radius_sm}px;")
        if hasattr(self, "_empty_state_label") and self._empty_state_label:
            self._empty_state_label.setStyleSheet(f"color: {p.text_disabled};")
        for lbl_attr in ("_detail_nom_lbl", "_detail_classe_label", "_detail_id_label"):
            lbl = getattr(self, lbl_attr, None)
            if lbl:
                lbl.setStyleSheet(f"color: {p.text_strong};")
        if hasattr(self, "_detail_nom_lbl"):
            self._detail_nom_lbl.setStyleSheet(
                f"font-size: {theme_manager.font_size(18)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        if hasattr(self, "_inp_nom") and self._inp_nom:
            self._inp_nom.setStyleSheet(ds.flat_input_qss())
        if hasattr(self, "_inp_prenom") and self._inp_prenom:
            self._inp_prenom.setStyleSheet(ds.flat_input_qss())
        if hasattr(self, "_current_student") and self._current_student:
            self._refresh_detail_badges(self._current_student["id"])

    # ──────────── Recherche ────────────

    @safe_slot("Unknown._on_search")
    def _on_search(self, checked: bool = False):
        nom = self._inp_nom.text().strip()
        prenom = self._inp_prenom.text().strip()
        if not nom and not prenom:
            return
        self._execute_search(nom, prenom)

    def _execute_search(self, last_name: str, first_name: str):
        if not db.is_server_connected:
            return
        """Recherche les eleves par nom et/ou prenom."""
        conn = db.server_conn
        if not conn:
            return
        # Skeleton loading
        self._results_table.hide()
        self._empty_state.hide()
        self._detail_panel.hide()
        self._search_skeleton.show()
        self._search_skeleton.start()
        QApplication.processEvents()
        try:
            cur = conn.cursor()
            like_nom = f"%{last_name}%" if last_name else "%"
            like_prenom = f"%{first_name}%" if first_name else "%"
            cur.execute(
                """
                SELECT aec.id, aec.last_name, aec.first_name,
                       c.label AS classroom, aec.date_of_birth,
                       COALESCE(s.validation, '{}'::jsonb) AS validation
                FROM larcauth_aecuser aec
                JOIN larcauth_student s ON s.aecuser_ptr_id = aec.id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                WHERE s.enabled = TRUE
                  AND aec.last_name ILIKE %s AND aec.first_name ILIKE %s
                ORDER BY aec.last_name, aec.first_name
                LIMIT 200
            """, (like_nom, like_prenom))
            self._results = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]
            self._populate_results()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentForm._execute_search: {e}")
        finally:
            self._search_skeleton.stop()
            self._search_skeleton.hide()

    def _populate_results(self):
        """Remplit le tableau : Nom | Prenom | Classe | Naissance | D | M | P | E."""
        self._results_table.setRowCount(0)
        for r in self._results:
            row = self._results_table.rowCount()
            self._results_table.insertRow(row)
            self._results_table.setItem(row, self._COL_NOM, QTableWidgetItem((r.get("last_name") or "").upper()))
            self._results_table.setItem(row, self._COL_PRENOM, QTableWidgetItem(r.get("first_name") or ""))
            self._results_table.setItem(row, self._COL_CLASSE, QTableWidgetItem(r.get("classroom") or ""))
            naissance = r.get("date_of_birth")
            naissance_str = str(naissance)[:10] if naissance else "—"
            self._results_table.setItem(row, self._COL_NAISSANCE, QTableWidgetItem(naissance_str))
            # Badges validation
            val = r.get("validation") or {}
            if isinstance(val, str):
                val = _json.loads(val) if val else {}
            for flag_key, col_idx, letter in [
                ("dossier", self._COL_D, "D"), ("parent", self._COL_M, "M"),
                ("photo", self._COL_P, "P"), ("email", self._COL_E, "E"),
            ]:
                entry = val.get(flag_key, {}) if isinstance(val, dict) else {}
                ok = entry.get("ok", False) if isinstance(entry, dict) else False
                badge = QLabel(letter)
                badge.setAlignment(Qt.AlignCenter)
                if ok:
                    badge.setStyleSheet(
                        f"background: {ds.p.success}; color: #FFFFFF; font-weight: bold; "
                        f"font-size: {ds.font_label_sm}px; border-radius: {ds.radius_md}px; "
                        f"padding: {ds.border_width}px;")
                else:
                    badge.setStyleSheet(
                        f"background: transparent; color: {ds.p.error}; font-weight: bold; "
                        f"font-size: {ds.font_label_sm}px; "
                        f"border: {ds.border_width}px solid {ds.p.error}; "
                        f"border-radius: {ds.radius_md}px; padding: {ds.border_width}px;")
                self._results_table.setCellWidget(row, col_idx, badge)
            self._results_table.setItem(row, self._COL_ID, QTableWidgetItem(str(r["id"])))
        count = len(self._results)
        self._results_label.setText(_("student_form.results_label").format(count=count))
        if count == 0:
            self._detail_panel.hide()
            self._empty_state.show()
        else:
            self._results_table.show()
            self._empty_state.hide()
            if count == 1:
                self._results_table.selectRow(0)

    # ──────────── Affichage du detail ────────────

    @safe_slot("StudentForm.on_result_selected")
    def _on_result_selected(self):
        rows = self._results_table.selectedItems()
        if not rows:
            return
        r = rows[0].row()
        id_item = self._results_table.item(r, self._COL_ID)
        if not id_item:
            return
        student_id = int(id_item.text())
        # Trouver les donnees dans self._results
        data = next((x for x in self._results if x["id"] == student_id), None)
        if not data:
            return
        self._current_student = data
        self._update_info_card(data)
        self._detail_panel.show()

    def _update_info_card(self, data: dict):
        """Met a jour la vignette info — Q22."""
        sid = data["id"]
        px = QPixmap(get_photo_path(sid))
        if px.isNull():
            px = _make_avatar(data.get("last_name", ""), data.get("first_name", ""), theme_manager.image.logo)
        else:
            px = px.scaled(theme_manager.image.logo, theme_manager.image.logo, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._detail_photo.setPixmap(px)
        # Q22c — Nom (prénom + nom)
        fn = data.get("first_name", "") or ""
        ln = data.get("last_name", "") or ""
        self._detail_nom_lbl.setText(f"{fn} {ln}" if fn else "—")
        # Q22d — Classe
        self._detail_classe_label.setText(_("student_form.class_label").format(label=data.get("classroom", "—")))
        # Q22e — ID
        self._detail_id_label.setText(_("student_form.id_label").format(id=sid))
        self._refresh_detail_badges(sid)

    def _refresh_detail_badges(self, sid: int):
        if not db.is_server_connected:
            return
        """Colore les 4 cercles D/M/P/E : P verifie is_payer sur un parent lie."""
        if not hasattr(self, "_detail_badges") or not self._detail_badges:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT validation FROM larcauth_student WHERE aecuser_ptr_id = %s", (sid,))
            row = cur.fetchone()
            val = row[0] if row and row[0] else {}
            if isinstance(val, str):
                val = _json.loads(val)

            # Badge P : parent payeur (requete live, pas JSONB)
            has_payer = False
            try:
                cur.execute(
                    "SELECT 1 FROM larcauth_student_parent sp "
                    "JOIN larcauth_parent p ON p.aecuser_ptr_id = sp.parent_id "
                    "WHERE sp.student_id = %s AND p.is_payer = TRUE AND p.enabled = TRUE LIMIT 1",
                    (sid,))
                has_payer = cur.fetchone() is not None
            except Exception:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                pass  # fallback : garder la valeur JSONB

            for flag_key, (badge_key, circle) in [
                ("dossier", ("dossier_valid", self._detail_badges.get("dossier_valid"))),
                ("parent",  ("parent_valid",  self._detail_badges.get("parent_valid"))),
                ("photo",   ("photo_valid",   self._detail_badges.get("photo_valid"))),
                ("email",   ("email_valid",   self._detail_badges.get("email_valid"))),
            ]:
                if circle is None:
                    continue
                # Badge P : verifier la presence d'un parent payeur
                if badge_key == "parent_valid":
                    ok = has_payer
                else:
                    entry = val.get(flag_key, {}) if isinstance(val, dict) else {}
                    ok = entry.get("ok", False)

                if ok:
                    circle.setStyleSheet(
                        f"background: {ds.p.success}; color: {ds.p.on_error if hasattr(ds.p, 'on_error') else '#FFFFFF'}; "
                        f"border: {ds.border_width * 2}px solid {ds.p.success}; "
                        f"font-weight: bold; font-size: {ds.font_label_sm}px; "
                        f"border-radius: {ds.radius_md}px;")
                else:
                    circle.setStyleSheet(
                        f"background: {ds.p.surface}; color: {ds.p.error}; "
                        f"border: {ds.border_width * 2}px solid {ds.p.error}; "
                        f"font-weight: bold; font-size: {ds.font_label_sm}px; "
                        f"border-radius: {ds.radius_md}px;")
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentForm._refresh_detail_badges: {e}")

    @safe_slot("StudentForm.open_edit_dialog")
    def _open_edit_dialog(self):
        if not self._current_student:
            return
        dlg = StudentEditDialog(self._current_student, self)
        if dlg.exec():
            # Re-afficher le detail frais
            self._refresh_current_student()

    def _refresh_current_student(self):
        if not db.is_server_connected:
            return
        """Recharge les donnees de l'eleve courant depuis la DB."""
        if not self._current_student:
            return
        sid = self._current_student["id"]
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT aec.id, aec.last_name, aec.first_name,
                       c.label AS classroom, aec.date_of_birth,
                       COALESCE(s.validation, '{}'::jsonb) AS validation
                FROM larcauth_aecuser aec
                JOIN larcauth_student s ON s.aecuser_ptr_id = aec.id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                WHERE aec.id = %s
            """, (sid,))
            row = cur.fetchone()
            if row:
                self._current_student = dict(zip(
                    ["id", "last_name", "first_name", "classroom", "date_of_birth", "validation"], row))
                self._update_info_card(self._current_student)
                # Recharger aussi dans self._results
                for i, r in enumerate(self._results):
                    if r["id"] == sid:
                        self._results[i] = dict(self._current_student)
                        break
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentForm._refresh_current_student: {e}")

    def eventFilter(self, obj, event):
        photo = getattr(self, "_detail_photo", None)
        if photo is not None and obj == photo and event.type() == QEvent.MouseButtonPress:
            self._open_edit_dialog()
            return True
        if obj == self._results_table and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._open_edit_dialog()
                return True
        return super().eventFilter(obj, event)

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_focus_once", False):
            self._focus_once = True
            if hasattr(self, "_inp_nom") and self._inp_nom:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(50, self._inp_nom.setFocus)


# ──────────────────────────────────────────────
#   StudentEditDialog — Modification d'un élève (popup)
# ──────────────────────────────────────────────


class StudentEditDialog(ThemedDialog):
    """Popup d'édition d'élève — grand formulaire comme la création."""

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self._sid = data["id"]
        self._data = self._fetch_fresh_data() or data
        self._dirty: bool = False  # Dossier modifié non sauvegardé → indicateur bouton Enregistrer
        self.setWindowTitle(_("student_form.edit_title").format(l=self._data.get("last_name", "?"), f=self._data.get("first_name", "?")))
        # 987×610 = paire dorée (610 = sidebar + golden_width(sidebar) ; 987 = golden_width(610))
        _min_h = ds.sidebar_width + ds.golden_width(ds.sidebar_width)  # 610
        self.setMinimumSize(ds.golden_width(_min_h), _min_h)  # 987×610
        try:
            self._init_ui()
            self._load_data()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback

            log(f"StudentEditDialog.__init__: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, _("common.dialog.error_title"), f"{e}")
            # raise : l'appelant n'atteindra jamais dlg.exec() (sinon il réafficherait
            # le dialogue vide/partiellement construit). safe_slot / PySide6 gèrent
            # l'exception proprement (log + traceback) sans casser l'app.
            raise
        # Connexion theme_changed UNIQUEMENT après construction réussie : si la
        # construction échoue (raise ci-dessus), le signal ne garde pas une
        # référence à un dialogue à moitié construit.
        ds.theme_changed.connect(self._restyle)
        # Afficher APRÈS construction : un showMaximized() précoce laisserait
        # une fenêtre vide si _init_ui() levait une exception (traceback invisible).
        self.showMaximized()

    def _fetch_fresh_data(self) -> dict | None:
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return None
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    s.aecuser_ptr_id AS id,
                    aec.last_name, aec.first_name, aec.email,
                    aec.emailperso, aec.tel_smartphone_1, aec.tel_maison,
                    c.label AS classroom, aec.date_joined,
                    aec.date_entree,
                    aec.date_of_birth,
                    aec.fk_foyer_id, aec.fk_gender_id,
                    s.s_classroom_id, s.notes, s.notes_json,
                    f.address_line1, f.address_line2, f.postal_code,
                    f.city, f.country, f.phone AS foyer_phone, f.email AS foyer_email
                FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                LEFT JOIN foyer f ON f.id = aec.fk_foyer_id
                WHERE s.aecuser_ptr_id = %s
            """,
                (self._sid,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row))
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentEditDialog._fetch_fresh_data: {e}")
            return None

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(ds.sp(SpacingToken.SM))
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)

        title = M3Label(_("student_form.edit_label"), style="title_small")
        layout.addWidget(title)

        def _lbl(t):
            lbl = M3Label(t, style="body_medium")
            lbl.setStyleSheet(f"font-weight: bold; color: {ds.p.text_strong};")
            lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
            return lbl

        # Photo + nom + actions
        photo_row = QHBoxLayout()
        photo_row.setSpacing(ds.sp(SpacingToken.SM))
        self._photo = QLabel()
        self._photo.setFixedSize(ds.sp(SpacingToken.XXXL), ds.sp(SpacingToken.XXXL))
        self._photo.setStyleSheet(f"background: {ds.p.primary_container}; border-radius: {ds.radius_sm}px;")
        self._photo.setAlignment(Qt.AlignCenter)
        photo_row.addWidget(self._photo)

        id_col = QVBoxLayout()
        id_col.setSpacing(ds.space_xxs)
        # Ligne 1 : PRÉNOM (plus grand) + NOM (majuscules)
        name_row = QHBoxLayout()
        name_row.setSpacing(ds.space_sm)
        self._id_prenom = M3Label("", style="headline_large")
        self._id_prenom.setStyleSheet(f"font-weight: bold; color: {ds.p.text_strong};")
        name_row.addWidget(self._id_prenom)
        self._id_nom = M3Label("", style="title_large")
        self._id_nom.setStyleSheet(f"font-weight: bold; color: {ds.p.text_strong};")
        name_row.addWidget(self._id_nom)
        name_row.addStretch()
        id_col.addLayout(name_row)
        # Ligne 2 : Classe
        self._id_classe = M3Label("", style="body_medium")
        self._id_classe.setStyleSheet(f"color: {ds.p.text_strong};")
        id_col.addWidget(self._id_classe)
        # Ligne 3 : Id
        self._id_id = M3Label("", style="body_medium")
        self._id_id.setStyleSheet(f"color: {ds.p.text_strong};")
        id_col.addWidget(self._id_id)
        id_col.addStretch()
        photo_row.addLayout(id_col, 1)

        # Boutons d'action (2 colonnes: PDF/Word | Save/Cancel)
        btn_col = QVBoxLayout()
        btn_col.setSpacing(ds.space_sm)
        btn_col.setAlignment(Qt.AlignTop)

        def _m3_btn(text, variant):
            b = M3Button(text, variant=variant)
            b.setMinimumHeight(ds.button_height)
            return b

        col_pdf = QVBoxLayout()
        col_pdf.setSpacing(ds.space_sm)
        col_pdf.setAlignment(Qt.AlignTop)
        pdf_btn = _m3_btn(_("student_form.pdf"), ButtonVariant.TONAL)
        pdf_btn.clicked.connect(self._export_pdf)
        col_pdf.addWidget(pdf_btn)
        word_btn = _m3_btn(_("student_form.word"), ButtonVariant.TONAL)
        word_btn.clicked.connect(self._export_word)
        col_pdf.addWidget(word_btn)
        photo_row.addLayout(col_pdf)

        self._save_btn = _m3_btn(_("student_form.save"), ButtonVariant.FILLED)
        self._save_btn.clicked.connect(self._save)
        btn_col.addWidget(self._save_btn)
        cancel_btn = _m3_btn(_("student_form.cancel"), ButtonVariant.OUTLINED)
        cancel_btn.clicked.connect(self.reject)
        btn_col.addWidget(cancel_btn)
        btn_col.addStretch()
        photo_row.addLayout(btn_col)

        layout.addLayout(photo_row)
        layout.addSpacing(ds.sp(SpacingToken.SM))

        # Champs — hauteur uniforme via Fibonacci
        _fh = ds.field_height
        self._inp_nom = M3TextField()
        self._inp_nom.setFixedHeight(_fh)
        self._inp_prenom = M3TextField()
        self._inp_prenom.setFixedHeight(_fh)
        self._inp_email = M3TextField()
        self._inp_email.setFixedHeight(_fh)
        self._inp_emailperso = M3TextField()
        self._inp_emailperso.setFixedHeight(_fh)
        self._inp_tel = M3TextField()
        self._inp_tel.setFixedHeight(_fh)
        self._inp_tel2 = M3TextField()
        self._inp_tel2.setFixedHeight(_fh)
        self._inp_date_joined = M3DateEdit()
        self._inp_date_joined.setFixedHeight(_fh)
        self._inp_date_joined.setDisplayFormat("yyyy-MM-dd")
        self._inp_date_joined.setCalendarPopup(True)
        self._inp_date_joined.setDate(QDate.currentDate())
        self._inp_date = M3DateEdit()
        self._inp_date.setFixedHeight(_fh)
        self._inp_date.setDisplayFormat("yyyy-MM-dd")
        self._inp_date.setCalendarPopup(True)
        self._inp_date.setDate(QDate.currentDate())
        self._inp_genre = M3ComboBox()
        self._inp_genre.setFixedHeight(_fh)
        self._load_genders()
        self._inp_birthdate = M3DateEdit()
        self._inp_birthdate.setFixedHeight(_fh)
        self._inp_birthdate.setDisplayFormat("yyyy-MM-dd")
        self._inp_birthdate.setCalendarPopup(True)
        self._inp_addr1 = M3TextEdit()
        self._inp_addr1.setFixedHeight(ds.sp(SpacingToken.XXXL))
        self._inp_addr1.setPlaceholderText(_("student_form.street_placeholder"))
        self._inp_addr1.setStyleSheet(ds.flat_input_qss())
        self._inp_addr2 = M3TextField()
        self._inp_addr2.setFixedHeight(_fh)
        self._inp_cp = M3TextField()
        self._inp_cp.setFixedHeight(_fh)
        self._inp_ville = M3TextField()
        self._inp_ville.setFixedHeight(_fh)
        self._inp_pays = M3TextField(_("student_form.default_country"))
        self._inp_pays.setFixedHeight(_fh)

        # Flat field styling via ds helper
        for w in (
            self._inp_nom,
            self._inp_prenom,
            self._inp_email,
            self._inp_emailperso,
            self._inp_tel,
            self._inp_tel2,
            self._inp_addr2,
            self._inp_cp,
            self._inp_ville,
            self._inp_pays,
        ):
            w.setStyleSheet(ds.flat_input_qss())
        for w in (self._inp_date_joined, self._inp_date, self._inp_birthdate):
            w.setStyleSheet(
                f"border: 1px solid {ds.p.outline}; border-radius: {ds.radius_xs}px; "
                f"padding: {ds.space_xxs}px {ds.space_xs}px; color: {ds.p.text_strong}; background: {ds.p.surface}; "
                f"QDateEdit QLineEdit {{ color: {ds.p.text_strong}; background: {ds.p.surface}; }}"
            )
            w.setMinimumWidth(ds.sp(SpacingToken.XXXL))

        # ═══════════════════════════════════════════════════════════
        #   Helpers de construction de sections (cartes responsives)
        # ═══════════════════════════════════════════════════════════

        def _section_card(title: str, icon_name: str):
            """Carte de section avec icône + titre + séparateur."""
            card = M3Card(variant=CardVariant.ELEVATED)
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

        def _field_row(label: str, widget, is_date: bool = False):
            """Label au-dessus du champ."""
            row = QVBoxLayout()
            row.setSpacing(ds.space_xxs)
            lbl = M3Label(label, style="label_small")
            lbl.setStyleSheet(f"color: {ds.p.text_strong}; font-weight: bold;")
            row.addWidget(lbl)
            widget.setMinimumHeight(ds.field_height)
            if not is_date:
                widget.setStyleSheet(ds.flat_input_qss())
            row.addWidget(widget)
            return row

        # ═══════════════════════════════════════════════════════════
        #   ScrollArea : toutes les sections en single-page scrollable
        # ═══════════════════════════════════════════════════════════

        scroll = M3ScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"M3ScrollArea {{ background: {ds.p.background}; border: none; }}")
        scroll_content = QWidget()
        scroll_content.setAttribute(Qt.WA_StyledBackground, True)
        scroll_content.setStyleSheet(f"background: {ds.p.background};")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(ds.space_md)
        scroll_layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)

        self._section_cards: list[M3Card] = []

        # ── 1. Identité ──
        id_card, id_cl = _section_card(_("student_form.tab_identity"), "person")
        id_grid = QGridLayout()
        id_grid.setSpacing(ds.space_md)
        id_grid.setColumnStretch(0, 1); id_grid.setColumnStretch(1, 1); id_grid.setColumnStretch(2, 1)
        id_grid.addLayout(_field_row(_("student_form.first_name_label"), self._inp_prenom), 0, 0)
        id_grid.addLayout(_field_row(_("student_form.last_name_label"), self._inp_nom), 0, 1)
        id_grid.addLayout(_field_row(_("student_form.gender_label"), self._inp_genre), 0, 2)
        id_grid.addLayout(_field_row(_("student_form.arrival_label"), self._inp_date_joined, is_date=True), 1, 0)
        id_grid.addLayout(_field_row(_("student_form.entry_date"), self._inp_date, is_date=True), 1, 1)
        id_grid.addLayout(_field_row(_("student_form.birth_date"), self._inp_birthdate, is_date=True), 1, 2)
        id_cl.addLayout(id_grid)
        scroll_layout.addWidget(id_card)
        self._section_cards.append(id_card)

        # ── 2. Contact ──
        ct_card, ct_cl = _section_card("Contact", "description")
        ct_grid = QGridLayout()
        ct_grid.setSpacing(ds.space_md)
        ct_grid.setColumnStretch(0, 1); ct_grid.setColumnStretch(1, 1)
        ct_grid.addLayout(_field_row(_("student_form.email_label"), self._inp_email), 0, 0)
        ct_grid.addLayout(_field_row(_("student_form.email_personal"), self._inp_emailperso), 0, 1)
        ct_grid.addLayout(_field_row(_("student_form.phone_mobile"), self._inp_tel), 1, 0)
        ct_grid.addLayout(_field_row(_("student_form.phone_fixed"), self._inp_tel2), 1, 1)
        ct_cl.addLayout(ct_grid)
        scroll_layout.addWidget(ct_card)
        self._section_cards.append(ct_card)

        # ── 3. Adresse ──
        ad_card, ad_cl = _section_card(_("student_form.address_title"), "home")
        ad_grid = QGridLayout()
        ad_grid.setSpacing(ds.space_md)
        ad_grid.setColumnStretch(0, 1); ad_grid.setColumnStretch(1, 1); ad_grid.setColumnStretch(2, 1)
        ad_grid.addLayout(_field_row(_("student_form.street_placeholder"), self._inp_addr1), 0, 0, 1, 3)
        ad_grid.addLayout(_field_row(_("student_form.address_complement"), self._inp_addr2), 1, 0, 1, 3)
        ad_grid.addLayout(_field_row(_("student_form.zip_label"), self._inp_cp), 2, 0)
        ad_grid.addLayout(_field_row(_("student_form.city_label"), self._inp_ville), 2, 1)
        ad_grid.addLayout(_field_row(_("student_form.country_label"), self._inp_pays), 2, 2)
        ad_cl.addLayout(ad_grid)
        scroll_layout.addWidget(ad_card)
        self._section_cards.append(ad_card)

        # ── 4. Parents ──
        par_card, par_cl = _section_card(_("student_form.parents_title"), "person")
        self._parents_table = M3TableWidget()
        self._parents_table.set_headers([
            _("student_form.parents_table_nom"), _("student_form.parents_table_nature"),
            _("student_form.parents_table_email"), _("student_form.parents_table_phone"),
        ])
        self._parents_table.horizontalHeader().setStretchLastSection(True)
        self._parents_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._parents_table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._parents_table.setShowGrid(True)
        self._parents_table.horizontalHeader().setFixedHeight(ds.field_height)
        self._parents_table.setStyleSheet(ds.table_qss())
        self._parents_table.verticalHeader().setDefaultSectionSize(ds.table_row_min)
        self._parents_table.setMaximumHeight(ds.sp(SpacingToken.XXXL))
        par_cl.addWidget(self._parents_table)

        parent_tools = QHBoxLayout()
        parent_tools.setSpacing(ds.space_sm)
        add_par_btn = M3Button(_("student_form.add_parent"), variant=ButtonVariant.FILLED)
        add_par_btn.clicked.connect(self._add_parent_link)
        parent_tools.addWidget(add_par_btn)
        edit_par_btn = M3Button(_("student_form.edit_nature"), variant=ButtonVariant.TONAL)
        edit_par_btn.clicked.connect(self._edit_parent_nature)
        parent_tools.addWidget(edit_par_btn)
        remove_par_btn = M3Button(_("student_form.remove_parent"), variant=ButtonVariant.OUTLINED)
        remove_par_btn.clicked.connect(self._remove_parent_link)
        parent_tools.addWidget(remove_par_btn)
        copy_btn = M3Button(_("student_form.copy_address"), variant=ButtonVariant.TONAL)
        copy_btn.clicked.connect(self._copy_parent_address)
        parent_tools.addWidget(copy_btn)
        parent_tools.addStretch()
        par_cl.addLayout(parent_tools)
        self._addr_status = M3Label("", style="body_small")
        self._addr_status.setWordWrap(True)
        self._addr_status.setStyleSheet(f"color: {ds.p.text_disabled};")
        self._addr_status.hide()
        par_cl.addWidget(self._addr_status)
        scroll_layout.addWidget(par_card)
        self._section_cards.append(par_card)

        # ── 5. Dossiers ──
        dos_card, dos_cl = _section_card(_("student_form.tab_documents"), "subject")
        from LarcSecretaire.views.dossier_panel import DossierPanel
        self._dossier_panel = DossierPanel(self._sid)
        self._dossier_panel.entries_changed.connect(self._mark_dirty)
        self._dossier_panel.setMinimumHeight(ds.window_height * 9 // 16)
        self._dossier_panel.setMaximumHeight(ds.window_height * 13 // 16)
        dos_cl.addWidget(self._dossier_panel)
        scroll_layout.addWidget(dos_card)
        self._section_cards.append(dos_card)

        # ── 6. Événements ──
        evt_card, evt_cl = _section_card(_("student_form.events_title"), "event")
        self._evt_table = M3TableWidget()
        self._evt_table.set_headers([
            _("student_form.events_table_date"), _("student_form.events_table_type"),
            _("student_form.events_table_note"), _("student_form.events_table_by"),
            _("student_form.events_table_validated"),
        ])
        hh_evt = self._evt_table.horizontalHeader()
        hh_evt.setSectionResizeMode(0, M3HeaderView.Interactive)
        hh_evt.setSectionResizeMode(1, M3HeaderView.Interactive)
        hh_evt.setSectionResizeMode(2, M3HeaderView.Stretch)
        hh_evt.setSectionResizeMode(3, M3HeaderView.Interactive)
        hh_evt.setSectionResizeMode(4, M3HeaderView.ResizeToContents)
        self._evt_table.setColumnWidth(0, ds.sp(SpacingToken.XXL) + ds.sp(SpacingToken.LG) + 34)
        self._evt_table.setColumnWidth(1, ds.sp(SpacingToken.XXL) + ds.sp(SpacingToken.MD) + 6)
        self._evt_table.setColumnWidth(3, ds.space_xxl)
        self._evt_table.setStyleSheet(ds.table_qss())
        self._evt_table.verticalHeader().setDefaultSectionSize(ds.table_row_min)
        self._evt_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._evt_table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._evt_table.setAlternatingRowColors(False)
        self._evt_table.setMaximumHeight(ds.window_height * 5 // 16)
        evt_cl.addWidget(self._evt_table)
        evt_btn_row = QHBoxLayout()
        self._add_event_btn = M3Button(_("student_form.add_event"), variant=ButtonVariant.FILLED)
        self._add_event_btn.clicked.connect(self._on_add_event)
        evt_btn_row.addWidget(self._add_event_btn)
        evt_btn_row.addStretch()
        evt_cl.addLayout(evt_btn_row)
        scroll_layout.addWidget(evt_card)
        self._section_cards.append(evt_card)

        # ── 7. Photos ──
        photo_card, photo_cl = _section_card(_("student_form.tab_photos"), "add")
        photo_box = QVBoxLayout()
        photo_box.setAlignment(Qt.AlignCenter)
        photo_box.setSpacing(ds.space_sm)
        self._photo_large = QLabel()
        self._photo_large.setFixedSize(ds.sp(SpacingToken.XXXL) * 2, ds.sp(SpacingToken.XXXL) * 2)
        self._photo_large.setStyleSheet(f"background: {ds.p.primary_container}; border-radius: {ds.radius_sm}px;")
        self._photo_large.setAlignment(Qt.AlignCenter)
        photo_box.addWidget(self._photo_large, 0, Qt.AlignCenter)
        self._upload_photo_btn = M3Button(_("student_form.change_photo"), variant=ButtonVariant.FILLED)
        self._upload_photo_btn.clicked.connect(self._on_change_photo)
        photo_box.addWidget(self._upload_photo_btn, 0, Qt.AlignCenter)
        photo_cl.addLayout(photo_box)
        scroll_layout.addWidget(photo_card)
        self._section_cards.append(photo_card)

        # ── 8. Bulletins & Relevés ──
        bul_card, bul_cl = _section_card(_("student_form.tab_bulletins"), "school")
        from LarcSecretaire.common.app_config import app_config as _acfg
        btn_row = QHBoxLayout()
        btn_row.setSpacing(ds.space_md)
        b_intra = M3Button(_("student_form.drive_intranet"), variant=ButtonVariant.FILLED)
        b_intra.clicked.connect(lambda checked: (
            self._open_drive_dir(_acfg.get("releves_dir", "")),
            self._open_drive_dir(_acfg.get("bulletins_dir", ""))
        ))
        btn_row.addWidget(b_intra)
        b_cloud = M3Button(_("student_form.drive_cloud"), variant=ButtonVariant.TONAL)
        b_cloud.clicked.connect(lambda checked: (
            self._open_drive_cloud(_acfg.get("releves_cloud_url", "")),
            self._open_drive_cloud(_acfg.get("bulletins_cloud_url", ""))
        ))
        btn_row.addWidget(b_cloud)
        btn_row.addStretch()
        bul_cl.addLayout(btn_row)
        scroll_layout.addWidget(bul_card)
        self._section_cards.append(bul_card)

        # ── 9. Confidentiel (restreint) ──
        from LarcSecretaire.common.session import UserRole
        from LarcSecretaire.common.session import session as _ses
        conf_card, conf_cl = _section_card(_("student_form.tab_confidential"), "lock")
        if _ses.role in (UserRole.ADMIN, UserRole.COORD, UserRole.SECR):
            conf_info = M3Label(_("student_form.confidential_desc"), style="body_medium")
            conf_info.setWordWrap(True)
            conf_cl.addWidget(conf_info)
            from LarcSecretaire.views.dossier_panel import ConfidentialPanel
            self._conf_panel = ConfidentialPanel(self._sid)
            self._conf_panel.entries_changed.connect(self._mark_dirty)
            self._conf_panel.setMaximumHeight(ds.window_height * 7 // 16)
            conf_cl.addWidget(self._conf_panel)
        else:
            deny = M3Label(_("student_form.confidential_restricted"), style="title_small")
            deny.setAlignment(Qt.AlignCenter)
            deny.setWordWrap(True)
            conf_cl.addWidget(deny)
        scroll_layout.addWidget(conf_card)
        self._section_cards.append(conf_card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        self._scroll = scroll

        # ── Bandeau de validation (fixe, toujours visible en haut) ──
        self._val_banner = QWidget()
        self._val_banner.setAttribute(Qt.WA_StyledBackground, True)
        self._val_banner.setStyleSheet(
            f"background: {ds.p.surface_container_low if hasattr(ds.p, 'surface_container_low') else ds.p.surface_variant}; "
            f"border: 1px solid {ds.p.outline_variant}; border-radius: {ds.radius_md}px; "
            f"padding: {ds.space_sm}px;")
        val_banner_layout = QHBoxLayout(self._val_banner)
        val_banner_layout.setSpacing(ds.space_md)
        val_banner_layout.setContentsMargins(ds.space_md, ds.space_sm, ds.space_md, ds.space_sm)

        self._val_items: dict[str, tuple[QCheckBox, M3Label]] = {}
        for key, label, icon_name in [
            ("photo_valid", _("sec_main.kpi.no_photo"), "image"),
            ("parent_valid", _("sec_main.kpi.no_parent"), "person"),
            ("email_valid", _("sec_main.kpi.no_email"), "mail"),
            ("dossier_valid", _("sec_main.kpi.no_doc"), "description"),
        ]:
            item_box = QVBoxLayout()
            item_box.setSpacing(ds.space_xxs)
            item_box.setAlignment(Qt.AlignCenter)
            cb = QCheckBox(label)
            cb.setStyleSheet(f"color: {ds.p.text_strong}; font-size: {ds.font_label_lg}px; "
                           f"spacing: {ds.space_xs}px; font-weight: bold;")
            cb.toggled.connect(lambda checked, k=key: self._on_flag_toggled(k, checked))
            item_box.addWidget(cb, 0, Qt.AlignCenter)
            who_lbl = M3Label(_("student_form.not_validated"), style="label_small")
            who_lbl.setStyleSheet(f"color: {ds.p.text_disabled};")
            who_lbl.setAlignment(Qt.AlignCenter)
            item_box.addWidget(who_lbl, 0, Qt.AlignCenter)
            val_banner_layout.addLayout(item_box)
            self._val_items[key] = (cb, who_lbl)

        # Ajouter le bandeau AVANT le scroll dans le layout
        layout.addWidget(self._val_banner)
        layout.addWidget(scroll, 1)

        # ── Chronologie : popup modale (n'est plus un onglet) ──
        self._dossier_panel.timeline_requested.connect(self._open_timeline_dialog)
        self._timeline_page = self._dossier_panel.timeline

    @safe_slot("Unknown._restyle")
    def _restyle(self):
        # Scroll area
        if hasattr(self, "_scroll") and self._scroll:
            self._scroll.setStyleSheet(
                f"M3ScrollArea {{ background: {ds.p.background}; border: none; }}")
            if self._scroll.widget():
                self._scroll.widget().setStyleSheet(f"background: {ds.p.background};")
        # Cartes de section
        section_style = (
            f"M3Card {{ background: {ds.p.surface}; "
            f"border: 1px solid {ds.p.outline_variant}; "
            f"border-radius: {ds.radius_md}px; }}")
        for card in getattr(self, "_section_cards", []):
            card.setStyleSheet(section_style)
        # Tables
        for attr in ("_parents_table", "_evt_table"):
            t = getattr(self, attr, None)
            if t:
                t.setStyleSheet(ds.table_qss())
        # Photos
        for attr in ("_photo", "_photo_large"):
            p = getattr(self, attr, None)
            if p:
                p.setStyleSheet(f"background: {ds.p.primary_container}; border-radius: {ds.radius_sm}px;")
        # Champs texte
        for w in self._inp_fields():
            w.setStyleSheet(ds.flat_input_qss())
        # Champs date
        for w in self._date_fields():
            w.setStyleSheet(
                f"border: 1px solid {ds.p.outline}; border-radius: {ds.radius_xs}px; "
                f"padding: {ds.space_xs}px {ds.space_md}px; color: {ds.p.text_strong}; "
                f"background: {ds.p.surface}; "
                f"QDateEdit QLineEdit {{ color: {ds.p.text_strong}; background: {ds.p.surface}; }}")
            w.setMinimumWidth(ds.sp(SpacingToken.XXXL))
        # Header élève
        for lbl in (self._id_prenom, self._id_nom):
            lbl.setStyleSheet(f"font-weight: bold; color: {ds.p.text_strong};")
        for lbl in (self._id_classe, self._id_id):
            lbl.setStyleSheet(f"color: {ds.p.text_strong};")
        # Combo genre
        if hasattr(self, "_inp_genre") and self._inp_genre:
            self._inp_genre.setStyleSheet(
                f"border: 1px solid {ds.p.outline}; border-radius: {ds.radius_xs}px; "
                f"padding: {ds.space_xxs}px {ds.space_xs}px; min-width: {ds.window_width * 3 // 20}px; "
                f"color: {ds.p.text_strong};")
            self._inp_genre.setFixedWidth(ds.sp(SpacingToken.XXL) + ds.sp(SpacingToken.MD))
        if hasattr(self, "_addr_status") and self._addr_status:
            self._addr_status.setStyleSheet(f"color: {ds.p.text_disabled};")
        # Bandeau de validation
        if hasattr(self, "_val_banner") and self._val_banner:
            self._val_banner.setStyleSheet(
                f"background: {ds.p.surface_container_low if hasattr(ds.p, 'surface_container_low') else ds.p.surface_variant}; "
                f"border: 1px solid {ds.p.outline_variant}; border-radius: {ds.radius_md}px; "
                f"padding: {ds.space_sm}px;")
        if hasattr(self, "_save_btn") and self._save_btn:
            self._update_save_indicator()

    def _inp_fields(self):
        fields = []
        for attr in [
            "_inp_nom",
            "_inp_prenom",
            "_inp_email",
            "_inp_emailperso",
            "_inp_tel",
            "_inp_tel2",
            "_inp_addr2",
            "_inp_cp",
            "_inp_ville",
            "_inp_pays",
        ]:
            if hasattr(self, attr):
                fields.append(getattr(self, attr))
        return fields

    def _date_fields(self):
        fields = []
        for attr in ["_inp_date_joined", "_inp_date", "_inp_birthdate"]:
            if hasattr(self, attr):
                fields.append(getattr(self, attr))
        return fields

    _VALIDATION_KEY_MAP = {
        "photo_valid": "photo", "parent_valid": "parent",
        "email_valid": "email", "dossier_valid": "dossier",
    }
    _CHECK_LABELS = {
        "photo_valid":   ("sec_main.kpi.no_photo",  "student_form.check_photo"),
        "parent_valid":  ("sec_main.kpi.no_parent",  "student_form.check_parent"),
        "email_valid":   ("sec_main.kpi.no_email",   "student_form.check_email"),
        "dossier_valid": ("sec_main.kpi.no_doc",     "student_form.check_dossier"),
    }

    def _on_flag_toggled(self, key: str, checked: bool):
        if not db.is_server_connected:
            return
        """Enregistre le changement de flag de validation dans le JSONB."""
        log(f"_on_flag_toggled: key={key} checked={checked} sid={self._sid}")
        conn = db.server_conn
        if not conn:
            log("_on_flag_toggled: no DB connection")
            return
        from datetime import datetime as _dt
        jsonb_key = self._VALIDATION_KEY_MAP.get(key, key)
        entry = _json.dumps({"ok": checked, "by": session.user_id, "at": _dt.now().isoformat()})
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE larcauth_student SET validation = "
                "COALESCE(validation, '{}'::jsonb) || jsonb_build_object(%s, %s::jsonb) "
                "WHERE aecuser_ptr_id = %s",
                (jsonb_key, entry, self._sid))
            conn.commit()
            log(f"_on_flag_toggled: OK rowcount={cur.rowcount}")
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_on_flag_toggled: DB error: {e}")
            try:
                conn.rollback()
            except Exception:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                pass
            cb, _who = self._val_items.get(key, (None, None))
            if cb:
                cb.blockSignals(True)
                cb.setChecked(not checked)
                cb.blockSignals(False)
            return
        if key in self._val_items:
            _cb, who_lbl = self._val_items[key]
            # Changer le texte de la checkbox pour lever l'ambiguite
            prob_key, ok_key = self._CHECK_LABELS.get(key, (None, None))
            if prob_key and ok_key:
                _cb.setText(_(ok_key) if checked else _(prob_key))
                _cb.setStyleSheet(
                    f"color: {ds.p.success if checked else ds.p.error}; "
                    f"font-size: {ds.font_label_lg}px; spacing: {ds.space_xs}px; font-weight: bold;")
            if checked:
                who_lbl.setText(_("student_form.validated_by").format(name=session.full_name)
                               if session.full_name else _("student_form.validated"))
                who_lbl.setStyleSheet(f"color: {ds.p.success}; font-weight: bold;")
            else:
                who_lbl.setText(_("student_form.not_validated"))
                who_lbl.setStyleSheet(f"color: {ds.p.text_disabled};")
        self._update_photo_badge()

    def _refresh_val_banner(self):
        if not db.is_server_connected:
            return
        """Recharge les flags de validation et les noms des validateurs depuis la DB."""
        if not hasattr(self, "_val_items") or not self._val_items:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            import json as _json
            cur = conn.cursor()
            cur.execute(
                "SELECT validation FROM larcauth_student WHERE aecuser_ptr_id = %s", (self._sid,))
            row = cur.fetchone()
            val = row[0] if row and row[0] else {}
            if isinstance(val, str):
                val = _json.loads(val)
            user_ids = set()
            for flag_key, _checkbox_key in [
                ("dossier", "dossier_valid"), ("photo", "photo_valid"),
                ("email", "email_valid"), ("parent", "parent_valid"),
            ]:
                entry = val.get(flag_key, {}) if isinstance(val, dict) else {}
                if entry.get("ok") and entry.get("by"):
                    user_ids.add(int(entry["by"]))
            names: dict[int, str] = {}
            if user_ids:
                cur.execute(
                    "SELECT id, last_name || ' ' || first_name FROM larcauth_aecuser WHERE id IN %s",
                    (tuple(user_ids),))
                names = {uid: name for uid, name in cur.fetchall()}
            for flag_key, checkbox_key in [
                ("dossier", "dossier_valid"), ("photo", "photo_valid"),
                ("email", "email_valid"), ("parent", "parent_valid"),
            ]:
                if checkbox_key not in self._val_items:
                    continue
                cb, who_lbl = self._val_items[checkbox_key]
                # Retrocompatibilite : chercher sous flag_key, puis sous checkbox_key
                entry = (val.get(flag_key) or val.get(checkbox_key) or {}) if isinstance(val, dict) else {}
                ok = entry.get("ok", False) if isinstance(entry, dict) else False
                cb.blockSignals(True)
                cb.setChecked(bool(ok))
                cb.blockSignals(False)
                # Texte dynamique : probleme ou OK
                prob_key, ok_key = self._CHECK_LABELS.get(checkbox_key, (None, None))
                if prob_key and ok_key:
                    cb.setText(_(ok_key) if ok else _(prob_key))
                    cb.setStyleSheet(
                        f"color: {ds.p.success if ok else ds.p.error}; "
                        f"font-size: {ds.font_label_lg}px; spacing: {ds.space_xs}px; font-weight: bold;")
                if ok and entry.get("by"):
                    by_name = names.get(int(entry["by"]), "")
                    who_lbl.setText(_("student_form.validated_by").format(name=by_name) if by_name
                                   else _("student_form.validated"))
                    who_lbl.setStyleSheet(f"color: {ds.p.success}; font-weight: bold;")
                else:
                    who_lbl.setText(_("student_form.not_validated"))
                    who_lbl.setStyleSheet(f"color: {ds.p.text_disabled};")
            self._update_photo_badge()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentEditDialog._refresh_val_banner: {e}")

    def _update_photo_badge(self):
        """Colorie la vignette photo selon le taux de completion (0→rouge, 4→vert, entre→orange)."""
        if not hasattr(self, "_val_items") or not self._val_items:
            return
        checked_count = sum(1 for _, (cb, _) in self._val_items.items() if cb.isChecked())
        if checked_count == 0:
            photo_bg = ds.p.error_container if hasattr(ds.p, 'error_container') else "#fce4ec"
            photo_border = ds.p.error
        elif checked_count == 4:
            photo_bg = ds.p.surface
            photo_border = ds.p.success
        else:
            photo_bg = ds.p.secondary_container if hasattr(ds.p, 'secondary_container') else "#fff3e0"
            photo_border = ds.p.tertiary
        if hasattr(self, "_photo") and self._photo:
            self._photo.setStyleSheet(
                f"background: {photo_bg}; border-radius: {ds.radius_sm}px; "
                f"border: 3px solid {photo_border};")

    @safe_slot("Unknown._open_timeline_dialog")
    def _open_timeline_dialog(self):
        """Bouton « Chronologie » du rail Dossiers -> ouvre une popup modale."""
        self._dossier_panel.refresh_timeline()
        dlg = M3Dialog(self)
        dlg.setWindowTitle(_("dossier.timeline.title"))
        dlg.setMinimumSize(ds.golden_width(600), 600)
        dlg.setStyleSheet(f"background: {ds.p.surface};")
        layout = QVBoxLayout(dlg)
        layout.addWidget(self._timeline_page)
        buttons = M3DialogButtonBox(M3DialogButtonBox.Close)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        dlg.exec()

    # ── Indicateur « dossier modifié » ──

    @safe_slot("Unknown._mark_dirty")
    def _mark_dirty(self):
        """Une entrée du dossier a été ajoutée/modifiée/supprimée → dossier modifié.

        Connecté à DossierPanel.entries_changed : le dossier se met à jour en
        temps réel, même sans changer d'onglet. L'indicateur ne bascule qu'une
        fois (pas de rafraîchissement inutile à chaque signal).
        """
        if not self._dirty:
            self._dirty = True
            self._update_save_indicator()

    def _update_save_indicator(self):
        """Affiche/masque l'indicateur « modifications non enregistrées ».

        Texte seul (aucun QSS dur) : le libellé du bouton Enregistrer change,
        les couleurs restent celles du variant FILLED actif (thème réactif).
        """
        if not hasattr(self, "_save_btn") or self._save_btn is None:
            return
        if self._dirty:
            self._save_btn.setText(_("student_form.save_changes"))
        else:
            self._save_btn.setText(_("student_form.save"))

    def _get_class_language(self, classroom_id: int) -> int | None:
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return None
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT l.fk_language_id
                FROM larcauth_classroom c
                JOIN larcauth_level l ON l.id = c.fk_level_id
                WHERE c.id = %s
            """,
                (classroom_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentEditDialog._get_class_language: {e}")
            return None

    def _load_genders(self, lang_id: int | None = None, include_gid: int | None = None):
        if not db.is_server_connected:
            return
        self._inp_genre.clear()
        self._inp_genre.addItem(_("student_form.gender_not_specified"), 0)
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            if lang_id:
                cur.execute("SELECT id, label FROM larcauth_gender WHERE fk_language_id = %s ORDER BY id", (lang_id,))
            else:
                cur.execute("SELECT id, label FROM larcauth_gender ORDER BY id")
            loaded = set()
            for gid, label in cur.fetchall():
                self._inp_genre.addItem(label, gid)
                loaded.add(gid)
            # Si le genre existant de l'élève n'est pas dans la langue, l'ajouter
            if include_gid is not None and include_gid not in loaded:
                cur.execute("SELECT label FROM larcauth_gender WHERE id = %s", (include_gid,))
                row = cur.fetchone()
                if row:
                    self._inp_genre.addItem(row[0], include_gid)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentEditDialog._load_genders: {e}")

    def _load_data(self):
        """Pré-remplit le formulaire avec les données existantes."""
        d = self._data
        sid = d["id"]

        # Photo
        px = QPixmap(get_photo_path(sid))
        if px.isNull():
            px = _make_avatar(d["last_name"], d["first_name"], 120)
        else:
            px = px.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._photo.setPixmap(px)

        # Identité — Nom en majuscules, prénom en plus grand
        self._id_prenom.setText(d.get("first_name", "") or "")
        self._id_nom.setText((d.get("last_name", "") or "").upper())
        self._id_classe.setText(_("student_form.class_label").format(label=d.get("classroom", "—")))
        self._id_id.setText(_("student_form.id_label").format(id=sid))

        # Champs
        self._inp_nom.setText(d.get("last_name", ""))
        self._inp_prenom.setText(d.get("first_name", ""))
        self._inp_email.setText(d.get("email", ""))
        self._inp_emailperso.setText(d.get("emailperso", "") or "")
        self._inp_tel.setText(d.get("tel_smartphone_1", "") or "")
        self._inp_tel2.setText(d.get("tel_maison", "") or "")
        raw_joined = d.get("date_joined", "")
        if raw_joined:
            self._inp_date_joined.setDate(QDate.fromString(str(raw_joined), "yyyy-MM-dd"))
        else:
            self._inp_date_joined.setDate(QDate())
        raw_date = d.get("date_entree", "")
        if raw_date:
            self._inp_date.setDate(QDate.fromString(str(raw_date), "yyyy-MM-dd"))
        else:
            self._inp_date.setDate(QDate())
        raw_birth = d.get("date_of_birth", "")
        if raw_birth:
            self._inp_birthdate.setDate(QDate.fromString(str(raw_birth), "yyyy-MM-dd"))
        else:
            self._inp_birthdate.setDate(QDate())
        # Recharger les genres selon la langue de la classe
        classroom_id = d.get("s_classroom_id")
        current_gid = d.get("fk_gender_id")
        if classroom_id:
            lang_id = self._get_class_language(classroom_id)
            self._load_genders(lang_id, include_gid=current_gid)
        gid = current_gid or 0
        idx = self._inp_genre.findData(gid)
        if idx >= 0:
            self._inp_genre.setCurrentIndex(idx)
        self._inp_addr1.setPlainText(d.get("address_line1", "") or "")
        self._inp_addr2.setText(d.get("address_line2", "") or "")
        self._inp_cp.setText(d.get("postal_code", "") or "")
        self._inp_ville.setText(d.get("city", "") or "")
        self._inp_pays.setText(d.get("country", "") or _("student_form.default_country"))
        raw_notes_json = d.get("notes_json") or None
        if raw_notes_json:
            if isinstance(raw_notes_json, str):
                try:
                    raw_notes_json = _json.loads(raw_notes_json)
                except _json.JSONDecodeError:
                    raw_notes_json = None
        if raw_notes_json and isinstance(raw_notes_json, dict):
            self._dossier_panel.set_data(raw_notes_json)
        else:
            # Fallback : importer les anciennes notes TEXT dans la section Autre
            old_notes = d.get("notes", "") or ""
            if old_notes:
                old_data = {
                    "autre": {
                        "intro": "<p>Notes importées de l'ancien système.</p>",
                        "entries": [
                            {
                                "no": 1,
                                "date": "",
                                "titre": "Anciennes notes",
                                "doc": old_notes[:500] + ("…" if len(old_notes) > 500 else ""),
                            }
                        ],
                    }
                }
                self._dossier_panel.set_data(old_data)
            else:
                self._dossier_panel.clear()

        # Initialiser les dossiers de fichiers
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "students", str(self._sid))
        dossiers_dir = os.path.join(base_dir, "dossiers")
        os.makedirs(dossiers_dir, exist_ok=True)
        conf_dir = os.path.join(base_dir, "confidentiel")
        os.makedirs(conf_dir, exist_ok=True)
        self._dossier_panel.set_directory(dossiers_dir)
        if hasattr(self, "_conf_panel"):
            self._conf_panel.set_directory(conf_dir)
            conf = raw_notes_json.get("confidentiel", {}) if isinstance(raw_notes_json, dict) else {}
            self._conf_panel.load_entries(conf.get("entries", []))

        # Charger les flags de validation dans le bandeau
        if hasattr(self, "_val_items") and self._val_items:
            self._refresh_val_banner()

        self._load_parents()
        self._load_events()

        # Fiche santé : vit dans la section Médical du dossier
        health = raw_notes_json.get("health", {}) if isinstance(raw_notes_json, dict) else {}
        self._dossier_panel.set_health(health)

        # Grande photo pour l'onglet Photos
        px_large = QPixmap(get_photo_path(sid))
        if px_large.isNull():
            px_large = _make_avatar(d["last_name"], d["first_name"], 240)
        else:
            px_large = px_large.scaled(240, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._photo_large.setPixmap(px_large)


    def _load_parents(self):
        if not db.is_server_connected:
            return
        self._parent_ids = []
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT sp.parent_id,
                       aec.last_name || ' ' || aec.first_name AS name,
                       COALESCE(sp.nature, par.nature, 'parent'),
                       aec.email,
                       COALESCE(aec.tel_smartphone_1, aec.tel_maison, '')
                FROM larcauth_student_parent sp
                JOIN larcauth_aecuser aec ON aec.id = sp.parent_id
                LEFT JOIN larcauth_parent par ON par.aecuser_ptr_id = aec.id
                WHERE sp.student_id = %s
                ORDER BY aec.last_name
            """,
                (self._sid,),
            )
            rows = list(cur.fetchall())
            self._parent_ids = []
            self._parents_table.setRowCount(len(rows))
            for i, (pid, name, nat, em, tel) in enumerate(rows):
                self._parent_ids.append(pid)
                self._parents_table.setItem(i, 0, QTableWidgetItem(name))
                self._parents_table.setItem(i, 1, QTableWidgetItem(nat or ""))
                self._parents_table.setItem(i, 2, QTableWidgetItem(em or ""))
                self._parents_table.setItem(i, 3, QTableWidgetItem(tel or ""))
            self._parents_table.resizeColumnsToContents()
            self._parents_table.selectRow(0)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentEditDialog._load_parents: {e}")

    def _load_events(self):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT se.event_at, se.event_type, se.note,
                       aec.last_name || ' ' || aec.first_name AS author,
                       CASE WHEN se.validated_by IS NOT NULL THEN '✓' ELSE '—' END
                FROM student_event se
                JOIN larcauth_aecuser aec ON aec.id = se.created_by
                WHERE se.student_id = %s
                ORDER BY se.event_at DESC LIMIT 100
            """,
                (self._sid,),
            )
            rows = cur.fetchall()
            self._evt_table.setRowCount(len(rows))
            for i, (evt_at, etype, note, author, validated) in enumerate(rows):
                self._evt_table.setItem(i, 0, QTableWidgetItem(str(evt_at)[:16]))
                it = QTableWidgetItem(_event_label(etype))
                it.setForeground(QColor(_event_color(etype)))
                self._evt_table.setItem(i, 1, it)
                self._evt_table.setItem(i, 2, QTableWidgetItem(note or ""))
                self._evt_table.setItem(i, 3, QTableWidgetItem(author))
                self._evt_table.setItem(i, 4, QTableWidgetItem(validated))
            self._evt_table.resizeColumnsToContents()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentEditDialog._load_events: {e}")

    @safe_slot("StudentEditDialog.save")
    def _save(self):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("student_form.error.no_connection"))
            return
        try:
            cur = conn.cursor()
            from datetime import datetime

            now = datetime.now().isoformat()

            aec = {
                "last_name": self._inp_nom.text().strip(),
                "first_name": self._inp_prenom.text().strip(),
                "email": self._inp_email.text().strip() or "",
                "emailperso": self._inp_emailperso.text().strip() or None,
                "tel_smartphone_1": self._inp_tel.text().strip() or None,
                "tel_maison": self._inp_tel2.text().strip() or None,
                "date_joined": (
                    self._inp_date_joined.date().toString("yyyy-MM-dd")
                    if self._inp_date_joined.date().isValid() and not self._inp_date_joined.date().isNull()
                    else None
                ),
                "date_entree": (
                    self._inp_date.date().toString("yyyy-MM-dd") if self._inp_date.date().isValid() and not self._inp_date.date().isNull() else None
                ),
                "date_of_birth": (
                    self._inp_birthdate.date().toString("yyyy-MM-dd")
                    if self._inp_birthdate.date().isValid() and not self._inp_birthdate.date().isNull()
                    else None
                ),
                "fk_gender_id": self._inp_genre.currentData() or None,
                "updated": now,
            }
            cur.execute(
                "UPDATE larcauth_aecuser SET " + ", ".join(f"{k}=%s" for k in aec) + " WHERE id=%s",
                list(aec.values()) + [self._sid],
            )
            if cur.rowcount == 0:
                raise ValueError(f"Aucun enregistrement trouve pour l'ID {self._sid}")

            addr = {
                "address_line1": self._inp_addr1.toPlainText().strip() or None,
                "address_line2": self._inp_addr2.text().strip() or None,
                "postal_code": self._inp_cp.text().strip() or None,
                "city": self._inp_ville.text().strip() or None,
                "country": self._inp_pays.text().strip() or None,
            }
            fid = self._data.get("fk_foyer_id") or self._sid
            cols = list(addr.keys())
            vals = list(addr.values())
            cur.execute(
                "INSERT INTO foyer (id, "
                + ", ".join(cols)
                + ") VALUES (%s, "
                + ", ".join("%s" for _i in cols)
                + ") ON CONFLICT (id) DO UPDATE SET "
                + ", ".join(f"{k}=EXCLUDED.{k}" for k in cols),
                [fid] + vals,
            )
            notes_data = self._dossier_panel.get_data()
            notes_data["health"] = self._dossier_panel.get_health()
            if hasattr(self, "_conf_panel"):
                notes_data["confidentiel"] = {"intro": "", "entries": self._conf_panel.get_entries()}
            notes_json = _json.dumps(notes_data)
            cur.execute(
                "UPDATE larcauth_student SET notes_json = %s WHERE aecuser_ptr_id = %s",
                (notes_json, self._sid),
            )
            if cur.rowcount == 0:
                raise ValueError(f"Aucun etudiant trouve pour l'ID {self._sid}")

            cur.execute("SET LOCAL app.sync_source = 'intranet'")
            cur.execute(f"SET LOCAL app.modified_by = {session.user_id}")
            changes = []
            for k in aec:
                old_v = str(self._data.get(k, ""))
                new_v = str(aec[k] or "")
                if old_v != new_v:
                    changes.append(k)
            if changes:
                audit.update_student(self._sid, f"Modifiés : {', '.join(changes)}")
            elif any(v is not None for v in addr.values()):
                audit.update_student(self._sid, "Adresse modifiée")

            conn.commit()
            log(f"StudentEditDialog: saved #{self._sid}")
            # Dossier sauvegardé → l'indicateur « Enregistrer » s'éteint.
            self._dirty = False
            self._update_save_indicator()

            QMessageBox.information(self, _("common.label.success"), _("student_form.success_updated"))
            self.accept()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            conn.rollback()
            log(f"StudentEditDialog._save: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    # ── Notes (formatage HTML) — supprimé, remplacé par NotesPanel JSON

    # ── Fichiers élèves ──

    def _student_dir(self) -> str:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "students")
        d = os.path.join(base, str(self._sid))
        os.makedirs(d, exist_ok=True)
        return d

    @safe_slot("StudentEditDialog.copy_parent_address")
    def _copy_parent_address(self):
        if not db.is_server_connected:
            return
        sel = self._parents_table.selectedItems()
        if not sel or not self._parent_ids:
            QMessageBox.warning(self, _("student_form.copy_address_title"), _("student_form.copy_address_none"))
            return
        row = sel[0].row()
        if row >= len(self._parent_ids):
            return
        pid = self._parent_ids[row]
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT address_line1, address_line2, postal_code, city, country
                FROM foyer WHERE id = %s
            """,
                (pid,),
            )
            row = cur.fetchone()
            if row and any(row):
                addr1, addr2, cp, ville, pays = row
                self._inp_addr1.setPlainText(addr1 or "")
                self._inp_addr2.setText(addr2 or "")
                self._inp_cp.setText(cp or "")
                self._inp_ville.setText(ville or "")
                if pays:
                    self._inp_pays.setText(pays)
                log(f"Copied address from parent #{pid} to student #{self._sid}")
                if hasattr(self, "_addr_status") and self._addr_status:
                    self._addr_status.hide()
            else:
                if hasattr(self, "_addr_status") and self._addr_status:
                    self._addr_status.setText(_("student_form.copy_address_no_address"))
                    self._addr_status.show()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentEditDialog._copy_parent_address: {e}")

    # ──── Ajouter un événement ────

    @safe_slot("StudentEditDialog.on_add_event")
    def _on_add_event(self):
        """Ouvre le dialogue d'ajout d'événement pour cet élève."""
        from LarcSecretaire.views.supervisor_panel import EventDialog

        dlg = EventDialog(
            self._sid,
            f"{self._data.get('last_name', '?')} {self._data.get('first_name', '?')}",
            self,
        )
        if dlg.exec():
            self._load_events()  # Recharger le tableau

    # ──── Changer la photo ────

    @safe_slot("StudentEditDialog.on_change_photo")
    def _on_change_photo(self):
        """Ouvre un FileDialog pour changer la photo de l'élève."""
        path, _f = QFileDialog.getOpenFileName(
            self,
            _("student_form.select_photo"),
            "",
            _("student_form.photo_filter"),
        )
        if not path:
            return
        from LarcSecretaire.common.photos import save_photo

        try:
            save_photo(self._sid, path)
            # Recharger les deux affichages (petite + grande photo)
            px = QPixmap(get_photo_path(self._sid))
            if not px.isNull():
                px_small = px.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._photo.setPixmap(px_small)
                px_large = px.scaled(240, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._photo_large.setPixmap(px_large)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentEditDialog._on_change_photo: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    # ──── Charger les notes/résultats ────

    # ──── Accès répertoires drive (relevés / bulletins) ────

    @safe_slot("StudentEditDialog.open_drive_dir")
    def _open_drive_dir(self, path: str):
        """Ouvre le répertoire intranet dans l'Explorateur (créé s'il manque)."""
        import subprocess

        path = path or ""
        if not path:
            QMessageBox.information(self, _("common.dialog.info_title"), _("student_form.drive_dir_missing"))
            return
        try:
            os.makedirs(path, exist_ok=True)
            subprocess.Popen(["explorer", path])
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentEditDialog._open_drive_dir: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    @safe_slot("StudentEditDialog.open_drive_cloud")
    def _open_drive_cloud(self, url: str):
        """Ouvre l'URL cloud (Supabase Storage) dans le navigateur par défaut."""
        import webbrowser

        if not url:
            QMessageBox.information(self, _("common.dialog.info_title"), _("student_form.drive_url_missing"))
            return
        webbrowser.open(url)

    @safe_slot("StudentEditDialog.add_parent_link")
    def _add_parent_link(self):
        if not db.is_server_connected:
            return
        dlg = M3Dialog(self)
        dlg.setWindowTitle(_("student_form.add_parent"))
        dlg.setMinimumSize(ds.window_height * 7 // 8, ds.window_height * 5 // 8)
        dlg.setStyleSheet(f"background: {ds.p.surface}; color: {ds.p.text_strong};")
        layout = QVBoxLayout(dlg)
        layout.setSpacing(ds.space_sm)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)

        layout.addWidget(M3Label(_("student_form.search_parent_label"), style="title_small"))

        search_inp = M3TextField()
        search_inp.setPlaceholderText(_("student_form.search_parent_placeholder"))
        search_inp.setStyleSheet(ds.flat_input_qss())
        search_inp.setMinimumHeight(ds.field_height)
        layout.addWidget(search_inp)

        # Combo au lieu de ListWidget — plus simple a selectionner
        parent_combo = M3ComboBox()
        parent_combo.setMinimumHeight(ds.field_height)
        parent_combo.setStyleSheet(
            f"border: 1px solid {ds.p.outline}; border-radius: {ds.radius_xs}px; "
            f"padding: {ds.space_xs}px; min-width: {ds.workspace_sidebar_width}px;")
        layout.addWidget(parent_combo)

        self._search_parents_data = []

        def on_search(text):
            if not db.is_server_connected:
                return
            if len(text.strip()) < 2:
                parent_combo.clear()
                self._search_parents_data.clear()
                return
            conn = db.server_conn
            if not conn:
                return
            try:
                cur = conn.cursor()
                q = "%" + text.strip() + "%"
                cur.execute(
                    """
                    SELECT aec.id, aec.last_name, aec.first_name, aec.email
                    FROM larcauth_aecuser aec
                    JOIN larcauth_parent par ON par.aecuser_ptr_id = aec.id
                    WHERE aec.is_active = TRUE
                      AND par.enabled = TRUE
                      AND (LOWER(aec.last_name) LIKE LOWER(%s)
                           OR LOWER(aec.first_name) LIKE LOWER(%s)
                           OR LOWER(aec.email) LIKE LOWER(%s))
                      AND aec.id NOT IN (
                           SELECT parent_id FROM larcauth_student_parent WHERE student_id = %s)
                    ORDER BY aec.last_name, aec.first_name
                    LIMIT 50
                """,
                    (q, q, q, self._sid),
                )
                parent_combo.clear()
                self._search_parents_data.clear()
                for pid, ln, fn, em in cur.fetchall():
                    disp = f"{ln or ''} {fn or ''} ({em or 'pas d e-mail'})"
                    parent_combo.addItem(disp, pid)
                    self._search_parents_data.append(pid)
            except Exception as e:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                log(f"_add_parent_link search: {e}")

        search_inp.textChanged.connect(on_search)

        buttons = M3DialogButtonBox(M3DialogButtonBox.Ok | M3DialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() == M3Dialog.Accepted:
            pid = parent_combo.currentData()
            if not pid:
                QMessageBox.warning(self, _("student_form.add_parent"),
                                    _("parent.error.no_parent_selected"))
                return
            conn = db.server_conn
            if not conn:
                return
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO larcauth_student_parent (student_id, parent_id) "
                    "VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (self._sid, pid))
                log(f"Linked parent #{pid} to student #{self._sid}")
            except Exception as e:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                log(f"_add_parent_link insert: {e}")
                QMessageBox.critical(self, _("common.dialog.error_title"), str(e))
            self._load_parents()

    @safe_slot("StudentEditDialog.edit_parent_nature")
    def _edit_parent_nature(self):
        if not db.is_server_connected:
            return
        sel = self._parents_table.selectedItems()
        if not sel or not self._parent_ids:
            QMessageBox.warning(self, _("student_form.nature_dialog_title"), _("parent.error.no_parent_selected"))
            return
        row = sel[0].row()
        if row >= len(self._parent_ids):
            return
        pid = self._parent_ids[row]
        nature, ok = QInputDialog.getText(self, _("student_form.nature_prompt_title"), _("student_form.nature_prompt_msg"))
        if not ok:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE larcauth_student_parent SET nature = %s WHERE student_id = %s AND parent_id = %s",
                (nature.strip(), self._sid, pid),
            )
            log(f"Updated nature for parent #{pid} of student #{self._sid}: {nature.strip()}")
            self._load_parents()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_edit_parent_nature: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    @safe_slot("StudentEditDialog.remove_parent_link")
    def _remove_parent_link(self):
        if not db.is_server_connected:
            return
        sel = self._parents_table.selectedItems()
        if not sel or not self._parent_ids:
            QMessageBox.warning(self, _("student_form.remove_parent"), _("parent.error.no_parent_selected"))
            return
        row = sel[0].row()
        if row >= len(self._parent_ids):
            return
        pid = self._parent_ids[row]
        confirm = QMessageBox.question(
            self,
            _("student_form.remove_confirm_title"),
            _("student_form.remove_confirm_msg"),
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM larcauth_student_parent WHERE student_id = %s AND parent_id = %s", (self._sid, pid))
            log(f"Removed parent #{pid} from student #{self._sid}")
            self._load_parents()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_remove_parent_link: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    def _build_full_html(self) -> str:
        if not db.is_server_connected:
            return
        d = self._data
        parts = ["<html><head><meta charset='utf-8'></head><body>"]

        def esc(s):
            import html

            return html.escape(str(s or ""))

        # En-tête
        parts.append(f"<h1>{esc(d.get('last_name', ''))} {esc(d.get('first_name', ''))}</h1>")
        parts.append("<table cellpadding='3' cellspacing='0' style='margin-bottom:12px;'>")
        parts.append(
            f"<tr><td><b>ID</b></td><td>{esc(d.get('id', ''))}</td><td style='padding-left:24px;'><b>Classe</b></td><td>{esc(d.get('classroom', ''))}</td></tr>"
        )
        parts.append(
            f"<tr><td><b>Date naissance</b></td><td>{esc(d.get('date_of_birth', ''))}</td>"
            f"<td style='padding-left:24px;'><b>Date entrée</b></td><td>{esc(d.get('date_entree', ''))}</td></tr>"
        )

        # Genre — requêter le label depuis la DB
        gid = d.get("fk_gender_id")
        gender_label = ""
        if gid:
            try:
                cur = db.server_conn.cursor()
                cur.execute("SELECT label FROM larcauth_gender WHERE id = %s", (gid,))
                row = cur.fetchone()
                if row:
                    gender_label = row[0]
            except Exception:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                pass
        parts.append(
            f"<tr><td><b>Genre</b></td><td>{esc(gender_label)}</td>"
            f"<td style='padding-left:24px;'><b>ID Foyer</b></td><td>{esc(d.get('fk_foyer_id', ''))}</td></tr>"
        )
        parts.append("</table>")

        # Contact
        parts.append("<h2>Contact</h2>")
        parts.append("<table cellpadding='3' cellspacing='0' style='margin-bottom:12px;'>")
        parts.append(f"<tr><td><b>Email</b></td><td>{esc(d.get('email', ''))}</td></tr>")
        parts.append(f"<tr><td><b>Email personnel</b></td><td>{esc(d.get('emailperso', ''))}</td></tr>")
        parts.append(f"<tr><td><b>Téléphone portable</b></td><td>{esc(d.get('tel_smartphone_1', ''))}</td></tr>")
        parts.append(f"<tr><td><b>Téléphone fixe</b></td><td>{esc(d.get('tel_maison', ''))}</td></tr>")
        parts.append("</table>")

        # Adresse
        parts.append("<h2>Adresse</h2>")
        parts.append(
            f"<p>{esc(d.get('address_line1', ''))}<br>"
            f"{esc(d.get('address_line2', ''))}<br>"
            f"{esc(d.get('postal_code', ''))} {esc(d.get('city', ''))}<br>"
            f"{esc(d.get('country', ''))}</p>"
        )

        # Parents
        parts.append("<h2>Parents / Tuteurs</h2>")
        if self._parents_table.rowCount() > 0:
            parts.append("<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;width:100%;margin-bottom:12px;'>")
            parts.append("<tr><th>Nom</th><th>Nature</th><th>Email</th><th>Téléphone</th></tr>")
            for i in range(self._parents_table.rowCount()):

                def _cell(col):
                    item = self._parents_table.item(i, col)
                    return esc(item.text()) if item and item.text() else ""

                parts.append(f"<tr><td>{_cell(0)}</td><td>{_cell(1)}</td><td>{_cell(2)}</td><td>{_cell(3)}</td></tr>")
            parts.append("</table>")
        else:
            parts.append("<p><i>Aucun parent/tuteur enregistré.</i></p>")

        # Notes structurées
        parts.append("<h2>Notes</h2>")
        section_labels = {
            "confidentielle": _("notes.section.confidential"),
            "medicale": _("notes.section.medical"),
            "pedagogique": _("notes.section.pedagogic"),
            "administrative": _("notes.section.administrative"),
            "communication": _("notes.section.communication"),
            "orientation": _("notes.section.orientation"),
            "autre": _("notes.section.other"),
        }
        notes_data = self._notes_panel.get_json() if hasattr(self, "_notes_panel") else {}
        has_notes = False
        for key, label in section_labels.items():
            sec = notes_data.get(key, {})
            raw_intro = (sec.get("intro") or "").strip()
            entries = sec.get("entries", [])
            if not raw_intro and not any(e.get("titre") or e.get("doc") for e in entries):
                continue
            has_notes = True
            parts.append(f"<h3>{esc(label)}</h3>")
            if raw_intro:
                parts.append(f"<div>{raw_intro}</div>")
            if entries:
                parts.append("<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;width:100%;margin-bottom:8px;'>")
                parts.append("<tr><th>N°</th><th>Date</th><th>Titre</th><th>Document / Note</th></tr>")
                for e in entries:
                    if e.get("titre") or e.get("doc") or e.get("date"):
                        parts.append(
                            f"<tr><td>{esc(e.get('no', ''))}</td><td>{esc(e.get('date', ''))}</td>"
                            f"<td>{esc(e.get('titre', ''))}</td><td>{esc(e.get('doc', ''))}</td></tr>"
                        )
                parts.append("</table>")
        if not has_notes:
            parts.append("<p><i>Aucune note.</i></p>")

        # Événements
        parts.append("<h2>Événements</h2>")
        if self._evt_table.rowCount() > 0:
            parts.append("<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;width:100%;margin-bottom:12px;'>")
            parts.append("<tr><th>Date/Heure</th><th>Type</th><th>Note</th><th>Par</th><th>Validé</th></tr>")
            for i in range(self._evt_table.rowCount()):

                def _ecell(col):
                    item = self._evt_table.item(i, col)
                    return esc(item.text()) if item and item.text() else ""

                parts.append(f"<tr><td>{_ecell(0)}</td><td>{_ecell(1)}</td><td>{_ecell(2)}</td><td>{_ecell(3)}</td><td>{_ecell(4)}</td></tr>")
            parts.append("</table>")
        else:
            parts.append("<p><i>Aucun événement.</i></p>")

        parts.append("</body></html>")
        return "\n".join(parts)

    @safe_slot("StudentEditDialog.export_pdf")
    def _export_pdf(self):
        html = self._build_full_html()
        d = self._data
        default_name = _("student_form.export_pdf_file").format(last=d.get("last_name", ""), first=d.get("first_name", ""))
        path, _f = QFileDialog.getSaveFileName(self, _("student_form.pdf"), default_name, "Fichier PDF (*.pdf)")
        if not path:
            return
        try:
            doc = QTextDocument()
            doc.setHtml(html)
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)
            printer.setPageSize(QPrinter.A4)
            doc.print_(printer)
            log(f"Export PDF #{d['id']}: {path}")
            QMessageBox.information(self, _("student_form.pdf"), _("student_form.export_pdf_success").format(path=path))
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"Export PDF error: {e}")
            QMessageBox.critical(self, _("student_form.export_pdf_error"), str(e))

    @safe_slot("StudentEditDialog.export_word")
    def _export_word(self):
        html = self._build_full_html()
        d = self._data
        default_name = _("student_form.export_word_file").format(last=d.get("last_name", ""), first=d.get("first_name", ""))
        path, _f = QFileDialog.getSaveFileName(self, _("student_form.word"), default_name, "Document HTML (*.html *.htm)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            log(f"Export Word #{d['id']}: {path}")
            QMessageBox.information(self, _("student_form.word"), _("student_form.export_word_success").format(path=path))
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"Export Word error: {e}")
            QMessageBox.critical(self, _("student_form.export_word_error"), str(e))


# ──────────────────────────────────────────────
#   StudentCreateDialog — Création d'un élève
# ──────────────────────────────────────────────


class StudentCreateDialog(ThemedDialog):
    """
    Fenêtre de création d'élève — grand formulaire, polices larges.

    Le slot libre est détecté automatiquement.
    ID = classroom_id × 100 + slot (gabarit).
    """

    def __init__(self, parent=None, preselected_class: int | None = None):
        super().__init__(parent)
        self.setWindowTitle(_("student_form.new_student_title"))
        # 987×610 = paire dorée (610 = sidebar + golden_width(sidebar) ; 987 = golden_width(610))
        _min_h = ds.sidebar_width + ds.golden_width(ds.sidebar_width)  # 610
        self.setMinimumSize(ds.golden_width(_min_h), _min_h)  # 987×610
        self._result_data: dict | None = None
        self._class_id: int | None = None
        self._next_free: int | None = None
        self._sid: int | None = None
        self._parent_ids: list[int] = []
        self._search_parents_data: list[int] = []
        self._classes: list[tuple] = []
        self._class_btns: dict[int, M3Button] = {}
        self._preselected_class = preselected_class
        self._init_ui()
        self._load_classes()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(ds.space_md)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)

        self._class_title = M3Label(_("student_form.new_student_label"), style="title_small")
        layout.addWidget(self._class_title)

        if self._preselected_class:
            self._class_info = M3Label(style="body_medium")
            self._class_info.setStyleSheet(f"padding-bottom: {ds.space_xs}px;")
            layout.addWidget(self._class_info)
            self._class_grid = None
        else:
            cl_label = M3Label(_("student_form.class_selector"), style="label_small")
            cl_label.setStyleSheet(f"font-weight: bold; color: {ds.p.text_strong};")
            layout.addWidget(cl_label)
            self._class_grid = M3Frame()
            self._class_grid_layout = QVBoxLayout(self._class_grid)
            self._class_grid_layout.setContentsMargins(0, 0, 0, 0)
            self._class_grid_layout.setSpacing(ds.space_xxs)
            layout.addWidget(self._class_grid)

        # Photo + identité + boutons (toujours visibles)
        photo_row = QHBoxLayout()
        self._photo = QLabel()
        self._photo.setFixedSize(ds.sp(SpacingToken.XXXL), ds.sp(SpacingToken.XXXL))
        self._photo.setStyleSheet(f"background: {ds.p.primary_container}; border-radius: {ds.radius_sm}px;")
        self._photo.setAlignment(Qt.AlignCenter)
        photo_row.addWidget(self._photo)

        id_col = QVBoxLayout()
        id_col.setSpacing(ds.space_xxs)
        # Ligne 1 : PRÉNOM (plus grand) + NOM (majuscules) — live depuis les champs
        name_row = QHBoxLayout()
        name_row.setSpacing(ds.space_sm)
        self._id_prenom = M3Label("", style="headline_large")
        self._id_prenom.setStyleSheet(f"font-weight: bold; color: {ds.p.text_strong};")
        name_row.addWidget(self._id_prenom)
        self._id_nom = M3Label("", style="title_large")
        self._id_nom.setStyleSheet(f"font-weight: bold; color: {ds.p.text_strong};")
        name_row.addWidget(self._id_nom)
        name_row.addStretch()
        id_col.addLayout(name_row)
        # Ligne 2 : Classe
        self._id_classe = M3Label("", style="body_medium")
        self._id_classe.setStyleSheet(f"color: {ds.p.text_strong};")
        id_col.addWidget(self._id_classe)
        # Ligne 3 : Id
        self._id_id = M3Label("", style="body_medium")
        self._id_id.setStyleSheet(f"color: {ds.p.text_strong};")
        id_col.addWidget(self._id_id)
        id_col.addStretch()
        photo_row.addLayout(id_col, 1)

        # Boutons d'action verticaux à droite
        btn_col = QVBoxLayout()
        btn_col.setSpacing(ds.space_sm)

        self._create_btn = M3Button(_("student_form.create_button"), variant=ButtonVariant.FILLED)
        self._create_btn.setEnabled(False)
        self._create_btn.clicked.connect(self._on_create)
        self._create_btn.setMinimumWidth(ds.sp(SpacingToken.XXL))
        btn_col.addWidget(self._create_btn)

        self._cancel_btn = M3Button(_("student_form.cancel_button"), variant=ButtonVariant.OUTLINED)
        self._cancel_btn.clicked.connect(self.reject)
        self._cancel_btn.setMinimumWidth(ds.sp(SpacingToken.XXL))
        btn_col.addWidget(self._cancel_btn)

        btn_col.addStretch()
        photo_row.addLayout(btn_col)

        layout.addLayout(photo_row)

        def _lbl(t):
            lbl = M3Label(t, style="body_medium")
            lbl.setStyleSheet(f"font-weight: bold; color: {ds.p.text_strong};")
            lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
            return lbl

        # Champs (créés avant les onglets)
        self._inp_nom = M3TextField()
        self._inp_nom.setStyleSheet(ds.flat_input_qss())
        self._inp_nom.setPlaceholderText(_("student_form.last_name_placeholder"))
        self._inp_prenom = M3TextField()
        self._inp_prenom.setStyleSheet(ds.flat_input_qss())
        self._inp_prenom.setPlaceholderText(_("student_form.first_name_placeholder"))
        self._inp_email = M3TextField()
        self._inp_email.setStyleSheet(ds.flat_input_qss())
        self._inp_email.setPlaceholderText(_("student_form.email_placeholder"))
        self._inp_emailperso = M3TextField()
        self._inp_emailperso.setStyleSheet(ds.flat_input_qss())
        self._inp_emailperso.setPlaceholderText(_("student_form.email_personal_placeholder"))
        self._inp_tel = M3TextField()
        self._inp_tel.setStyleSheet(ds.flat_input_qss())
        self._inp_tel.setPlaceholderText(_("student_form.phone_placeholder"))
        self._inp_tel2 = M3TextField()
        self._inp_tel2.setStyleSheet(ds.flat_input_qss())
        self._inp_tel2.setPlaceholderText(_("student_form.phone_fixed_placeholder"))
        self._inp_date_joined = M3DateEdit()
        self._inp_date_joined.setDisplayFormat("yyyy-MM-dd")
        self._inp_date_joined.setCalendarPopup(True)
        self._inp_date_joined.setDate(QDate.currentDate())
        self._inp_date_joined.setStyleSheet(
            f"border: 1px solid {ds.p.outline}; border-radius: {ds.radius_xs}px; padding: {ds.space_xs}px {ds.space_sm}px; color: {ds.p.text_strong};"
        )
        self._inp_date = M3DateEdit()
        self._inp_date.setDisplayFormat("yyyy-MM-dd")
        self._inp_date.setCalendarPopup(True)
        self._inp_date.setDate(QDate.currentDate())
        self._inp_date.setStyleSheet(f"border: 1px solid {ds.p.outline}; border-radius: {ds.radius_xs}px; padding: {ds.space_xs}px {ds.space_sm}px; color: {ds.p.text_strong};")
        self._inp_genre = M3ComboBox()
        self._inp_genre.setStyleSheet(
            f"border: 1px solid {ds.p.outline}; border-radius: {ds.radius_xs}px; padding: {ds.space_md}px; min-width: {ds.window_width * 3 // 20}px;"
        )
        self._load_genders()
        self._inp_birthdate = M3DateEdit()
        self._inp_birthdate.setDisplayFormat("yyyy-MM-dd")
        self._inp_birthdate.setCalendarPopup(True)
        self._inp_birthdate.setDate(QDate.currentDate())
        self._inp_birthdate.setStyleSheet(
            f"border: 1px solid {ds.p.outline}; border-radius: {ds.radius_xs}px; padding: {ds.space_xs}px {ds.space_sm}px; color: {ds.p.text_strong};"
        )
        self._inp_addr1 = M3TextEdit()
        self._inp_addr1.setStyleSheet(ds.flat_input_qss())
        self._inp_addr1.setFixedHeight(ds.sp(SpacingToken.XXL))
        self._inp_addr1.setPlaceholderText(_("student_form.street_placeholder"))
        self._inp_addr2 = M3TextField()
        self._inp_addr2.setStyleSheet(ds.flat_input_qss())
        self._inp_addr2.setPlaceholderText(_("student_form.address_complement"))
        self._inp_cp = M3TextField()
        self._inp_cp.setStyleSheet(ds.flat_input_qss())
        self._inp_cp.setPlaceholderText(_("student_form.zip_placeholder"))
        self._inp_ville = M3TextField()
        self._inp_ville.setStyleSheet(ds.flat_input_qss())
        self._inp_ville.setPlaceholderText(_("student_form.city_placeholder"))
        self._inp_pays = M3TextField(_("student_form.default_country"))
        self._inp_pays.setStyleSheet(ds.flat_input_qss())

        # ═══════════════════════════════════════════════════════════
        #   Helpers de construction (identiques au dialogue édition)
        # ═══════════════════════════════════════════════════════════

        def _section_card(title: str, icon_name: str):
            card = M3Card(variant=CardVariant.ELEVATED)
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

        def _field_row(label: str, widget):
            row = QVBoxLayout()
            row.setSpacing(ds.space_xxs)
            lbl = M3Label(label, style="label_small")
            lbl.setStyleSheet(f"color: {ds.p.text_strong}; font-weight: bold;")
            row.addWidget(lbl)
            widget.setMinimumHeight(ds.field_height)
            widget.setStyleSheet(ds.flat_input_qss())
            row.addWidget(widget)
            return row

        # ═══════════════════════════════════════════════════════════
        #   ScrollArea : sections en single-page
        # ═══════════════════════════════════════════════════════════

        scroll = M3ScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"M3ScrollArea {{ background: {ds.p.background}; border: none; }}")
        scroll_content = QWidget()
        scroll_content.setAttribute(Qt.WA_StyledBackground, True)
        scroll_content.setStyleSheet(f"background: {ds.p.background};")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(ds.space_md)
        scroll_layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)

        self._section_cards: list[M3Card] = []

        # ── 0. Classe (grille de sélection + info slot) ──
        if self._preselected_class:
            class_card, class_cl = _section_card(_("student_form.class_selector") or "Classe", "school")
            class_cl.addWidget(self._class_info)
            self._slot_info = M3Label(_("student_form.select_class"), style="body_medium")
            self._slot_info.setStyleSheet(f"padding: {ds.space_xs}px; font-style: italic;")
            class_cl.addWidget(self._slot_info)
            scroll_layout.addWidget(class_card)
            self._section_cards.append(class_card)
        else:
            class_card, class_cl = _section_card(_("student_form.class_selector") or "Classe", "school")
            if self._class_grid:
                class_cl.addWidget(self._class_grid)
            self._slot_info = M3Label(_("student_form.select_class"), style="body_medium")
            self._slot_info.setStyleSheet(f"padding: {ds.space_xs}px; font-style: italic;")
            class_cl.addWidget(self._slot_info)
            scroll_layout.addWidget(class_card)
            self._section_cards.append(class_card)

        # ── 1. Identité ──
        id_card, id_cl = _section_card(_("student_form.tab_identity"), "person")
        id_grid = QGridLayout()
        id_grid.setSpacing(ds.space_md)
        id_grid.setColumnStretch(0, 1); id_grid.setColumnStretch(1, 1); id_grid.setColumnStretch(2, 1)
        id_grid.addLayout(_field_row(_("student_form.first_name_label"), self._inp_prenom), 0, 0)
        id_grid.addLayout(_field_row(_("student_form.last_name_label"), self._inp_nom), 0, 1)
        id_grid.addLayout(_field_row(_("student_form.gender_label"), self._inp_genre), 0, 2)
        id_grid.addLayout(_field_row(_("student_form.arrival_label"), self._inp_date_joined, is_date=True), 1, 0)
        id_grid.addLayout(_field_row(_("student_form.entry_date"), self._inp_date, is_date=True), 1, 1)
        id_grid.addLayout(_field_row(_("student_form.birth_date"), self._inp_birthdate, is_date=True), 1, 2)
        id_cl.addLayout(id_grid)
        scroll_layout.addWidget(id_card)
        self._section_cards.append(id_card)

        # ── 2. Contact ──
        ct_card, ct_cl = _section_card("Contact", "description")
        ct_grid = QGridLayout()
        ct_grid.setSpacing(ds.space_md)
        ct_grid.setColumnStretch(0, 1); ct_grid.setColumnStretch(1, 1)
        ct_grid.addLayout(_field_row(_("student_form.email_label"), self._inp_email), 0, 0)
        ct_grid.addLayout(_field_row(_("student_form.email_personal"), self._inp_emailperso), 0, 1)
        ct_grid.addLayout(_field_row(_("student_form.phone_mobile"), self._inp_tel), 1, 0)
        ct_grid.addLayout(_field_row(_("student_form.phone_fixed"), self._inp_tel2), 1, 1)
        ct_cl.addLayout(ct_grid)
        scroll_layout.addWidget(ct_card)
        self._section_cards.append(ct_card)

        # ── 3. Adresse ──
        ad_card, ad_cl = _section_card(_("student_form.address_title"), "home")
        ad_grid = QGridLayout()
        ad_grid.setSpacing(ds.space_md)
        ad_grid.setColumnStretch(0, 1); ad_grid.setColumnStretch(1, 1); ad_grid.setColumnStretch(2, 1)
        ad_grid.addLayout(_field_row(_("student_form.street_placeholder"), self._inp_addr1), 0, 0, 1, 3)
        ad_grid.addLayout(_field_row(_("student_form.address_complement"), self._inp_addr2), 1, 0, 1, 3)
        ad_grid.addLayout(_field_row(_("student_form.zip_label"), self._inp_cp), 2, 0)
        ad_grid.addLayout(_field_row(_("student_form.city_label"), self._inp_ville), 2, 1)
        ad_grid.addLayout(_field_row(_("student_form.country_label"), self._inp_pays), 2, 2)
        ad_cl.addLayout(ad_grid)
        scroll_layout.addWidget(ad_card)
        self._section_cards.append(ad_card)

        # ── 4. Parents ──
        par_card, par_cl = _section_card(_("student_form.parents_title"), "person")
        self._parents_table = M3TableWidget()
        self._parents_table.set_headers([
            _("student_form.parents_table_nom"), _("student_form.parents_table_nature"),
            _("student_form.parents_table_email"), _("student_form.parents_table_phone"),
        ])
        self._parents_table.horizontalHeader().setStretchLastSection(True)
        self._parents_table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._parents_table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._parents_table.setShowGrid(True)
        self._parents_table.horizontalHeader().setFixedHeight(ds.field_height)
        self._parents_table.setStyleSheet(ds.table_qss())
        self._parents_table.verticalHeader().setDefaultSectionSize(ds.table_row_min)
        self._parents_table.setMaximumHeight(ds.sp(SpacingToken.XXXL))
        par_cl.addWidget(self._parents_table)

        parent_tools = QHBoxLayout()
        parent_tools.setSpacing(ds.space_sm)
        add_par_btn = M3Button(_("student_form.add_parent"), variant=ButtonVariant.FILLED)
        add_par_btn.clicked.connect(self._add_parent_link)
        parent_tools.addWidget(add_par_btn)
        edit_par_btn = M3Button(_("student_form.edit_nature"), variant=ButtonVariant.TONAL)
        edit_par_btn.clicked.connect(self._edit_parent_nature)
        parent_tools.addWidget(edit_par_btn)
        remove_par_btn = M3Button(_("student_form.remove_parent"), variant=ButtonVariant.OUTLINED)
        remove_par_btn.clicked.connect(self._remove_parent_link)
        parent_tools.addWidget(remove_par_btn)
        copy_btn = M3Button(_("student_form.copy_address"), variant=ButtonVariant.TONAL)
        copy_btn.clicked.connect(self._copy_parent_address)
        parent_tools.addWidget(copy_btn)
        parent_tools.addStretch()
        par_cl.addLayout(parent_tools)
        self._addr_status = M3Label("", style="body_small")
        self._addr_status.setWordWrap(True)
        self._addr_status.setStyleSheet(f"color: {ds.p.text_disabled};")
        self._addr_status.hide()
        par_cl.addWidget(self._addr_status)
        scroll_layout.addWidget(par_card)
        self._section_cards.append(par_card)

        # ── 5. Dossiers (placeholder — l'élève n'existe pas encore) ──
        dos_card, dos_cl = _section_card(_("student_form.tab_documents"), "subject")
        from LarcSecretaire.views.dossier_panel import DossierPanel
        self._dossier_panel = DossierPanel(0)
        self._dossier_panel.setMinimumHeight(ds.window_height * 3 // 8)
        self._dossier_panel.setMaximumHeight(ds.window_height * 9 // 16)
        dos_cl.addWidget(self._dossier_panel)
        scroll_layout.addWidget(dos_card)
        self._section_cards.append(dos_card)
        self._timeline_page = self._dossier_panel.timeline

        # ── 6. Événements (placeholder — l'élève n'existe pas encore) ──
        evt_card, evt_cl = _section_card(_("student_form.events_title"), "event")
        ph_evt = M3Label(_("student_form.events_placeholder"), style="body_medium")
        ph_evt.setAlignment(Qt.AlignCenter)
        ph_evt.setWordWrap(True)
        evt_cl.addWidget(ph_evt)
        scroll_layout.addWidget(evt_card)
        self._section_cards.append(evt_card)

        # ── 7. Photos ──
        photo_card, photo_cl = _section_card(_("student_form.tab_photos"), "add")
        photo_box = QVBoxLayout()
        photo_box.setAlignment(Qt.AlignCenter)
        photo_box.setSpacing(ds.space_sm)
        self._photo_large = QLabel()
        self._photo_large.setFixedSize(ds.sp(SpacingToken.XXXL) * 2, ds.sp(SpacingToken.XXXL) * 2)
        self._photo_large.setStyleSheet(f"background: {ds.p.primary_container}; border-radius: {ds.radius_sm}px;")
        self._photo_large.setAlignment(Qt.AlignCenter)
        photo_box.addWidget(self._photo_large, 0, Qt.AlignCenter)
        self._upload_photo_btn = M3Button(_("student_form.change_photo"), variant=ButtonVariant.FILLED)
        self._upload_photo_btn.clicked.connect(self._on_change_photo)
        photo_box.addWidget(self._upload_photo_btn, 0, Qt.AlignCenter)
        photo_cl.addLayout(photo_box)
        scroll_layout.addWidget(photo_card)
        self._section_cards.append(photo_card)

        # ── 8. Bulletins & Relevés ──
        bul_card, bul_cl = _section_card(_("student_form.tab_bulletins"), "school")
        from LarcSecretaire.common.app_config import app_config as _acfg
        btn_row = QHBoxLayout()
        btn_row.setSpacing(ds.space_md)
        b_intra = M3Button(_("student_form.drive_intranet"), variant=ButtonVariant.FILLED)
        b_intra.clicked.connect(lambda checked: (
            self._open_drive_dir(_acfg.get("releves_dir", "")),
            self._open_drive_dir(_acfg.get("bulletins_dir", ""))
        ))
        btn_row.addWidget(b_intra)
        b_cloud = M3Button(_("student_form.drive_cloud"), variant=ButtonVariant.TONAL)
        b_cloud.clicked.connect(lambda checked: (
            self._open_drive_cloud(_acfg.get("releves_cloud_url", "")),
            self._open_drive_cloud(_acfg.get("bulletins_cloud_url", ""))
        ))
        btn_row.addWidget(b_cloud)
        btn_row.addStretch()
        bul_cl.addLayout(btn_row)
        scroll_layout.addWidget(bul_card)
        self._section_cards.append(bul_card)

        # ── 9. Confidentiel (restreint) ──
        from LarcSecretaire.common.session import UserRole
        from LarcSecretaire.common.session import session as _ses
        conf_card, conf_cl = _section_card(_("student_form.tab_confidential"), "lock")
        if _ses.role in (UserRole.ADMIN, UserRole.COORD, UserRole.SECR):
            conf_info = M3Label(_("student_form.confidential_desc"), style="body_medium")
            conf_info.setWordWrap(True)
            conf_cl.addWidget(conf_info)
            from LarcSecretaire.views.dossier_panel import ConfidentialPanel
            self._conf_panel = ConfidentialPanel(0)
            self._conf_panel.setMaximumHeight(ds.window_height * 7 // 16)
            conf_cl.addWidget(self._conf_panel)
        else:
            deny = M3Label(_("student_form.confidential_restricted"), style="title_small")
            deny.setAlignment(Qt.AlignCenter)
            deny.setWordWrap(True)
            conf_cl.addWidget(deny)
        scroll_layout.addWidget(conf_card)
        self._section_cards.append(conf_card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        self._scroll = scroll
        layout.addWidget(scroll, 1)

        # ── Chronologie : popup modale ──
        self._dossier_panel.timeline_requested.connect(self._open_timeline_dialog)

        # Infos slot
        self._slot_info = M3Label(_("student_form.select_class"), style="body_medium")
        self._slot_info.setStyleSheet(f"padding: {ds.space_xs}px; font-style: italic;")
        layout.addWidget(self._slot_info)

        # Header élève : prénom/nom mis à jour en direct pendant la saisie
        def _update_name_header(_t=""):
            if hasattr(self, "_id_prenom"):
                self._id_prenom.setText(self._inp_prenom.text().strip())
                self._id_nom.setText(self._inp_nom.text().strip().upper())

        self._inp_nom.textChanged.connect(_update_name_header)
        self._inp_prenom.textChanged.connect(_update_name_header)

        ds.theme_changed.connect(self._restyle)

    @safe_slot("Unknown._restyle")
    def _restyle(self):
        # Scroll area
        if hasattr(self, "_scroll") and self._scroll:
            self._scroll.setStyleSheet(
                f"M3ScrollArea {{ background: {ds.p.background}; border: none; }}")
            if self._scroll.widget():
                self._scroll.widget().setStyleSheet(f"background: {ds.p.background};")
        # Cartes de section
        section_style = (
            f"M3Card {{ background: {ds.p.surface}; "
            f"border: 1px solid {ds.p.outline_variant}; "
            f"border-radius: {ds.radius_md}px; }}")
        for card in getattr(self, "_section_cards", []):
            card.setStyleSheet(section_style)
        # Photos
        for attr in ("_photo", "_photo_large"):
            p = getattr(self, attr, None)
            if p:
                p.setStyleSheet(f"background: {ds.p.primary_container}; border-radius: {ds.radius_sm}px;")
        # Header élève
        for lbl in (self._id_prenom, self._id_nom):
            lbl.setStyleSheet(f"font-weight: bold; color: {ds.p.text_strong};")
        for lbl in (self._id_classe, self._id_id):
            lbl.setStyleSheet(f"color: {ds.p.text_strong};")
        # Tables
        if hasattr(self, "_parents_table") and self._parents_table:
            self._parents_table.setStyleSheet(ds.table_qss())
        # Champs texte
        for w in self._inp_fields():
            w.setStyleSheet(ds.flat_input_qss())
        # Champs date
        for w in self._date_fields():
            w.setStyleSheet(
                f"border: 1px solid {ds.p.outline}; border-radius: {ds.radius_xs}px; "
                f"padding: {ds.space_xs}px {ds.space_md}px; color: {ds.p.text_strong}; "
                f"background: {ds.p.surface}; "
                f"QDateEdit QLineEdit {{ color: {ds.p.text_strong}; background: {ds.p.surface}; }}")
            w.setMinimumWidth(ds.sp(SpacingToken.XXXL))
        # Combo genre
        if hasattr(self, "_inp_genre") and self._inp_genre:
            self._inp_genre.setStyleSheet(
                f"border: 1px solid {ds.p.outline}; border-radius: {ds.radius_xs}px; "
                f"padding: {ds.space_xxs}px {ds.space_xs}px; min-width: {ds.window_width * 3 // 20}px; "
                f"color: {ds.p.text_strong};")
            self._inp_genre.setFixedWidth(ds.sp(SpacingToken.XXL) + ds.sp(SpacingToken.MD))
        if hasattr(self, "_addr_status") and self._addr_status:
            self._addr_status.setStyleSheet(f"color: {ds.p.text_disabled};")

    @safe_slot("Unknown._open_timeline_dialog")
    def _open_timeline_dialog(self):
        """Bouton « Chronologie » du rail Dossiers -> ouvre une popup modale."""
        self._dossier_panel.refresh_timeline()
        dlg = M3Dialog(self)
        dlg.setWindowTitle(_("dossier.timeline.title"))
        dlg.setMinimumSize(ds.golden_width(600), 600)
        dlg.setStyleSheet(f"background: {ds.p.surface};")
        layout = QVBoxLayout(dlg)
        layout.addWidget(self._timeline_page)
        buttons = M3DialogButtonBox(M3DialogButtonBox.Close)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        dlg.exec()

    @safe_slot("StudentCreateDialog.on_change_photo")
    def _on_change_photo(self):
        if not self._sid:
            QMessageBox.information(self, _("student_form.save_first"), _("student_form.save_first_msg"))
            return
        path, _f = QFileDialog.getOpenFileName(
            self,
            _("student_form.select_photo"),
            "",
            _("student_form.photo_filter"),
        )
        if not path:
            return
        from LarcSecretaire.common.photos import save_photo

        try:
            save_photo(self._sid, path)
            px = QPixmap(get_photo_path(self._sid))
            if not px.isNull():
                px_small = px.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._photo.setPixmap(px_small)
                px_large = px.scaled(240, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._photo_large.setPixmap(px_large)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentCreateDialog._on_change_photo: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    @safe_slot("StudentCreateDialog.open_drive_dir")
    def _open_drive_dir(self, path: str):
        import subprocess

        path = path or ""
        if not path:
            QMessageBox.information(self, _("common.dialog.info_title"), _("student_form.drive_dir_missing"))
            return
        try:
            os.makedirs(path, exist_ok=True)
            subprocess.Popen(["explorer", path])
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentCreateDialog._open_drive_dir: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    @safe_slot("StudentCreateDialog.open_drive_cloud")
    def _open_drive_cloud(self, url: str):
        import webbrowser

        if not url:
            QMessageBox.information(self, _("common.dialog.info_title"), _("student_form.drive_url_missing"))
            return
        webbrowser.open(url)

    def _inp_fields(self):
        fields = []
        for attr in [
            "_inp_nom",
            "_inp_prenom",
            "_inp_email",
            "_inp_emailperso",
            "_inp_tel",
            "_inp_tel2",
            "_inp_addr2",
            "_inp_cp",
            "_inp_ville",
            "_inp_pays",
        ]:
            if hasattr(self, attr):
                fields.append(getattr(self, attr))
        return fields

    def _date_fields(self):
        fields = []
        for attr in ["_inp_date_joined", "_inp_date", "_inp_birthdate"]:
            if hasattr(self, attr):
                fields.append(getattr(self, attr))
        return fields

    def _load_classes(self):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            if self._preselected_class:
                # Mode classe connue : pas de grille, juste le label
                cur.execute(
                    """
                    SELECT c.label
                    FROM larcauth_classroom c
                    WHERE c.id = %s
                """,
                    (self._preselected_class,),
                )
                row = cur.fetchone()
                if row:
                    self._class_info.setText(_("student_form.class_slot").format(label=row[0]))
                self._on_class_changed(self._preselected_class)
            else:
                # Mode libre : grille de boutons
                cur.execute("""
                    SELECT c.id, c.label, l.fk_program_id, pr.sigle
                    FROM larcauth_classroom c
                    JOIN larcauth_level l ON l.id = c.fk_level_id
                    JOIN larcauth_program pr ON pr.id = l.fk_program_id
                    WHERE pr.sigle IN ('PEI', 'MYP', 'DPEn', 'DPFr')
                      AND c.enabled = TRUE
                    ORDER BY pr.sigle, l.label, c.label
                """)
                self._classes = list(cur.fetchall())
                self._build_class_buttons()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentCreateDialog._load_classes: {e}")

    def _build_class_buttons(self):
        if not hasattr(self, "_class_grid_layout") or not self._class_grid:
            return

        prog_style = {
            "PEI": (ds.p.primary, ds.p.primary_container, ds.p.on_primary),
            "MYP": (ds.p.secondary, ds.p.secondary_container, ds.p.on_secondary),
            "DPFr": (ds.p.error, ds.p.error_container, ds.p.on_error),
            "DPEn": (ds.p.tertiary, ds.p.tertiary_container, ds.p.on_tertiary),
        }

        groups = {k: [] for k in ["PEI", "MYP", "DPEn", "DPFr"]}
        for cid, label, pid, sigle in self._classes:
            if sigle in groups:
                groups[sigle].append((cid, label))

        sections = [
            (_("sec_main.college"), [("PEI", "PEI"), ("MYP", "MYP")]),
            (_("sec_main.lycee"), [("DP", "DPFr"), ("DPEn", "DPEn")]),
        ]

        self._clear_class_grid()
        self._class_btns.clear()

        for sec_name, columns in sections:
            sec_hdr = M3Label(sec_name, style="label_small")
            sec_hdr.setStyleSheet(
                f"font-weight: bold; color: {ds.p.text_strong}; border-bottom: 2px solid {ds.p.outline_variant}; padding: {ds.space_xxs // 2}px 0;"
            )
            self._class_grid_layout.addWidget(sec_hdr)

            grd = QGridLayout()
            grd.setSpacing(ds.space_xxs)

            for col_idx, (hdr_text, prog_key) in enumerate(columns):
                if prog_key not in groups:
                    continue
                fg, bg, on_fg = prog_style[prog_key]
                items = groups[prog_key]

                col_hdr = M3Label(hdr_text, style="label_small")
                col_hdr.setStyleSheet(f"background: {fg}; color: {on_fg}; border-radius: {ds.radius_sm}px; font-weight: bold; padding: {ds.space_xxs}px;")
                col_hdr.setAlignment(Qt.AlignCenter)
                col_hdr.setMinimumHeight(ds.field_height)
                grd.addWidget(col_hdr, 0, col_idx)

                for i, (cid, label) in enumerate(items):
                    btn = M3Button(label, variant=ButtonVariant.TONAL)
                    btn.setMinimumHeight(ds.field_height + ds.space_xs)
                    btn.setStyleSheet(
                        f"M3Button {{ background: {bg}; color: {fg}; border: 2px solid transparent; "
                        f"border-radius: {ds.radius_sm}px; font-size: {ds.font_label_lg}px; "
                        f"padding: {ds.space_xs}px {ds.space_sm}px; }}"
                        f"M3Button:hover {{ background: {fg}; color: {bg}; }}"
                    )
                    btn.clicked.connect(lambda checked, c=cid: self._on_class_changed(c))
                    self._class_btns[cid] = btn
                    grd.addWidget(btn, i + 1, col_idx)

            self._class_grid_layout.addLayout(grd)
            self._class_grid_layout.addSpacing(ds.space_xxs)

        self._class_grid_layout.addStretch()

    def _clear_class_grid(self):
        if not self._class_grid:
            return
        while self._class_grid_layout.count():
            item = self._class_grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _on_class_changed(self, class_id: int):
        if not db.is_server_connected:
            return
        if not class_id:
            return
        self._class_id = class_id

        # Header élève : Classe mise à jour dès la sélection
        _label = ""
        for _c in self._classes:
            if _c[0] == class_id:
                _label = _c[1]
                break
        self._id_classe.setText(_("student_form.class_label").format(label=_label or "—"))

        # Mettre à jour la sélection visuelle (si grille de boutons)
        if self._class_btns:
            for cid, btn in self._class_btns.items():
                _, _, _, sigle = next((c for c in self._classes if c[0] == cid), (None, None, None, None))
                prog_map = {
                    "PEI": (ds.p.primary, ds.p.primary_container, ds.p.on_primary),
                    "MYP": (ds.p.secondary, ds.p.secondary_container, ds.p.on_secondary),
                    "DPFr": (ds.p.error, ds.p.error_container, ds.p.on_error),
                    "DPEn": (ds.p.tertiary, ds.p.tertiary_container, ds.p.on_tertiary),
                }
                fg, bg, on_fg = prog_map.get(sigle, (ds.p.text_strong, ds.p.surface_variant, ds.p.text_strong))
                if cid == class_id:
                    btn.setStyleSheet(
                        f"M3Button {{ background: {fg}; color: {bg}; border: 2px solid {fg}; "
                        f"border-radius: {ds.radius_sm}px; font-size: {ds.font_label_lg}px; "
                        f"padding: {ds.space_xs}px {ds.space_sm}px; }}"
                        f"M3Button:hover {{ background: {fg}; color: {bg}; }}"
                    )
                else:
                    btn.setStyleSheet(
                        f"M3Button {{ background: {bg}; color: {fg}; border: 2px solid transparent; "
                        f"border-radius: {ds.radius_sm}px; font-size: {ds.font_label_lg}px; "
                        f"padding: {ds.space_xs}px {ds.space_sm}px; }}"
                        f"M3Button:hover {{ background: {fg}; color: {bg}; }}"
                    )

        # Filtrer les genres selon la langue de la classe
        lang_id = self._get_class_language(class_id)
        self._load_genders(lang_id)

        conn = db.server_conn
        if not conn:
            return

        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT s.aecuser_ptr_id, aec.last_name, s.enabled
                FROM larcauth_student s
                JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
                WHERE s.s_classroom_id = %s
                ORDER BY s.aecuser_ptr_id
            """,
                (self._class_id,),
            )
            all_rows = list(cur.fetchall())

            # Prochain slot libre (01→40) : enabled=FALSE et nom placeholder
            free = None
            for rid, ln, en in all_rows:
                slot = rid % 100
                if 1 <= slot <= 40 and not en and ("Name of" in (ln or "")):
                    free = slot
                    break

            self._next_free = free
            if free:
                self._sid = self._class_id * 100 + free
                self._id_id.setText(_("student_form.id_label").format(id=self._sid))
                base_dir = self._student_dir()
                dossiers_dir = os.path.join(base_dir, "dossiers")
                os.makedirs(dossiers_dir, exist_ok=True)
                conf_dir = os.path.join(base_dir, "confidentiel")
                os.makedirs(conf_dir, exist_ok=True)
                self._dossier_panel.set_directory(dossiers_dir)
                if hasattr(self, "_conf_panel"):
                    self._conf_panel.set_directory(conf_dir)
            else:
                self._sid = None

            if free:
                self._slot_info.setText(_("student_form.free_slot").format(n=free, id=self._class_id * 100 + free))
                self._slot_info.setStyleSheet(f"font-size: {ds.font_px_md}px; color: {ds.p.success}; padding: {ds.space_xs}px; font-weight: bold;")
                self._create_btn.setEnabled(True)
            else:
                self._slot_info.setText(_("student_form.no_slot"))
                self._slot_info.setStyleSheet(f"font-size: {ds.font_px_md}px; color: {ds.p.error}; padding: {ds.space_xs}px;")
                self._create_btn.setEnabled(False)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentCreateDialog._on_class_changed: {e}")

    def _get_class_language(self, classroom_id: int) -> int | None:
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return None
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT l.fk_language_id
                FROM larcauth_classroom c
                JOIN larcauth_level l ON l.id = c.fk_level_id
                WHERE c.id = %s
            """,
                (classroom_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentCreateDialog._get_class_language: {e}")
            return None

    def _load_genders(self, lang_id: int | None = None):
        if not db.is_server_connected:
            return
        self._inp_genre.clear()
        self._inp_genre.addItem(_("student_form.gender_not_specified"), 0)
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            if lang_id:
                cur.execute("SELECT id, label FROM larcauth_gender WHERE fk_language_id = %s ORDER BY id", (lang_id,))
            else:
                cur.execute("SELECT id, label FROM larcauth_gender ORDER BY id")
            for gid, label in cur.fetchall():
                self._inp_genre.addItem(label, gid)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentCreateDialog._load_genders: {e}")

    @safe_slot("Unknown._on_create")
    def _on_create(self):
        nom = self._inp_nom.text().strip()
        prenom = self._inp_prenom.text().strip()
        if not nom or not prenom:
            QMessageBox.warning(self, _("common.dialog.confirm_title"), _("student_form.validation_required"))
            return
        self._create_student()

    # ── Notes (formatage HTML) — supprimé, remplacé par NotesPanel JSON

    def _student_dir(self) -> str:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "students")
        d = os.path.join(base, str(self._sid))
        os.makedirs(d, exist_ok=True)
        return d

    def _create_student(self):
        if not db.is_server_connected:
            return
        slot = self._next_free
        if slot is None:
            return
        student_id = self._class_id * 100 + slot

        nom = self._inp_nom.text().strip()
        prenom = self._inp_prenom.text().strip()
        email = self._inp_email.text().strip()
        emailperso = self._inp_emailperso.text().strip() or None
        tel = self._inp_tel.text().strip() or None
        tel2 = self._inp_tel2.text().strip() or None
        date_str = self._inp_date.date().toString("yyyy-MM-dd") if self._inp_date.date().isValid() and not self._inp_date.date().isNull() else None

        conn = db.server_conn
        if not conn:
            return

        try:
            cur = conn.cursor()
            from datetime import datetime

            now = datetime.now().isoformat()
            birth_str = (
                self._inp_birthdate.date().toString("yyyy-MM-dd") if self._inp_birthdate.date().isValid() and not self._inp_birthdate.date().isNull() else None
            )
            username = email or f"student.{nom.lower()}.{prenom.lower()}"

            joined_str = (
                self._inp_date_joined.date().toString("yyyy-MM-dd")
                if self._inp_date_joined.date().isValid() and not self._inp_date_joined.date().isNull()
                else None
            )
            cur.execute(
                """
                UPDATE larcauth_aecuser SET
                    first_name = %s, last_name = %s, email = %s,
                    username = %s, is_active = TRUE, updated = %s,
                    emailperso = %s, tel_smartphone_1 = %s, tel_maison = %s,
                    date_joined = %s, date_entree = %s, date_of_birth = %s, fk_gender_id = %s
                WHERE id = %s
            """,
                (
                    prenom,
                    nom,
                    email or "",
                    username,
                    now,
                    emailperso,
                    tel,
                    tel2,
                    joined_str,
                    date_str,
                    birth_str,
                    self._inp_genre.currentData() or None,
                    student_id,
                ),
            )

            notes_data = self._dossier_panel.get_data()
            notes_data["health"] = self._dossier_panel.get_health()
            if hasattr(self, "_conf_panel"):
                notes_data["confidentiel"] = {"intro": "", "entries": self._conf_panel.get_entries()}
            notes_json = _json.dumps(notes_data)
            cur.execute(
                """
                UPDATE larcauth_student SET enabled = TRUE, updated_s = %s, notes_json = %s
                WHERE aecuser_ptr_id = %s
            """,
                (now, notes_json, student_id),
            )

            cur.execute(
                """
                INSERT INTO foyer (id, enabled, address_line1, address_line2,
                                   postal_code, city, country)
                VALUES (%s, TRUE, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    address_line1 = EXCLUDED.address_line1,
                    address_line2 = EXCLUDED.address_line2,
                    postal_code = EXCLUDED.postal_code,
                    city = EXCLUDED.city,
                    country = EXCLUDED.country
            """,
                (
                    student_id,
                    self._inp_addr1.toPlainText().strip() or None,
                    self._inp_addr2.text().strip() or None,
                    self._inp_cp.text().strip() or None,
                    self._inp_ville.text().strip() or None,
                    self._inp_pays.text().strip() or None,
                ),
            )
            cur.execute("UPDATE larcauth_aecuser SET fk_foyer_id = %s WHERE id = %s", (student_id, student_id))

            cur.execute("SET LOCAL app.sync_source = 'intranet'")
            cur.execute(f"SET LOCAL app.modified_by = {session.user_id}")
            audit.create_student(student_id, f"Création {prenom} {nom}")

            conn.commit()
            self._result_data = {"id": student_id, "last_name": nom, "first_name": prenom}
            self._sid = student_id
            log(f"StudentCreateDialog: activated #{student_id} (slot {slot:02d})")

            # Charger les parents maintenant que l'élève existe
            self._load_parents()

            QMessageBox.information(self, _("student_form.created"), _("student_form.created_msg").format(f=prenom, l=nom, sid=student_id, slot=slot))

            # Réinitialiser le formulaire pour une autre saisie
            for w in [
                self._inp_nom,
                self._inp_prenom,
                self._inp_email,
                self._inp_emailperso,
                self._inp_tel,
                self._inp_tel2,
                self._inp_date,
                self._inp_addr1,
                self._inp_addr2,
                self._inp_cp,
                self._inp_ville,
            ]:
                w.clear()
            self._dossier_panel.clear()
            if hasattr(self, "_conf_panel"):
                self._conf_panel.clear()
            self._inp_pays.setText("Togo")
            self._sid = None
            self._parent_ids = []
            self._parents_table.setRowCount(0)
            # Re-vérifier le slot libre
            self._on_class_changed(self._class_id)

        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            conn.rollback()
            log(f"StudentCreateDialog._create_student: {e}")
            QMessageBox.critical(self, _("common.dialog.error_title"), str(e))

    def _load_parents(self):
        if not db.is_server_connected:
            return
        self._parent_ids = []
        conn = db.server_conn
        if not conn or not self._sid:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT aec.id, aec.last_name || ' ' || aec.first_name, sp.nature, aec.email, aec.tel_smartphone_1
                FROM larcauth_student_parent sp
                JOIN larcauth_aecuser aec ON aec.id = sp.parent_id
                WHERE sp.student_id = %s
                ORDER BY aec.last_name, aec.first_name
            """,
                (self._sid,),
            )
            rows = cur.fetchall()
            self._parent_ids = []
            self._parents_table.setRowCount(len(rows))
            for i, (pid, name, nat, em, tel) in enumerate(rows):
                self._parent_ids.append(pid)
                self._parents_table.setItem(i, 0, QTableWidgetItem(name))
                if nat:
                    self._parents_table.setItem(i, 1, QTableWidgetItem(nat))
                self._parents_table.setItem(i, 2, QTableWidgetItem(em or ""))
                self._parents_table.setItem(i, 3, QTableWidgetItem(tel or ""))
            self._parents_table.resizeColumnsToContents()
            if rows:
                self._parents_table.selectRow(0)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentCreateDialog._load_parents: {e}")

    @safe_slot("StudentEditDialog.copy_parent_address")
    def _copy_parent_address(self):
        if not db.is_server_connected:
            return
        if not self._sid:
            QMessageBox.information(self, _("student_form.save_first"), _("student_form.save_first_msg"))
            return
        sel = self._parents_table.selectedItems()
        if not sel or not self._parent_ids:
            QMessageBox.warning(self, _("student_form.copy_address_title"), _("student_form.copy_address_none"))
            return
        row = sel[0].row()
        if row >= len(self._parent_ids):
            return
        pid = self._parent_ids[row]
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT address_line1, address_line2, postal_code, city, country
                FROM foyer WHERE id = %s
            """,
                (pid,),
            )
            row = cur.fetchone()
            if row and any(row):
                addr1, addr2, cp, ville, pays = row
                self._inp_addr1.setPlainText(addr1 or "")
                self._inp_addr2.setText(addr2 or "")
                self._inp_cp.setText(cp or "")
                self._inp_ville.setText(ville or "")
                if pays:
                    self._inp_pays.setText(pays)
                if hasattr(self, "_addr_status") and self._addr_status:
                    self._addr_status.hide()
            else:
                if hasattr(self, "_addr_status") and self._addr_status:
                    self._addr_status.setText(_("student_form.copy_address_no_address"))
                    self._addr_status.show()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"StudentCreateDialog._copy_parent_address: {e}")

    @safe_slot("StudentEditDialog.add_parent_link")
    def _add_parent_link(self):
        if not db.is_server_connected:
            return
        if not self._sid:
            QMessageBox.information(self, _("student_form.save_first"), _("student_form.save_first_msg"))
            return
        dlg = M3Dialog(self)
        dlg.setWindowTitle(_("student_form.add_parent"))
        dlg.setMinimumSize(ds.window_height * 7 // 8, ds.window_height * 5 // 8)
        dlg.setStyleSheet(f"background: {ds.p.surface}; color: {ds.p.text_strong};")
        layout = QVBoxLayout(dlg)
        layout.setSpacing(ds.space_sm)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)

        layout.addWidget(M3Label(_("student_form.search_parent_label"), style="title_small"))

        search_inp = M3TextField()
        search_inp.setPlaceholderText(_("student_form.search_parent_placeholder"))
        search_inp.setStyleSheet(ds.flat_input_qss())
        search_inp.setMinimumHeight(ds.field_height)
        layout.addWidget(search_inp)

        parent_combo = M3ComboBox()
        parent_combo.setMinimumHeight(ds.field_height)
        layout.addWidget(parent_combo)

        self._search_parents_data = []

        def on_search(text):
            if not db.is_server_connected:
                return
            if len(text.strip()) < 2:
                parent_combo.clear()
                self._search_parents_data.clear()
                return
            conn = db.server_conn
            if not conn:
                return
            try:
                cur = conn.cursor()
                q = "%" + text.strip() + "%"
                cur.execute(
                    """
                    SELECT aec.id, aec.last_name, aec.first_name, aec.email
                    FROM larcauth_aecuser aec
                    JOIN larcauth_parent par ON par.aecuser_ptr_id = aec.id
                    WHERE aec.is_active = TRUE
                      AND par.enabled = TRUE
                      AND (LOWER(aec.last_name) LIKE LOWER(%s) OR LOWER(aec.first_name) LIKE LOWER(%s) OR LOWER(aec.email) LIKE LOWER(%s))
                      AND aec.id NOT IN (SELECT parent_id FROM larcauth_student_parent WHERE student_id = %s)
                    ORDER BY aec.last_name, aec.first_name LIMIT 50
                """,
                    (q, q, q, self._sid),
                )
                parent_combo.clear()
                self._search_parents_data.clear()
                for pid, ln, fn, em in cur.fetchall():
                    parent_combo.addItem(f"{ln or ''} {fn or ''} ({em or 'pas d e-mail'})", pid)
                    self._search_parents_data.append(pid)
            except Exception as e:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                log(f"_add_parent_link search: {e}")

        search_inp.textChanged.connect(on_search)

        buttons = M3DialogButtonBox(M3DialogButtonBox.Ok | M3DialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() == M3Dialog.Accepted:
            pid = parent_combo.currentData()
            if not pid:
                QMessageBox.warning(self, _("student_form.add_parent"),
                                    _("parent.error.no_parent_selected"))
                return
            conn = db.server_conn
            if not conn:
                return
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO larcauth_student_parent (student_id, parent_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (self._sid, pid),
                )
            except Exception as e:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                log(f"_add_parent_link insert: {e}")
                QMessageBox.critical(self, _("common.dialog.error_title"), str(e))
            self._load_parents()

    @safe_slot("StudentEditDialog.edit_parent_nature")
    def _edit_parent_nature(self):
        if not db.is_server_connected:
            return
        if not self._sid:
            QMessageBox.information(self, _("student_form.save_first"), _("student_form.save_first_msg"))
            return
        sel = self._parents_table.selectedItems()
        if not sel or not self._parent_ids:
            QMessageBox.warning(self, _("student_form.nature_dialog_title"), _("parent.error.no_parent_selected"))
            return
        row = sel[0].row()
        if row >= len(self._parent_ids):
            return
        pid = self._parent_ids[row]
        from PySide6.QtWidgets import QInputDialog

        nature, ok = QInputDialog.getText(self, _("student_form.nature_prompt_title"), _("student_form.nature_prompt_msg"))
        if not ok:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE larcauth_student_parent SET nature = %s WHERE student_id = %s AND parent_id = %s",
                (nature.strip(), self._sid, pid),
            )
            self._load_parents()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_edit_parent_nature: {e}")

    @safe_slot("StudentEditDialog.remove_parent_link")
    def _remove_parent_link(self):
        if not db.is_server_connected:
            return
        if not self._sid:
            QMessageBox.information(self, _("student_form.save_first"), _("student_form.save_first_msg"))
            return
        sel = self._parents_table.selectedItems()
        if not sel or not self._parent_ids:
            QMessageBox.warning(self, _("student_form.remove_parent"), _("student_form.edit_nature"))
            return
        row = sel[0].row()
        if row >= len(self._parent_ids):
            return
        pid = self._parent_ids[row]
        confirm = QMessageBox.question(self, _("student_form.remove_confirm_title"), _("student_form.remove_confirm_msg"), QMessageBox.Yes | QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM larcauth_student_parent WHERE student_id = %s AND parent_id = %s", (self._sid, pid))
            self._load_parents()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_remove_parent_link: {e}")

    def get_data(self) -> dict | None:
        return self._result_data
