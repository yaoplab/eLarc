"""timeline.py — frise temporelle scolaire à l'échelle (widget partagé).

Affiche une année scolaire complète : bande "unités" (une couleur stable
par unité, réutilise STAFF_TYPE_COLORS — déjà theme-aware clair/sombre),
bande "trimestres" en couleurs de rôle, marqueur "aujourd'hui", bornes
d'année. Le segment courant (unité/trimestre actif) ressort avec une
bordure marquée, sans jamais redéfinir lequel fait autorité — c'est
l'appelant qui transmet current_unit_nr/current_trim_nr (généralement
dérivé de current_term_number, pas des dates, par app).

Générique en nombre de segments (pas figé à 3 trimestres / 6 unités) —
le cycle de couleurs se répète via modulo sur la taille réelle des
listes transmises.

Utilisé par LarcConfig (panel_accueil.py) ; réutilisable par toute app
qui affiche la même année scolaire (ex. LarcProf).
"""
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from larccommon.design_system import ds
from larccommon.theme import staff_type_color, theme_manager

_DATE_FMT = '%d/%m/%Y'

# 6 teintes distinctes (theme-aware) pour les unités de l'année -- réutilise
# STAFF_TYPE_COLORS (déjà conçu pour rester lisible clair/sombre), sans lien
# sémantique avec les rôles staff : juste des couleurs stables et distinctes.
_UNIT_COLOR_KEYS = ['administrateur', 'coordonnateur', 'superviseur',
                     'secretaire', 'professeur', 'staff']


