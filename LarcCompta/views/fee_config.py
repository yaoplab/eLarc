"""FeeConfig — barèmes par programme + échéancier + milestones (skills Larc)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QScrollArea, QFrame,
    QLineEdit, QFormLayout, QDateEdit, QMessageBox,
)

from larccommon.database import db
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot
from larccommon.icons import icon as md3_icon


def _fmt(amount: int) -> str:
    if amount >= 1000000: return f"{amount / 1000000:.1f} M"
    return f"{amount // 1000:,} K".replace(",", " ")

# Regroupement niveaux → programmes
PROG_ORDER = ["PYP", "PP", "PEI", "MYP", "DPFr", "DPEn"]
PROG_COLORS = {"PYP": "primary", "PP": "secondary", "PEI": "primary",
               "MYP": "secondary", "DPFr": "error", "DPEn": "tertiary"}
MONTHS = ["Septembre", "Octobre", "Novembre", "Décembre",
          "Janvier", "Février", "Mars", "Avril", "Mai", "Juin"]


class FeeConfig(QScrollArea):
    """Configuration : barèmes groupés par programme + échéancier + milestones."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setObjectName("fee_config")
        ds.theme_changed.connect(self._restyle)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
        self._layout.setSpacing(ds.space_md)
        self.setWidget(self._container)
        self._restyle()
        self._setup_ui()
        self.refresh()

    @safe_slot("FeeConfig._restyle")
    def _restyle(self):
        self.setStyleSheet(
            f"#fee_config {{ background: {theme_manager.palette.background}; border: none; }}")

    def _setup_ui(self):
        s = theme_manager.font_size
        # ── Titre ──
        title = QLabel("Configuration — Barèmes & Échéanciers")
        title.setStyleSheet(f"font-size: {s(18)}px; font-weight: bold; "
                            f"color: {theme_manager.palette.text_strong}; border: none;")
        self._layout.addWidget(title)

        # ── Placeholder grille programmes ──
        self._prog_grid = QGridLayout()
        self._prog_grid.setSpacing(ds.space_md)
        self._layout.addLayout(self._prog_grid)

        # ── Échéancier ──
        self._sched_card = None
        self._sched_layout = None

        # ── Milestones ──
        self._milestone_card = None
        self._milestone_layout = None

        self._layout.addStretch()

    def refresh(self):
        self._load_fees()
        self._load_schedule()
        self._load_milestones()

    # ═══════════════ BARÈME PAR PROGRAMME ═══════════════
    def _load_fees(self):
        # Nettoyer
        if not db.is_server_connected:
            return
        while self._prog_grid.count():
            item = self._prog_grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        p = theme_manager.palette
        s = theme_manager.font_size
        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()
        cur.execute("""
            SELECT cfl.id, l.label, p.sigle, cfl.annual_fee, cfl.level_id
            FROM compta_fee_level cfl
            JOIN larcauth_level l ON l.id = cfl.level_id
            JOIN larcauth_program p ON p.id = l.fk_program_id
            WHERE cfl.academic_year = '2026-2027'
            ORDER BY p.sigle, l.label
        """)
        rows = cur.fetchall()

        # Grouper par sigle
        by_prog: dict[str, list] = {sig: [] for sig in PROG_ORDER}
        for row in rows:
            fid, level, sigle, annual, lid = row
            if sigle in by_prog:
                by_prog[sigle].append((fid, level, annual, lid))

        # Disposer les cartes en grille 2 colonnes
        col = 0
        row = 0
        for sigle in PROG_ORDER:
            levels = by_prog[sigle]
            if not levels:
                continue
            card = self._build_prog_card(sigle, levels, p, s)
            self._prog_grid.addWidget(card, row, col)
            col += 1
            if col >= 2:
                col = 0
                row += 1

    def _build_prog_card(self, sigle: str, levels: list, p, s) -> QFrame:
        """Carte M3Frame pour un programme."""
        accent = getattr(p, PROG_COLORS.get(sigle, "primary"))
        card = QFrame()
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet(f"""
            QFrame {{
                background: {p.surface}; border: 1px solid {p.outline_variant};
                border-radius: {ds.radius_sm}px; border-left: 4px solid {accent};
            }}
        """)
        lo = QVBoxLayout(card)
        lo.setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
        lo.setSpacing(ds.space_xs)

        # En-tête programme
        hdr = QLabel(sigle)
        hdr.setStyleSheet(f"font-size: {s(16)}px; font-weight: bold; color: {accent}; border: none;")
        lo.addWidget(hdr)

        for fid, level, annual, lid in levels:
            row_w = QWidget()
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(ds.space_xs, ds.space_xxs, ds.space_xs, ds.space_xxs)
            rl.setSpacing(ds.space_sm)

            lbl = QLabel(level)
            lbl.setFixedWidth(ds.space_xxl + ds.space_md)
            lbl.setStyleSheet(f"font-size: {s(12)}px; color: {p.text_strong}; border: none;")
            rl.addWidget(lbl)

            # Champ montant éditable
            fee = QLineEdit(str(annual))
            fee.setFixedWidth(ds.space_xxl)
            fee.setFixedHeight(ds.field_height - ds.space_md)
            fee.setAlignment(Qt.AlignRight)
            fee.setStyleSheet(
                f"background: {p.background}; border: 1px solid {p.outline}; "
                f"border-radius: {ds.radius_xs}px; padding: {ds.space_xxs}px {ds.space_xs}px; "
                f"color: {p.text_strong}; font-size: {s(12)}px;")
            fee.editingFinished.connect(lambda le=fee, f=fid: self._save_fee(f, le.text()))
            rl.addWidget(fee)

            fcfa = QLabel("FCFA")
            fcfa.setStyleSheet(f"font-size: {s(11)}px; color: {p.text_soft}; border: none;")
            rl.addWidget(fcfa)
            rl.addStretch()

            lo.addWidget(row_w)

        return card

    def _save_fee(self, fee_id: int, text: str):
        if not db.is_server_connected:
            return
        try:
            amount = int(text.replace(" ", ""))
        except ValueError:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return
        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()
        cur.execute("UPDATE compta_fee_level SET annual_fee=%s, monthly_amount=%s WHERE id=%s",
                    (amount, amount // 10, fee_id))

    # ═══════════════ ÉCHÉANCIER GLOBAL ═══════════════
    def _load_schedule(self):
        if not db.is_server_connected:
            return
        p = theme_manager.palette
        s = theme_manager.font_size
        # Retirer l'ancienne carte
        if self._sched_card and self._sched_card.parent():
            self._layout.removeWidget(self._sched_card)
            self._sched_card.deleteLater()

        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()
        cur.execute("SELECT id, month_number, percentage_expected "
                    "FROM compta_payment_schedule WHERE academic_year='2026-2027' "
                    "ORDER BY month_number")

        card = QFrame()
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet(f"""
            QFrame {{ background: {p.surface}; border: 1px solid {p.outline_variant};
            border-radius: {ds.radius_sm}px; border-left: 4px solid {p.primary}; }}
        """)
        lo = QVBoxLayout(card)
        lo.setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
        lo.setSpacing(ds.space_xs)

        hdr = QLabel("Échéancier global (% attendu cumulé)")
        hdr.setStyleSheet(f"font-size: {s(16)}px; font-weight: bold; color: {p.primary}; border: none;")
        lo.addWidget(hdr)

        # Grille 5×2 pour les 10 mois
        grid = QGridLayout()
        grid.setSpacing(ds.space_sm)
        for i, (sid2, mn, pct) in enumerate(cur.fetchall()):
            w = QWidget()
            rl = QHBoxLayout(w)
            rl.setContentsMargins(ds.space_xs, ds.space_xxs, ds.space_xs, ds.space_xxs)
            rl.setSpacing(ds.space_xs)

            lbl = QLabel(MONTHS[mn - 1] if mn <= 10 else f"Mois {mn}")
            lbl.setStyleSheet(f"font-size: {s(11)}px; color: {p.text_strong}; border: none;")
            rl.addWidget(lbl)

            pct_edit = QLineEdit(str(pct))
            pct_edit.setFixedWidth(ds.logo_small)  # 55px
            pct_edit.setFixedHeight(ds.field_height - ds.space_md)
            pct_edit.setAlignment(Qt.AlignRight)
            pct_edit.setStyleSheet(
                f"background: {p.background}; border: 1px solid {p.outline}; "
                f"border-radius: {ds.radius_xs}px; padding: {ds.space_xxs}px {ds.space_xs}px; "
                f"color: {p.text_strong}; font-size: {s(11)}px;")
            pct_edit.editingFinished.connect(lambda le=pct_edit, sid=sid2: self._save_schedule(sid, le.text()))
            rl.addWidget(pct_edit)

            pct_lbl = QLabel("%")
            pct_lbl.setStyleSheet(f"font-size: {s(11)}px; color: {p.text_soft}; border: none;")
            rl.addWidget(pct_lbl)

            grid.addWidget(w, i // 2, i % 2)

        lo.addLayout(grid)
        self._sched_card = card
        self._sched_layout = lo
        # Insérer avant le stretch final
        self._layout.insertWidget(self._layout.count() - 1, card)

    def _save_schedule(self, sid: int, text: str):
        if not db.is_server_connected:
            return
        try:
            pct = float(text)
            if pct < 0 or pct > 100: return
        except ValueError:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return
        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()
        cur.execute("UPDATE compta_payment_schedule SET percentage_expected=%s WHERE id=%s", (pct, sid))

    # ═══════════════ ÉCHÉANCES PARENTS ═══════════════
    def _load_milestones(self):
        if not db.is_server_connected:
            return
        p = theme_manager.palette
        s = theme_manager.font_size
        if self._milestone_card and self._milestone_card.parent():
            self._layout.removeWidget(self._milestone_card)
            self._milestone_card.deleteLater()

        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()
        cur.execute("""
            SELECT m.id, a.first_name, a.last_name, m.due_date, m.amount_expected, m.notes
            FROM compta_parent_milestone m
            JOIN larcauth_aecuser a ON a.id = m.parent_id
            ORDER BY m.due_date DESC, a.last_name LIMIT 50
        """)
        rows = cur.fetchall()

        card = QFrame()
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet(f"""
            QFrame {{ background: {p.surface}; border: 1px solid {p.outline_variant};
            border-radius: {ds.radius_sm}px; border-left: 4px solid {p.tertiary}; }}
        """)
        lo = QVBoxLayout(card)
        lo.setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
        lo.setSpacing(ds.space_sm)

        hdr_row = QHBoxLayout()
        hdr = QLabel("Échéances personnalisées parents")
        hdr.setStyleSheet(f"font-size: {s(16)}px; font-weight: bold; color: {p.tertiary}; border: none;")
        hdr_row.addWidget(hdr)
        hdr_row.addStretch()

        add_btn = QPushButton("+ Ajouter")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setFixedHeight(ds.button_height)
        add_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: {ds.radius_sm}px; padding: {ds.space_xs}px {ds.space_md}px; "
            f"font-size: {s(12)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.primary}; }}")
        add_btn.clicked.connect(self._add_milestone)
        hdr_row.addWidget(add_btn)
        lo.addLayout(hdr_row)

        if not rows:
            empty = QLabel("Aucune échéance personnalisée")
            empty.setStyleSheet(f"font-size: {s(12)}px; color: {p.text_soft}; font-style: italic; border: none;")
            lo.addWidget(empty)
        else:
            for mid, fn, ln, due, amount, notes in rows:
                rw = QWidget()
                rl = QHBoxLayout(rw)
                rl.setContentsMargins(ds.space_sm, ds.space_xxs, ds.space_sm, ds.space_xxs)
                rl.setSpacing(ds.space_md)

                for text, w, color, bold in [
                    (f"{fn} {ln}", ds.space_xxxl, p.text_strong, True),
                    (str(due), ds.space_xxl + ds.space_md, p.text_soft, False),
                    (_fmt(amount), ds.space_xxl, p.primary, True),
                    (notes or "", ds.space_xxxl, p.text_soft, False),
                ]:
                    lbl = QLabel(text)
                    lbl.setFixedWidth(w)
                    lbl.setStyleSheet(f"font-size: {s(11)}px; {'font-weight: bold;' if bold else ''} "
                                      f"color: {color}; border: none;")
                    rl.addWidget(lbl)

                del_btn = QPushButton("×")
                del_btn.setCursor(Qt.PointingHandCursor)
                del_btn.setFixedSize(ds.space_lg, ds.space_lg)
                del_btn.setStyleSheet(
                    f"QPushButton {{ background: transparent; color: {p.error}; border: 1px solid {p.error}; "
                    f"border-radius: {ds.radius_xs // 2}px; font-size: {s(14)}px; font-weight: bold; }}"
                    f"QPushButton:hover {{ background: {p.error}; color: white; }}")
                del_btn.clicked.connect(lambda checked, m=mid: self._delete_milestone(m))
                rl.addWidget(del_btn)
                rl.addStretch()

                lo.addWidget(rw)

        self._milestone_card = card
        self._layout.insertWidget(self._layout.count() - 1, card)

    @safe_slot("FeeConfig._add_milestone")
    def _add_milestone(self):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()

        from PySide6.QtWidgets import QDialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Nouvelle échéance parent")
        dlg.setMinimumSize(ds.golden_width(ds.sidebar_width), ds.space_xxxl + ds.space_xl)
        dlg.setStyleSheet(f"background: {theme_manager.palette.surface};")
        lo = QFormLayout(dlg)
        lo.setSpacing(ds.space_sm)

        fstyle = (f"background: {theme_manager.palette.background}; "
                  f"border: 1px solid {theme_manager.palette.outline}; "
                  f"border-radius: {ds.radius_xs}px; padding: {ds.space_sm}px; "
                  f"color: {theme_manager.palette.text_strong}; "
                  f"font-size: {theme_manager.font_size(13)}px;")

        parent_name = QLineEdit()
        parent_name.setPlaceholderText("Nom du parent payeur...")
        parent_name.setFixedHeight(ds.field_height)
        parent_name.setStyleSheet(fstyle)
        lo.addRow("Parent :", parent_name)

        due_date = QDateEdit()
        due_date.setDate(QDate.currentDate())
        due_date.setCalendarPopup(True)
        due_date.setFixedHeight(ds.field_height)
        due_date.setStyleSheet(fstyle)
        lo.addRow("Date échéance :", due_date)

        amount = QLineEdit()
        amount.setPlaceholderText("Montant attendu (FCFA)")
        amount.setFixedHeight(ds.field_height)
        amount.setStyleSheet(fstyle)
        lo.addRow("Montant :", amount)

        note = QLineEdit()
        note.setPlaceholderText("Note (optionnel)")
        note.setFixedHeight(ds.field_height)
        note.setStyleSheet(fstyle)
        lo.addRow("Note :", note)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Annuler")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setFixedHeight(ds.button_height)
        cancel.setStyleSheet(f"QPushButton {{ background: transparent; color: {theme_manager.palette.text_strong}; "
            f"border: 1px solid {theme_manager.palette.outline}; border-radius: {ds.radius_sm}px; "
            f"padding: {ds.space_xs}px {ds.space_md}px; }}"
            f"QPushButton:hover {{ background: {theme_manager.palette.surface_variant}; }}")
        cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel)
        save_btn = QPushButton("Ajouter")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setFixedHeight(ds.button_height)
        save_btn.setStyleSheet(f"QPushButton {{ background: {theme_manager.palette.primary}; color: white; "
            f"border: none; border-radius: {ds.radius_sm}px; "
            f"padding: {ds.space_xs}px {ds.space_md}px; font-weight: bold; }}")
        btn_row.addWidget(save_btn)
        lo.addRow(btn_row)

        def on_save():
            name = parent_name.text().strip()
            try:
                amt = int(amount.text().replace(" ", ""))
            except ValueError:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                return
            if not name or amt <= 0: return
            cur2 = conn.cursor()
            cur2.execute("SELECT id FROM larcauth_aecuser WHERE "
                         "(first_name || ' ' || last_name) ILIKE %s LIMIT 1", (f"%{name}%",))
            pr = cur2.fetchone()
            if not pr:
                QMessageBox.warning(dlg, "Erreur", "Parent introuvable.")
                return
            cur2.execute("INSERT INTO compta_parent_milestone (parent_id, due_date, amount_expected, notes) "
                         "VALUES (%s, %s, %s, %s)",
                         (pr[0], due_date.date().toPython(), amt, note.text().strip() or None))
            dlg.accept()

        save_btn.clicked.connect(on_save)
        if dlg.exec():
            self.refresh()

    def _delete_milestone(self, mid: int):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()
        cur.execute("DELETE FROM compta_parent_milestone WHERE id = %s", (mid,))
        self.refresh()
