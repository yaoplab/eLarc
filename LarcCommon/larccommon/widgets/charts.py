"""charts.py — graphiques QPainter maison (skill dashboard-pattern).

- HBarCell : rangées horizontales (libellé | barre | valeur) — par classe
- RingChart : anneau de répartition avec total au centre + légende
- StatChange : valeur + variation (petit texte) pour cartes KPI

Couleurs : une série accepte un nom de rôle de theme_manager.palette
(ex. "primary", "success") résolu au moment du paint — réactif au thème —
ou une couleur brute. Polices via theme_manager.font (multiplicateur).
Aucune dépendance externe.
"""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from larccommon.design_system import ds
from larccommon.theme import theme_manager


def _pen(color, width):
    pen = QPen(QColor(color))
    pen.setWidth(width)
    return pen


def _resolve_color(value) -> str:
    """Nom de rôle palette → couleur du thème courant, sinon couleur brute."""
    pal = theme_manager.palette
    if isinstance(value, str) and hasattr(pal, value):
        return getattr(pal, value)
    return value


class HBarCell(QWidget):
    """Barres horizontales : libellé à gauche, barre proportionnelle (base
    carrée, extrémité arrondie 4 px), valeur en fin de barre. Une rangée
    par item. Les couleurs de série peuvent être des rôles de palette."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []  # (label, value, color)
        self.setMinimumHeight(ds.space_xxxl + ds.space_xxl)  # ~220
        ds.theme_changed.connect(self.update)

    def set_items(self, items):
        """items : (label, value, color) ou None (séparateur de groupe).
        La hauteur minimale s'adapte au nombre de rangées."""
        self._items = items
        n_bars = sum(1 for it in items if it is not None)
        n_seps = len(items) - n_bars
        need = n_bars * ds.space_md + n_seps * ds.space_xs
        self.setMinimumHeight(max(ds.space_xxxl + ds.space_xxl, need))
        self.update()

    def paintEvent(self, event):
        if not self._items:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme_manager.palette

        h = self.height()
        n_bars = sum(1 for it in self._items if it is not None)
        n_seps = len(self._items) - n_bars
        sep_h = ds.space_xs
        row_h = max((h - n_seps * sep_h) / max(n_bars, 1), ds.space_m3)
        label_w = min(110, self.width() * 0.28)
        bar_h = ds.space_xs + ds.border_width * 2  # 10 px ≤ 24 (dataviz)
        bar_max = self.width() - label_w - 66
        values = [it[1] for it in self._items if it is not None]
        max_val = max(values, default=1) or 1
        fm_label = QFontMetrics(theme_manager.font_px(ds.font_small))

        p.setFont(theme_manager.font_px(ds.font_small))
        y = 0
        for item in self._items:
            if item is None:
                y += sep_h  # gap entre groupes de programmes
                continue
            label, value, color = item
            yy = y + (row_h - bar_h) / 2
            # Libellé (encre douce, élisé) — jamais en couleur de série
            p.setPen(_pen(pal.text_soft, 1))
            elided = fm_label.elidedText(str(label), Qt.TextElideMode.ElideRight,
                                         label_w - ds.space_xs)
            p.drawText(QRectF(0, y, label_w - ds.space_xs, row_h),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       elided)
            # Barre — base carrée à gauche, extrémité droite arrondie
            bw = max(bar_max * (value / max_val), bar_h)
            r = bar_h / 2
            path = QPainterPath()
            path.moveTo(label_w, yy)
            path.lineTo(label_w + bw - r, yy)
            path.arcTo(label_w + bw - 2 * r, yy, 2 * r, bar_h, 90, -180)
            path.lineTo(label_w, yy + bar_h)
            path.closeSubpath()
            p.fillPath(path, QColor(_resolve_color(color)))
            # Valeur en fin de barre (encre forte) ; repliée dans la barre
            # si la place manque
            p.setFont(theme_manager.font_px(ds.font_small, QFont.Weight.Bold))
            if label_w + bw + 66 <= self.width():
                p.setPen(_pen(pal.text_strong, 1))
                p.drawText(QRectF(label_w + bw + ds.space_xs, yy, 60, bar_h),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           str(value))
            else:
                p.setPen(_pen(pal.on_primary, 1))
                p.drawText(QRectF(label_w + bw - 60 - ds.space_xs, yy, 60, bar_h),
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                           str(value))
            y += row_h
        p.end()


