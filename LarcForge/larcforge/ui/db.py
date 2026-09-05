"""Connexions PostgreSQL de l'IHM — une connexion par opération (jamais partagée).

Les profils de connexion (profiles.DbProfile) sont des écoles : quand un
profil est fourni, ses paramètres explicitent la connexion ; sinon on retombe
sur le config.ini master (section IntranetDatabase).
"""

from __future__ import annotations

from .. import database as pg
from .profiles import DbProfile


def open_db(root, profile: DbProfile | None = None):
    """Ouvre une connexion (autocommit). Lève pg.DBUnavailable si injoignable.

    L'appelant affiche la carte « Base de données indisponible » (common).
    """
    if profile is None:
        return pg.connect(root=root)
    params = {
        "host": profile.host,
        "port": profile.port,
        "dbname": profile.dbname,
        "user": profile.user,
        "password": profile.password,
    }
    # champs vides → le config.ini fait foi (paramètres explicites
    # court-circuitent l'INI dans pg.connect)
    params = {k: v for k, v in params.items() if v}
    return pg.connect(section=profile.section or "IntranetDatabase",
                      root=root, params=params)
