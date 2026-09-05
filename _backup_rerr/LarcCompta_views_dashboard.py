"""Dashboard LarcCompta — conforme aux 6 skills design Larc."""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QFont, QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QScrollArea,
)

from larccommon.database import db
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot

# ── Constantes métier (tokens FCFA, pas des px) ──
COLLEGE_FEE = 2500000
LYCEE_FEE = 3000000
COLLEGE_IDS = (11, 12, 21, 22)  # PYP, PP, MYP, PEI
LYCEE_IDS = (13, 23)             # DPEn, DPFr
PRIMAIRE_IDS = (11, 21)          # PYP, PP

# Mapping group_mode → filtre SQL
GROUP_FILTER_SQL = {
    "grp_all":      "AND p.sigle IN ('PYP','PP','PEI','MYP','DPEn','DPFr')",
    "grp_primaire": "AND (p.sigle ILIKE 'PYP' OR p.sigle ILIKE 'PP')",
    "grp_college":  "AND (p.sigle ILIKE 'PEI' OR p.sigle ILIKE 'MYP')",
    "grp_lycee":    "AND (p.sigle ILIKE 'DPEn' OR p.sigle ILIKE 'DPFr')",
}

# ═══════════════════════════════════════════════════════════════════════════
#  Health Bar — S2a (jauge % encaissé global + par programme)
# ═══════════════════════════════════════════════════════════════════════════
class _HealthBar(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._global_pct = 0
        self._programs: list[tuple[str, int]] = []
        self.setObjectName("health_bar")
        self.setMinimumHeight(ds.header_height)  # 52px
        ds.theme_changed.connect(self.update)

    def set_data(self, global_pct: int, programs: list[tuple[str, int]]):
        self._global_pct = global_pct
        self._programs = programs
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            p.end(); return
        pal = theme_manager.palette
        bar_h = 14
        bar_y = (h - bar_h) // 2
        bar_w = w - ds.space_md * 2

        # Fond gris
        p.fillRect(ds.space_md, bar_y, bar_w, bar_h, QColor(pal.outline_variant))
        # Barre verte
        fill_w = max(2, int(bar_w * self._global_pct / 100))
        p.fillRect(ds.space_md, bar_y, fill_w, bar_h, QColor(pal.success))
        # % texte (grand, lisible)
        p.setPen(QColor(pal.text_strong))
        p.setFont(QFont("Segoe UI", 16, QFont.Bold))
        p.drawText(ds.space_md, 0, bar_w, bar_y + 4, Qt.AlignCenter,
                   f"{self._global_pct} % encaissé")

        # Textes programme
        p.setFont(QFont("Segoe UI", 12))
        prog_colors = {"Primaire": pal.primary, "College": pal.success, "Lycee": pal.tertiary}
        tx = ds.space_md
        for prog, pct in self._programs:
            txt = f"  {prog} {pct}%  "
            tw = p.fontMetrics().horizontalAdvance(txt)
            p.setPen(QColor(prog_colors.get(prog, pal.text_soft)))
            p.drawText(tx, bar_y + bar_h + 18, tw, 16, Qt.AlignLeft, txt)
            tx += tw

        p.end()


# ═══════════════════════════════════════════════════════════════════════════
#  Projection Chart — S2b (courbe attendu standard + ajustée + réel)
# ═══════════════════════════════════════════════════════════════════════════
class _ProjectionChart(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._real: list[int] = []
        self._expected: list[int] = []
        self.setObjectName("projection")
        self.setMinimumHeight(ds.space_xxxl + ds.space_xxl)  # ~220px
        ds.theme_changed.connect(self.update)

    def set_data(self, real: list[int], expected: list[int]):
        self._real = real
        self._expected = expected
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0 or not self._expected:
            p.end(); return
        pal = theme_manager.palette
        s = theme_manager.font_size
        p.fillRect(0, 0, w, h, QColor(pal.surface))

        p.setPen(QColor(pal.text_strong))
        p.setFont(QFont("Segoe UI", 14, QFont.Bold))
        p.drawText(ds.space_sm, 20, "Projection")

        if len(self._expected) < 2:
            p.end(); return

        n = len(self._expected)
        margin = ds.space_md
        chart_w = w - margin * 2
        chart_h = h - 50 - margin
        y0 = h - margin
        max_val = max(max(self._expected), max(self._real or [1]), 1)

        months = ["S", "O", "N", "D", "J", "F", "M", "A", "M", "J"]

        def _x(i):
            return margin + int(i * chart_w / max(1, n - 1))

        def _y(val):
            return y0 - int(val * chart_h / max_val)

        # Grille
        p.setPen(QPen(QColor(pal.outline_variant), 1, Qt.DotLine))
        for pct in [25, 50, 75, 100]:
            y_ = _y(int(max_val * pct / 100))
            p.drawLine(margin, y_, margin + chart_w, y_)
            p.setPen(QColor(pal.text_soft))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(2, y_ + 5, f"{pct}%")
            p.setPen(QPen(QColor(pal.outline_variant), 1, Qt.DotLine))

        # Courbe attendu (pointillés, gris)
        pen_std = QPen(QColor(pal.text_soft), 2, Qt.DashLine)
        p.setPen(pen_std)
        for i in range(n - 1):
            p.drawLine(_x(i), _y(self._expected[i]), _x(i + 1), _y(self._expected[i + 1]))
        for i in range(n):
            p.drawEllipse(QPointF(_x(i), _y(self._expected[i])), 3, 3)

        # Courbe réelle (pleine, couleur)
        if self._real and len(self._real) == n:
            pen_real = QPen(QColor(pal.primary), 3)
            p.setPen(pen_real)
            for i in range(n - 1):
                p.drawLine(_x(i), _y(self._real[i]), _x(i + 1), _y(self._real[i + 1]))
            for i in range(n):
                p.setBrush(QColor(pal.primary))
                p.drawEllipse(QPointF(_x(i), _y(self._real[i])), 4, 4)

        # Mois
        p.setPen(QColor(pal.text_soft))
        p.setFont(QFont("Segoe UI", 10))
        for i in range(n):
            p.drawText(_x(i) - 10, y0 + 14, 20, 14, Qt.AlignCenter,
                       months[i] if i < len(months) else str(i + 1))

        p.end()


def _build_filter(mode: str) -> str:
    """Construit une clause WHERE pour filtrer par programme."""
    if mode in GROUP_FILTER_SQL:
        return GROUP_FILTER_SQL[mode]
    if mode.startswith("grp_"):
        sigle = mode.split("_")[1]
        return f"AND p.sigle ILIKE '{sigle}'"
    return GROUP_FILTER_SQL["grp_all"]


def _fmt(amount: int) -> str:
    if amount >= 1000000:
        return f"{amount / 1000000:.1f} M"
    return f"{amount // 1000:,} K".replace(",", " ")


# ═══════════════════════════════════════════════════════════════════════════
#  KPI Card — DP2 pattern (M3Frame, FixedHeight = ds.kpi_card_height)
# ═══════════════════════════════════════════════════════════════════════════
class _KpiCard(QFrame):

    def __init__(self, label: str, accent_token: str, parent=None):
        super().__init__(parent)
        self._label_text = label
        self._accent_token = accent_token
        self._value = "—"
        self.setObjectName("kpi_card")
        self.setFixedHeight(ds.kpi_card_height)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._value_label: QLabel | None = None
        self._setup_ui()
        ds.theme_changed.connect(self._restyle)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(ds.space_m3, ds.space_sm, ds.space_m3, ds.space_sm)
        layout.setSpacing(ds.space_m3)

        # Barre accent a gauche
        bar = QWidget()
        bar.setObjectName("accent")
        bar.setFixedWidth(ds.space_xxs)
        layout.addWidget(bar)

        col = QVBoxLayout()
        col.setSpacing(ds.space_xxs)
        self._value_label = QLabel(self._value)
        col.addWidget(self._value_label)
        lbl = QLabel(self._label_text)
        col.addWidget(lbl)
        layout.addLayout(col, 1)
        self._restyle()

    def set_value(self, value: str):
        self._value = value
        if self._value_label:
            self._value_label.setText(value)

    @safe_slot("_KpiCard._restyle")
    def _restyle(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        accent = getattr(p, self._accent_token, p.primary)
        self.setStyleSheet(f"""
            #kpi_card {{
                background: {p.surface}; border: 1px solid {p.outline_variant};
                border-radius: {ds.radius_sm}px;
            }}
            QWidget#accent {{ background: {accent}; border-radius: {ds.radius_xs // 2}px; }}
        """)
        if self._value_label:
            self._value_label.setStyleSheet(
                f"font-size: {s(ds.font_headline_md)}px; font-weight: bold; color: {accent}; border: none;")
        for lbl in self.findChildren(QLabel):
            if lbl != self._value_label:
                lbl.setStyleSheet(f"font-size: {s(11)}px; color: {p.text_soft}; border: none;")


# ═══════════════════════════════════════════════════════════════════════════
#  Donut Chart — Q1 (hover) + Q5 (restyle) + tokens ds.p.*
# ═══════════════════════════════════════════════════════════════════════════
class _DonutSlice:
    def __init__(self, label: str, value: int, accent: str):
        self.label = label
        self.value = value
        self.accent = accent


class _DonutChart(QWidget):

    def __init__(self, title: str, slices: list[_DonutSlice], parent=None):
        super().__init__(parent)
        self._title = title
        self._slices = slices
        self.setObjectName("donut_chart")
        self.setMinimumSize(ds.golden_width(ds.kpi_card_height), ds.golden_height(ds.kpi_card_height * 4))
        ds.theme_changed.connect(self.update)
        self._restyle()

    @safe_slot("_DonutChart._restyle")
    def _restyle(self):
        self.setStyleSheet(
            f"#donut_chart {{ background: {theme_manager.palette.surface}; "
            f"border: 1px solid {theme_manager.palette.outline_variant}; "
            f"border-radius: {ds.radius_sm}px; }}")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            p.end()
            return
        pal = theme_manager.palette
        s = theme_manager.font_size

        self.setStyleSheet(self.styleSheet())  # refresh QSS
        p.fillRect(0, 0, w, h, QColor(pal.surface))

        p.setPen(QColor(pal.text_strong))
        p.setFont(QFont("Segoe UI", s(11), QFont.Bold))
        p.drawText(ds.space_sm, s(21), self._title)

        cx, cy = w // 2, h // 2 + s(8)
        outer_r = min(cx, cy) - s(21)
        inner_r = outer_r * 3 // 5
        total = max(1, sum(sl.value for sl in self._slices))

        start_angle = 0
        for sl in self._slices:
            span = int(sl.value * 360 * 16 / total)
            if span > 0:
                p.setBrush(QColor(getattr(pal, sl.accent, pal.primary)))
                p.setPen(Qt.NoPen)
                p.drawPie(QRectF(cx - outer_r, cy - outer_r, outer_r * 2, outer_r * 2),
                          start_angle, span)
                start_angle += span

        p.setBrush(QColor(pal.surface))
        p.drawEllipse(QPointF(cx, cy), inner_r, inner_r)

        p.setPen(QColor(pal.text_strong))
        p.setFont(QFont("Segoe UI", s(13), QFont.Bold))
        p.drawText(QRectF(cx - ds.kpi_card_height, cy - s(13), ds.kpi_card_height * 2, s(21)),
                   Qt.AlignCenter, _fmt(total))
        p.setFont(QFont("Segoe UI", s(8)))
        p.setPen(QColor(pal.text_soft))
        p.drawText(QRectF(cx - ds.kpi_card_height, cy + s(8), ds.kpi_card_height * 2, s(13)),
                   Qt.AlignCenter, "Total du")

        # Legende
        lx = w - ds.space_xxxl - ds.space_lg
        ly = s(34)
        p.setFont(QFont("Segoe UI", s(8)))
        for sl in self._slices:
            p.setBrush(QColor(getattr(pal, sl.accent, pal.primary)))
            p.setPen(Qt.NoPen)
            p.drawRect(lx, ly, ds.space_sm, ds.space_sm)
            p.setPen(QColor(pal.text_strong))
            p.drawText(lx + ds.space_m3, ly + ds.space_sm,
                       f"{sl.label}: {_fmt(sl.value)}")
            ly += s(18)

        p.end()


# ═══════════════════════════════════════════════════════════════════════════
#  Bar Chart — DP4b pattern (hauteur = golden_height)
# ═══════════════════════════════════════════════════════════════════════════
class _BarChart(QWidget):

    def __init__(self, title: str, data: list[tuple[str, int, int]], parent=None):
        super().__init__(parent)
        self._title = title
        self._data = data
        self.setObjectName("bar_chart")
        self.setMinimumHeight(ds.golden_height(ds.space_xxl))
        ds.theme_changed.connect(self.update)

    @safe_slot("_BarChart._restyle")
    def _restyle(self):
        self.setStyleSheet(
            f"#bar_chart {{ background: {theme_manager.palette.surface}; "
            f"border: 1px solid {theme_manager.palette.outline_variant}; "
            f"border-radius: {ds.radius_sm}px; }}")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if h < ds.space_lg or not self._data:
            p.end()
            return
        pal = theme_manager.palette
        s = theme_manager.font_size

        self.setStyleSheet(self.styleSheet())
        p.fillRect(0, 0, w, h, QColor(pal.surface))

        p.setPen(QColor(pal.text_strong))
        p.setFont(QFont("Segoe UI", s(11), QFont.Bold))
        p.drawText(ds.space_sm, s(21), self._title)

        if not self._data or not self._data[0][2]:
            p.end()
            return

        n = len(self._data)
        bar_w = max(s(21), min(ds.kpi_card_height, (w - ds.kpi_card_height) // n - ds.space_sm))
        chart_h = max(1, h - ds.kpi_card_height)
        x0 = ds.space_lg
        y0 = h - ds.space_md
        max_val = max(v[2] for v in self._data) or 1

        p.setPen(QPen(QColor(pal.outline_variant), 1, Qt.DotLine))
        for frac in [0.25, 0.5, 0.75, 1.0]:
            y = y0 - int(frac * chart_h)
            p.drawLine(x0, y, w - s(21), y)
            p.setPen(QColor(pal.text_soft))
            p.setFont(QFont("Segoe UI", s(7)))
            p.drawText(s(8), y + s(5), _fmt(int(frac * max_val)))
            p.setPen(QPen(QColor(pal.outline_variant), 1, Qt.DotLine))

        colors = [
            QColor(pal.primary), QColor(pal.success), QColor(pal.secondary),
            QColor(pal.error), QColor(pal.tertiary), QColor(pal.primary_container),
        ]
        for i, (label, val, _max) in enumerate(self._data):
            x = x0 + i * (bar_w + ds.space_sm)
            h_val = int((val / max_val) * chart_h) if max_val > 0 else 0
            h_max = int((_max / max_val) * chart_h) if max_val > 0 else 0

            if _max > val:
                p.fillRect(x, y0 - h_max, bar_w, h_max, QColor(pal.outline_variant))
            if h_val > 0:
                p.fillRect(x, y0 - h_val, bar_w, h_val, colors[i % len(colors)])

            p.setPen(QColor(pal.text_strong))
            p.setFont(QFont("Segoe UI", s(8)))
            p.drawText(x - s(8), y0 + s(13), bar_w + ds.space_m3, s(13),
                       Qt.AlignCenter, label[:12])
            p.setFont(QFont("Segoe UI", s(7), QFont.Bold))
            p.drawText(x - s(8), y0 - h_max - s(13), bar_w + ds.space_m3, s(13),
                       Qt.AlignCenter, _fmt(val))

        p.end()


# ═══════════════════════════════════════════════════════════════════════════
#  Dashboard — DP1-DP8 pattern canonique
# ═══════════════════════════════════════════════════════════════════════════
class Dashboard(QScrollArea):

    def __init__(self, group_mode: str = "grp_all", parent=None):
        super().__init__(parent)
        self._group_mode = group_mode
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setObjectName("dashboard")
        ds.theme_changed.connect(self._restyle)
        self._restyle()

        self._container = QWidget()
        self._setup_ui()
        self.setWidget(self._container)
        self.refresh()

    def set_group_mode(self, mode: str):
        """Change le filtre de groupe et recharge les donnees."""
        if mode != self._group_mode:
            self._group_mode = mode
            labels = {"grp_all": "Tous les niveaux", "grp_primaire": "Primaire (PYP/PP)",
                      "grp_college": "College (PEI/MYP)", "grp_lycee": "Lycee (DP)"}
            scope_label = labels.get(mode, mode)
            if hasattr(self, '_scope_label'):
                self._scope_label.setText(f"Tableau de bord — {scope_label}")
            self.refresh()

    @safe_slot("Dashboard._restyle")
    def _restyle(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        self.setStyleSheet(
            f"#dashboard {{ background: {p.background}; border: none; }}")
        self._scope_label.setStyleSheet(
            f"font-size: {s(ds.font_title)}px; font-weight: bold; color: {p.primary}; border: none;")
        self._kpi_title.setStyleSheet(
            f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        self._tbl_title.setStyleSheet(
            f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong}; border: none;")

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
        layout.setSpacing(ds.space_sm)

        # DP1 — SCOPE LABEL
        labels = {"grp_all": "Tous les niveaux", "grp_primaire": "Primaire (PYP/PP)",
                  "grp_college": "College (PEI/MYP)", "grp_lycee": "Lycee (DP)"}
        scope_label = labels.get(self._group_mode, self._group_mode)
        self._scope_label = QLabel(f"Tableau de bord — {scope_label}")
        self._scope_label.setAlignment(Qt.AlignCenter)
        self._scope_label.setStyleSheet(
            f"font-size: {s(ds.font_title)}px; font-weight: bold; color: {p.primary}; border: none;")
        layout.addWidget(self._scope_label)

        # ── BARRE DE SANTÉ (S2a) ──
        self._health_bar = _HealthBar()
        self._health_bar.setFixedHeight(ds.header_height)
        layout.addWidget(self._health_bar)

        # ── PROJECTION + BAR CHART côte à côte ──
        charts_row = QHBoxLayout()
        charts_row.setSpacing(ds.space_sm)
        self._projection = _ProjectionChart()
        charts_row.addWidget(self._projection, 5)
        self._bar = QWidget()
        charts_row.addWidget(self._bar, 5)
        layout.addLayout(charts_row)

        # DP2 — KPI ROW (cards horizontales)
        self._kpi_title = QLabel("Indicateurs cles")
        self._kpi_title.setStyleSheet(
            f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        layout.addWidget(self._kpi_title)

        self._kpi_grid = QGridLayout()
        self._kpi_grid.setSpacing(ds.space_sm)
        layout.addLayout(self._kpi_grid)

        # DP4 — BODY (gauche table + droite donut)
        body = QHBoxLayout()
        body.setSpacing(ds.space_sm)

        # DP4a — Colonne gauche (table par programme)
        left = QVBoxLayout()
        left.setSpacing(ds.space_xs)
        self._tbl_title = QLabel("Detail par programme")
        self._tbl_title.setStyleSheet(
            f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        left.addWidget(self._tbl_title)
        self._table_layout = QVBoxLayout()
        self._table_layout.setSpacing(ds.space_xxs)
        left.addLayout(self._table_layout)
        left.addStretch()
        body.addLayout(left, 5)

        # DP4b — Colonne droite (graphiques)
        right = QVBoxLayout()
        right.setSpacing(ds.space_sm)
        self._donut = QWidget()
        right.addWidget(self._donut, 4)
        self._bar = QWidget()
        right.addWidget(self._bar, 6)
        body.addLayout(right, 5)

        layout.addLayout(body, 1)

    def refresh(self):
        self._load_health()
        self._load_kpis()
        self._load_charts()
        self._load_table()

    # ── Health Bar + Projection (S2a, S2b) ──
    def _load_health(self):
        conn = db.server_conn
        if not conn: return
        cur = conn.cursor()

        # % encaissé global
        cur.execute("""
            SELECT COALESCE(SUM(total_paid), 0), COALESCE(SUM(total_due), 0)
            FROM compta_parent_balance WHERE academic_year = '2026-2027'
        """)
        paid, due = cur.fetchone() or (0, 0)
        global_pct = int(paid / due * 100) if due > 0 else 0

        # Par programme — repartition proportionnelle
        programs = []
        all_ids = [(11, 12, 21, 22), (13, 23)]  # college, lycee
        for cat, col_ids, lycee_ids in [("Primaire", (11, 21), ()),
                                          ("College", (12, 22), ()),
                                          ("Lycee", (), (13, 23))]:
            prog_ids = col_ids + lycee_ids
            id_str = ','.join(str(i) for i in prog_ids)
            fee = COLLEGE_FEE if cat != "Lycee" else LYCEE_FEE
            cur.execute(f"""
                SELECT COALESCE(SUM(part), 0) FROM (
                    SELECT COALESCE(SUM(cp.amount), 0) * {fee}
                        / NULLIF(SUM(sf.annual_fee), 0) AS part
                    FROM larcauth_aecuser par
                    JOIN larcauth_student_parent sp ON sp.parent_id = par.id
                    JOIN larcauth_parent lp ON lp.aecuser_ptr_id = par.id AND lp.is_payer = TRUE
                    JOIN larcauth_student s ON s.aecuser_ptr_id = sp.student_id
                    JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                    JOIN larcauth_level l ON l.id = c.fk_level_id
                    JOIN larcauth_program p ON p.id = l.fk_program_id
                    LEFT JOIN compta_payment cp ON cp.parent_id = par.id
                    LEFT JOIN compta_student_fee sf ON sf.student_id = sp.student_id
                    WHERE p.id IN ({id_str}) AND s.enabled = TRUE
                    GROUP BY par.id
                ) sub
            """)
            pp = int(cur.fetchone()[0] or 0)
            # Total du dans ce programme
            cur.execute(f"""
                SELECT COUNT(*) * {fee}
                FROM larcauth_student s
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program p ON p.id = l.fk_program_id
                WHERE p.id IN ({id_str}) AND s.enabled = TRUE
            """)
            dd = cur.fetchone()[0] or 0
            pct = int(pp / dd * 100) if dd > 0 else 0
            programs.append((cat, pct))

        self._health_bar.set_data(global_pct, programs)

        # Projection : attendu (échéancier) vs réel (paiements) mois par mois
        cur.execute("SELECT month_number, percentage_expected FROM compta_payment_schedule "
                    "WHERE academic_year = '2026-2027' ORDER BY month_number")
        schedule = {r[0]: float(r[1]) for r in cur.fetchall()}

        expected = []
        real = []
        for month in range(1, 11):
            pct = schedule.get(month, 0)
            expected.append(int(due * pct / 100) if due > 0 else 0)
            cur.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM compta_payment cp
                JOIN compta_parent_balance b ON b.parent_id = cp.parent_id
                    AND b.academic_year = '2026-2027'
                WHERE cp.payment_date <= '2026-0{:d}-01'::date + INTERVAL '1 month' - INTERVAL '1 day'
            """.format(month))
            real_paid = int(cur.fetchone()[0] or 0)
            real.append(real_paid)

        self._projection.set_data(real, expected)

    # ── KPI Cards (DP2 pattern) ──
    def _load_kpis(self):
        for i in reversed(range(self._kpi_grid.count())):
            item = self._kpi_grid.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()

        conn = db.server_conn
        if not conn:
            return
        cur = conn.cursor()

        flt = _build_filter(self._group_mode)

        # Total eleves + total du dans le groupe filtre
        cur.execute(f"""
            SELECT COUNT(*) FILTER (WHERE p.id IN (11,12,21,22)),
                   COUNT(*) FILTER (WHERE p.id IN (13,23))
            FROM larcauth_student s
            JOIN larcauth_classroom c ON c.id = s.s_classroom_id
            JOIN larcauth_level l ON l.id = c.fk_level_id
            JOIN larcauth_program p ON p.id = l.fk_program_id
            WHERE s.enabled = true {flt}
        """)
        row = cur.fetchone() or (0, 0)
        n_co, n_ly = row[0], row[1]
        total_du = n_co * COLLEGE_FEE + n_ly * LYCEE_FEE
        total_students = n_co + n_ly

        # Paiements : chaque parent contribue une seule fois,
        # reparti proportionnellement sur ses enfants dans le groupe filtre
        flt_inner = flt.replace('AND p.', 'AND p.')
        cur.execute(f"""
            SELECT COALESCE(SUM(part), 0) FROM (
                SELECT par.id AS parent_id,
                       SUM(cp.amount) AS total_paid,
                       SUM(sf.annual_fee) AS total_du_family,
                       SUM(cp.amount) * SUM(CASE WHEN p.id IN (13,23) THEN {LYCEE_FEE} ELSE {COLLEGE_FEE} END)
                           / NULLIF(SUM(sf.annual_fee), 0) AS part
                FROM larcauth_aecuser par
                JOIN larcauth_student_parent sp ON sp.parent_id = par.id
                JOIN larcauth_parent lp ON lp.aecuser_ptr_id = par.id AND lp.is_payer = TRUE
                JOIN larcauth_student s ON s.aecuser_ptr_id = sp.student_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program p ON p.id = l.fk_program_id
                LEFT JOIN compta_payment cp ON cp.parent_id = par.id
                LEFT JOIN compta_student_fee sf ON sf.student_id = sp.student_id
                WHERE s.enabled = true {flt}
                GROUP BY par.id
            ) sub
        """)
        paid = int((cur.fetchone() or [0])[0] or 0)
        rem = max(0, total_du - paid)
        taux = (paid / total_du * 100) if total_du > 0 else 0

        # Nombre de parents payeurs dans le filtre
        cur.execute(f"""
            SELECT COUNT(DISTINCT par.id)
            FROM larcauth_aecuser par
            JOIN larcauth_student_parent sp ON sp.parent_id = par.id
            JOIN larcauth_parent lp ON lp.aecuser_ptr_id = par.id AND lp.is_payer = TRUE
            JOIN larcauth_student s ON s.aecuser_ptr_id = sp.student_id
            JOIN larcauth_classroom c ON c.id = s.s_classroom_id
            JOIN larcauth_level l ON l.id = c.fk_level_id
            JOIN larcauth_program p ON p.id = l.fk_program_id
            WHERE s.enabled = true {flt}
        """)
        n_payers = (cur.fetchone() or [0])[0] or 0

        kpis = [
            ("Total du", _fmt(total_du), "primary"),
            ("Encaisses", _fmt(paid), "success"),
            ("Reste a encaisser", _fmt(rem), "error"),
            (f"Taux ({taux:.0f} %)", f"{n_payers}/{total_students}", "secondary"),
        ]
        for i, (lbl, val, accent) in enumerate(kpis):
            card = _KpiCard(lbl, accent)
            card.set_value(val)
            self._kpi_grid.addWidget(card, 0, i)

    # ── Charts (DP4b) ──
    def _load_charts(self):
        p = theme_manager.palette
        conn = db.server_conn
        if not conn:
            return
        cur = conn.cursor()

        flt = _build_filter(self._group_mode)

        # Total du dans le groupe + paiements par parent
        cur.execute(f"""
            SELECT COUNT(*) FILTER (WHERE p.id IN (11,12,21,22)) * {COLLEGE_FEE} +
                   COUNT(*) FILTER (WHERE p.id IN (13,23)) * {LYCEE_FEE}
            FROM larcauth_student s
            JOIN larcauth_classroom c ON c.id = s.s_classroom_id
            JOIN larcauth_level l ON l.id = c.fk_level_id
            JOIN larcauth_program p ON p.id = l.fk_program_id
            WHERE s.enabled = true {flt}
        """)
        total_du = (cur.fetchone() or [0])[0] or 0

        # Paiements agreges par parent
        cur.execute(f"""
            SELECT COALESCE(SUM(part), 0) FROM (
                SELECT par.id,
                       COALESCE(SUM(cp.amount), 0) * COALESCE(SUM(CASE WHEN p.id IN (13,23) THEN {LYCEE_FEE} ELSE {COLLEGE_FEE} END), 0)
                           / NULLIF(SUM(sf.annual_fee), 0) AS part
                FROM larcauth_aecuser par
                JOIN larcauth_student_parent sp ON sp.parent_id = par.id
                JOIN larcauth_parent lp ON lp.aecuser_ptr_id = par.id AND lp.is_payer = TRUE
                JOIN larcauth_student s ON s.aecuser_ptr_id = sp.student_id
                JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program p ON p.id = l.fk_program_id
                LEFT JOIN compta_payment cp ON cp.parent_id = par.id
                LEFT JOIN compta_student_fee sf ON sf.student_id = sp.student_id
                WHERE s.enabled = true {flt}
                GROUP BY par.id
            ) sub
        """)
        paid = int((cur.fetchone() or [0])[0] or 0)
        rem = max(0, total_du - paid)

        donut = _DonutChart("Repartition des frais", [
            _DonutSlice("Encaisses", paid, "success"),
            _DonutSlice("Reste a encaisser", rem, "error"),
        ])

        cur.execute(f"""
            SELECT CASE WHEN p.id IN (11,12,21,22) THEN 'College' ELSE 'Lycee' END,
                   COUNT(*), 0
            FROM larcauth_student s
            JOIN larcauth_classroom c ON c.id = s.s_classroom_id
            JOIN larcauth_level l ON l.id = c.fk_level_id
            JOIN larcauth_program p ON p.id = l.fk_program_id
            WHERE s.enabled = true {flt}
            GROUP BY 1
        """)
        bar_data = []
        for cat, cnt, _ in cur.fetchall():
            is_college = cat == 'College'
            ids = COLLEGE_IDS if is_college else LYCEE_IDS
            fee = COLLEGE_FEE if is_college else LYCEE_FEE
            id_list = ','.join(str(i) for i in ids)
            cur.execute(f"""
                SELECT COALESCE(SUM(part), 0) FROM (
                    SELECT COALESCE(SUM(cp.amount), 0) * {fee}
                        / NULLIF(SUM(sf.annual_fee), 0) AS part
                    FROM larcauth_aecuser par
                    JOIN larcauth_student_parent sp ON sp.parent_id = par.id
                    JOIN larcauth_parent lp ON lp.aecuser_ptr_id = par.id AND lp.is_payer = TRUE
                    JOIN larcauth_student s ON s.aecuser_ptr_id = sp.student_id
                    JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                    JOIN larcauth_level l ON l.id = c.fk_level_id
                    JOIN larcauth_program p ON p.id = l.fk_program_id
                    LEFT JOIN compta_payment cp ON cp.parent_id = par.id
                    LEFT JOIN compta_student_fee sf ON sf.student_id = sp.student_id
                    WHERE p.id IN ({id_list}) AND s.enabled = true {flt}
                    GROUP BY par.id
                ) sub
            """)
            pad = int((cur.fetchone() or [0])[0] or 0)
            pad = min(pad, cnt * fee)
            bar_data.append((f"{cat} ({_fmt(fee)})", pad, cnt * fee))
            pad = int((cur.fetchone() or [0])[0] or 0)
            pad = min(pad, cnt * fee)
            bar_data.append((f"{cat} ({_fmt(fee)})", pad, cnt * fee))

        bar = _BarChart("Encaissements par categorie", bar_data)

        lo = self._container.layout()
        if self._donut:
            lo.replaceWidget(self._donut, donut)
            self._donut.deleteLater()
            self._donut = donut
        if self._bar:
            lo.replaceWidget(self._bar, bar)
            self._bar.deleteLater()
            self._bar = bar

    # ── Table detail (DP4a) ──
    def _load_table(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        while self._table_layout.count():
            item = self._table_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        conn = db.server_conn
        if not conn:
            return
        cur = conn.cursor()

        flt = _build_filter(self._group_mode)

        cur.execute(f"""
            SELECT p.sigle, COUNT(*),
                   CASE WHEN bool_or(p.id IN (11,12,21,22)) THEN {COLLEGE_FEE} ELSE {LYCEE_FEE} END
            FROM larcauth_student s
            JOIN larcauth_classroom c ON c.id = s.s_classroom_id
            JOIN larcauth_level l ON l.id = c.fk_level_id
            JOIN larcauth_program p ON p.id = l.fk_program_id
            WHERE s.enabled = true {flt}
            GROUP BY p.sigle
            ORDER BY p.sigle
        """)

        for sigle, cnt, fee in cur.fetchall():
            total = cnt * fee
            cur.execute(f"""
                SELECT COALESCE(SUM(part), 0) FROM (
                    SELECT COALESCE(SUM(cp.amount), 0) * {fee}
                        / NULLIF(SUM(sf.annual_fee), 0) AS part
                    FROM larcauth_aecuser par
                    JOIN larcauth_student_parent sp ON sp.parent_id = par.id
                    JOIN larcauth_parent lp ON lp.aecuser_ptr_id = par.id AND lp.is_payer = TRUE
                    JOIN larcauth_student s ON s.aecuser_ptr_id = sp.student_id
                    JOIN larcauth_classroom c ON c.id = s.s_classroom_id
                    JOIN larcauth_level l ON l.id = c.fk_level_id
                    JOIN larcauth_program p ON p.id = l.fk_program_id
                    LEFT JOIN compta_payment cp ON cp.parent_id = par.id
                    LEFT JOIN compta_student_fee sf ON sf.student_id = sp.student_id
                    WHERE p.sigle = %s AND s.enabled = true {flt}
                    GROUP BY par.id
                ) sub
            """, (sigle,))
            pad = int((cur.fetchone() or [0])[0] or 0)
            pad = min(pad, total)
            pct = (pad / total * 100) if total > 0 else 0

            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(ds.space_sm, ds.space_xxs, ds.space_sm, ds.space_xxs)
            rl.setSpacing(ds.space_sm)

            items = [
                (sigle, ds.space_xxxl // 2 - ds.space_lg, p.text_strong),
                (f"{cnt} eleves", ds.kpi_card_height, p.text_soft),
                (_fmt(total), ds.kpi_card_height + ds.space_sm, p.text_strong),
                (_fmt(pad), ds.kpi_card_height + ds.space_sm, p.success),
                (f"{pct:.0f} %", ds.space_lg + ds.space_sm,
                 p.primary if pct > ds.space_lg else p.error),
            ]
            for text, w, color in items:
                lbl = QLabel(text)
                lbl.setFixedWidth(w)
                lbl.setStyleSheet(f"font-size: {s(12)}px; color: {color}; border: none;")
                rl.addWidget(lbl)

            # Barre progression
            bar_w = ds.space_xxxl
            bar_bg = QFrame()
            bar_bg.setAttribute(Qt.WA_StyledBackground, True)
            bar_bg.setFixedSize(bar_w, ds.space_sm)
            bar_bg.setStyleSheet(
                f"background: {p.outline_variant}; border-radius: {ds.radius_xs // 2}px;")
            bar_fill = QFrame(bar_bg)
            bar_fill.setAttribute(Qt.WA_StyledBackground, True)
            bar_fill.setFixedSize(max(ds.space_xxs, int(bar_w * pct / 100)), ds.space_sm)
            bar_fill.setStyleSheet(
                f"background: {p.success if pct > 50 else p.error}; "
                f"border-radius: {ds.radius_xs // 2}px;")
            rl.addWidget(bar_bg)

            rl.addStretch()
            row.setStyleSheet(
                f"QWidget {{ background: {p.surface}; border-radius: {ds.radius_xs}px; }}"
                f"QWidget:hover {{ background: {p.surface_variant}; }}")
            self._table_layout.addWidget(row)
