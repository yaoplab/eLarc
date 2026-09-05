"""StudentsList — conforme aux 6 skills design Larc."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
)

from larccommon.database import db
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot

COLLEGE = 2500000
LYCEE = 3000000


def _fmt(amount: int) -> str:
    if amount >= 1000000:
        return f"{amount / 1000000:.1f} M"
    return f"{amount // 1000:,} K".replace(",", " ")


class StudentsList(QScrollArea):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setObjectName("students")
        ds.theme_changed.connect(self._restyle)
        self._restyle()

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
        self._layout.setSpacing(ds.space_sm)
        self.setWidget(self._container)
        self._setup_ui()

    @safe_slot("StudentsList._restyle")
    def _restyle(self):
        self.setStyleSheet(
            f"#students {{ background: {theme_manager.palette.background}; border: none; }}")

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size

        title = QLabel("Eleves — Statut des frais")
        title.setStyleSheet(
            f"font-size: {s(ds.font_title_md)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        self._layout.addWidget(title)

        sub = QLabel("Statut herite du parent. Solde = frais - paiements recus.")
        sub.setStyleSheet(f"font-size: {s(12)}px; color: {p.text_soft}; border: none;")
        self._layout.addWidget(sub)

        hdr = QWidget()
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(ds.space_sm, ds.space_xs, ds.space_sm, ds.space_xs)
        hl.setSpacing(ds.space_m3)
        for lbl, w in [("Eleve", ds.space_xxxl - ds.space_lg), ("Classe", ds.space_xxl + ds.space_md),
                        ("Parent(s)", ds.space_xxxl - ds.space_lg),
                        ("Frais", ds.space_xxl), ("Encaisses", ds.space_xxl),
                        ("Solde", ds.space_xxl), ("Progression", ds.space_xxxl - ds.space_lg)]:
            l = QLabel(lbl)
            l.setFixedWidth(w)
            l.setStyleSheet(
                f"font-size: {s(ds.font_label_sm)}px; font-weight: bold; color: {p.text_soft}; border: none;")
            hl.addWidget(l)
        hl.addStretch()
        self._layout.addWidget(hdr)

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setSpacing(ds.border_width)
        self._layout.addLayout(self._rows_layout)
        self._layout.addStretch()

    def refresh(self):
        self._load()

    def _load(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        conn = db.server_conn
        if not conn:
            return
        cur = conn.cursor()

        cur.execute(f"""
            SELECT stu.id, stu.first_name, stu.last_name,
                   COALESCE(cl.label, '') as class_label,
                   COALESCE(STRING_AGG(DISTINCT par.first_name || ' ' || par.last_name, ', '), '—') as parents,
                   CASE WHEN prog.id IN (13,23) THEN {LYCEE} ELSE {COLLEGE} END as fee,
                   COALESCE(pay.paid_amount, 0) as paid,
                   COALESCE(sf2.payment_mode, 'inconnu') as mode
            FROM larcauth_aecuser stu
            JOIN larcauth_student s2 ON s2.aecuser_ptr_id = stu.id
            LEFT JOIN larcauth_classroom cl ON cl.id = s2.s_classroom_id
            LEFT JOIN larcauth_level l ON l.id = cl.fk_level_id
            LEFT JOIN larcauth_program prog ON prog.id = l.fk_program_id
            LEFT JOIN larcauth_student_parent sp ON sp.student_id = stu.id
            LEFT JOIN larcauth_aecuser par ON par.id = sp.parent_id
            LEFT JOIN compta_student_fee sf2 ON sf2.student_id = stu.id
            LEFT JOIN LATERAL (
                SELECT COALESCE(SUM(cp.amount), 0) as paid_amount
                FROM compta_payment cp
                JOIN larcauth_student_parent sp2 ON sp2.parent_id = cp.parent_id
                WHERE sp2.student_id = stu.id
            ) pay ON true
            WHERE s2.enabled = true
            GROUP BY stu.id, stu.first_name, stu.last_name, cl.label, prog.id,
                     pay.paid_amount, sf2.payment_mode
            ORDER BY (CASE WHEN prog.id IN (13,23) THEN {LYCEE} ELSE {COLLEGE} END
                     - COALESCE(pay.paid_amount, 0)) DESC
        """)

        for row in cur.fetchall():
            _, fn, ln, cls, parents, fee, paid, mode = row
            remaining = max(0, fee - paid)
            pct = (paid / fee * 100) if fee > 0 else 0

            if pct >= 100:
                status, sc = "Solde", p.success
            elif pct >= 40:
                status, sc = "En cours", p.primary
            elif paid > 0:
                status, sc = "En retard", "error"
            else:
                status, sc = "Non solde", "error"

            row_w = QWidget()
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(ds.space_sm, ds.space_xxs, ds.space_sm, ds.space_xxs)
            rl.setSpacing(ds.space_m3)

            items = [
                (f"{fn} {ln}", ds.space_xxxl - ds.space_lg, p.text_strong, True),
                (cls, ds.space_xxl + ds.space_md, p.text_soft, False),
                (parents[:30], ds.space_xxxl - ds.space_lg, p.text_soft, False),
                (_fmt(fee), ds.space_xxl, p.text_strong, False),
                (_fmt(paid), ds.space_xxl, p.success, False),
                (_fmt(remaining), ds.space_xxl, getattr(p, sc, p.error), True),
            ]
            for text, w, color, bold in items:
                lbl = QLabel(text)
                lbl.setFixedWidth(w)
                lbl.setStyleSheet(
                    f"font-size: {s(12) if bold else s(11)}px; "
                    f"{'font-weight: bold;' if bold else ''} color: {color}; border: none;")
                rl.addWidget(lbl)

            # Barre progression
            bar_w = ds.space_xxxl - ds.space_lg
            bar_bg = QFrame()
            bar_bg.setAttribute(Qt.WA_StyledBackground, True)
            bar_bg.setFixedSize(bar_w, ds.space_sm)
            bar_bg.setStyleSheet(
                f"background: {p.outline_variant}; border-radius: {ds.radius_xs // 2}px;")
            bar_fill = QFrame(bar_bg)
            bar_fill.setAttribute(Qt.WA_StyledBackground, True)
            bar_fill.setFixedSize(max(ds.space_xxs, int(bar_w * pct / 100)), ds.space_sm)
            bar_fill.setStyleSheet(
                f"background: {p.success if pct >= 100 else p.primary if pct >= 40 else p.error}; "
                f"border-radius: {ds.radius_xs // 2}px;")
            rl.addWidget(bar_bg)

            st_lbl = QLabel(status)
            st_lbl.setFixedWidth(ds.space_lg + ds.space_sm)
            st_lbl.setStyleSheet(
                f"font-size: {s(11)}px; font-weight: bold; color: {getattr(p, sc, p.error)}; border: none;")
            rl.addWidget(st_lbl)

            rl.addStretch()
            row_w.setStyleSheet(
                f"QWidget {{ background: {p.surface}; border-radius: {ds.radius_xs}px; }}"
                f"QWidget:hover {{ background: {p.surface_variant}; }}")
            self._rows_layout.addWidget(row_w)

        self._rows_layout.addStretch()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