class TimelineWidget(QWidget):
    """Ligne de temps scolaire à l'échelle (frise sans cadre)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start = None
        self._end = None
        self._events = []  # (date, label, kind) -- 'today' + bornes annee
        self._unites = []  # [{'nr', 'label', 'start', 'end'}] langue deja resolue
        self._trimestres = []  # [{'nr', 'label', 'start', 'end'}]
        self._current_unit_nr = None
        self._current_trim_nr = None
        # 208 px : frise compacte -- bandes unites/trimestres + 5 lignes de
        # legendes max sous l'axe
        self.setMinimumHeight(ds.space_xxxl + ds.space_lg + ds.space_md)
        ds.theme_changed.connect(self.update)

    def set_data(self, start, end, events, unites=None, trimestres=None,
                 current_unit_nr=None, current_trim_nr=None):
        self._start = start
        self._end = end
        self._events = events
        self._unites = unites or []
        self._trimestres = trimestres or []
        self._current_unit_nr = current_unit_nr
        self._current_trim_nr = current_trim_nr
        self.update()

    @staticmethod
    def _pen(color, width):
        pen = QPen(QColor(color))
        pen.setWidth(width)
        return pen

    def paintEvent(self, event):
        if self._start is None or self._end is None or not self._events:
            return
        if self._end <= self._start:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme_manager.palette

        w = self.width()
        left = ds.space_md
        right = w - ds.space_md
        # 112 px sous l'axe : 5 lignes de légendes (8 + 5×18 = 98 + marge)
        axis_y = self.height() - ds.space_xxxl + ds.space_md + ds.space_xxs
        span = (self._end - self._start).days

        def x(d):
            return left + (d - self._start).days / span * (right - left)

        events = {k: d for d, _l, k in self._events}

        # Bande trimestres (fine, sans libellé — segments contigus,
        # couleurs de rôle distinctes) juste au-dessus de la bande unités.
        term_band_h = ds.space_xs
        term_band_bottom = axis_y - ds.space_xs - ds.space_md - ds.space_xxs
        term_band_top = term_band_bottom - term_band_h
        term_colors = (pal.primary, pal.accent, pal.tertiary)
        for t in self._trimestres:
            t_start, t_end = t.get('start'), t.get('end')
            if not t_start or not t_end:
                continue
            rect = QRectF(x(t_start), term_band_top,
                          max(x(t_end) - x(t_start), ds.border_width * 2),
                          term_band_h)
            color = term_colors[(t['nr'] - 1) % len(term_colors)]
            p.fillRect(rect, QColor(color))
            if t['nr'] == self._current_trim_nr:
                p.setPen(self._pen(pal.text_strong, ds.border_width * 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(rect)

        # Bande unités (plus épaisse, libellé « U1 »..« Un » si assez de
        # place) — segments contigus, une couleur stable par unité, sur
        # toute l'année (couleur + temps distingués).
        unit_band_h = ds.space_md
        unit_band_bottom = axis_y - ds.space_xs
        unit_band_top = unit_band_bottom - unit_band_h
        unit_fm = QFontMetrics(theme_manager.font_px(ds.font_small))
        for u in self._unites:
            u_start, u_end = u.get('start'), u.get('end')
            if not u_start or not u_end:
                continue
            rx0, rx1 = x(u_start), x(u_end)
            rect = QRectF(rx0, unit_band_top,
                          max(rx1 - rx0, ds.border_width * 2), unit_band_h)
            key = _UNIT_COLOR_KEYS[(u['nr'] - 1) % len(_UNIT_COLOR_KEYS)]
            badge, _container, on_badge = staff_type_color(key)
            p.fillRect(rect, QColor(badge))
            if u['nr'] == self._current_unit_nr:
                p.setPen(self._pen(pal.text_strong, ds.border_width * 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(rect.adjusted(1, 1, -1, -1))
            short = f"U{u['nr']}"
            if rect.width() >= unit_fm.horizontalAdvance(short) + ds.space_xxs:
                p.setPen(self._pen(on_badge, 1))
                p.setFont(theme_manager.font_px(ds.font_small))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, short)

        # Axe
        p.setPen(self._pen(pal.outline_variant, ds.border_width * 2))
        p.drawLine(left, axis_y, right, axis_y)

        # « Aujourd'hui » — TOUJOURS en rouge sur la ligne ; clampé aux
        # bornes de l'année si hors période.
        today_d = events.get('today')
        if today_d is not None:
            tx = min(max(x(today_d), left), right)
            pen = self._pen(pal.error, ds.border_width * 2)
            pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawLine(tx, ds.space_xs, tx, axis_y + ds.space_xxs)

        # Placement anti-chevauchement des libellés (lignes sous l'axe)
        colors = {'year': pal.primary, 'today': pal.error}
        fm = QFontMetrics(theme_manager.font_px(ds.font_small))
        rows = []  # lignes : list[(lx, rx)] des créneaux occupés
        render = []  # (date, caption, kind, above, lx, lw, row_i)
        # Chaque événement porte SA date avec l'année (« Fin année ·
        # 19/06/2026 »). Allocation anti-chevauchement : 4 lignes × 3
        # alignements (centré / à gauche du repère / à droite) — deux
        # événements du même jour finissent toujours sur des lignes
        # différentes
        for d, label, kind in self._events:
            caption = f"{label} · {d.strftime(_DATE_FMT)}"
            tx = min(max(x(d), left), right)
            lw = min(fm.horizontalAdvance(caption) + ds.space_xs,
                     ds.space_xxxl * 2)
            candidates = (
                min(max(tx - lw / 2, left), right - lw),      # centré
                min(max(tx - lw, left), right - lw),          # finit au repère
                min(tx, right - lw),                          # part du repère
                min(max(tx - lw * 1.5, left), right - lw),    # décalé à gauche
            )
            if kind == 'today':
                render.append((d, caption, kind, True, candidates[0], lw, 0))
                continue
            placed = False
            for i, row in enumerate(rows):
                for cand in candidates:
                    if all(not (cand < r[1] and cand + lw > r[0])
                           for r in row):
                        row.append((cand, cand + lw))
                        render.append((d, caption, kind, False, cand, lw, i))
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                if len(rows) < 5:
                    rows.append([(candidates[0], candidates[0] + lw)])
                    render.append((d, caption, kind, False, candidates[0],
                                   lw, len(rows) - 1))
                else:
                    # saturation : repli centré sur la dernière ligne
                    render.append((d, caption, kind, False, candidates[0],
                                   lw, 4))

        row_h = ds.space_m3 + ds.border_width * 2  # 18 px — lignes denses
        p.setFont(theme_manager.font_px(ds.font_small))
        for d, caption, kind, above, lx, lw, row_i in render:
            tx = min(max(x(d), left), right)
            family = kind.split('_', 1)[0]
            color = colors.get(family, pal.primary)
            # Marqueur
            p.setPen(self._pen(color, ds.border_width * 2))
            p.drawLine(tx, axis_y - ds.space_xxs, tx, axis_y + ds.space_xxs)
            p.setBrush(QColor(color))
            r = ds.space_sm // 2 if kind == 'today' else ds.space_xs // 2
            p.drawEllipse(QPointF(tx, axis_y), r, r)
            # Légende « nom · date avec année » — « Aujourd'hui » au-dessus
            # (en rouge), les autres sous l'axe sur une ligne dédiée
            if above:
                p.setPen(self._pen(pal.error, 1))
                p.drawText(QRectF(lx, 0, lw, row_h),
                           Qt.AlignmentFlag.AlignHCenter, caption)
            else:
                p.setPen(self._pen(pal.text_soft, 1))
                y = axis_y + ds.space_xs + row_i * row_h
                p.drawText(QRectF(lx, y, lw, row_h),
                           Qt.AlignmentFlag.AlignHCenter, caption)
        p.end()
