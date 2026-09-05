"""Garde-molette global — input-ergonomics IE1/IE2.

La molette ne doit modifier un widget de valeur (spinbox, combo, date) que
lorsqu'il a le focus clavier — jamais au simple survol pendant le scroll du
formulaire. Sinon, scroller la page peut altérer silencieusement une donnée
(ex. le salaire d'un contrat).

SANS focus, la molette est RETRANSMISE à la scroll area parente pour que le
formulaire continue de scroller (sinon « pas de scroll » ressenti quand le
curseur survole les champs — signalé 2026-08-16).
"""
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QApplication, QScrollArea

# QAbstractSpinBox couvre QSpinBox, QDoubleSpinBox, QDateEdit, QDateTimeEdit, QTimeEdit
WHEEL_SENSITIVE = (QAbstractSpinBox, QComboBox)


class WheelGuard(QObject):
    """Molette : sans focus sur un widget de valeur → la valeur ne change pas
    ET l'événement remonte à la scroll area (le formulaire scrolle)."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and isinstance(obj, WHEEL_SENSITIVE):
            if not obj.hasFocus():
                scroll = self._scroll_area(obj)
                if scroll is not None:
                    QApplication.sendEvent(scroll.viewport(), event)
                return True  # consomme : la molette ne change pas la valeur
        return super().eventFilter(obj, event)

    @staticmethod
    def _scroll_area(widget) -> QScrollArea | None:
        w = widget.parentWidget()
        while w is not None:
            if isinstance(w, QScrollArea):
                return w
            w = w.parentWidget()
        return None


def install_wheel_guard(app) -> None:
    """Installe le garde-molette sur l'application (à appeler une fois dans main.py)."""
    app.installEventFilter(WheelGuard(app))
