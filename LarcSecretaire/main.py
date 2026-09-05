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


def _ensure_student_parent(conn) -> None:
    """Cree la table larcauth_student_parent si elle n'existe pas."""
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS larcauth_student_parent (
                id            SERIAL PRIMARY KEY,
                student_id    INTEGER NOT NULL,
                parent_id     INTEGER NOT NULL,
                nature        TEXT,
                is_emergency  BOOLEAN NOT NULL DEFAULT FALSE,
                is_authorized BOOLEAN NOT NULL DEFAULT TRUE,
                updated_at    TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (student_id, parent_id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_student_parent_student ON larcauth_student_parent(student_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_student_parent_parent  ON larcauth_student_parent(parent_id)")
    except Exception:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        pass


def main() -> None:
    import faulthandler, time
    faulthandler.enable()
    time.sleep(0.05)  # laisser Windows initialiser COM

    set_debug(True)  # Dev: affiche les erreurs dans les slots
    init_app('LarcSecretaire')  # télémétrie : excepthook + error_log
    app = QApplication(sys.argv)
    app.setApplicationName("LarcSecretaire")
    app.setOrganizationName("LarcSpace")
    app.setFont(QFont("Segoe UI", 10))

    from larccommon.l10n import Translator
    lang = os.environ.get("LARC_LANG", "fr")
    Translator.instance(lang).load_dir(Translator.l10n_dir())

    from LarcSecretaire.common.database import db, DBMode
    from LarcSecretaire.common.logger import log
    from LarcSecretaire.common.app_config import app_config
    from LarcSecretaire.common.sqlite_init import sqlite_init
    from LarcSecretaire.common.auth import AuthManager
    from LarcSecretaire.common.session import session, ConnMode, UserRole
    from LarcSecretaire.common.audit import audit

    db.connect_intranet()
    if not db.server_conn:
        db.connect_cloud()
    # S'assurer que les tables applicatives existent (intranet + cloud)
    from LarcSecretaire.views.todo_panel import ensure_todo_table
    ensure_todo_table()
    # Table de jonction eleves-parents
    _ensure_student_parent(db.server_conn)
    if db.server_mode != DBMode.CLOUD:
        db.connect_cloud()
        ensure_todo_table()
        _ensure_student_parent(db.server_conn)
        db.connect_intranet()
    # S'assurer que la colonne JSONB validation existe
    _cur = db.server_conn.cursor() if db.server_conn else None
    if _cur:
        try:
            _cur.execute(
                "ALTER TABLE larcauth_student ADD COLUMN IF NOT EXISTS validation JSONB DEFAULT '{}'")
            db.server_conn.commit()
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            db.server_conn.rollback()
    sqlite_init.init()
    app_config.load()
    log("LarcSecretaire démarré")

    def _check_secretary(email):
        conn = db.server_conn
        if not conn:
            return None
        cur = conn.cursor()
        cur.execute(
            "SELECT aec.id, aec.last_name, aec.first_name "
            "FROM larcauth_aecuser aec "
            "WHERE LOWER(aec.email) = %s AND aec.type_secretary = TRUE AND aec.is_active = TRUE "
            "LIMIT 1",
            (email.lower().strip(),),
        )
        return cur.fetchone()

    def on_intranet_login(email, password):
        result = AuthManager.auth_intranet(email, password)
        ok, res, err = result
        if not ok:
            return (False, None, err)
        row = _check_secretary(res.email)
        if not row:
            return (False, None, "Ce compte n'est pas une secrétaire active.")
        res.user_id = row[0]
        res.full_name = f"{row[1]} {row[2]}"
        if not sqlite_init.init():
            return (False, None, "Impossible d'initialiser la base locale.")
        sqlite_init.set_module_config('secretary_name', res.full_name)
        sqlite_init.set_module_config('secretary_email', res.email)
        sqlite_init.set_module_config('secretary_id', str(res.user_id))
        session.user_id = res.user_id
        session.email = res.email
        session.full_name = res.full_name
        session.role = UserRole.SECR
        session.conn_mode = ConnMode.INTRANET
        audit.login(session.user_id, session.full_name, ConnMode.INTRANET.value)
        return (True, res, "")

    def on_cloud_login():
        result = AuthManager.auth_cloud()
        ok, res, err = result
        if not ok:
            return (False, None, err)
        row = _check_secretary(res.email)
        if not row:
            return (False, None, "Ce compte n'est pas une secrétaire active.")
        res.user_id = row[0]
        res.full_name = f"{row[1]} {row[2]}"
        if not sqlite_init.init():
            return (False, None, "Impossible d'initialiser la base locale.")
        sqlite_init.set_module_config('secretary_name', res.full_name)
        sqlite_init.set_module_config('secretary_email', res.email)
        sqlite_init.set_module_config('secretary_id', str(res.user_id))
        session.user_id = res.user_id
        session.email = res.email
        session.full_name = res.full_name
        session.role = UserRole.SECR
        session.conn_mode = ConnMode.CLOUD
        audit.login(session.user_id, session.full_name, ConnMode.CLOUD.value)
        return (True, res, "")

    def on_success():
        from LarcSecretaire.views.main_window import MainWindow
        window = MainWindow()
        window.showMaximized()

    from larccommon.login import LoginWindow
    login = LoginWindow(
        on_success=on_success,
        title_prefix="LarcSecrétariat",
        subtitle=_("login.subtitle.secretaire"),
        on_intranet_login=on_intranet_login,
        on_cloud_login=on_cloud_login,
    )
    login.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
