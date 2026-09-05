"""ReminderPanel — conforme aux 6 skills design Larc."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QScrollArea, QDialog, QFormLayout, QTextEdit, QComboBox,
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


class _ReminderForm(ThemedDialog):

    def __init__(self, sid: int, name: str, due_amount: int, parent_id: int = 0, parent=None):
        super().__init__(parent)
        self._sid = sid
        self._parent_id = parent_id
        self._name = name
        self._due = due_amount
        self.setWindowTitle(f"Rappel — {name}")
        self.setMinimumSize(ds.golden_width(ds.sidebar_width), ds.golden_width(ds.space_xxl))
        self._setup_ui()

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        self.setStyleSheet(f"background: {p.surface};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_sm)

        label = "Parent" if self._parent_id else "Eleve"
        info = QLabel(f"{label} : {self._name}\nMontant du : {_fmt(self._due)} FCFA")
        info.setStyleSheet(
            f"font-size: {s(ds.font_body_md)}px; color: {p.text_strong}; font-weight: bold; border: none;")
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(ds.space_sm)
        fstyle = (
            f"background: {p.background}; border: {ds.border_width}px solid {p.outline}; "
            f"border-radius: {ds.radius_xs}px; padding: {ds.space_sm}px; "
            f"color: {p.text_strong}; font-size: {s(ds.font_label_lg)}px;"
        )
        self._f_type = QComboBox()
        self._f_type.addItems(["email", "sms", "whatsapp", "courrier"])
        self._f_type.setFixedHeight(ds.field_height)
        self._f_type.setStyleSheet(fstyle)
        form.addRow("Type de rappel :", self._f_type)

        self._f_msg = QTextEdit()
        self._f_msg.setFixedHeight(ds.space_xxxl - ds.space_md)
        self._f_msg.setStyleSheet(fstyle)
        self._f_msg.setPlainText(
            f"Madame, Monsieur,\n\n"
            f"Nous vous informons que la scolarite de votre enfant {self._name} "
            f"presente un solde de {_fmt(self._due)} FCFA.\n\n"
            f"Merci de bien vouloir regulariser la situation.\n\n"
            f"Cordialement,\nLe service comptabilite")
        form.addRow("Message :", self._f_msg)

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
            f"font-size: {s(ds.font_label_lg)}px; }}")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        send = QPushButton("Envoyer le rappel")
        send.setCursor(Qt.PointingHandCursor)
        send.setFixedHeight(ds.button_height)
        send.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; border: none; "
            f"border-radius: {ds.radius_sm}px; padding: {ds.space_xs}px {ds.space_m3}px; "
            f"font-size: {s(ds.font_label_lg)}px; font-weight: bold; }}")
        send.clicked.connect(self._on_send)
        btn_row.addWidget(send)
        layout.addLayout(btn_row)

    @safe_slot("_ReminderForm._on_send")
    def _on_send(self):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()
        # Si parent_id fourni directement, l'utiliser
        if self._parent_id:
            pid = self._parent_id
        else:
            # Trouver le parent payeur lie a cet eleve
            cur.execute("SELECT p.id FROM larcauth_aecuser p "
                        "JOIN larcauth_student_parent sp ON sp.parent_id = p.id "
                        "JOIN larcauth_parent lp ON lp.aecuser_ptr_id = p.id AND lp.is_payer = TRUE "
                        "WHERE sp.student_id = %s LIMIT 1", (self._sid,))
            pr = cur.fetchone()
            if not pr:
                return
            pid = pr[0]
        cur.execute("""INSERT INTO compta_reminder (parent_id, reminder_type, message)
            VALUES (%s, %s, %s)""",
            (pid, self._f_type.currentText(), self._f_msg.toPlainText().strip()))
        self.accept()


class ReminderPanel(QScrollArea):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setObjectName("reminders")
        ds.theme_changed.connect(self._restyle)
        self._restyle()

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
        self._layout.setSpacing(ds.space_sm)
        self.setWidget(self._container)
        self._setup_ui()
        self.refresh()

    @safe_slot("ReminderPanel._restyle")
    def _restyle(self):
        self.setStyleSheet(
            f"#reminders {{ background: {theme_manager.palette.background}; border: none; }}")

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size

        title = QLabel("Rappels de paiement")
        title.setStyleSheet(
            f"font-size: {s(ds.font_title_md)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        self._layout.addWidget(title)

        sub = QLabel("Eleves avec solde impaye. Cliquez pour envoyer un rappel.")
        sub.setStyleSheet(f"font-size: {s(12)}px; color: {p.text_soft}; border: none;")
        self._layout.addWidget(sub)

        self._list_layout = QVBoxLayout()
        self._list_layout.setSpacing(ds.border_width)
        self._layout.addLayout(self._list_layout)

        hist_title = QLabel("Historique des rappels envoyes")
        hist_title.setStyleSheet(
            f"font-size: {s(ds.font_body_md)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        self._layout.addWidget(hist_title)

        self._history_layout = QVBoxLayout()
        self._history_layout.setSpacing(ds.border_width)
        self._layout.addLayout(self._history_layout)

    def refresh(self):
        self._load_due()
        self._load_history()

    def _load_due(self):
        if not db.is_server_connected:
            return
        p = theme_manager.palette
        s = theme_manager.font_size
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()

        cur.execute(f"""
            SELECT a.id, a.first_name, a.last_name,
                   CASE WHEN prog.id IN (11,12,21,22) THEN {COLLEGE} ELSE {LYCEE} END,
                   COALESCE((SELECT SUM(cp.amount) FROM compta_payment cp
                       JOIN larcauth_student_parent sp2 ON sp2.parent_id = cp.parent_id
                       WHERE sp2.student_id = a.id), 0),
                   c.label, a.tel_smartphone_1, a.email
            FROM larcauth_aecuser a
            JOIN larcauth_student s2 ON s2.aecuser_ptr_id = a.id
            JOIN larcauth_classroom c ON c.id = s2.s_classroom_id
            JOIN larcauth_level l ON l.id = c.fk_level_id
            JOIN larcauth_program prog ON prog.id = l.fk_program_id
            WHERE s2.enabled = true
        """)
        for row in cur.fetchall():
            sid, fn, ln, fee, paid, cls, phone, email = row
            remaining = fee - paid
            if remaining <= 0: continue
            pct = (paid / fee * 100) if fee > 0 else 0

            rw = QWidget()
            rl = QHBoxLayout(rw)
            rl.setContentsMargins(ds.space_sm, ds.space_xs, ds.space_sm, ds.space_xs)
            rl.setSpacing(ds.space_m3)

            for text, w, color, bold in [
                (f"{fn} {ln}", ds.space_xxxl - ds.space_md, p.text_strong, True),
                (cls or "", ds.space_xxl, p.text_soft, False),
                (f"du {_fmt(remaining)}", ds.space_xxxl - ds.space_md, p.error, True),
            ]:
                lbl = QLabel(text)
                lbl.setFixedWidth(w)
                lbl.setStyleSheet(
                    f"font-size: {s(11)}px; {'font-weight: bold;' if bold else ''} "
                    f"color: {color}; border: none;")
                rl.addWidget(lbl)

            bar_w = ds.space_xxxl - ds.space_md
            bar_bg = QFrame()
            bar_bg.setAttribute(Qt.WA_StyledBackground, True)
            bar_bg.setFixedSize(bar_w, ds.space_sm)
            bar_bg.setStyleSheet(f"background: {p.outline_variant}; border-radius: {ds.radius_xs // 2}px;")
            bar_fill = QFrame(bar_bg)
            bar_fill.setAttribute(Qt.WA_StyledBackground, True)
            bar_fill.setFixedSize(max(ds.space_xxs, int(bar_w * pct / 100)), ds.space_sm)
            bar_fill.setStyleSheet(f"background: {p.error if pct < 50 else p.primary}; border-radius: {ds.radius_xs // 2}px;")
            rl.addWidget(bar_bg)

            if phone or email:
                cl = QLabel(f"{phone or ''} {'·' if phone and email else ''} {email or ''}")
                cl.setStyleSheet(f"font-size: {s(10)}px; color: {p.text_soft}; border: none;")
                rl.addWidget(cl)

            rl.addStretch()

            remind_btn = QPushButton("Rappel")
            remind_btn.setCursor(Qt.PointingHandCursor)
            remind_btn.setFixedHeight(ds.space_lg)
            remind_btn.setStyleSheet(
                f"QPushButton {{ background: {p.error}; color: {p.on_error}; border: none; "
                f"border-radius: {ds.radius_xs}px; padding: {ds.space_xxs}px {ds.space_sm}px; "
                f"font-size: {s(11)}px; font-weight: bold; }}")
            remind_btn.clicked.connect(
                lambda checked, s=sid, n=f"{fn} {ln}", r=remaining: self._send_reminder(s, n, r))
            rl.addWidget(remind_btn)

            rw.setStyleSheet(
                f"QWidget {{ background: {p.surface}; border-radius: {ds.radius_xs}px; }}"
                f"QWidget:hover {{ background: {p.surface_variant}; }}")
            self._list_layout.addWidget(rw)

        self._list_layout.addStretch()

    def _load_history(self):
        if not db.is_server_connected:
            return
        p = theme_manager.palette
        s = theme_manager.font_size
        while self._history_layout.count():
            item = self._history_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()
        cur.execute("""
            SELECT r.sent_at, r.reminder_type, a.first_name, a.last_name, r.status, LEFT(r.message, 80)
            FROM compta_reminder r JOIN larcauth_aecuser a ON a.id = r.parent_id
            ORDER BY r.sent_at DESC LIMIT 30
        """)
        for row in cur.fetchall():
            sent_at, rtype, fn, ln, _, msg = row
            rw = QWidget()
            rl = QHBoxLayout(rw)
            rl.setContentsMargins(ds.space_sm, ds.space_xxs, ds.space_sm, ds.space_xxs)
            rl.setSpacing(ds.space_m3)

            for text, w in [(str(sent_at)[:16], ds.space_xxxl),
                             (rtype, ds.space_xxl - ds.space_md),
                             (f"{fn} {ln}", ds.space_xxxl - ds.space_md)]:
                lbl = QLabel(text)
                lbl.setFixedWidth(w)
                lbl.setStyleSheet(f"font-size: {s(10)}px; color: {p.text_soft}; border: none;")
                rl.addWidget(lbl)
            if msg:
                ml = QLabel(msg)
                ml.setStyleSheet(f"font-size: {s(10)}px; color: {p.text_soft}; border: none;")
                rl.addWidget(ml, 1)

            rw.setStyleSheet(f"QWidget {{ background: {p.surface}; border-radius: {ds.radius_xs}px; }}")
            self._history_layout.addWidget(rw)

        self._history_layout.addStretch()

    @safe_slot("ReminderPanel._send_reminder")
    def _send_reminder(self, sid: int, name: str, amount: int):
        dlg = _ReminderForm(sid, name, amount, self)
        if dlg.exec():
            self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
