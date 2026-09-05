from larccommon.design_system import ds
from larccommon.l10n import _
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication, QLineEdit

from common.auth import AuthManager, OAuth2Manager
from common.database import db
from common.session import AuthResult, ConnMode, session
from common.sqlite_init import sqlite_init
from larccommon.safe_slot import safe_slot


# ---------------------------------------------------------------------------
# Generic background worker
# ---------------------------------------------------------------------------
class _Worker(QThread):
    done = Signal(object)

    def __init__(self, fn, *args, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._args = args
        self.finished.connect(self.deleteLater)

    def run(self):
        try:
            self.done.emit(self._fn(*self._args))
        except Exception as exc:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self.done.emit((False, None, str(exc)))


class LoginAuthMixin:
    """Mixin LoginAuthMixin — voir le module parent."""
    # ------------------------------------------------------------------
    # Auth handlers (inchangés)
    # ------------------------------------------------------------------
    @safe_slot("Unknown._on_intranet")
    def _on_intranet(self) -> None:
        email = self._edt_i_email.text().strip()
        pwd = self._edt_i_pass.text()
        if not email or not pwd:
            self._show_error(_("login.error.required"))
            return
        if not self._check_email_module(email):
            return
        self._hide_error()
        self._set_busy(True)
        self._worker = _Worker(self._connect_then_auth_intranet, email, pwd, parent=self)
        self._worker.done.connect(lambda r: self._on_auth_done(r, ConnMode.INTRANET))
        self._worker.start()

    @staticmethod
    def _connect_then_auth_intranet(email: str, pwd: str):
        if not db.connect_intranet():
            return (False, AuthResult(), "Connexion à l'intranet impossible (vérifier le réseau).")
        return AuthManager.auth_intranet(email, pwd)

    @safe_slot("Unknown._on_cloud")
    def _on_cloud(self) -> None:
        self._hide_error()
        self._set_busy(True)
        self._worker = _Worker(self._connect_then_auth_cloud, parent=self)
        self._worker.done.connect(lambda r: self._on_auth_done(r, ConnMode.CLOUD))
        self._worker.start()

    @staticmethod
    def _connect_then_auth_cloud():
        if not db.connect_cloud():
            return (
                False,
                AuthResult(),
                "Connexion au cloud impossible (vérifier l'accès internet).",
            )
        return OAuth2Manager.authenticate()

    def _check_email_module(self, email: str) -> bool:
        try:
            conn = db.local_conn
            if conn is None:
                self._show_error(
                    "Aucune base locale. Créez d'abord une instance "
                    'via l\'onglet "Nouvelle instance" ou le mode 4.'
                )
                return False
            cur = conn.cursor()
            cur.execute("SELECT email_professeur FROM module_config WHERE id = 1")
            row = cur.fetchone()
            if not row or not row[0]:
                self._show_error(
                    "Module non instancié. Créez d'abord une instance "
                    'via l\'onglet "Nouvelle instance" ou le mode 4.'
                )
                return False
            if row[0].lower() != email.lower():
                self._show_error(
                    f"Cette instance est liée à {row[0]}. "
                    f"Connectez-vous avec ce compte ou créez votre propre instance."
                )
                return False
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self._show_error(
                "Erreur de lecture du module. Créez une nouvelle instance "
                'via l\'onglet "Nouvelle instance" ou le mode 4.'
            )
            return False
        return True

    @safe_slot("Unknown._on_pin")
    def _on_pin(self) -> None:
        email = self._edt_p_email.text().strip()
        pin = self._edt_p_pin.text()
        if not email or not pin:
            self._show_error("Veuillez saisir votre email et votre PIN.")
            return
        if not sqlite_init.init():
            self._show_error("Impossible d'initialiser la base locale.")
            return
        if not self._check_email_module(email):
            return

        # Rate limiting PIN : 5 tentatives max, puis verrouillage 15 min
        conn = db.local_conn
        if conn:
            row = conn.execute(
                "SELECT pin_attempts, pin_locked_until FROM session_cache "
                "WHERE LOWER(email) = LOWER(?)",
                (email,)
            ).fetchone()
            if row:
                locked_until = row['pin_locked_until']
                if locked_until:
                    from datetime import datetime
                    if datetime.now().isoformat() < locked_until:
                        self._show_error(
                            "Trop de tentatives. Reessayez dans 15 minutes."
                        )
                        return

        self._hide_error()
        self._set_busy(True)
        self._worker = _Worker(AuthManager.auth_pin, email, pin, db.local_conn, parent=self)
        self._worker.done.connect(lambda r: self._on_auth_done(r, ConnMode.OFFLINE, email))
        self._worker.start()

    @safe_slot("LoginWindow._on_auth_done")
    def _on_auth_done(self, result, mode: ConnMode, email: str = '') -> None:
        self._set_busy(False)
        ok, res, err = result

        # PIN rate limiting : suivre les tentatives echouees
        if mode == ConnMode.OFFLINE and email:
            conn = db.local_conn
            if conn and not ok:
                from datetime import datetime, timedelta
                row = conn.execute(
                    "SELECT pin_attempts FROM session_cache WHERE LOWER(email) = LOWER(?)",
                    (email,)
                ).fetchone()
                if row:
                    attempts = (row['pin_attempts'] or 0) + 1
                    if attempts >= 5:
                        locked_until = (datetime.now() + timedelta(minutes=15)).isoformat()
                        conn.execute(
                            "UPDATE session_cache SET pin_attempts = ?, pin_locked_until = ? "
                            "WHERE LOWER(email) = LOWER(?)",
                            (attempts, locked_until, email)
                        )
                        conn.commit()
                        self._show_error("Trop de tentatives. Compte verrouille 15 minutes.")
                        return
                    else:
                        conn.execute(
                            "UPDATE session_cache SET pin_attempts = ? "
                            "WHERE LOWER(email) = LOWER(?)",
                            (attempts, email)
                        )
                        conn.commit()
            elif conn and ok:
                conn.execute(
                    "UPDATE session_cache SET pin_attempts = 0, pin_locked_until = NULL "
                    "WHERE LOWER(email) = LOWER(?)",
                    (email,)
                )
                conn.commit()

        if not ok:
            self._show_error(err or _("login.error.auth_failed"))
            return

        if mode in (ConnMode.INTRANET, ConnMode.CLOUD):
            exists, infos = AuthManager.check_teacher_exists(res.email)
            if not exists:
                self._show_error("Ce compte n'est pas un professeur actif.")
                return
            res.user_id = infos["user_id"]
            res.full_name = f"{infos['first_name']} {infos['last_name']}"
            res.term_id = infos["trimestre_courant"]
            res.term_label = infos["trimestre_label"]

            if not sqlite_init.init():
                self._show_error("Impossible d'initialiser la base locale.")
                return
            sqlite_init.init_module_config(
                annee_scolaire=infos["annee_scolaire"],
                trimestre_courant=infos["trimestre_courant"],
                nom_professeur=res.full_name,
                email_professeur=res.email,
            )
            self._apply_session(res, mode)
            return

        if mode == ConnMode.OFFLINE and db.server_conn is not None:
            exists, infos = AuthManager.check_teacher_exists(res.email)
            if not exists:
                self._show_error("Ce compte n'est pas un professeur actif.")
                return
            res.user_id = infos["user_id"]
            res.full_name = f"{infos['first_name']} {infos['last_name']}"
            res.term_id = infos["trimestre_courant"]
            res.term_label = infos["trimestre_label"]

            if not sqlite_init.init():
                self._show_error("Impossible d'initialiser la base locale.")
                return
            sqlite_init.init_module_config(
                annee_scolaire=infos["annee_scolaire"],
                trimestre_courant=infos["trimestre_courant"],
                nom_professeur=res.full_name,
                email_professeur=res.email,
            )
            self._show_confirmation_dialog(res, mode, infos)
            return

        if mode == ConnMode.OFFLINE and db.server_conn is None:
            if not sqlite_init.init():
                self._show_error("Impossible d'initialiser la base locale.")
                return
            sqlite_init.init_module_config(
                annee_scolaire="",
                trimestre_courant=res.term_id,
                nom_professeur=res.full_name,
                email_professeur=res.email,
            )

        if mode == ConnMode.OFFLINE and db.server_conn is not None:
            if not sqlite_init.init():
                self._show_error("Impossible d'initialiser la base locale.")
                return
            sqlite_init.init_module_config(
                annee_scolaire=infos["annee_scolaire"],
                trimestre_courant=infos["trimestre_courant"],
                nom_professeur=res.full_name,
                email_professeur=res.email,
            )
            self._show_confirmation_dialog(res, mode, infos)
            return

        self._apply_session(res, mode)

    def _show_confirmation_dialog(self, res: AuthResult, mode: ConnMode, infos: dict) -> None:
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

        dlg = QDialog(self)
        dlg.setWindowTitle("Confirmation")
        dlg.setMinimumWidth(ds.golden_width(ds.sidebar_width))  # 377px
        layout = QVBoxLayout(dlg)

        msg = QLabel(
            "Les étapes suivantes vont être exécutées :\n\n"
            "1. Initialisation de la base locale SQLite\n"
            "2. Téléchargement des données du professeur\n"
            "3. Sauvegarde de la session\n\n"
            "Veuillez patienter quelques minutes.\n"
            "L'interface peut sembler figée pendant l'opération."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(lambda *a: self._execute_steps(res, mode, dlg, infos))
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        dlg.exec()

    def _execute_steps(self, res: AuthResult, mode: ConnMode, dlg, infos: dict) -> None:
        if dlg is not None:
            dlg.accept()
        self._set_busy(True)
        self._log("Début du téléchargement des données du professeur…")
        self._log(
            f"Infos reçues : user_id={infos.get('user_id')}, trimestre={infos.get('trimestre_courant')}"
        )
        QApplication.processEvents()

        if not sqlite_init.init():
            self._show_error("Impossible d'initialiser la base locale.")
            self._set_busy(False)
            return

        self._temp_conn = db.local_conn
        self._show_spinner(True)
        QApplication.processEvents()

        try:
            ok, err_msg = sqlite_init.take_teacher_data(infos, self._log, self._temp_conn, None)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self._log(f"Exception dans take_teacher_data : {e}")
            self._show_spinner(False)
            self._set_busy(False)
            self._temp_conn = None
            self._show_error(f"Erreur lors du téléchargement : {e}")
            return

        self._show_spinner(False)
        self._set_busy(False)
        self._temp_conn = None

        self._log(f"Résultat du téléchargement : ok={ok}, msg={err_msg}")
        if not ok:
            self._show_error(f"Échec du téléchargement des données du professeur : {err_msg}")
            return
        self._log("Téléchargement terminé avec succès.")
        try:
            conn = db.local_conn
            if conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM larcauth_evaluation")
                count_eval = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM larcauth_learnerpei_has_termsubjectpei")
                count_pei = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM larcauth_learnerdp_has_termsubjectdp")
                count_dp = cur.fetchone()[0]
                self._log(
                    f"Comptes après téléchargement : eval={count_eval}, pei={count_pei}, dp={count_dp}"
                )
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self._log(f"Erreur lors de la vérification des comptes : {e}")
        self._apply_session(res, mode)

    def _apply_session(self, res: AuthResult, mode: ConnMode) -> None:
        session.user_id = res.user_id
        session.email = res.email
        session.full_name = res.full_name
        session.role = res.role
        session.term_id = res.term_id
        session.term_label = res.term_label
        session.conn_mode = mode
        session.is_authenticated = True
        # Charger tous les flags de roles depuis le serveur
        session.load_role_flags()

        if mode == ConnMode.INTRANET:
            self._update_indicators(True, False)
        elif mode == ConnMode.CLOUD:
            self._update_indicators(False, True)
        else:
            self._update_indicators(False, False)

        sqlite_init.init()

        local_email = None
        try:
            conn = db.local_conn
            if conn:
                cur = conn.cursor()
                cur.execute("SELECT email_professeur FROM module_config WHERE id = 1")
                row = cur.fetchone()
                if row:
                    local_email = row[0]
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self._log(f"Erreur lors de la lecture du module local : {e}")

        skip_pin = local_email is not None and local_email.lower() == res.email.lower()

        if mode in (ConnMode.INTRANET, ConnMode.CLOUD) and not skip_pin:
            pin, ok = self._ask_pin_setup(res.full_name)
            sqlite_init.save_session(res, pin if ok else "")
        else:
            sqlite_init.save_session(res)

        self._update_status_bar(res, mode)
        self._open_main_window(res)

    def _ask_pin_setup(self, name: str):
        from PySide6.QtWidgets import QInputDialog

        return QInputDialog.getText(
            self,
            "PIN hors connexion",
            f"Définissez un PIN pour {name} (laisser vide pour ignorer) :",
            QLineEdit.Password,
        )
