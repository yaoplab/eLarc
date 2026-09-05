"""AbsencePlanner — planning hebdomadaire des absences/retards par trim.

Pattern: DP1 scope label + toggle absences/retards + grille semaines.
"""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout,
)

from larccommon.database import db
from larccommon.design_system import ds
from phibuilder.phi.scale import SpacingToken
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot

_JOURS_COURTS = ["Lun", "Mar", "Mer", "Jeu", "Ven"]

TERMS = [
    (0, "Pré-rentrée",    date(2026, 8, 1),   date(2026, 8, 31)),
    (1, "Trimestre 1",    date(2026, 9, 1),   date(2026, 11, 27)),
    (2, "Trimestre 2",    date(2026, 11, 30), date(2027, 3, 12)),
    (3, "Trimestre 3",    date(2027, 3, 15),  date(2027, 6, 18)),
]

CAMPUS_CODE = {1: "Mat", 2: "Prim", 3: "CL"}
_CAMPUS_COLORS: dict[int, str] = {}


def _load_campus_colors():
    if not db.is_server_connected:
        return
    conn = db.server_conn
    if not conn:
        return
    cur = conn.cursor()
    cur.execute("SELECT s_id, color FROM larcauth_campus WHERE color IS NOT NULL")
    for row in cur.fetchall():
        _CAMPUS_COLORS[row[0]] = row[1]


