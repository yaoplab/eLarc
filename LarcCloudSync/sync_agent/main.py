"""Point d'entrée du daemon de synchronisation."""
import time
import sys
from datetime import datetime

from .config import load, table_frequency
from .logger import log
from . import db, sync


def _last_check() -> dict:
    """Dernier timestamp de vérification par table."""
    return {}


def main():
    log.info("=== Démarrage du daemon LarcCloudSync ===")
    cfg = load()
    poll = cfg.get('poll_interval', 30)
    tables = list(cfg['tables'].keys())
    last_check = {t: 0.0 for t in tables}

    # Connexions initiales
    try:
        db.connect_intranet()
        log.info("Connexion Intranet établie")
    except Exception as e:
        log.error(f"Impossible de se connecter à l'Intranet : {e}")
        sys.exit(1)

    try:
        db.connect_cloud()
        log.info("Connexion Cloud établie")
    except Exception as e:
        log.error(f"Impossible de se connecter au Cloud : {e}")
        sys.exit(1)

    log.info(f"{len(tables)} table(s) à synchroniser, intervalle de scrutation {poll}s")

    while True:
        now = time.time()
        for t in tables:
            freq = table_frequency(t, cfg)  # en minutes
            if freq <= 0:
                continue
            elapsed = now - last_check.get(t, 0)
            if elapsed < freq * 60:
                continue
            log.info(f"Sync {t}...")
            try:
                result = sync.sync_table(t, freq)
                log.info(f"Sync {t} : {result}")
            except Exception as e:
                log.error(f"Sync {t} échoué : {e}")
            last_check[t] = now
        time.sleep(poll)


if __name__ == '__main__':
    main()
