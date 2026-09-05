"""
M3Skeleton — placeholders animes avec shimmer pour les etats de chargement.

Usage:
    # Direct
    skeleton = M3Skeleton.card(parent)
    skeleton.start()
    ...
    skeleton.stop()
    skeleton.hide()

    # Context manager (cache puis restaure le widget existant)
    with skeleton_loader(M3Skeleton.table(parent, rows=5, cols=3), target=table_widget):
        ... chargement ...
"""

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from larccommon.design_system import ds


def skeleton_loader(skeleton: "M3Skeleton", target: QWidget):
    """Context manager : cache la target, montre le skeleton, le cache a la sortie."""
    from PySide6.QtWidgets import QApplication

    class _Loader:
        def __enter__(self):
            target.hide()
            skeleton.show()
            skeleton.start()
            QApplication.processEvents()
            return skeleton

        def __exit__(self, *args):
            skeleton.stop()
            skeleton.hide()
            target.show()

    return _Loader()

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from larccommon.design_system import ds
from larccommon.safe_slot import safe_slot


class M3Skeleton(QWidget):
    """Widget de chargement avec effet shimmer Material Design 3.

    Sans QGraphicsOpacityEffect (instable sur Windows), l'animation
    shimmer est pilotee par QTimer + update() directement dans paintEvent.
    """

    _TIMER_MS = 30  # ~33 fps

    def __init__(self, parent=None):
        super().__init__(parent)
        self._offset = -1.0
        self._running = False
        self._label: str | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._draw_func = lambda p, r: p.drawRoundedRect(
            QRectF(0, 0, r.width(), r.height()), ds.radius_md, ds.radius_md)
        self.setMinimumSize(ds.icon_btn_size, ds.icon_btn_size)
        self.setAttribute(Qt.WA_StyledBackground, True)

    # ── Factory methods ──

    @classmethod
    def card(cls, parent=None, height: int = 120, width: int | None = None):
        w = cls(parent)
        if width:
            w.setFixedWidth(width)
        w.setMinimumHeight(height)
        w._draw_func = lambda p, r: p.drawRoundedRect(
            QRectF(0, 0, r.width(), r.height()), ds.radius_md, ds.radius_md)
        return w

    @classmethod
    def text(cls, parent=None, lines: int = 3, spacing: int | None = None):
        w = cls(parent)
        sp = spacing or ds.space_sm
        w.setMinimumHeight(lines * (ds.field_height + sp) - sp)
        w._draw_func = lambda p, r: cls._draw_text_lines(p, r, lines, sp)
        return w

    @classmethod
    def avatar(cls, parent=None, size: int = 64):
        w = cls(parent)
        w.setFixedSize(size, size)
        w._draw_func = lambda p, r: p.drawEllipse(
            QPointF(r.width() / 2, r.height() / 2), size / 2, size / 2)
        return w

    @classmethod
    def table(cls, parent=None, rows: int = 5, cols: int = 4):
        w = cls(parent)
        w.setMinimumHeight(rows * (ds.table_row_min + ds.space_xxs) + ds.field_height)
        w._draw_func = lambda p, r: cls._draw_table_rows(p, r, rows, cols)
        return w

    @classmethod
    def form(cls, parent=None, fields: int = 6, cols: int = 2):
        w = cls(parent)
        rows_count = (fields + cols - 1) // cols
        h = rows_count * (ds.field_height + ds.font_label_sm + ds.space_xxs + ds.space_sm)
        w.setMinimumHeight(int(h))
        w._draw_func = lambda p, r: cls._draw_form_fields(p, r, fields, cols)
        return w

    # ── Texte d'indication ──

    def set_label(self, text: str):
        self._label = text
        self.update()

    # ── Animation ──

    def start(self):
        if self._running:
            return
        self._running = True
        self._offset = -1.0
        self._timer.start(self._TIMER_MS)

    def stop(self):
        if not self._running:
            return
        self._running = False
        self._offset = -1.0
        self._timer.stop()
        self.update()

    @safe_slot("M3Skeleton._tick")
    def _tick(self):
        self._offset += 0.02  # vitesse de glissement
        if self._offset > 2.0:
            self._offset = -1.0
        self.update()

    # ── Dessin ──

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        base = QColor(ds.p.surface_variant)
        highlight = QColor(ds.p.surface)
        r = self.rect()

        # Fond statique
        painter.setBrush(QBrush(base))
        painter.setPen(Qt.NoPen)
        self._draw_func(painter, r)

        # Surimpression du degrade shimmer anime
        if self._running:
            highlight.setAlpha(140)
            w = r.width()
            gradient = QLinearGradient(QPointF(0, 0), QPointF(w, 0))
            gradient.setColorAt(0.0, Qt.transparent)
            gradient.setColorAt(max(0.0, self._offset - 0.15), Qt.transparent)
            gradient.setColorAt(max(0.0, self._offset + 0.05), highlight)
            gradient.setColorAt(max(0.0, self._offset + 0.2), Qt.transparent)
            gradient.setColorAt(1.0, Qt.transparent)
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(QRectF(0, 0, r.width(), r.height()),
                                   ds.radius_sm, ds.radius_sm)

        # Label discret
        if self._label:
            painter.setPen(QColor(ds.p.text_disabled))
            font = painter.font()
            font.setPixelSize(ds.font_body_sm)
            painter.setFont(font)
            painter.drawText(r.adjusted(0, 0, -ds.space_sm, -ds.space_xs),
                           Qt.AlignRight | Qt.AlignBottom, self._label)

        painter.end()

    # ── Helpers de dessin ──

    @staticmethod
    def _draw_text_lines(painter, rect, lines, spacing):
        h = ds.field_height
        y = 0
        widths = [0.9, 0.7, 0.85, 0.6, 0.75, 0.8, 0.65]
        for i in range(lines):
            w = rect.width() * widths[i % len(widths)]
            painter.drawRoundedRect(QRectF(0, y, w, h), ds.radius_sm, ds.radius_sm)
            y += h + spacing

    @staticmethod
    def _draw_table_rows(painter, rect, rows, cols):
        h = ds.table_row_min
        header_h = ds.field_height
        y = header_h
        painter.drawRoundedRect(QRectF(0, 0, rect.width(), header_h), ds.radius_sm, ds.radius_sm)
        col_w = rect.width() / cols
        for r_idx in range(rows):
            for c in range(cols):
                gap = ds.space_xxs
                painter.drawRoundedRect(
                    QRectF(c * col_w + 2, y + gap, col_w - 4, h),
                    ds.radius_xs, ds.radius_xs)
            y += h + ds.space_xxs

    @staticmethod
    def _draw_form_fields(painter, rect, fields, cols):
        col_w = rect.width() / cols
        label_h = ds.font_label_sm + 2
        field_h = ds.field_height
        for i in range(fields):
            r_idx = i // cols
            c = i % cols
            x = c * col_w + 2
            y = r_idx * (label_h + field_h + ds.space_sm)
            painter.drawRoundedRect(
                QRectF(x, y, col_w * 0.5 - 4, label_h), ds.radius_xs, ds.radius_xs)
            painter.drawRoundedRect(
                QRectF(x, y + label_h + ds.space_xxs, col_w - 4, field_h),
                ds.radius_sm, ds.radius_sm)
