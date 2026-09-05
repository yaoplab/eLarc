"""PaymentList — conforme aux 6 skills design Larc, parent-based."""
from __future__ import annotations

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QScrollArea, QDialog, QFormLayout, QLineEdit, QComboBox,
    QDateEdit, QMessageBox,
)

from larccommon.database import db
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot


def _fmt(amount: int) -> str:
    if amount >= 1000000: return f"{amount / 1000000:.1f} M"
    return f"{amount // 1000:,} K".replace(",", " ")


class _PaymentForm(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enregistrer un paiement")
        self.setMinimumSize(ds.golden_width(ds.sidebar_width), ds.sidebar_width)
        self._parent_id: int | None = None
        self._setup_ui()

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_sm)

        self.setStyleSheet(f"background: {p.surface};")
        fstyle = (
            f"background: {p.background}; border: {ds.border_width}px solid {p.outline}; "
            f"border-radius: {ds.radius_xs}px; padding: {ds.space_sm}px; "
            f"color: {p.text_strong}; font-size: {s(ds.font_body_md)}px;"
        )

        # Recherche parent payeur
        self._search = QLineEdit()
        self._search.setPlaceholderText("Nom du parent payeur...")
        self._search.setFixedHeight(ds.field_height)
        self._search.setStyleSheet(fstyle)
        self._search.textChanged.connect(self._on_search)
        layout.addWidget(self._search)

        self._results = QWidget()
        self._rl = QVBoxLayout(self._results)
        self._rl.setContentsMargins(0, 0, 0, 0)
        self._rl.setSpacing(ds.border_width)
        self._results.setVisible(False)
        layout.addWidget(self._results)

        self._selected = QLabel("Aucun parent selectionne")
        self._selected.setStyleSheet(
            f"font-weight: bold; color: {p.primary}; font-size: {s(ds.font_label_lg)}px; border: none;")
        layout.addWidget(self._selected)

        form = QFormLayout()
        form.setSpacing(ds.space_sm)

        self._f_amount = QLineEdit()
        self._f_amount.setPlaceholderText("Montant en FCFA")
        self._f_amount.setFixedHeight(ds.field_height)
        self._f_amount.setStyleSheet(fstyle)
        form.addRow("Montant (FCFA) :", self._f_amount)

        self._f_date = QDateEdit()
        self._f_date.setDate(QDate.currentDate())
        self._f_date.setCalendarPopup(True)
        self._f_date.setFixedHeight(ds.field_height)
        self._f_date.setStyleSheet(fstyle)
        form.addRow("Date :", self._f_date)

        self._f_method = QComboBox()
        self._f_method.addItems(["especes", "cheque", "virement", "mobile_money"])
        self._f_method.setFixedHeight(ds.field_height)
        self._f_method.setStyleSheet(fstyle)
        form.addRow("Mode :", self._f_method)

        self._f_ref = QLineEdit()
        self._f_ref.setPlaceholderText("Reference")
        self._f_ref.setFixedHeight(ds.field_height)
        self._f_ref.setStyleSheet(fstyle)
        form.addRow("Reference :", self._f_ref)

        self._f_note = QLineEdit()
        self._f_note.setPlaceholderText("Note (optionnel)")
        self._f_note.setFixedHeight(ds.field_height)
        self._f_note.setStyleSheet(fstyle)
        form.addRow("Note :", self._f_note)

        layout.addLayout(form)
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Annuler")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setFixedHeight(ds.button_height)
        cancel.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p.text_strong}; "
            f"border: {ds.border_width}px solid {p.outline}; "
            f"border-radius: {ds.radius_sm}px; padding: {ds.space_xs}px {ds.space_m3}px; "
            f"font-size: {s(ds.font_label_lg)}px; }}"
            f"QPushButton:hover {{ background: {p.surface_variant}; }}")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        save = QPushButton("Enregistrer")
        save.setCursor(Qt.PointingHandCursor)
        save.setFixedHeight(ds.button_height)
        save.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: {ds.radius_sm}px; padding: {ds.space_xs}px {ds.space_m3}px; "
            f"font-size: {s(ds.font_label_lg)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.primary}; }}")
        save.clicked.connect(self._on_save)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)

    @safe_slot("_PaymentForm._on_search")
    def _on_search(self):
        if not db.is_server_connected:
            return
        q = self._search.text().strip()
        while self._rl.count():
            item = self._rl.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        if len(q) < 2:
            self._results.setVisible(False)
            return
        conn = db.server_conn
        if not conn:
            return
        cur = conn.cursor()
        cur.execute("""
            SELECT a.id, a.first_name, a.last_name, a.tel_smartphone_1
            FROM larcauth_aecuser a
            JOIN larcauth_parent p ON p.aecuser_ptr_id = a.id
            WHERE p.is_payer = TRUE AND p.enabled = TRUE
            AND (a.last_name ILIKE %s OR a.first_name ILIKE %s)
            ORDER BY a.last_name LIMIT 8
        """, (f"%{q}%", f"%{q}%"))
        for row in cur.fetchall():
            pid, fn, ln, _ = row
            btn = QPushButton(f"{ln} {fn}")
            btn.setFlat(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ text-align: left; padding: {ds.space_xxs}px {ds.space_xs}px; "
                f"color: {theme_manager.palette.text_strong}; font-size: {theme_manager.font_size(12)}px; }}"
                f"QPushButton:hover {{ background: {theme_manager.palette.surface_variant}; }}")
            btn.clicked.connect(lambda checked, i=pid, t=f"{ln} {fn}": self._select(i, t))
            self._rl.addWidget(btn)
        self._results.setVisible(True)

    def _select(self, pid: int, name: str):
        self._parent_id = pid
        self._selected.setText(f"Parent : {name}")
        self._results.setVisible(False)
        self._search.setText(name)

    @safe_slot("_PaymentForm._on_save")
    def _on_save(self):
        if not db.is_server_connected:
            return
        if not self._parent_id:
            QMessageBox.warning(self, "Erreur", "Selectionnez un parent.")
            return
        try:
            amount = int(self._f_amount.text().replace(" ", ""))
        except ValueError:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            QMessageBox.warning(self, "Erreur", "Montant invalide.")
            return
        conn = db.server_conn
        if not conn:
            return
        cur = conn.cursor()
        cur.execute("""INSERT INTO compta_payment (parent_id, amount, payment_date, payment_method, reference, notes)
            VALUES (%s, %s, %s, %s, %s, %s)""",
            (self._parent_id, amount, self._f_date.date().toPython(),
             self._f_method.currentText(), self._f_ref.text().strip() or None,
             self._f_note.text().strip() or None))
        self.accept()


