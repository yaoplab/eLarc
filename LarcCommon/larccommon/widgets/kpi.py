"""kpi.py — carte KPI (skill dashboard-pattern).

Pattern canonique (LarcRH/LarcCompta) : QFrame #kpi_card, barre d'accent à
gauche, icône MD3, valeur en grand, libellé et détail. QSS via
QssHelper.kpi_common. L'accent est un nom de rôle palette résolu au
restyle → réactif au thème (ds.theme_changed).
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.safe_slot import safe_slot
from larccommon.theme import QssHelper, theme_manager


class KpiCard(QFrame):
    """KPI : libellé au-dessus, valeur en grand (couleur accent), détail
    discret. `accent_token` = nom de rôle palette (ex. "success")."""

    def __init__(self, label: str, icon_name: str = "dashboard",
                 accent_token: str = "primary", parent=None):
        super().__init__(parent)
        self._label_text = label
        self._icon_name = icon_name
        self._accent_token = accent_token
        self.setObjectName("kpi_card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        # Calcul vertical : valeur jusqu'à 28 px (ligne ≈ 38) + libellé 12
        # (≈ 16) + détail 12 (≈ 16) + 2 espacements de 4 + marges 2×12
        # ≈ 98 px → 112 px (kpi_card_height + space_lg) pour ne pas couper
        self.setFixedHeight(ds.kpi_card_height + ds.space_lg)
        self.setMinimumWidth(ds.kpi_card_min_width)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(ds.space_m3, ds.space_sm, ds.space_m3, ds.space_sm)
        layout.setSpacing(ds.space_m3)

        # Barre accent à gauche (4 px, pleine hauteur)
        bar = QFrame()
        bar.setObjectName("accent")
        bar.setFixedWidth(ds.space_xxs)
        layout.addWidget(bar)

        self._icon_lbl = QLabel()
        layout.addWidget(self._icon_lbl)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(ds.space_xxs)
        self._value_lbl = QLabel("—")
        self._value_lbl.setObjectName("kpi_value")
        col.addWidget(self._value_lbl)
        self._label_lbl = QLabel(label)
        self._label_lbl.setObjectName("kpi_label")
        col.addWidget(self._label_lbl)
        self._detail_lbl = QLabel("")
        self._detail_lbl.setObjectName("kpi_detail")
        self._detail_lbl.setVisible(False)
        col.addWidget(self._detail_lbl)
        layout.addLayout(col, 1)

        ds.theme_changed.connect(self._restyle)
        self._restyle()

    def set_value(self, value: str):
        self._value_lbl.setText(value)
        self._apply_value_size()

    def set_detail(self, text: str):
        self._detail_lbl.setText(text)
        self._detail_lbl.setVisible(bool(text))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_value_size()

    def _apply_value_size(self):
        """Auto-fit de la valeur : réduit de 2 px tant que le texte déborde
        (min ds.font_title) — jamais de texte coupé."""
        text = self._value_lbl.text()
        avail = self._value_lbl.width()
        if not text or avail <= 0:
            return
        size = ds.font_headline_md  # 28
        fm = QFontMetrics(theme_manager.font_px(size, QFont.Weight.Bold))
        while size > ds.font_title and fm.horizontalAdvance(text) > avail:
            size -= ds.border_width * 2
            fm = QFontMetrics(theme_manager.font_px(size, QFont.Weight.Bold))
        # −3 px (espace_xxs − border) : respiration volontaire — la valeur
        # doit être plus petite que le strict maximum qui « tient »
        size = max(size - (ds.space_xxs - ds.border_width), ds.font_small)
        accent = getattr(theme_manager.palette, self._accent_token,
                         theme_manager.palette.primary)
        self._value_lbl.setStyleSheet(
            f"font-size: {theme_manager.font_size(size)}px; "
            f"font-weight: bold; color: {accent};")

    @safe_slot("KpiCard.restyle")
    def _restyle(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        accent = getattr(p, self._accent_token, p.primary)
        self.setStyleSheet(
            f"{QssHelper.kpi_common(p, theme_manager.design, s)}"
            f"QFrame#accent {{ background: {accent}; border: none; }}"
            f"QLabel#kpi_value {{ font-size: {s(ds.font_headline_md)}px; "
            f"font-weight: bold; color: {accent}; }}"
            f"QLabel#kpi_label {{ font-size: {s(ds.font_small)}px; "
            f"color: {p.text_strong}; }}"
            f"QLabel#kpi_detail {{ font-size: {s(ds.font_small)}px; "
            f"color: {p.text_strong}; }}")
        self._icon_lbl.setPixmap(
            md3_icon(self._icon_name, color=accent, size=ds.icon_md)
            .pixmap(ds.icon_md, ds.icon_md))
        self._apply_value_size()
