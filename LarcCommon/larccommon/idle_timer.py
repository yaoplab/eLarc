"""IdleGuard — déconnexion automatique après une période d'inactivité.

Une interaction souris/clavier (clic, touche, mouvement, molette) remet le
compte à rebours à zéro. Au bout de `minutes` sans activité, le signal
`idle_timeout` est émis — l'app décide alors de la déconnexion (retour au
login, fermeture, etc.).

Usage (main.py, après le login) :
    from larccommon.idle_timer import IdleGuard
    idle = IdleGuard(minutes=10)
    idle.idle_timeout.connect(self._on_idle)
    idle.start()
"""
from PySide6.QtCore import QEvent, QObject, QTimer, Signal


class IdleGuard(QObject):
    idle_timeout = Signal()

    def __init__(self, minutes: int = 10, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(int(minutes * 60 * 1000))
        self._timer.timeout.connect(self.idle_timeout)

    def start(self):
        """Installe le filtre d'activité et lance le compte à rebours."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)
        self._timer.start()

    def stop(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.removeEventFilter(self)
        self._timer.stop()

    def eventFilter(self, obj, event):
        # Toute interaction remet le minuteur à zéro (activité = présence)
        if event.type() in (QEvent.MouseButtonPress, QEvent.KeyPress,
                            QEvent.MouseMove, QEvent.Wheel):
            self._timer.start()
        return super().eventFilter(obj, event)
