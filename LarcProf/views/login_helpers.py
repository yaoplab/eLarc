from typing import Optional

from larccommon.design_system import ds
from phibuilder.phi.scale import SpacingToken
from PySide6.QtCore import Q_ARG, QMetaObject, Qt

from common.database import db
from common.session import AuthResult, ConnMode, UserRole
from common.theme import theme_manager


# ---------------------------------------------------------------------------
# Generic background worker
# ---------------------------------------------------------------------------


class LoginHelpersMixin:
    """Mixin LoginHelpersMixin — voir le module parent."""

    def _restyle_all(self) -> None:
        """Hook de restyle piloté par le parent (règle D6).

        La classe composante (LoginWindow) connecte theme_changed → son
        _restyle() ré-applique tous les styles palette posés ici.
        """

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Helpers (inchangés)
    # ------------------------------------------------------------------
    def _set_busy(self, busy: bool) -> None:
        for btn in (self._btn_intra, self._btn_google, self._btn_pin, self._btn_create):
            QMetaObject.invokeMethod(btn, "setEnabled", Qt.QueuedConnection, Q_ARG(bool, not busy))
        text = "Connexion en cours" if busy else "Détection du réseau"
        QMetaObject.invokeMethod(self._net_lbl, "setText", Qt.QueuedConnection, Q_ARG(str, text))

    def _show_error(self, msg: str) -> None:
        p = theme_manager.theme.palette
        QMetaObject.invokeMethod(self._err_lbl, "setText", Qt.QueuedConnection, Q_ARG(str, msg))
        QMetaObject.invokeMethod(
            self._err_lbl,
            "setStyleSheet",
            Qt.QueuedConnection,
            Q_ARG(
                str,
                f"color: {p.error}; font-size: {theme_manager.font_size(11)}px; font-weight: bold;",
            ),
        )
        QMetaObject.invokeMethod(self._err_lbl, "show", Qt.QueuedConnection)

    def _log(self, msg: str) -> None:
        QMetaObject.invokeMethod(
            self._log_area, "appendPlainText", Qt.QueuedConnection, Q_ARG(str, msg)
        )
        QMetaObject.invokeMethod(self._log_area, "show", Qt.QueuedConnection)
        sb = self._log_area.verticalScrollBar()
        QMetaObject.invokeMethod(sb, "setValue", Qt.QueuedConnection, Q_ARG(int, sb.maximum()))

    def _show_progress(self, msg: str) -> None:
        p = theme_manager.theme.palette
        self._err_lbl.setText(msg)
        self._err_lbl.setStyleSheet(
            f"color: {p.text_strong}; font-size: {theme_manager.font_size(11)}px;"
        )
        self._err_lbl.show()
        self._log(msg)

    def _show_spinner(self, visible: bool) -> None:
        if not hasattr(self, "_spinner"):
            from PySide6.QtWidgets import QProgressBar

            self._spinner = QProgressBar()
            self._spinner.setRange(0, 0)
            self._spinner.setFixedHeight(ds.table_row_min)  # 21px
            p = theme_manager.theme.palette
            self._spinner.setStyleSheet(
                f"QProgressBar {{ border: 1px solid {p.border}; border-radius: {ds.radius_xs}px; "
                f"background: {p.surface}; text-align: center; }}"
                f"QProgressBar::chunk {{ background: {p.primary}; }}"
            )
            layout = self.centralWidget().layout()
            layout.insertWidget(layout.indexOf(self._bottom_indicator), self._spinner)
        self._spinner.setVisible(visible)

    def _hide_error(self) -> None:
        self._err_lbl.hide()

    def _get_module_config(self) -> Optional[dict]:
        try:
            conn = db.local_conn
            if conn is None:
                return None
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='module_config'"
            )
            if not cur.fetchone():
                return None
            cur.execute(
                "SELECT nom_professeur, annee_scolaire, trimestre_courant, email_professeur FROM module_config LIMIT 1"
            )
            row = cur.fetchone()
            if row and row[0]:
                return {
                    "nom_professeur": row[0],
                    "annee_scolaire": row[1],
                    "trimestre_courant": row[2],
                    "email_professeur": row[3] if len(row) > 3 else "",
                }
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self._log(f"Erreur dans _get_module_config : {e}")
        return None

    def _get_module_config_dates(self) -> dict:
        try:
            conn = db.local_conn
            if conn is None:
                return {"date_creation_module": "", "derniere_synchronisation": ""}
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='module_config'"
            )
            if not cur.fetchone():
                return {"date_creation_module": "", "derniere_synchronisation": ""}
            cur.execute(
                "SELECT date_creation_module, derniere_synchronisation FROM module_config LIMIT 1"
            )
            row = cur.fetchone()
            if row:
                return {
                    "date_creation_module": row[0] or "",
                    "derniere_synchronisation": row[1] or "",
                }
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self._log(f"Erreur dans _get_module_config_dates : {e}")
        return {"date_creation_module": "", "derniere_synchronisation": ""}

    def _update_status_bar_from_module_config(self) -> None:
        try:
            if db.local_conn is None:
                self._bottom_indicator.setText("Module LarcProf non instanciée")
                return
            config = self._get_module_config()
            if config:
                prof_name = config["nom_professeur"]
                from common.session import session

                mode = session.conn_mode if session.is_authenticated else ConnMode.OFFLINE
                self._update_status_bar(
                    AuthResult(
                        user_id=0,
                        email="",
                        full_name=prof_name,
                        role=UserRole.PROF,
                        term_id=config["trimestre_courant"],
                        term_label="",
                    ),
                    mode,
                )
            else:
                self._bottom_indicator.setText("Module LarcProf non instanciée")
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self._log(f"Erreur dans _update_status_bar_from_module_config : {e}")
            self._bottom_indicator.setText("Module LarcProf non instanciée")

    def _update_status_bar(self, res: AuthResult, mode: ConnMode) -> None:
        sp = self._sp
        p = theme_manager.theme.palette
        prof_name = res.full_name or (self._get_module_config() or {}).get("nom_professeur", "")

        if mode == ConnMode.INTRANET:
            title = f"Module de {prof_name} : Connecté à l'Intranet"
            color = ds.p.success
        elif mode == ConnMode.CLOUD:
            title = f"Module de {prof_name} : Connecté au Cloud"
            color = ds.p.success
        elif prof_name:
            title = f"Module de {prof_name} : Non connecté"
            color = p.text_strong
        else:
            title = "Module LarcProf non instanciée"
            color = p.text_strong

        self._bottom_indicator.setText(title)
        self._bottom_indicator.setStyleSheet(
            f"color: {color}; font-size: {theme_manager.font_size(13)}px; font-weight: bold;"
            f"padding: {sp(SpacingToken.SM)}px {sp(SpacingToken.MD)}px;"
        )

    def _open_main_window(self, res: AuthResult) -> None:
        from views.home_window import HomeWindow

        # PAS de parent : la HomeWindow doit être une vraie fenêtre top-level.
        # Avec un parent (LoginWindow cachée), isVisible() reste False → quand
        # les notes se ferment, quitOnLastWindowClosed ne la voit pas → l'app
        # quitte au lieu de revenir au tableau de bord.
        self._main_window = HomeWindow()
        self._main_window.show()
        self.hide()
