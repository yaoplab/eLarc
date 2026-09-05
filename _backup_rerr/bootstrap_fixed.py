"""Bootstrap commun des apps LARC — télémétrie (R1) + mise à jour douce (R3).

Usage dans chaque main.py (APRÈS set_debug, AVANT QApplication) :
    from larccommon.bootstrap import init_app
    init_app('LarcSuperviseur')
"""
import atexit
import os
import sys
import threading
import traceback
from typing import Optional

from .error_reporting import ErrorReporter, _set_reporter, get_reporter
from .logger import log as _log

_APP_NAME = 'LarcApp'
_inited = False

# Verrou de processus (R3) : les DLL PySide6/psycopg2 chargées empêchent le
# remplacement de fichiers pendant un git pull sur Windows.
_LOCK_PATH: Optional[str] = None


# -- version -----------------------------------------------------------
def current_app_version() -> str:
    """Version locale : D:\\projets\\VERSION, fallback config.ini [App] Version."""
    try:
        version_path = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', '..', 'VERSION'))
        if os.path.isfile(version_path):
            with open(version_path, encoding='utf-8') as f:
                return f.read().strip() or ''
    except Exception:
        get_reporter().report_exception()
        pass
    try:
        import configparser
        from .config_loader import find_cfg
        cfg = configparser.ConfigParser()
        cfg.read(find_cfg())
        return cfg.get('App', 'Version', fallback='')
    except Exception:
        get_reporter().report_exception()
        return ''


# -- capture des exceptions --------------------------------------------
def install_excepthooks() -> None:
    """sys.excepthook + threading.excepthook → reporter + stderr. Jamais de raise."""

    def _sys_hook(exc_type, exc_value, exc_tb):
        _report_from_hook(exc_value, exc_tb, 'sys.excepthook')
        try:
            traceback.print_exception(exc_type, exc_value, exc_tb)
        except Exception:
            get_reporter().report_exception()
            pass

    def _thread_hook(args):
        _report_from_hook(args.exc_value, args.exc_traceback,
                          'threading.excepthook')
        try:
            traceback.print_exception(args.exc_type, args.exc_value,
                                      args.exc_traceback)
        except Exception:
            get_reporter().report_exception()
            pass

    sys.excepthook = _sys_hook
    threading.excepthook = _thread_hook


def _report_from_hook(exc_value, exc_tb, hook_name: str) -> None:
    rep = get_reporter()
    if rep is None:
        return
    try:
        rep.report_exception(exc_value, exc_tb, context={'hook': hook_name})
    except Exception:
        get_reporter().report_exception()
        pass


# -- capture des messages Qt -------------------------------------------
_qt_handler_installed = False
_old_qt_handler = None


def install_qt_message_handler() -> None:
    global _qt_handler_installed, _old_qt_handler
    if _qt_handler_installed:
        return
    try:
        from PySide6 import QtCore
        _old_qt_handler = QtCore.qInstallMessageHandler(_qt_handler)
        _qt_handler_installed = True
    except Exception:
        get_reporter().report_exception()
        pass


def _qt_handler(mode, context, message):
    try:
        from PySide6 import QtCore
        rep = get_reporter()
        level = {QtCore.QtMsgType.QtCriticalMsg: 'ERROR',
                 QtCore.QtMsgType.QtFatalMsg: 'CRITICAL'}.get(mode)
        if level is not None and rep is not None:
            rep.report(level, str(message), module='qt',
                       context={'file': getattr(context, 'file', '') or '',
                                'line': getattr(context, 'line', 0) or 0})
        if mode == QtCore.QtMsgType.QtFatalMsg:
            # Ne jamais avaler un crash fatal : rappeler l'ancien handler.
            if _old_qt_handler is not None:
                _old_qt_handler(mode, context, message)
    except Exception:
        get_reporter().report_exception()
        pass


# -- verrou de processus (R3) -------------------------------------------
def _create_lock() -> None:
    global _LOCK_PATH
    if _LOCK_PATH is not None:
        return
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        lock_dir = os.path.join(root, 'runtime', 'locks')
        os.makedirs(lock_dir, exist_ok=True)
        _LOCK_PATH = os.path.join(lock_dir, f"{_APP_NAME}.pid")
        with open(_LOCK_PATH, 'w', encoding='utf-8') as f:
            f.write(str(os.getpid()))
        atexit.register(_remove_lock)
    except Exception:
        get_reporter().report_exception()
        pass


