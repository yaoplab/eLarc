"""Log du daemon."""
import logging
from .config import load

def setup(name='sync_daemon') -> logging.Logger:
    cfg = load()
    log = logging.getLogger(name)
    log.setLevel(logging.INFO)
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    fh = logging.FileHandler(cfg.get('log_file', 'sync_daemon.log'), encoding='utf-8')
    fh.setFormatter(fmt)
    log.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(sh)
    return log

log = setup()
