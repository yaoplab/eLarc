"""Updater détaché — applique la mise à jour douce (R3).

Lancé en détaché par l'app : attend l'extinction du processus parent,
vérifie les verrous runtime/locks/*.pid (DLL PySide6 chargées bloquent le
pull sur Windows), git fetch + pull --ff-only (retry ×3), journalise le
résultat dans error_log (R1), puis relance l'app avec ses argv d'origine.

Usage : python LarcCommon/scripts/update_app.py <pid_parent>
"""
import json
import os
import subprocess
import sys
import time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LARCCOMMON_ROOT = os.path.normpath(os.path.join(_SCRIPT_DIR, '..'))
MONOREPO = os.path.normpath(os.path.join(LARCCOMMON_ROOT, '..'))
PENDING_FILE = os.path.join(LARCCOMMON_ROOT, 'runtime', 'pending_update.json')
LOCK_DIR = os.path.join(LARCCOMMON_ROOT, 'runtime', 'locks')


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        return False


def _locks_clear() -> bool:
    """Aucun verrou d'app vivant → le pull peut remplacer les fichiers."""
    if not os.path.isdir(LOCK_DIR):
        return True
    for name in os.listdir(LOCK_DIR):
        if not name.endswith('.pid'):
            continue
        try:
            with open(os.path.join(LOCK_DIR, name), encoding='utf-8') as f:
                pid = int(f.read().strip() or '0')
            if pid and _pid_alive(pid):
                return False
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            continue
    return True


def _report(app_name: str, message: str) -> None:
    """Journalise dans error_log (best-effort, R1) — succès ET échec."""
    try:
        sys.path.insert(0, LARCCOMMON_ROOT)
        from larccommon.error_reporting import ErrorReporter
        rep = ErrorReporter(app_name, '', {'Enabled': 'true'})
        rep.report('ERROR', message)
        rep.flush(timeout=2.0)
        rep.stop()
    except Exception:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        pass


def _git_pull() -> tuple[bool, str]:
    last = ''
    for attempt in range(3):
        try:
            r = subprocess.run(['git', '-C', MONOREPO, 'fetch', 'origin'],
                               capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                last = f"fetch: {(r.stderr or r.stdout).strip()[:200]}"
                time.sleep(2)
                continue
            r = subprocess.run(['git', '-C', MONOREPO, 'pull', '--ff-only'],
                               capture_output=True, text=True, timeout=180)
            if r.returncode == 0:
                return True, 'pull réussi'
            last = f"pull: {(r.stderr or r.stdout).strip()[:200]}"
            time.sleep(2)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            last = str(e)[:200]
            time.sleep(2)
    return False, last


def main() -> int:
    parent_pid = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    # 1. Attendre l'extinction de l'app parent (max 120 s)
    if parent_pid:
        for _ in range(120):
            if not _pid_alive(parent_pid):
                break
            time.sleep(1)

    # 2. Attendre la libération des verrous (max 10 s)
    for _ in range(10):
        if _locks_clear():
            break
        time.sleep(1)
    if not _locks_clear():
        _report('LarcUpdate', 'mise à jour : verrous d\'apps toujours actifs')
        return 2

    # 3. Lire l'état persistant puis pull
    pending = {}
    try:
        with open(PENDING_FILE, encoding='utf-8') as f:
            pending = json.load(f)
    except Exception:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        pass

    ok, msg = _git_pull()
    if not ok:
        _report('LarcUpdate', f'mise à jour échouée : {msg}')
        return 3

    _report('LarcUpdate', f"mise à jour appliquée ({pending.get('target', '?')})")
    try:
        os.remove(PENDING_FILE)
    except Exception:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        pass

    # 4. Relancer l'app avec ses argv d'origine
    main_path = pending.get('main') or ''
    argv = pending.get('argv') or []
    if main_path and os.path.isfile(main_path):
        subprocess.Popen([sys.executable, main_path] + argv,
                         cwd=os.path.dirname(main_path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
