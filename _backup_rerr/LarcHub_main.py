import os
import sys
import traceback

_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

for _pkg in ("LarcCommon", "LarcSuperviseur", "LarcSecretaire", "LarcRH", "LarcCompta"):
    _p = os.path.join(_root, _pkg)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from larccommon.bootstrap import init_app
from larccommon.l10n import _
from larccommon.safe_slot import set_debug


def main() -> None:
    set_debug(True)
    init_app('LarcHub')  # télémétrie : excepthook + error_log
    app = QApplication(sys.argv)
    app.setApplicationName("LarcHub")
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

    def _fetch_type_flags(user_id):
        """Charge les flags de role type_* depuis larcauth_aecuser."""
        conn = db.server_conn
        if not conn:
            return {}
        cur = conn.cursor()
        cur.execute(
            "SELECT type_director, type_coordonator, type_supervisor, "
            "type_secretary, type_teacher FROM larcauth_aecuser WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        if row:
            return {
                "director": bool(row[0]),
                "coordinator": bool(row[1]),
                "supervisor": bool(row[2]),
                "secretary": bool(row[3]),
                "teacher": bool(row[4]),
            }
        return {}

    def on_intranet_login(email, password):
        from larccommon.auth import AuthManager
        result = AuthManager.auth_intranet(email, password)
        ok, res, err = result
        if not ok:
            return (False, None, err)
        session.user_id = res.user_id
        session.email = res.email
        session.full_name = res.full_name
        session.role = res.role
        session.conn_mode = ConnMode.INTRANET
        session.is_authenticated = True
        session.type_flags = _fetch_type_flags(res.user_id)
        return (True, res, "")

    def on_cloud_login():
        from larccommon.auth import AuthManager
        result = AuthManager.auth_cloud()
        ok, res, err = result
        if not ok:
            return (False, None, err)
        session.user_id = res.user_id
        session.email = res.email
        session.full_name = res.full_name
        session.role = res.role
        session.conn_mode = ConnMode.CLOUD
        session.is_authenticated = True
        session.type_flags = _fetch_type_flags(res.user_id)
        return (True, res, "")

    def on_success():
        from LarcHub.views.hub_window import HubWindow
        hub = HubWindow()
        hub.showMaximized()

    from larccommon.login import LoginWindow
    login = LoginWindow(
        on_success=on_success,
        title_prefix="LarcHub",
        subtitle="Supervision · Scolarité · RH · Secrétariat",
        on_intranet_login=on_intranet_login,
        on_cloud_login=on_cloud_login,
    )
    login.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
