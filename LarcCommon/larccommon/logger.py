import os
from datetime import datetime

LOG_TO_FILE = True

LOG_FILENAME = 'superviseur.log'

# Rotation : au-delà de 5 Mo, rotation .1/.2/.3 (elarc.log atteignait 92 Mo)
_MAX_BYTES = 5 * 1024 * 1024
_KEEP = 3

_LOG_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', LOG_FILENAME
))


def log(msg: str, level: str = "INFO", exc: BaseException | None = None) -> None:
    """Log fichier plat (rétro-compatible) + remontée au reporter pour
    ERROR/CRITICAL. Ne lève jamais."""
    if LOG_TO_FILE:
        try:
            _rotate_if_needed()
            with open(_LOG_PATH, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{timestamp}] {msg}\n")
        except Exception:
            log('erreur ignoree')
            pass
    if level in ("ERROR", "CRITICAL"):
        _report(msg, level, exc)


def log_error(msg: str, exc: BaseException | None = None) -> None:
    """Alias : log(msg, 'ERROR', exc) — remonte aussi vers error_log."""
    log(msg, "ERROR", exc)


def _report(msg: str, level: str, exc: BaseException | None) -> None:
    try:
        from .error_reporting import get_reporter
        rep = get_reporter()
        if rep is None:
            return
        tb = ''
        if exc is not None:
            import traceback
            tb = ''.join(traceback.format_exception(
                type(exc), exc, exc.__traceback__))
        rep.report(level, str(msg), traceback=tb)
    except Exception:
        log('erreur ignoree')
        pass


def _rotate_if_needed() -> None:
    if not os.path.isfile(_LOG_PATH):
        return
    try:
        if os.path.getsize(_LOG_PATH) <= _MAX_BYTES:
            return
        for i in range(_KEEP - 1, 0, -1):
            src = f"{_LOG_PATH}.{i}"
            dst = f"{_LOG_PATH}.{i + 1}"
            if os.path.isfile(src):
                os.replace(src, dst)
        os.replace(_LOG_PATH, f"{_LOG_PATH}.1")
    except Exception:
        log('erreur ignoree')
        pass


def set_log_to_file(value: bool) -> None:
    global LOG_TO_FILE
    LOG_TO_FILE = value


def get_log_path() -> str:
    return _LOG_PATH


def set_log_filename(name: str) -> None:
    global _LOG_PATH, LOG_FILENAME
    LOG_FILENAME = name
    _LOG_PATH = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', name
    ))