class PaymentList(QScrollArea):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setObjectName("payments")
        ds.theme_changed.connect(self._restyle)
        self._restyle()

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
        self._layout.setSpacing(ds.space_sm)
        self.setWidget(self._container)
        self._setup_ui()
        self.refresh()

    @safe_slot("PaymentList._restyle")
    def _restyle(self):
        self.setStyleSheet(f"#payments {{ background: {theme_manager.palette.background}; border: none; }}")

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size

        hdr = QHBoxLayout()
        title = QLabel("Paiements enregistres")
        title.setStyleSheet(f"font-size: {s(ds.font_title_md)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        hdr.addWidget(title)
        hdr.addStretch()

        add_btn = QPushButton("+ Nouveau paiement")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setFixedHeight(ds.button_height)
        add_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: {ds.radius_sm}px; padding: {ds.space_xs}px {ds.space_m3}px; "
            f"font-size: {s(12)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.primary}; }}")
        add_btn.clicked.connect(self._on_add)
        hdr.addWidget(add_btn)
        self._layout.addLayout(hdr)

        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(ds.border_width)
        self._layout.addLayout(self._list_layout)

    def refresh(self):
        self._load()

    def _load(self):
        if not db.is_server_connected:
            return
        p = theme_manager.palette
        s = theme_manager.font_size
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        conn = db.server_conn
        if not conn:
            return
        cur = conn.cursor()
        cur.execute("""
            SELECT cp.id, a.first_name, a.last_name, cp.amount, cp.payment_date,
                   cp.payment_method, cp.reference
            FROM compta_payment cp
            JOIN larcauth_aecuser a ON a.id = cp.parent_id
            ORDER BY cp.payment_date DESC, cp.id DESC LIMIT 100
        """)
        for row in cur.fetchall():
            _, fn, ln, amount, date, method, ref = row
            rw = QWidget()
            rl = QHBoxLayout(rw)
            rl.setContentsMargins(ds.space_sm, ds.space_xs, ds.space_sm, ds.space_xs)
            rl.setSpacing(ds.space_m3)

            for text, w, color, size, bold in [
                (str(date), ds.space_xxl - ds.space_lg, p.text_soft, 11, False),
                (f"{ln} {fn}", ds.space_xxxl - ds.space_md, p.text_strong, 12, True),
                (_fmt(amount), ds.space_xxl + ds.space_md, p.success, 13, True),
                (method, ds.space_xxl, p.text_soft, 11, False),
            ]:
                lbl = QLabel(text)
                lbl.setFixedWidth(w)
                lbl.setStyleSheet(f"font-size: {s(size)}px; {'font-weight: bold;' if bold else ''} color: {color}; border: none;")
                rl.addWidget(lbl)

            if ref:
                rl2 = QLabel(ref)
                rl2.setStyleSheet(f"font-size: {s(10)}px; color: {p.text_soft}; border: none;")
                rl.addWidget(rl2)

            rl.addStretch()
            rw.setStyleSheet(f"QWidget {{ background: {p.surface}; border-radius: {ds.radius_xs}px; }}"
                             f"QWidget:hover {{ background: {p.surface_variant}; }}")
            self._list_layout.addWidget(rw)

        self._list_layout.addStretch()

    @safe_slot("PaymentList._on_add")
    def _on_add(self):
        dlg = _PaymentForm(self)
        if dlg.exec():
            self.refresh()