class AbsencePlanner(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_term = 0
        self._mode = "absences"  # "absences" or "retards"
        _load_campus_colors()
        self._setup_ui()
        self.refresh()
        ds.theme_changed.connect(self._restyle)

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        s = theme_manager.font_size
        return f"""
            AbsencePlanner {{ background: {p.background}; }}
            QPushButton#term_btn {{
                background: {p.surface};
                color: {p.text_strong};
                border: 1px solid {p.outline};
                border-radius: {ds.radius_xs}px;
                padding: {ds.space_xxs}px {ds.space_md}px;
                font-size: {s(ds.font_body)}px;
            }}
            QPushButton#term_btn:checked {{
                background: {p.primary};
                color: white;
                border-color: {p.primary};
            }}
            QPushButton#term_btn:hover:!checked {{ border-color: {p.primary}; }}
        """

    @safe_slot("AbsencePlanner._restyle")
    def _restyle(self):
        try:
            self.setStyleSheet(self._STYLE)
        except RuntimeError:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size

        outer = QVBoxLayout(self)
        outer.setContentsMargins(ds.space_md, ds.space_sm, ds.space_md, ds.space_md)
        outer.setSpacing(ds.space_sm)

        # ── Titre ──
        self._title_lbl = QLabel("")
        self._title_lbl.setAlignment(Qt.AlignCenter)
        self._title_lbl.setStyleSheet(
            f"font-size: {s(ds.font_title)}px; font-weight: bold; "
            f"color: {p.primary}; border: none;")
        outer.addWidget(self._title_lbl)

        # ── Toggle Absences / Retards ──
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(ds.space_sm)
        toggle_row.addStretch()

        self._btn_absences = QPushButton("Absences")
        self._btn_absences.setObjectName("term_btn")
        self._btn_absences.setCheckable(True)
        self._btn_absences.setChecked(True)
        self._btn_absences.setCursor(Qt.PointingHandCursor)
        self._btn_absences.setFixedHeight(ds.field_height)
        self._btn_absences.setStyleSheet(
            f"QPushButton#term_btn:checked {{ background: {p.error}; color: white; "
            f"border-color: {p.error}; }}")
        self._btn_absences.clicked.connect(lambda checked: self._switch_mode("absences"))
        toggle_row.addWidget(self._btn_absences)

        self._btn_retards = QPushButton("Retards")
        self._btn_retards.setObjectName("term_btn")
        self._btn_retards.setCheckable(True)
        self._btn_retards.setCursor(Qt.PointingHandCursor)
        self._btn_retards.setFixedHeight(ds.field_height)
        self._btn_retards.setStyleSheet(
            f"QPushButton#term_btn:checked {{ background: {p.tertiary}; color: white; "
            f"border-color: {p.tertiary}; }}")
        self._btn_retards.clicked.connect(lambda checked: self._switch_mode("retards"))
        toggle_row.addWidget(self._btn_retards)

        toggle_row.addStretch()
        outer.addLayout(toggle_row)

        # ── Sélecteur période ──
        sel_row = QHBoxLayout()
        sel_row.setSpacing(ds.space_xs)
        sel_row.addStretch()

        self._term_btns: dict[int, QPushButton] = {}
        for tnum, tlabel, tstart, tend in TERMS:
            btn = QPushButton(tlabel)
            btn.setObjectName("term_btn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(ds.field_height)
            btn.setToolTip(f"{tstart.strftime('%d/%m/%Y')}  {tend.strftime('%d/%m/%Y')}")
            btn.clicked.connect(lambda checked, t=tnum: self._switch_term(t))
            sel_row.addWidget(btn)
            self._term_btns[tnum] = btn

        sel_row.addStretch()
        outer.addLayout(sel_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {p.outline_variant};")
        outer.addWidget(sep)

        # ── Légende couleurs ──
        leg_row = QHBoxLayout()
        leg_row.addStretch()
        for s_id, code in sorted(CAMPUS_CODE.items()):
            color = _CAMPUS_COLORS.get(s_id, p.text_soft)
            dot = QLabel(" ●")
            dot.setStyleSheet(f"color: {color}; font-size: {s(14)}px; border: none;")
            leg_row.addWidget(dot)
            lbl = QLabel(code)
            lbl.setStyleSheet(f"font-size: {s(ds.font_small)}px; color: {p.text_soft}; border: none;")
            leg_row.addWidget(lbl)
            leg_row.addSpacing(ds.space_xs)
        leg_row.addStretch()
        outer.addLayout(leg_row)

        # ── Infos compteur ──
        self._info_lbl = QLabel("")
        self._info_lbl.setAlignment(Qt.AlignCenter)
        self._info_lbl.setStyleSheet(
            f"font-size: {s(ds.font_small)}px; color: {p.text_soft}; border: none;")
        outer.addWidget(self._info_lbl)

        # ── Scroll weeks ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._weeks_w = QWidget()
        self._weeks_layout = QVBoxLayout(self._weeks_w)
        self._weeks_layout.setContentsMargins(0, 0, 0, 0)
        self._weeks_layout.setSpacing(ds.space_sm)
        self._scroll.setWidget(self._weeks_w)
        outer.addWidget(self._scroll, 1)

        self._term_btns[0].setChecked(True)
        self._update_title()
        self.setStyleSheet(self._STYLE)

    def _update_title(self):
        label = "Planning des absences" if self._mode == "absences" else "Planning des retards"
        self._title_lbl.setText(label)

    # ── Data ──

    def _load_absences(self) -> dict[str, list[dict]]:
        return self._load_events_type("Absence%")

    def _load_retards(self) -> dict[str, list[dict]]:
        return self._load_events_type("Retard%")

    def _load_events_type(self, like: str) -> dict[str, list[dict]]:
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return {}
        cur = conn.cursor()
        cur.execute("""
            SELECT e.staff_id, e.event_type,
                   COALESCE(e.event_at, e.created_at)::date AS event_date,
                   a.first_name, a.last_name, e.note,
                   c.s_id AS campus_id
            FROM staff_event e
            JOIN larcauth_aecuser a ON a.id = e.staff_id
            LEFT JOIN larcauth_campus c ON c.id = a.fk_campus_id
            WHERE COALESCE(e.event_at, e.created_at) BETWEEN '2026-08-01' AND '2027-08-01'
              AND e.event_type LIKE %s
            ORDER BY e.event_at
        """, (like,))
        by_date: dict[str, list[dict]] = {}
        for r in cur.fetchall():
            ed = str(r[2])[:10] if r[2] else ""
            if ed:
                by_date.setdefault(ed, []).append({
                    "staff_id": r[0], "event_type": r[1], "event_date": str(r[2])[:10],
                    "first_name": r[3], "last_name": r[4], "note": r[5],
                    "campus_id": r[6] or 0,
                })
        return by_date

    @safe_slot("AbsencePlanner._switch_mode")
    def _switch_mode(self, mode: str):
        self._mode = mode
        self._btn_absences.setChecked(mode == "absences")
        self._btn_retards.setChecked(mode == "retards")
        self._update_title()
        self._render()

    @safe_slot("AbsencePlanner._switch_term")
    def _switch_term(self, tnum: int):
        self._current_term = tnum
        for t, btn in self._term_btns.items():
            btn.setChecked(t == tnum)
        self._render()

    # ── Render ──

    def _render(self):
        p = theme_manager.palette
        s = theme_manager.font_size

        while self._weeks_layout.count():
            w = self._weeks_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

        tlabel, tstart, tend = [(l, ts, te) for tn, l, ts, te in TERMS if tn == self._current_term][0]
        weeks = self._build_weeks(tstart, tend)

        if self._mode == "absences":
            evt_by_date = self._load_absences()
            label_mot = "absence"
        else:
            evt_by_date = self._load_retards()
            label_mot = "retard"

        total = 0
        for week_days in weeks:
            card = self._make_week_card(week_days, evt_by_date, p, s)
            self._weeks_layout.addWidget(card)
            for d in week_days:
                total += len(evt_by_date.get(d.isoformat(), []))

        self._weeks_layout.addStretch()
        self._info_lbl.setText(
            f"{tlabel} — {len(weeks)} semaines — {total} {label_mot}(s)")

    def _build_weeks(self, tstart: date, tend: date) -> list[list[date]]:
        d = tstart
        while d.weekday() > 0:
            d += timedelta(days=1)
        first_monday = d
        weeks: list[list[date]] = []
        current: list[date] = []
        d = first_monday
        while d <= tend:
            if d.weekday() < 5:
                current.append(d)
            if d.weekday() == 4 and current:
                weeks.append(current)
                current = []
            d += timedelta(days=1)
        if current:
            weeks.append(current)
        return weeks

    def _make_week_card(self, days: list[date], evt_by_date, p, s) -> QFrame:
        iso_week = days[0].isocalendar()[1]
        start_str = days[0].strftime("%d/%m")

        card = QFrame()
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet(
            f"QFrame {{ background: {p.surface}; border: 1px solid {p.outline_variant}; "
            f"border-radius: {ds.radius_sm}px; }}")

        cl = QVBoxLayout(card)
        cl.setContentsMargins(ds.space_sm, ds.space_xs, ds.space_sm, ds.space_sm)
        cl.setSpacing(ds.space_xs)

        wlbl = QLabel(f"Semaine {iso_week} — {start_str}")
        wlbl.setStyleSheet(
            f"font-size: {s(ds.font_body)}px; font-weight: bold; "
            f"color: {p.primary}; border: none;")
        cl.addWidget(wlbl)

        grid = QGridLayout()
        grid.setSpacing(ds.space_xxs)

        for col_idx, d in enumerate(days):
            hdr = QLabel(f"{_JOURS_COURTS[col_idx]} {d.strftime('%d/%m')}")
            hdr.setAlignment(Qt.AlignCenter)
            hdr.setStyleSheet(
                f"font-size: {s(ds.font_small)}px; font-weight: bold; "
                f"color: {p.text_strong}; background: {p.surface_variant}; "
                f"border-radius: {ds.radius_xs}px; padding: {ds.space_xxs}px; "
                f"border: none;")
            grid.addWidget(hdr, 0, col_idx)

            evts = evt_by_date.get(d.isoformat(), [])
            if evts:
                lines = []
                for evt in evts:
                    s_id = evt.get("campus_id", 0)
                    ccode = CAMPUS_CODE.get(s_id, "")
                    color = _CAMPUS_COLORS.get(s_id, "#64748B")
                    nom = f"{evt.get('last_name', '')} {evt.get('first_name', '')}"
                    note = (evt.get("note") or "")[:30]
                    if ccode:
                        lines.append(
                            f'<span style="color:{color};font-weight:bold;'
                            f'font-size:{ds.font_body_sm}px;">{ccode}</span>'
                            f'<span style="color:{p.text_strong};font-size:{ds.font_body_sm}px;">'
                            f'  {nom}</span>')
                    else:
                        lines.append(
                            f'<span style="color:{p.text_strong};font-size:{ds.font_body_sm}px;">'
                            f'{nom}</span>')
                    if note:
                        lines.append(
                            f'<span style="color:{p.text_soft};font-size:{ds.font_label_sm}px;">'
                            f'  {note}</span>')
                text = "<br>".join(lines)
            else:
                text = "—"

            cell = QLabel(text)
            cell.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            cell.setWordWrap(True)
            cell.setMinimumHeight(ds.table_row_min + ds.space_xs * 2)
            cell.setTextFormat(Qt.RichText)
            cell.setStyleSheet(
                f"QLabel {{ font-size: {s(ds.font_label_sm)}px; color: {p.text_strong}; "
                f"background: {p.surface}; border-radius: {ds.radius_xs}px; "
                f"padding: {ds.space_xxs}px; border: 1px solid {p.outline_variant}; }}")
            grid.addWidget(cell, 1, col_idx)

        cl.addLayout(grid)
        return card

    def refresh(self):
        _load_campus_colors()
        self._render()
