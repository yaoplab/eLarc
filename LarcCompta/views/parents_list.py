"""ParentsList — Master-Detail : liste parents + dossier paiements par parent."""
from __future__ import annotations

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QDialog, QFormLayout, QLineEdit,
    QComboBox, QDateEdit, QMessageBox, QSplitter, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
)

from larccommon.database import db
from larccommon.widgets.themed_widget import ThemedDialog
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot

COLLEGE = 2500000
LYCEE = 3000000

def _fmt(amount: int) -> str:
    if amount >= 1000000: return f"{amount / 1000000:.1f} M"
    return f"{amount // 1000:,} K".replace(",", " ")

def _compute_status(paid: int, total_du: int, expected_pct: float) -> str:
    """Calcule le statut : solde, en_cours, en_retard."""
    if total_du <= 0:
        return "en_retard"
    if paid >= total_du:
        return "solde"
    expected_amount = int(total_du * expected_pct / 100.0)
    if paid >= expected_amount:
        return "en_cours"
    return "en_retard"

STATUS_COLORS = {"solde": "primary", "en_cours": "success", "en_retard": "error"}
STATUS_LABELS = {"solde": "Soldé", "en_cours": "En cours", "en_retard": "En retard"}


class _PaymentForm(ThemedDialog):
    """Dialogue d'enregistrement d'un paiement."""

    def __init__(self, parent_id: int, parent_name: str, parent=None):
        super().__init__(parent)
        self._pid = parent_id
        self._name = parent_name
        self.setWindowTitle(f"Paiement — {parent_name}")
        self.setMinimumSize(ds.golden_width(ds.sidebar_width), ds.sidebar_width)
        self._setup_ui()

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        self.setStyleSheet(f"background: {p.surface};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_sm)

        info = QLabel(f"Parent : {self._name}")
        info.setStyleSheet(f"font-size: {s(14)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        layout.addWidget(info)

        fstyle = (f"background: {p.background}; border: 1px solid {p.outline}; "
                  f"border-radius: {ds.radius_xs}px; padding: {ds.space_sm}px; "
                  f"color: {p.text_strong}; font-size: {s(13)}px;")

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
        self._f_ref.setPlaceholderText("Référence")
        self._f_ref.setFixedHeight(ds.field_height)
        self._f_ref.setStyleSheet(fstyle)
        form.addRow("Référence :", self._f_ref)

        self._f_file = QLineEdit()
        self._f_file.setPlaceholderText("Chemin du fichier (scan, photo, PDF)")
        self._f_file.setFixedHeight(ds.field_height)
        self._f_file.setStyleSheet(fstyle)
        form.addRow("Preuve (fichier) :", self._f_file)

        layout.addLayout(form)
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Annuler")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setFixedHeight(ds.button_height)
        cancel.setStyleSheet(f"QPushButton {{ background: transparent; color: {p.text_strong}; "
            f"border: 1px solid {p.outline}; border-radius: {ds.radius_sm}px; "
            f"padding: {ds.space_xs}px {ds.space_md}px; font-size: {s(13)}px; }}"
            f"QPushButton:hover {{ background: {p.surface_variant}; }}")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        save = QPushButton("Enregistrer")
        save.setCursor(Qt.PointingHandCursor)
        save.setFixedHeight(ds.button_height)
        save.setStyleSheet(f"QPushButton {{ background: {p.primary}; color: white; border: none; "
            f"border-radius: {ds.radius_sm}px; padding: {ds.space_xs}px {ds.space_md}px; "
            f"font-size: {s(13)}px; font-weight: bold; }}")
        save.clicked.connect(self._on_save)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)

    @safe_slot("_PaymentForm._on_save")
    def _on_save(self):
        if not db.is_server_connected:
            return
        try:
            amount = int(self._f_amount.text().replace(" ", ""))
        except ValueError:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            QMessageBox.warning(self, "Erreur", "Montant invalide.")
            return
        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()
        file_url = self._f_file.text().strip() or None
        cur.execute("INSERT INTO compta_payment (parent_id, amount, payment_date, payment_method, reference, file_url) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (self._pid, amount, self._f_date.date().toPython(),
                     self._f_method.currentText(), self._f_ref.text().strip() or None, file_url))
        self.accept()