class RingChart(QWidget):
    """Anneau de répartition : segments (label, valeur, couleur), trou en
    surface avec le total héros au centre, légende à droite avec effectifs
    (toujours présente si ≥ 2 séries). Couleurs = rôles ou couleurs brutes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._segments = []  # (label, value, color)
        self.setMinimumHeight(ds.space_xxxl + ds.space_xxl)  # ~220
        ds.theme_changed.connect(self.update)

    def set_segments(self, segments):
        self._segments = segments
        self.update()

    def paintEvent(self, event):
        if not self._segments:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme_manager.palette

        total = sum(v for _, v, _ in self._segments) or 1
        h = self.height()
        legend_w = min(150, self.width() * 0.42) if len(self._segments) >= 2 else 0
        d = min(h - ds.space_md, self.width() - legend_w - ds.space_md * 2)
        rect = QRectF(ds.space_xs, (h - d) / 2, d, d)

        # Segments (sens horaire depuis 12 h) avec gap 1° = surface visible
        start = 90 * 16
        gap = 16  # 1° en 1/16 de degré
        for _label, value, color in self._segments:
            span = -int(360 * 16 * value / total)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(_resolve_color(color)))
            p.drawPie(rect, start, span + gap if span < -gap else span)
            start += span
        # Trou + total héros au centre
        hole = rect.adjusted(d * 0.32, d * 0.32, -d * 0.32, -d * 0.32)
        p.setBrush(QColor(pal.surface))
        p.drawEllipse(hole)
        p.setPen(_pen(pal.text_strong, 1))
        # Total héros 36 px (headline_large) — auto-fit 28 px si le trou
        # est étroit. Un seul chiffre héros par vue (dataviz).
        total_font = theme_manager.font_px(ds.font_headline_lg, QFont.Weight.Bold)
        if QFontMetrics(total_font).horizontalAdvance(str(total)) > hole.width() - ds.space_md:
            total_font = theme_manager.font_px(ds.font_headline_md, QFont.Weight.Bold)
        p.setFont(total_font)
        p.drawText(hole, Qt.AlignmentFlag.AlignCenter, str(total))

        # Légende à droite : swatch + libellé + effectif (≥ 2 séries)
        if len(self._segments) >= 2:
            p.setFont(theme_manager.font_px(ds.font_small))
            row_h = ds.space_md
            ly = (h - len(self._segments) * row_h) / 2
            swatch = ds.space_xs
            for label, value, color in self._segments:
                p.setBrush(QColor(_resolve_color(color)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRect(QRectF(rect.right() + ds.space_md - ds.space_xs,
                                  ly + (row_h - swatch) / 2, swatch, swatch))
                p.setPen(_pen(pal.text_strong, 1))
                p.drawText(QRectF(rect.right() + ds.space_md + ds.space_xs,
                                  ly, legend_w - ds.space_md - ds.space_sm, row_h),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           label)
                p.setPen(_pen(pal.text_soft, 1))
                p.drawText(QRectF(self.width() - 64, ly, 60, row_h),
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                           str(value))
                ly += row_h
        p.end()


class StatChange(QWidget):
    """Valeur en grand + variation en petit (contenu de carte KPI)."""

    def __init__(self, value: str, delta: str = '', parent=None):
        super().__init__(parent)
        self._value = value
        self._delta = delta
        self.setMinimumHeight(ds.space_xxl)
        ds.theme_changed.connect(self.update)

    def set_value(self, value: str, delta: str = ''):
        self._value = value
        self._delta = delta
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme_manager.palette
        p.setPen(_pen(pal.text_strong, 1))
        p.setFont(theme_manager.font_px(ds.font_headline_md, QFont.Weight.Bold))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                   self._value)
        if self._delta:
            p.setPen(_pen(pal.text_soft, 1))
            p.setFont(theme_manager.font_px(ds.font_small))
            p.drawText(QRectF(0, 34, self.width(), 16),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                       self._delta)
        p.end()
