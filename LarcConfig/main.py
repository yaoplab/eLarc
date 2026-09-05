"""Point d'entrée LarcConfig."""
import os
import sys
from PySide6.QtWidgets import QApplication
from larccommon.bootstrap import init_app
from larccommon.l10n import Translator
from larccommon.logger import log_error
from larccommon.safe_slot import set_debug
from larccommon.session import ConnMode, session
from larccommon.theme import theme_manager
from LarcConfig.views.login import LoginWindow


def _on_intranet_login(email, password):
    from larccommon.auth import AuthManager
    ok, res, err = AuthManager.auth_intranet(email, password)
    if not ok:
        return (False, None, err)
    session.user_id = res.user_id
    session.email = res.email
    session.full_name = res.full_name
    session.role = res.role
    session.conn_mode = ConnMode.INTRANET
    session.is_authenticated = True
    _refresh_audit_context()
    return (True, res, "")


def _on_cloud_login():
    from larccommon.auth import OAuth2Manager
    ok, res, err = OAuth2Manager.authenticate()
    if not ok:
        return (False, None, err)
    session.user_id = res.user_id
    session.email = res.email
    session.full_name = res.full_name
    session.role = res.role
    session.conn_mode = ConnMode.CLOUD
    session.is_authenticated = True
    _refresh_audit_context()
    return (True, res, "")


def _refresh_audit_context():
    """Attribution d'audit (qui fait quoi) après le login."""
    try:
        from larccommon.audit_context import refresh
        from larccommon.database import db
        refresh()
        db._apply_session_vars()
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"refresh audit context: {e}")


def main():
    set_debug(True)  # Dev: affiche les erreurs dans les slots
    init_app('LarcConfig')  # télémétrie : excepthook + error_log
    lang = os.environ.get('LARC_LANG', 'fr')
    Translator.instance(lang).load_dir(Translator.l10n_dir())
    app = QApplication(sys.argv)
    app.setApplicationName('LarcConfig')
    app.setOrganizationName('Arc-en-Ciel')
    app.setStyle('Fusion')
    theme_manager.bind(app)  # réactivité thème (skill theme-reactivity)
    win = LoginWindow(
        title_prefix="LarcConfig",
        on_intranet_login=_on_intranet_login,
        on_cloud_login=_on_cloud_login,
    )
    win.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
