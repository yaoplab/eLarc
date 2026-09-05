"""LeaveBalanceWidget — solde de congés + historique demandes + validation."""
from __future__ import annotations
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTextEdit, QButtonGroup, QMessageBox, QHeaderView,
)

from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.icons import icon as md3_icon
from larccommon.safe_slot import safe_slot
from larccommon.session import session
from larccommon.widgets.themed_widget import ThemedDialog
from phibuilder.phi.scale import SpacingToken
from phibuilder.widgets import M3TableWidget, M3ProgressBar

from LarcRH.common.hr_database import HRDatabase

LEAVE_LABELS = {
    'CA': 'Congé annuel', 'CM': 'Congé maladie', 'MAT': 'Congé maternité',
    'PAT': 'Congé paternité', 'CF': 'Congé familial', 'CS': 'Congé sans solde',
    'CFOR': 'Congé formation', 'REC': 'Récupération', 'AUT': 'Autorisation',
}


class LeaveBalanceWidget(QWidget):
    """Cartes de solde de congés par type."""

    def __init__(self, staff_data: dict, parent=None):
        super().__init__(parent)
        self._staff = staff_data
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(ds.space_sm)
        p = theme_manager.palette
        title = QLabel("Solde de congés")
        title.setStyleSheet(f"font-weight: bold; font-size: {theme_manager.font_size(14)}px; color: {p.text_strong}; border: none;")
        self._layout.addWidget(title)
        self._cards_layout = QHBoxLayout()
        self._cards_layout.setSpacing(ds.space_sm)
        self._layout.addLayout(self._cards_layout)

    def refresh(self):
        # Clear
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        staff_id = self._staff.get("id", 0)
        HRDatabase.ensure_annual_leave(staff_id)
        balances = HRDatabase.get_leave_balance(staff_id)

        if not balances:
            empty = QLabel("Aucun solde de congés initialisé")
            p = theme_manager.palette
            empty.setStyleSheet(f"color: {p.text_soft}; font-size: {theme_manager.font_size(12)}px; border: none;")
            self._cards_layout.addWidget(empty)
            return

        for b in balances:
            card = self._make_balance_card(b)
            self._cards_layout.addWidget(card)
        self._cards_layout.addStretch()

    def _make_balance_card(self, balance: dict) -> QFrame:
        p = theme_manager.palette
        s = theme_manager.font_size
        total = float(balance["total_days"])
        used = float(balance["used_days"])
        remaining = float(balance.get("remaining", total - used))
        pct = (used / total * 100) if total > 0 else 0

        card = QFrame()
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setFixedSize(
            ds.sp(SpacingToken.XXXL) + ds.space_sm * 2,
            ds.sp(SpacingToken.XXXL) - ds.space_m3,
        )
        card.setStyleSheet(f"""
            QFrame {{ background: {p.surface}; border: 1px solid {p.outline_variant};
            border-radius: {ds.radius_sm}px; }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(ds.space_sm, ds.space_sm, ds.space_sm, ds.space_sm)
        cl.setSpacing(ds.space_xxs)

        label = LEAVE_LABELS.get(balance["leave_type"], balance["leave_type"])
        name = QLabel(label)
        name.setStyleSheet(f"font-size: {s(12)}px; color: {p.text_soft}; border: none;")
        cl.addWidget(name)

        days = QLabel(f"{remaining:.0f}")
        days.setStyleSheet(f"font-size: {s(24)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        cl.addWidget(days)

        sub = QLabel(f"jours restants / {total:.0f}")
        sub.setStyleSheet(f"font-size: {s(10)}px; color: {p.text_soft}; border: none;")
        cl.addWidget(sub)

        bar_color = p.success if pct < 50 else (p.warning if hasattr(p, 'warning') else p.primary) if pct < 80 else p.error
        bar = M3ProgressBar()
        bar.setMaximum(100)
        bar.setValue(int(pct))
        bar.setFixedHeight(ds.space_xxs)
        bar.setStyleSheet(f"""
            QProgressBar {{ background: {p.surface_variant}; border: none; border-radius: {ds.radius_xs}px; }}
            QProgressBar::chunk {{ background: {bar_color}; border-radius: {ds.radius_xs}px; }}
        """)
        cl.addWidget(bar)

        cl.addStretch()
        return card


class ValidateLeaveDialog(ThemedDialog):
    """Dialogue de validation d'une demande de congé (approuver / refuser)."""

    def __init__(self, request_data: dict, parent=None):
        super().__init__(parent)
        self._request = request_data
        self._approved = True

        leave_label = LEAVE_LABELS.get(request_data["leave_type"], request_data["leave_type"])
        staff = f"{request_data.get('first_name', '')} {request_data.get('last_name', '')}"
        self.setWindowTitle(f"Validation congé — {staff}")
        _w = ds.sidebar_width + ds.golden_width(ds.sidebar_width)
        self.setMinimumSize(ds.golden_width(ds.sidebar_width), ds.sp(SpacingToken.XXXL) * 2)
        self._setup_ui()

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        return f"""
            ValidateLeaveDialog {{ background: {p.surface}; }}
        """

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        r = self._request

        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_sm)

        head = QLabel("Validation de la demande")
        head.setStyleSheet(
            f"font-size: {s(16)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        layout.addWidget(head)

        # ── Request summary ──
        leave_label = LEAVE_LABELS.get(r["leave_type"], r["leave_type"])
        info = QLabel(
            f"{leave_label}  ·  {r.get('date_debut','')} → {r.get('date_fin','')}  ·  "
            f"{r.get('nb_days','')} jour(s)")
        info.setStyleSheet(f"font-size: {s(13)}px; color: {p.text_soft}; border: none;")
        layout.addWidget(info)

        if r.get("motif"):
            motif = QLabel(f"Motif : {r['motif'][:120]}")
            motif.setWordWrap(True)
            motif.setStyleSheet(f"font-size: {s(12)}px; color: {p.text_soft}; border: none;")
            layout.addWidget(motif)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {p.outline_variant}; border: none;")
        layout.addWidget(sep)

        # ── Decision chips ──
        lbl = QLabel("Décision")
        lbl.setStyleSheet(
            f"font-size: {s(12)}px; color: {p.text_soft}; font-weight: bold; border: none;")
        layout.addWidget(lbl)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(ds.space_xs)

        self._approve_btn = QPushButton("  Approuver")
        self._approve_btn.setIcon(md3_icon("check_circle", color=p.success, size=18))
        self._approve_btn.setCheckable(True)
        self._approve_btn.setChecked(True)
        self._approve_btn.setCursor(Qt.PointingHandCursor)
        self._approve_btn.setFixedHeight(ds.field_height + ds.space_xs)
        self._approve_btn.setStyleSheet(f"""
            QPushButton {{ background: {p.surface_variant}; color: {p.text_strong};
            border: 1px solid {p.outline}; border-radius: {ds.radius_sm}px;
            padding: {ds.space_xs}px {ds.space_md}px; font-size: {s(13)}px; }}
            QPushButton:checked {{ background: {p.success}; color: white;
            border-color: {p.success}; }}
        """)
        self._approve_btn.clicked.connect(lambda: self._set_decision(True))
        chip_row.addWidget(self._approve_btn)

        self._reject_btn = QPushButton("  Refuser")
        self._reject_btn.setIcon(md3_icon("cancel", color=p.error, size=18))
        self._reject_btn.setCheckable(True)
        self._reject_btn.setCursor(Qt.PointingHandCursor)
        self._reject_btn.setFixedHeight(ds.field_height + ds.space_xs)
        self._reject_btn.setStyleSheet(f"""
            QPushButton {{ background: {p.surface_variant}; color: {p.text_strong};
            border: 1px solid {p.outline}; border-radius: {ds.radius_sm}px;
            padding: {ds.space_xs}px {ds.space_md}px; font-size: {s(13)}px; }}
            QPushButton:checked {{ background: {p.error}; color: white;
            border-color: {p.error}; }}
        """)
        self._reject_btn.clicked.connect(lambda: self._set_decision(False))
        chip_row.addWidget(self._reject_btn)
        chip_row.addStretch()
        layout.addLayout(chip_row)

        # ── Note ──
        lbl2 = QLabel("Note de validation")
        lbl2.setStyleSheet(
            f"font-size: {s(12)}px; color: {p.text_soft}; font-weight: bold; border: none;")
        layout.addWidget(lbl2)

        self._note = QTextEdit()
        self._note.setFixedHeight(ds.kpi_card_height // 2)
        self._note.setStyleSheet(f"""
            QTextEdit {{ background: {p.background}; border: 1px solid {p.outline};
            border-radius: {ds.radius_xs}px; padding: {ds.space_xs}px;
            color: {p.text_strong}; font-size: {s(13)}px; }}
            QTextEdit:focus {{ border-color: {p.primary}; }}
        """)
        layout.addWidget(self._note)

        layout.addStretch()

        # ── Actions (Q19b) ──
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

        confirm = QPushButton("Confirmer")
        confirm.setCursor(Qt.PointingHandCursor)
        confirm.setFixedHeight(ds.field_height + ds.space_xs)
        confirm.setStyleSheet(f"""
            QPushButton {{ background: {p.primary}; color: white; border: none;
            border-radius: {ds.radius_sm}px; padding: {ds.space_xs}px {ds.space_md}px;
            font-size: {s(13)}px; font-weight: bold; }}
            QPushButton:hover {{ background: {p.primary}; }}
        """)
        confirm.clicked.connect(self.accept)
        btn_row.addWidget(confirm)

        layout.addLayout(btn_row)
        self.setStyleSheet(self._STYLE)

    def _set_decision(self, approved: bool):
        self._approved = approved
        self._approve_btn.setChecked(approved)
        self._reject_btn.setChecked(not approved)

    @property
    def approved(self) -> bool:
        return self._approved

    @property
    def note(self) -> str:
        return self._note.toPlainText().strip()


class LeaveRequestHistory(QWidget):
    """Historique des demandes de congé + bouton nouvelle demande."""

    leave_validated = Signal()

    def __init__(self, staff_data: dict, parent=None):
        super().__init__(parent)
        self._staff = staff_data
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, ds.space_sm, 0, 0)
        layout.setSpacing(ds.space_sm)
        p = theme_manager.palette

        hdr = QHBoxLayout()
        title = QLabel("Demandes de congé")
        title.setStyleSheet(f"font-weight: bold; font-size: {theme_manager.font_size(14)}px; color: {p.text_strong}; border: none;")
        hdr.addWidget(title)
        hdr.addStretch()

        add_btn = QPushButton("+ Nouvelle demande")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setFixedHeight(ds.field_height)
        add_btn.setStyleSheet(f"""
            QPushButton {{ background: {p.primary}; color: white; border: none;
            border-radius: {ds.radius_xs}px; padding: {ds.space_xxs}px {ds.space_sm}px;
            font-size: {theme_manager.font_size(12)}px; font-weight: bold; }}
            QPushButton:hover {{ background: {p.primary}; }}
        """)
        add_btn.clicked.connect(self._on_new_request)
        hdr.addWidget(add_btn)
        layout.addLayout(hdr)

        self._table = M3TableWidget()
        self._table.set_headers(["ID", "Type", "Début", "Fin", "Jours", "Motif", "Statut", "Créé par", ""])
        self._table.setColumnHidden(0, True)
        self._table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setDefaultSectionSize(ds.field_height)
        self._table.setStyleSheet(ds.table_qss())
        layout.addWidget(self._table)

    def refresh(self):
        requests = HRDatabase.get_leave_requests(self._staff.get("id", 0))
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtGui import QColor
        p = theme_manager.palette

        for i, r in enumerate(requests):
            self._table.setRowCount(i + 1)
            self._table.setItem(i, 0, QTableWidgetItem(str(r["id"])))
            self._table.setItem(i, 1, QTableWidgetItem(LEAVE_LABELS.get(r["leave_type"], r["leave_type"])))
            self._table.setItem(i, 2, QTableWidgetItem(str(r.get("date_debut", ""))))
            self._table.setItem(i, 3, QTableWidgetItem(str(r.get("date_fin", ""))))
            self._table.setItem(i, 4, QTableWidgetItem(str(r.get("nb_days", ""))))
            self._table.setItem(i, 5, QTableWidgetItem((r.get("motif", "") or "")[:80]))
            self._table.setItem(i, 7, QTableWidgetItem(r.get("created_by_name", "—")))

            status_item = QTableWidgetItem(r.get("status", "en_attente"))
            if r["status"] == "valide":
                status_item.setForeground(QColor(p.success))
            elif r["status"] == "refuse":
                status_item.setForeground(QColor(p.error))
            self._table.setItem(i, 6, status_item)

            # Action buttons for en_attente requests
            if r.get("status") == "en_attente":
                actions = QWidget()
                actions.setAttribute(Qt.WA_StyledBackground, True)
                actions.setStyleSheet("border: none;")
                al = QHBoxLayout(actions)
                al.setContentsMargins(0, 0, 0, 0)
                al.setSpacing(ds.space_xxs)

                app_btn = QPushButton()
                app_btn.setIcon(md3_icon("check_circle", color=p.success, size=16))
                app_btn.setFixedSize(ds.icon_btn_size, ds.icon_btn_size)
                app_btn.setCursor(Qt.PointingHandCursor)
                app_btn.setToolTip("Approuver")
                app_btn.setStyleSheet("QPushButton { border: none; background: transparent; }")
                app_btn.clicked.connect(lambda checked, req=r: self._on_validate(req, True))
                al.addWidget(app_btn)

                rej_btn = QPushButton()
                rej_btn.setIcon(md3_icon("cancel", color=p.error, size=16))
                rej_btn.setFixedSize(ds.icon_btn_size, ds.icon_btn_size)
                rej_btn.setCursor(Qt.PointingHandCursor)
                rej_btn.setToolTip("Refuser")
                rej_btn.setStyleSheet("QPushButton { border: none; background: transparent; }")
                rej_btn.clicked.connect(lambda checked, req=r: self._on_validate(req, False))
                al.addWidget(rej_btn)

                al.addStretch()
                self._table.setCellWidget(i, 7, actions)
            else:
                # Already validated/refused — show revoke button
                actions = QWidget()
                actions.setAttribute(Qt.WA_StyledBackground, True)
                actions.setStyleSheet("border: none;")
                al = QHBoxLayout(actions)
                al.setContentsMargins(0, 0, 0, 0)
                al.setSpacing(ds.space_xxs)

                revoke_btn = QPushButton()
                revoke_btn.setIcon(md3_icon("refresh", color=p.text_soft, size=14))
                revoke_btn.setFixedSize(ds.icon_btn_size, ds.icon_btn_size)
                revoke_btn.setCursor(Qt.PointingHandCursor)
                revoke_btn.setToolTip("Révoquer la validation")
                revoke_btn.setStyleSheet("QPushButton { border: none; background: transparent; }")
                revoke_btn.clicked.connect(lambda checked, req=r: self._on_revoke(req))
                al.addWidget(revoke_btn)

                al.addStretch()
                self._table.setCellWidget(i, 7, actions)

        h = self._table.horizontalHeader()
        # IE8 : seule la colonne Type s'étire ; les autres au contenu
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setStretchLastSection(False)
        h.resizeSection(2, ds.sp(SpacingToken.XXL) + ds.sp(SpacingToken.XS))
        h.resizeSection(3, ds.sp(SpacingToken.XXL) + ds.sp(SpacingToken.XS))
        h.resizeSection(4, ds.sp(SpacingToken.XL))
        h.resizeSection(5, ds.sp(SpacingToken.XXXL) + ds.sp(SpacingToken.SM))
        h.resizeSection(6, ds.sp(SpacingToken.XXL))
        h.resizeSection(7, ds.field_height + ds.space_xs)
        self._table.setSortingEnabled(True)  # IE8d : tri par clic

    @safe_slot("LeaveRequestHistory._on_validate")
    def _on_validate(self, request_data: dict, approved: bool):
        dlg = ValidateLeaveDialog(request_data, parent=self)
        if dlg.exec():
            HRDatabase.validate_leave_request(
                request_data["id"],
                session.user_id,
                dlg.approved,
                dlg.note,
            )
            self.refresh()
            self.leave_validated.emit()
            QMessageBox.information(
                self, "LarcRH",
                "Demande de congé validée." if dlg.approved else "Demande de congé refusée.")

    @safe_slot("LeaveRequestHistory._on_revoke")
    def _on_revoke(self, request_data: dict):
        HRDatabase.revoke_leave_request(request_data["id"])
        self.refresh()
        self.leave_validated.emit()

    @safe_slot("LeaveRequestHistory._on_new_request")
    def _on_new_request(self):
        from LarcRH.views.leave_request import LeaveRequestDialog
        dlg = LeaveRequestDialog(self._staff.get("id", 0), parent=self)
        if dlg.exec():
            self.refresh()
            QMessageBox.information(self, "LarcRH", "Demande de congé enregistrée.")
