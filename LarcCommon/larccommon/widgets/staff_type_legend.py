"""StaffTypeLegend — légende des types d'employés (STAFF_TYPE_COLORS).

Bande horizontale compacte : pastille colorée + libellé pour chacun des
6 types (administrateur → staff non enseignant). Thème-réactif : les
pastilles relisent staff_type_color() à chaque theme_changed — la
déclinaison clair/sombre suit automatiquement.

Usage :
    from larccommon.widgets.staff_type_legend import StaffTypeLegend
    layout.addWidget(StaffTypeLegend())
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from larccommon.design_system import ds
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from larccommon.theme import staff_type_color, theme_manager

# Ordre d'affichage de la légende
LEGEND_ORDER: list[tuple[str, str]] = [
    ("administrateur", "staff_type.administrateur"),
    ("coordonnateur", "staff_type.coordonnateur"),
    ("superviseur", "staff_type.superviseur"),
    ("secretaire", "staff_type.secretaire"),
    ("professeur", "staff_type.professeur"),
    ("staff", "staff_type.staff"),
]


class StaffTypeLegend(QWidget):
    """Légende horizontale : ● Administrateur  ● Coordonnateur  … """

    def __init__(self, parent=None, order: list[tuple[str, str]] | None = None):
        super().__init__(parent)
        self._order = order or LEGEND_ORDER
        self._dots: dict[str, tuple[QLabel, QLabel]] = {}
        self._build()
        theme_manager.theme_changed.connect(self._restyle)

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_xxs, ds.space_md, ds.space_xxs)
        layout.setSpacing(ds.space_xs)
        for key, i18n_key in self._order:
            dot = QLabel("●")
            dot.setAlignment(Qt.AlignCenter)
            dot.setStyleSheet("border: none; background: transparent;")
            lbl = QLabel(_(i18n_key))
            lbl.setStyleSheet("border: none; background: transparent;")
            layout.addWidget(dot)
            layout.addWidget(lbl)
            self._dots[key] = (dot, lbl)
        layout.addStretch()
        self._restyle()

    @safe_slot("StaffTypeLegend._restyle")
    def _restyle(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        for key, (dot, lbl) in self._dots.items():
            badge, _, _ = staff_type_color(key)
            dot.setStyleSheet(
                f"color: {badge}; font-size: {s(14)}px; border: none; background: transparent;")
            lbl.setStyleSheet(
                f"color: {p.text_strong}; font-size: {s(11)}px; border: none; background: transparent;")
