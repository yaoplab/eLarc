"""Impayes — liste actionnable des parents en retard (skill scolarite-finance S5)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QComboBox,
)

from larccommon.database import db
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot


def _fmt(amount: int) -> str:
    if amount >= 1000000: return f"{amount / 1000000:.1f} M"
    return f"{amount // 1000:,} K".replace(",", " ")


class Impayes(QScrollArea):
    """Liste des parents en retard avec filtres et actions groupées (S5a-S5c)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setObjectName("impayes")
        ds.theme_changed.connect(self._restyle)
        self._restyle()

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
        self._layout.setSpacing(ds.space_md)
        self.setWidget(self._container)

        self._filter_prog = "tous"
        self._filter_amount = 0
        self._setup_ui()
        self.refresh()

    @safe_slot("Impayes._restyle")
    def _restyle(self):
        self.setStyleSheet(
            f"#impayes {{ background: {theme_manager.palette.background}; border: none; }}")

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size

        # Titre
        title = QLabel("Impayés")
        title.setStyleSheet(
            f"font-size: {s(18)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        self._layout.addWidget(title)

        # ── Filtres ──
        flt_card = QFrame()
        flt_card.setAttribute(Qt.WA_StyledBackground, True)
        flt_card.setStyleSheet(f"""
            QFrame {{ background: {p.surface}; border: 1px solid {p.outline_variant};
            border-radius: {ds.radius_sm}px; border-left: 4px solid {p.error}; }}
        """)
        flt_lo = QHBoxLayout(flt_card)
        flt_lo.setContentsMargins(ds.space_m3, ds.space_sm, ds.space_m3, ds.space_sm)
        flt_lo.setSpacing(ds.space_md)

        flt_lo.addWidget(QLabel("Programme :"))
        prog_combo = QComboBox()
        prog_combo.addItems(["Tous", "PYP", "PP", "PEI", "MYP", "DPFr", "DPEn"])
        prog_combo.currentTextChanged.connect(
            lambda t: self._set_filter(prog=t.lower() if t != "Tous" else "tous"))
        prog_combo.setStyleSheet(
            f"background: {p.background}; border: 1px solid {p.outline}; "
            f"border-radius: {ds.radius_xs}px; padding: {ds.space_xs}px; "
            f"color: {p.text_strong}; font-size: {s(12)}px;")
        flt_lo.addWidget(prog_combo)

        flt_lo.addWidget(QLabel("Restant >"))
        amt_combo = QComboBox()
        amt_combo.addItems(["Tout", "500 000", "1 000 000", "2 000 000", "5 000 000"])
        amt_combo.currentTextChanged.connect(
            lambda t: self._set_filter(amount=0 if t == "Tout" else int(t.replace(" ", ""))))
        amt_combo.setStyleSheet(
            f"background: {p.background}; border: 1px solid {p.outline}; "
            f"border-radius: {ds.radius_xs}px; padding: {ds.space_xs}px; "
            f"color: {p.text_strong}; font-size: {s(12)}px;")
        flt_lo.addWidget(amt_combo)

        flt_lo.addStretch()

        rappel_btn = QPushButton("📩 Rappel groupé")
        rappel_btn.setCursor(Qt.PointingHandCursor)
        rappel_btn.setFixedHeight(ds.button_height)
        rappel_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: {ds.radius_sm}px; padding: {ds.space_xs}px {ds.space_md}px; "
            f"font-size: {s(12)}px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {p.primary}; }}")
        rappel_btn.clicked.connect(self._on_send_all)
        flt_lo.addWidget(rappel_btn)

        self._layout.addWidget(flt_card)

        # ── Liste ──
        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(ds.border_width)
        self._layout.addLayout(self._list_layout)
        self._layout.addStretch()

    def _set_filter(self, prog: str | None = None, amount: int | None = None):
        if prog is not None:
            self._filter_prog = prog
        if amount is not None:
            self._filter_amount = amount
        self.refresh()

    def refresh(self):
        self._load()

    def _load(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()

        # Filtre programme
        prog_filter = ""
        prog_params = []
        if self._filter_prog != "tous":
            prog_filter = "AND EXISTS (SELECT 1 FROM larcauth_student_parent sp2 JOIN larcauth_student st2 ON st2.aecuser_ptr_id = sp2.student_id JOIN larcauth_classroom c2 ON c2.id = st2.s_classroom_id JOIN larcauth_level l2 ON l2.id = c2.fk_level_id JOIN larcauth_program p2 ON p2.id = l2.fk_program_id WHERE sp2.parent_id = b.parent_id AND p2.sigle = %s)"
            prog_params = [self._filter_prog]

        # Filtre montant
        amount_filter = ""
        if self._filter_amount > 0:
            amount_filter = "AND b.remaining > %s"
            prog_params.append(self._filter_amount)

        cur.execute(f"""
            SELECT b.parent_id, a.first_name, a.last_name,
                   b.total_due, b.total_paid, b.remaining,
                   b.status,
                   COALESCE((SELECT MAX(cp.payment_date) FROM compta_payment cp WHERE cp.parent_id = b.parent_id), NULL) as last_payment,
                   COALESCE((SELECT COUNT(DISTINCT sp.student_id) FROM larcauth_student_parent sp WHERE sp.parent_id = b.parent_id), 0) as nb_enfants
            FROM compta_parent_balance b
            JOIN larcauth_aecuser a ON a.id = b.parent_id
            WHERE b.academic_year = '2026-2027'
              AND b.remaining > 0
              {prog_filter}
              {amount_filter}
            ORDER BY b.remaining DESC
            LIMIT 50
        """, prog_params)

        rows = cur.fetchall()
        if not rows:
            empty = QLabel("Aucun impayé trouvé. Félicitations !")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(
                f"font-size: {s(14)}px; color: {p.success}; font-style: italic; border: none;")
            self._list_layout.addWidget(empty)
            return

        # Résumé en haut
        total_restant = sum(r[5] for r in rows)
        summary = QLabel(f"{len(rows)} parents en retard — {_fmt(total_restant)} restant à encaisser")
        summary.setStyleSheet(
            f"font-size: {s(13)}px; font-weight: bold; color: {p.error}; border: none;")
        self._list_layout.addWidget(summary)

        for pid, fn, ln, total_du, total_paid, remaining, status, last_payment, nb_kids in rows:
            rw = QWidget()
            rl = QHBoxLayout(rw)
            rl.setContentsMargins(ds.space_sm, ds.space_xs, ds.space_sm, ds.space_xs)
            rl.setSpacing(ds.space_md)

            # Nom
            name_lbl = QLabel(f"{fn} {ln}")
            name_lbl.setFixedWidth(ds.space_xxxl + ds.space_md)
            name_lbl.setStyleSheet(
                f"font-size: {s(12)}px; font-weight: bold; color: {p.text_strong}; border: none;")
            rl.addWidget(name_lbl)

            # Enfants
            kids = QLabel(f"{nb_kids} enf.")
            kids.setFixedWidth(ds.space_lg + ds.space_md)
            kids.setStyleSheet(f"font-size: {s(11)}px; color: {p.text_soft}; border: none;")
            rl.addWidget(kids)

            # Dû
            du_lbl = QLabel(_fmt(total_du))
            du_lbl.setFixedWidth(ds.space_xxl)
            du_lbl.setStyleSheet(f"font-size: {s(12)}px; color: {p.text_strong}; border: none;")
            rl.addWidget(du_lbl)

            # Payé
            paid_lbl = QLabel(_fmt(total_paid))
            paid_lbl.setFixedWidth(ds.space_xxl)
            paid_lbl.setStyleSheet(f"font-size: {s(12)}px; color: {p.success}; border: none;")
            rl.addWidget(paid_lbl)

            # Restant
            rem_lbl = QLabel(_fmt(remaining))
            rem_lbl.setFixedWidth(ds.space_xxl)
            rem_lbl.setStyleSheet(
                f"font-size: {s(13)}px; font-weight: bold; color: {p.error}; border: none;")
            rl.addWidget(rem_lbl)

            # Barre progression
            pct = (total_paid / total_du * 100) if total_du > 0 else 0
            bar_w = ds.space_xxxl - ds.space_md
            bar_bg = QFrame()
            bar_bg.setAttribute(Qt.WA_StyledBackground, True)
            bar_bg.setFixedSize(bar_w, ds.space_sm)
            bar_bg.setStyleSheet(
                f"background: {p.outline_variant}; border-radius: {ds.radius_xs // 2}px;")
            bar_fill = QFrame(bar_bg)
            bar_fill.setAttribute(Qt.WA_StyledBackground, True)
            bar_fill.setFixedSize(max(ds.space_xxs, int(bar_w * pct / 100)), ds.space_sm)
            bar_fill.setStyleSheet(
                f"background: {p.error if pct < 50 else p.primary}; "
                f"border-radius: {ds.radius_xs // 2}px;")
            rl.addWidget(bar_bg)

            # Dernier paiement
            lp = str(last_payment) if last_payment else "Jamais"
            last = QLabel(lp)
            last.setFixedWidth(ds.space_xxl + ds.space_md)
            last.setStyleSheet(f"font-size: {s(10)}px; color: {p.text_soft}; border: none;")
            rl.addWidget(last)

            rl.addStretch()

            # Action : rappel individuel
            remind = QPushButton("Rappel")
            remind.setCursor(Qt.PointingHandCursor)
            remind.setFixedHeight(ds.space_lg)
            remind.setStyleSheet(
                f"QPushButton {{ background: {p.error}; color: white; border: none; "
                f"border-radius: {ds.radius_xs}px; padding: {ds.space_xxs}px {ds.space_xs}px; "
                f"font-size: {s(ds.font_label_sm)}px; font-weight: bold; }}"
                f"QPushButton:hover {{ background: {p.error}; }}")
            remind.clicked.connect(
                lambda checked, pid2=pid, name=f"{fn} {ln}": self._send_reminder(pid2, name))
            rl.addWidget(remind)

            rw.setStyleSheet(
                f"QWidget {{ background: {p.surface}; border-radius: {ds.radius_xs}px; }}"
                f"QWidget:hover {{ background: {p.surface_variant}; }}")
            self._list_layout.addWidget(rw)

    @safe_slot("Impayes._send_reminder")
    def _send_reminder(self, parent_id: int, name: str):
        from LarcCompta.views.reminders import _ReminderForm
        dlg = _ReminderForm(0, name, 0, parent_id=parent_id, parent=self)
        if dlg.exec():
            self.refresh()

    @safe_slot("Impayes._on_send_all")
    def _on_send_all(self):
        """Envoie un rappel groupé à tous les parents affichés."""
        pass  # Placeholder — sera implémenté avec la refonte reminders

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
