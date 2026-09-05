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
from larccommon.safe_slot import set_debug


def main() -> None:
    if not db.is_server_connected:
        return
    set_debug(True)
    init_app('LarcCompta')  # télémétrie : excepthook + error_log
    app = QApplication(sys.argv)
    app.setApplicationName("LarcScolarite")
    app.setOrganizationName("LarcSpace")
    app.setFont(QFont("Segoe UI", 10))

    from larccommon.l10n import Translator
    lang = os.environ.get("LARC_LANG", "fr")
    Translator.instance(lang).load_dir(Translator.l10n_dir())

    from larccommon.database import db
    from larccommon.session import session, ConnMode, UserRole

    db.connect_intranet()
    if not db.server_conn:
        db.connect_cloud()

    def _check_access(email):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return None
        cur = conn.cursor()
        cur.execute(
            "SELECT aec.id, aec.last_name, aec.first_name "
            "FROM larcauth_aecuser aec "
            "WHERE LOWER(aec.email) = %s AND aec.is_active = TRUE "
            "AND (aec.type_secretary = TRUE OR aec.type_director = TRUE) "
            "LIMIT 1",
            (email.lower().strip(),),
        )
        return cur.fetchone()

    def on_intranet_login(email, password):
        from larccommon.auth import AuthManager
        result = AuthManager.auth_intranet(email, password)
        ok, res, err = result
        if not ok:
            return (False, None, err)
        row = _check_access(res.email)
        if not row:
            return (False, None, "Acces reserve aux secretaires et directeurs.")
        res.user_id = row[0]
        res.full_name = f"{row[1]} {row[2]}"
        session.user_id = res.user_id
        session.email = res.email
        session.full_name = res.full_name
        session.role = UserRole.SECR
        session.conn_mode = ConnMode.INTRANET
        session.is_authenticated = True
        return (True, res, "")

    def on_cloud_login():
        from larccommon.auth import AuthManager
        result = AuthManager.auth_cloud()
        ok, res, err = result
        if not ok:
            return (False, None, err)
        row = _check_access(res.email)
        if not row:
            return (False, None, "Acces reserve aux secretaires et directeurs.")
        res.user_id = row[0]
        res.full_name = f"{row[1]} {row[2]}"
        session.user_id = res.user_id
        session.email = res.email
        session.full_name = res.full_name
        session.role = UserRole.SECR
        session.conn_mode = ConnMode.CLOUD
        session.is_authenticated = True
        return (True, res, "")

    def on_success():
        from LarcCompta.views.main_window import MainWindow
        window = MainWindow()
        window.showMaximized()

    from larccommon.login import LoginWindow
    login = LoginWindow(
        on_success=on_success,
        title_prefix="LarcScolarite",
        subtitle="Scolarite & Frais",
        on_intranet_login=on_intranet_login,
        on_cloud_login=on_cloud_login,
    )
    login.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