class ParentsList(QWidget):
    """Master-Detail : liste parents à gauche, dossier à droite."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_pid: int = 0
        self._selected_paid: int = 0
        self._selected_du: int = 0
        self._status_filter: str = "tous"
        self._setup_ui()
        ds.theme_changed.connect(self._restyle)

    def _setup_ui(self):
        # QSplitter horizontal : liste | dossier
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._splitter)

        # ── Gauche : liste des parents ──
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(ds.space_md, ds.space_md, ds.space_xs, ds.space_md)
        ll.setSpacing(ds.space_sm)

        p = theme_manager.palette
        s = theme_manager.font_size

        # Recherche
        search = QLineEdit()
        search.setPlaceholderText("Rechercher un parent...")
        search.setFixedHeight(ds.field_height)
        search.setStyleSheet(f"background: {p.background}; border: 1px solid {p.outline}; "
            f"border-radius: {ds.radius_xs}px; padding: {ds.space_sm}px; "
            f"color: {p.text_strong}; font-size: {s(13)}px;")
        search.textChanged.connect(self._on_search)
        ll.addWidget(search)

        # Filtres statut
        flt_row = QHBoxLayout()
        flt_row.setSpacing(ds.space_xs)
        for key, label in [("tous", "Tous"), ("en_retard", "Retard"), ("en_cours", "Cours"), ("solde", "Soldé")]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(key == "tous")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(ds.space_lg)
            btn.setStyleSheet(f"QPushButton {{ background: {p.surface}; color: {p.text_strong}; "
                f"border: 1px solid {p.outline}; border-radius: {ds.radius_xs}px; "
                f"padding: {ds.space_xxs}px {ds.space_xs}px; font-size: {s(ds.font_label_sm)}px; }}"
                f"QPushButton:checked {{ background: {p.primary}; color: white; border-color: {p.primary}; }}")
            btn.clicked.connect(lambda checked, k=key: self._on_filter(k))
            flt_row.addWidget(btn)
        flt_row.addStretch()
        ll.addLayout(flt_row)

        # Table des parents
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Parent", "Statut", "Solde"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setStyleSheet(f"background: {p.surface}; alternate-background-color: {p.surface_variant}; "
            f"color: {p.text_strong}; gridline-color: {p.outline_variant}; "
            f"border: 1px solid {p.outline_variant}; border-radius: {ds.radius_xs}px;")
        self._table.horizontalHeader().setStyleSheet(f"QHeaderView::section {{ background: {p.surface_variant}; "
            f"color: {p.text_strong}; font-weight: bold; padding: {ds.space_xxs}px; border: none; }}")
        self._table.itemSelectionChanged.connect(self._on_select_parent)
        ll.addWidget(self._table, 1)

        self._splitter.addWidget(left)

        # ── Droite : dossier du parent ──
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QScrollArea.NoFrame)
        self._right = QWidget()
        self._right_layout = QVBoxLayout(self._right)
        self._right_layout.setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
        self._right_layout.setSpacing(ds.space_md)
        right_scroll.setWidget(self._right)

        self._detail_header = QLabel("Sélectionnez un parent")
        self._detail_header.setStyleSheet(f"font-size: {s(18)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        self._right_layout.addWidget(self._detail_header)

        self._children_layout = QVBoxLayout()
        self._right_layout.addLayout(self._children_layout)

        self._payments_layout = QVBoxLayout()
        self._right_layout.addLayout(self._payments_layout)

        self._summary_layout = QVBoxLayout()
        self._right_layout.addLayout(self._summary_layout)

        # Bouton ajouter paiement
        self._add_btn = QPushButton("+ Enregistrer un paiement")
        self._add_btn.setCursor(Qt.PointingHandCursor)
        self._add_btn.setFixedHeight(ds.button_height)
        self._add_btn.setStyleSheet(f"QPushButton {{ background: {p.primary}; color: white; border: none; "
            f"border-radius: {ds.radius_sm}px; padding: {ds.space_xs}px {ds.space_md}px; "
            f"font-size: {s(13)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.primary}; }}")
        self._add_btn.clicked.connect(self._on_add_payment)
        self._add_btn.setVisible(False)
        self._right_layout.addWidget(self._add_btn)

        self._right_layout.addStretch()
        self._splitter.addWidget(right_scroll)
        self._splitter.setSizes([ds.sidebar_width * 2, ds.sidebar_width * 4])

    @safe_slot("ParentsList._restyle")
    def _restyle(self):
        self.setStyleSheet(f"background: {theme_manager.palette.background}; border: none;")

    def refresh(self):
        self._load_list()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    # ── Liste des parents ──
    def _load_list(self):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()

        filter_clause = ""
        if self._status_filter != "tous":
            filter_clause = f"AND statut = '{self._status_filter}'"

        cur.execute(f"""
            SELECT par.id, par.first_name, par.last_name,
                   COALESCE(SUM(sf.annual_fee), 0) AS total_du,
                   COALESCE(pay.total_paid, 0) AS total_paid,
                   COUNT(DISTINCT sp.student_id) AS nb_enfants
            FROM larcauth_aecuser par
            JOIN larcauth_student_parent sp ON sp.parent_id = par.id
            JOIN larcauth_parent lp ON lp.aecuser_ptr_id = par.id AND lp.is_payer = TRUE
            LEFT JOIN compta_student_fee sf ON sf.student_id = sp.student_id
            LEFT JOIN LATERAL (
                SELECT COALESCE(SUM(cp.amount), 0) AS total_paid
                FROM compta_payment cp WHERE cp.parent_id = par.id
            ) pay ON true
            WHERE lp.enabled = TRUE {filter_clause}
            GROUP BY par.id, par.first_name, par.last_name, pay.total_paid
            ORDER BY (COALESCE(SUM(sf.annual_fee), 0) - COALESCE(pay.total_paid, 0)) DESC
        """)

        rows = cur.fetchall()
        self._table.setRowCount(len(rows))

        # Get expected pct for current month
        month = QDate.currentDate().month()
        cur.execute("SELECT percentage_expected FROM compta_payment_schedule "
                    "WHERE academic_year = '2026-2027' AND month_number = %s", (month,))
        sched = cur.fetchone()
        expected_pct = float(sched[0]) if sched else 0.0

        p = theme_manager.palette
        for i, row in enumerate(rows):
            pid, fn, ln, total_du, total_paid, nb_kids = row
            status = _compute_status(total_paid, total_du, expected_pct)

            name_item = QTableWidgetItem(f"{fn} {ln}  ({nb_kids} enf.)")
            name_item.setData(Qt.UserRole, pid)
            name_item.setData(Qt.UserRole + 1, total_paid)
            name_item.setData(Qt.UserRole + 2, total_du)

            status_item = QTableWidgetItem(STATUS_LABELS.get(status, status))
            sc = getattr(p, STATUS_COLORS.get(status, "text_strong"))
            status_item.setForeground(Qt.GlobalColor(int(sc[1:], 16)) if False else None)

            solde = total_du - total_paid
            solde_item = QTableWidgetItem(f"{_fmt(solde)} à payer" if solde > 0 else "Soldé")

            self._table.setItem(i, 0, name_item)
            self._table.setItem(i, 1, status_item)
            self._table.setItem(i, 2, solde_item)

        self._table.setColumnWidth(0, 230)
        self._table.setColumnWidth(1, 90)

    @safe_slot("ParentsList._on_search")
    def _on_search(self, text: str):
        # Filtre local sur le QTableWidget
        for i in range(self._table.rowCount()):
            item = self._table.item(i, 0)
            if item:
                item.setHidden(bool(text.lower() and text.lower() not in item.text().lower()))

    @safe_slot("ParentsList._on_filter")
    def _on_filter(self, key: str):
        self._status_filter = key
        self.refresh()

    # ── Dossier parent ──
    @safe_slot("ParentsList._on_select_parent")
    def _on_select_parent(self):
        sel = self._table.selectedItems()
        if not sel:
            return
        item = self._table.item(sel[0].row(), 0)
        if not item:
            return
        pid = item.data(Qt.UserRole)
        self._selected_pid = pid
        self._selected_paid = item.data(Qt.UserRole + 1)
        self._selected_du = item.data(Qt.UserRole + 2)
        self._load_dossier(pid)

    def _load_dossier(self, pid: int):
        if not db.is_server_connected:
            return
        p = theme_manager.palette
        s = theme_manager.font_size
        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()

        # Infos parent
        cur.execute("SELECT first_name, last_name, email, tel_smartphone_1 FROM larcauth_aecuser WHERE id = %s", (pid,))
        row = cur.fetchone()
        if not row: return
        fn, ln, email, phone = row

        # Nettoyer le panneau droit
        for layout_name in ['_children_layout', '_payments_layout', '_summary_layout']:
            lo = getattr(self, layout_name)
            while lo.count():
                item = lo.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()

        # En-tête
        self._detail_header.setText(f"Dossier de {fn} {ln}")
        cont = QLabel(f"Email : {email or '—'}  ·  Tél : {phone or '—'}")
        cont.setStyleSheet(f"font-size: {s(11)}px; color: {p.text_soft}; border: none;")
        self._detail_header.setVisible(True)
        # Insérer sous le titre
        # (pas élégant mais fonctionnel)
        self._right_layout.insertWidget(1, cont)
        self._detail_contact = cont

        # ── Enfants ──
        cur.execute(f"""
            SELECT a.first_name, a.last_name, c.label AS class_label,
                   COALESCE(sf.annual_fee, CASE WHEN prog.id IN (13,23) THEN {LYCEE} ELSE {COLLEGE} END) AS fee,
                   p_stat.sigle
            FROM larcauth_student_parent sp
            JOIN larcauth_student st ON st.aecuser_ptr_id = sp.student_id
            JOIN larcauth_aecuser a ON a.id = st.aecuser_ptr_id
            JOIN larcauth_classroom c ON c.id = st.s_classroom_id
            JOIN larcauth_level l ON l.id = c.fk_level_id
            JOIN larcauth_program prog ON prog.id = l.fk_program_id
            JOIN larcauth_program p_stat ON p_stat.id = l.fk_program_id  -- for GROUP BY
            LEFT JOIN compta_student_fee sf ON sf.student_id = sp.student_id
            WHERE sp.parent_id = %s AND st.enabled = TRUE
            LIMIT 10
        """, (pid,))
        children = cur.fetchall()

        if children:
            title = QLabel("ENFANTS")
            title.setStyleSheet(f"font-size: {s(12)}px; font-weight: bold; color: {p.primary}; border: none;")
            self._children_layout.addWidget(title)

            for fn2, ln2, cls, fee, sigle in children:
                row_w = QWidget()
                row_w.setAttribute(Qt.WA_StyledBackground, True)
                rl = QHBoxLayout(row_w)
                rl.setContentsMargins(ds.space_sm, ds.space_xxs, ds.space_sm, ds.space_xxs)
                rl.setSpacing(ds.space_md)
                rl.addWidget(QLabel(f"{fn2} {ln2}"))
                rl.addWidget(QLabel(f"{cls} ({sigle})"))
                rl.addWidget(QLabel(_fmt(fee)))
                rl.addStretch()
                for lbl in row_w.findChildren(QLabel):
                    lbl.setStyleSheet(f"font-size: {s(12)}px; color: {p.text_strong}; border: none;")
                row_w.setStyleSheet(f"QWidget {{ background: {p.surface}; border-radius: {ds.radius_xs}px; }}")
                self._children_layout.addWidget(row_w)

        # ── Paiements ──
        cur.execute("""
            SELECT amount, payment_date, payment_method, reference, file_url
            FROM compta_payment WHERE parent_id = %s ORDER BY payment_date DESC LIMIT 20
        """, (pid,))
        payments = cur.fetchall()

        if payments:
            title2 = QLabel("PAIEMENTS")
            title2.setStyleSheet(f"font-size: {s(12)}px; font-weight: bold; color: {p.primary}; border: none;")
            self._payments_layout.addWidget(title2)

            for amt, date, method, ref, file_url in payments:
                row_w = QWidget()
                rl = QHBoxLayout(row_w)
                rl.setContentsMargins(ds.space_sm, ds.space_xxs, ds.space_sm, ds.space_xxs)
                rl.setSpacing(ds.space_md)
                rl.addWidget(QLabel(str(date)))
                rl.addWidget(QLabel(_fmt(amt)))
                rl.addWidget(QLabel(method))
                if ref:
                    rl.addWidget(QLabel(ref))
                if file_url:
                    link = QLabel(file_url)
                    link.setStyleSheet(f"font-size: {s(10)}px; color: {p.primary}; "
                                      f"text-decoration: underline; border: none;")
                    link.setToolTip(file_url)
                    rl.addWidget(link)
                rl.addStretch()
                for lbl in row_w.findChildren(QLabel):
                    lbl.setStyleSheet(f"font-size: {s(12)}px; color: {p.text_strong}; border: none;")
                    if file_url and lbl.text() == file_url:
                        lbl.setStyleSheet(f"font-size: {s(10)}px; color: {p.primary}; "
                                         f"text-decoration: underline; border: none;")
                row_w.setStyleSheet(f"QWidget {{ background: {p.surface}; border-radius: {ds.radius_xs}px; }}")
                self._payments_layout.addWidget(row_w)
        else:
            empty = QLabel("Aucun paiement enregistré")
            empty.setStyleSheet(f"font-size: {s(12)}px; color: {p.text_soft}; font-style: italic; border: none;")
            self._payments_layout.addWidget(empty)

        # ── Résumé ──
        self._add_btn.setVisible(True)
        self._refresh_summary()

    def _refresh_summary(self):
        if not db.is_server_connected:
            return
        p = theme_manager.palette
        s = theme_manager.font_size
        while self._summary_layout.count():
            item = self._summary_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()

        # Lire la balance (1 seule requete)
        cur.execute("""
            SELECT total_due, total_paid, remaining, status, status_override,
                   COALESCE(change_history, '[]'::jsonb)
            FROM compta_parent_balance
            WHERE parent_id = %s AND academic_year = '2026-2027'
        """, (self._selected_pid,))
        bal = cur.fetchone()
        if not bal:
            return
        total_du, total_paid, remaining, status, is_overridden, history = bal
        self._selected_paid = total_paid
        self._selected_du = total_du

        # Echeancier pour info
        month = QDate.currentDate().month()
        cur.execute("SELECT percentage_expected FROM compta_payment_schedule "
                    "WHERE academic_year = '2026-2027' AND month_number = %s", (month,))
        sched = cur.fetchone()
        expected_pct = float(sched[0]) if sched else 0.0
        expected_amount = int(total_du * expected_pct / 100.0)

        summary_w = QWidget()
        sl = QFormLayout(summary_w)
        sl.setSpacing(ds.space_xs)

        def _row(label, value, color):
            lbl = QLabel(label)
            lbl.setStyleSheet(f"font-size: {s(12)}px; font-weight: bold; color: {p.text_soft}; border: none;")
            val = QLabel(value)
            val.setStyleSheet(f"font-size: {s(14)}px; font-weight: bold; color: {color}; border: none;")
            sl.addRow(lbl, val)

        _row("Total dû", _fmt(total_du), p.text_strong)
        _row("Total payé", _fmt(total_paid), p.success)
        _row("Reste à payer", _fmt(remaining), p.error if remaining > 0 else p.success)
        _row(f"Attendu ({expected_pct:.0f}%)", _fmt(expected_amount), p.primary)

        # Barre
        pct_val = (total_paid / total_du * 100) if total_du > 0 else 0
        bar_bg = QFrame()
        bar_bg.setAttribute(Qt.WA_StyledBackground, True)
        bar_bg.setFixedHeight(ds.space_md)
        bar_bg.setStyleSheet(f"background: {p.outline_variant}; border-radius: {ds.radius_xs // 2}px;")
        bar_fill = QFrame(bar_bg)
        bar_fill.setAttribute(Qt.WA_StyledBackground, True)
        bar_fill.setFixedSize(max(ds.space_xxs, int(300 * pct_val / 100)), ds.space_md)
        bar_fill.setStyleSheet(f"background: {getattr(p, STATUS_COLORS.get(status, 'primary'))}; "
                               f"border-radius: {ds.radius_xs // 2}px;")
        sl.addRow("Progression", bar_bg)

        # Statut
        status_color = getattr(p, STATUS_COLORS.get(status, "primary"))
        override_mark = " ✎" if is_overridden else ""
        status_lbl = QLabel(STATUS_LABELS.get(status, status) + override_mark)
        status_lbl.setStyleSheet(f"font-size: {s(22)}px; font-weight: bold; color: {status_color}; border: none;")
        sl.addRow("Statut", status_lbl)

        # Combo override
        combo = QComboBox()
        combo.addItems(["en_retard", "en_cours", "solde", "exonere"])
        combo.setCurrentText(status)
        combo.setFixedWidth(ds.space_xxxl + ds.space_md)  # 136+20=156
        combo.setStyleSheet(f"background: {p.background}; border: 1px solid {p.outline}; "
            f"border-radius: {ds.radius_xs}px; padding: {ds.space_xs}px; "
            f"color: {p.text_strong}; font-size: {s(12)}px;")
        combo.currentTextChanged.connect(
            lambda t, pid=self._selected_pid: self._set_status_override(pid, t))
        sl.addRow("Modifier statut", combo)

        # Historique
        if history:
            hist_title = QLabel("Historique des changements")
            hist_title.setStyleSheet(f"font-size: {s(11)}px; font-weight: bold; color: {p.text_soft}; border: none;")
            sl.addRow(hist_title)
            for entry in history:
                e = QLabel(f"{entry.get('at','?')[:16]} — {entry.get('what','?')} : {entry.get('new_status','?')}")
                e.setStyleSheet(f"font-size: {s(10)}px; color: {p.text_soft}; border: none;")
                sl.addRow(e)

        self._summary_layout.addWidget(summary_w)

    def _set_status_override(self, pid: int, new_status: str):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()
        import json as _j
        # Mettre a jour la balance parent
        cur.execute("""
            UPDATE compta_parent_balance SET
                status = %s,
                status_override = TRUE,
                change_history = change_history || %s::jsonb,
                updated_at = NOW()
            WHERE parent_id = %s AND academic_year = '2026-2027'
        """, (new_status, _j.dumps([{"at": str(QDate.currentDate().toPython()),
                                      "what": "status_override", "new_status": new_status}]), pid))
        # Propager aux enfants
        cur.execute("""
            UPDATE larcauth_student SET statut_scolarite = %s
            WHERE aecuser_ptr_id IN (
                SELECT sp.student_id FROM larcauth_student_parent sp WHERE sp.parent_id = %s
            )
        """, (new_status, pid))
        self._refresh_summary()

    @safe_slot("ParentsList._on_add_payment")
    def _on_add_payment(self):
        if not db.is_server_connected:
            return
        if not self._selected_pid:
            return
        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()
        cur.execute("SELECT first_name, last_name FROM larcauth_aecuser WHERE id = %s",
                    (self._selected_pid,))
        row = cur.fetchone()
        name = f"{row[1]} {row[0]}" if row else "Parent"
        dlg = _PaymentForm(self._selected_pid, name, self)
        if dlg.exec():
            # Recalculer le statut du parent et propager à tous ses enfants
            self._sync_parent_to_children(self._selected_pid)
            self._load_dossier(self._selected_pid)
            self.refresh()

    def _sync_parent_to_children(self, parent_id: int):
        if not db.is_server_connected:
            return
        """Recalcule le statut et met a jour compta_parent_balance + larcauth_student."""
        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()

        # Total du pour ce parent
        cur.execute("""SELECT COALESCE(SUM(sf.annual_fee), 0)
            FROM larcauth_student_parent sp
            JOIN compta_student_fee sf ON sf.student_id = sp.student_id
            WHERE sp.parent_id = %s""", (parent_id,))
        total_du = cur.fetchone()[0] or 0

        # Total paye
        cur.execute("SELECT COALESCE(SUM(amount), 0) FROM compta_payment WHERE parent_id = %s",
                    (parent_id,))
        total_paid = cur.fetchone()[0] or 0
        remaining = total_du - total_paid

        # Echeancier
        month = QDate.currentDate().month()
        cur.execute("SELECT percentage_expected FROM compta_payment_schedule "
                    "WHERE academic_year = '2026-2027' AND month_number = %s", (month,))
        sched = cur.fetchone()
        expected_pct = float(sched[0]) if sched else 0.0

        status = _compute_status(total_paid, total_du, expected_pct)

        # 1. Mettre a jour la balance parent (source de verite)
        import json as _j
        cur.execute("""
            INSERT INTO compta_parent_balance (parent_id, academic_year, total_due, total_paid, remaining, status, change_history)
            VALUES (%s, '2026-2027', %s, %s, %s, %s, %s)
            ON CONFLICT (parent_id, academic_year) DO UPDATE SET
                total_due = EXCLUDED.total_due,
                total_paid = EXCLUDED.total_paid,
                remaining = EXCLUDED.remaining,
                status = EXCLUDED.status,
                change_history = compta_parent_balance.change_history || EXCLUDED.change_history::jsonb,
                updated_at = NOW()
        """, (parent_id, total_du, total_paid, remaining, status,
              _j.dumps([{"at": str(QDate.currentDate().toPython()),
                          "what": "paiement_sync", "new_status": status,
                          "paid": total_paid, "du": total_du}])))

        # 2. Propager aux enfants
        cur.execute("""
            UPDATE larcauth_student SET statut_scolarite = %s
            WHERE aecuser_ptr_id IN (
                SELECT sp.student_id FROM larcauth_student_parent sp WHERE sp.parent_id = %s
            )
        """, (status, parent_id))