def _remove_lock() -> None:
    global _LOCK_PATH
    if _LOCK_PATH is not None:
        try:
            os.remove(_LOCK_PATH)
        except Exception:
            get_reporter().report_exception()
            pass
        _LOCK_PATH = None


# -- point d'entrée -----------------------------------------------------
def init_app(app_name: str, *, qt: bool = True,
             check_updates: bool = True,
             config: Optional[dict] = None) -> Optional[ErrorReporter]:
    """Initialise la télémétrie d'une app. À appeler dans chaque main.py
    APRÈS set_debug(...) et AVANT QApplication. Idempotent."""
    global _APP_NAME, _inited
    _APP_NAME = app_name

    rep = get_reporter()
    if rep is None:
        cfg = config or _load_error_reporting_cfg()
        rep = ErrorReporter(app_name, current_app_version(), cfg)
        rep.start()
        _set_reporter(rep)
        try:
            _log(f"init_app: télémétrie active ({app_name})")
        except Exception:
            get_reporter().report_exception()
            pass

    install_excepthooks()
    if qt:
        install_qt_message_handler()
    _create_lock()

    if check_updates:
        try:
            from .update_manager import schedule_update_check
            schedule_update_check()  # no-op silencieux si R3 désactivé
        except Exception:
            get_reporter().report_exception()
            pass  # R3 pas encore installé — dégradation silencieuse

    _inited = True
    return rep


def _load_error_reporting_cfg() -> dict:
    try:
        import configparser
        from .config_loader import find_cfg
        cfg = configparser.ConfigParser()
        cfg.read(find_cfg())
        if cfg.has_section('ErrorReporting'):
            return dict(cfg['ErrorReporting'])
    except Exception:
        get_reporter().report_exception()
        pass
    return {}


# -- R3 (Phase 3) --------------------------------------------------------
def _monorepo_root() -> str:
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', '..'))


def _load_update_cfg() -> dict:
    try:
        import configparser
        from .config_loader import find_cfg
        cfg = configparser.ConfigParser()
        cfg.read(find_cfg())
        if cfg.has_section('Update'):
            return dict(cfg['Update'])
    except Exception:
        get_reporter().report_exception()
        pass
    return {}


def _launch_updater() -> None:
    """Lance l'updater détaché — il attendra l'extinction de ce processus."""
    try:
        import subprocess
        script = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'scripts',
            'update_app.py'))
        subprocess.Popen([sys.executable, script, str(os.getpid())])
    except Exception:
        get_reporter().report_exception()
        pass


_UPDATE_TIMER = None  # garde la référence du QTimer périodique


def arm_update_on_quit(app) -> None:
    """Arme la mise à jour douce (R3) — à appeler APRÈS création de QApplication.

    Silencieux : applique l'update au quit, aucun dialogue.
    Informé : dialogue après 2 s (seulement si l'app est au repos), puis
    périodiquement (CheckIntervalMin).
    """
    global _UPDATE_TIMER
    try:
        from .update_manager import UpdateManager
        mgr = UpdateManager(_APP_NAME, current_app_version(),
                            config=_load_update_cfg())
        if not mgr.enabled():
            return
        main_path = os.path.join(_monorepo_root(), _APP_NAME, 'main.py')

        def _apply_and_quit():
            info = mgr.check()
            if info is None:
                return
            if mgr.apply(info, main_path, list(sys.argv[1:])):
                _launch_updater()
                app.quit()

        if mgr.silent():
            def _on_quit():
                try:
                    if mgr.should_apply_on_quit():
                        _apply_and_quit()
                except Exception:
                    get_reporter().report_exception()
                    pass
            app.aboutToQuit.connect(_on_quit)
            return

        # Mode informé
        from PySide6.QtCore import QTimer
        from .widgets.update_dialog import UpdateDialog

        def _offer():
            try:
                if app.activeModalWidget() is not None:
                    return  # app occupée — la prochaine tick retentera
                info = mgr.check()
                if info is None:
                    return
                dlg = UpdateDialog(info, None, parent=app.activeWindow())
                if dlg.exec() and dlg.result_choice() == 'install':
                    _apply_and_quit()
            except Exception:
                get_reporter().report_exception()
                pass

        QTimer.singleShot(2000, _offer)
        _UPDATE_TIMER = QTimer()
        _UPDATE_TIMER.timeout.connect(_offer)
        _UPDATE_TIMER.start(mgr.check_interval_min() * 60000)
    except Exception:
        get_reporter().report_exception()
        pass
