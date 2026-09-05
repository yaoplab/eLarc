import os
import sys

_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

_larc_common = os.path.normpath(os.path.join(_root, "LarcCommon"))
if os.path.isdir(_larc_common) and _larc_common not in sys.path:
    sys.path.insert(0, _larc_common)

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from larccommon.bootstrap import init_app
from larccommon.l10n import _
from larccommon.safe_slot import set_debug


def main() -> None:
    if not db.is_server_connected:
        return
    set_debug(True)
    init_app('LarcRH')  # télémétrie : excepthook + error_log
    app = QApplication(sys.argv)
    app.setApplicationName("LarcRH")
    app.setOrganizationName("LarcSpace")
    app.setFont(QFont("Segoe UI", 10))

    from larccommon.l10n import Translator
    lang = os.environ.get("LARC_LANG", "fr")
    Translator.instance(lang).load_dir(Translator.l10n_dir())

    # Garde-molette (input-ergonomics IE1/IE2) : la molette ne change un
    # spin/combo/date que s'il a le focus — jamais au survol pendant le scroll.
    from larccommon.ergonomics import install_wheel_guard
    install_wheel_guard(app)

    # Thème global + boîtes de dialogue aux boutons TOUJOURS visibles
    # (les QMessageBox natifs Windows ignorent le QSS — OK blanc sur blanc).
    from larccommon.theme import theme_manager
    theme_manager.bind(app)
    from larccommon.msgbox import patch_message_boxes
    patch_message_boxes()

    from larccommon.database import db
    from larccommon.session import session, ConnMode, UserRole

    db.connect_intranet()
    if not db.server_conn:
        db.connect_cloud()

    def _check_rh_access(email):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return None
        cur = conn.cursor()
        cur.execute("""
            SELECT aec.id, aec.last_name, aec.first_name,
                   aec.type_secretary, aec.type_director,
                   COALESCE(s.type_DRH, FALSE),
                   COALESCE(s.type_ressources_Humaines, FALSE)
            FROM larcauth_aecuser aec
            LEFT JOIN larcauth_staff s ON s.aecuser_ptr_id = aec.id
            WHERE LOWER(aec.email) = %s AND aec.is_active = TRUE
            AND (aec.type_secretary = TRUE OR aec.type_director = TRUE
                 OR s.type_DRH = TRUE OR s.type_ressources_Humaines = TRUE)
            LIMIT 1
        """, (email.lower().strip(),))
        return cur.fetchone()

    def on_intranet_login(email, password):
        from larccommon.auth import AuthManager
        result = AuthManager.auth_intranet(email, password)
        ok, res, err = result
        if not ok:
            return (False, None, err)
        row = _check_rh_access(res.email)
        if not row:
            return (False, None, "Accès réservé aux personnels RH, secrétaires et directeurs.")
        res.user_id = row[0]
        res.full_name = f"{row[1]} {row[2]}"
        session.user_id = res.user_id
        session.email = res.email
        session.full_name = res.full_name
        session.role = UserRole.SECR if row[3] else UserRole.ADMIN
        session.conn_mode = ConnMode.INTRANET
        session.is_authenticated = True
        return (True, res, "")

    def on_cloud_login():
        from larccommon.auth import AuthManager
        result = AuthManager.auth_cloud()
        ok, res, err = result
        if not ok:
            return (False, None, err)
        row = _check_rh_access(res.email)
        if not row:
            return (False, None, "Accès réservé aux personnels RH, secrétaires et directeurs.")
        res.user_id = row[0]
        res.full_name = f"{row[1]} {row[2]}"
        session.user_id = res.user_id
        session.email = res.email
        session.full_name = res.full_name
        session.role = UserRole.SECR if row[3] else UserRole.ADMIN
        session.conn_mode = ConnMode.CLOUD
        session.is_authenticated = True
        return (True, res, "")

    def on_success():
        from LarcRH.views.main_window import MainWindow
        window = MainWindow()
        window.showMaximized()

        # Déconnexion automatique après 10 min d'inactivité (souris/clavier)
        from larccommon.idle_timer import IdleGuard
        idle = IdleGuard(minutes=10)

        def _on_idle_timeout():
            window.close()
            idle.stop()
            session.is_authenticated = False
            from LarcRH.common.hr_database import HRDatabase
            HRDatabase.set_session_offline(session.user_id or 0)
            login.clear_fields()
            login.show()

        idle.idle_timeout.connect(_on_idle_timeout)
        idle.start()

    from larccommon.login import LoginWindow
    login = LoginWindow(
        on_success=on_success,
        title_prefix="LarcRH",
        subtitle="Ressources Humaines",
        on_intranet_login=on_intranet_login,
        on_cloud_login=on_cloud_login,
    )
    login.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
