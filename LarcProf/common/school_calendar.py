"""Lecture de l'année scolaire / trimestres / unités depuis PostgreSQL.

Même requête que LarcConfig (common/db_access.py::get_temps) — ces tables
(larcauth_academicyear/larcauth_term/larcauth_unit_period) sont partagées
par toute l'école, pas propres à LarcConfig. Nécessite une connexion
serveur active (db.server_conn) ; pas de mise en cache locale pour
l'instant, cette info est purement informationnelle (bandeau du menu
principal), pas critique pour la saisie de notes hors-ligne.
"""
from .database import db
from .logger import log


def get_temps(within_year: bool = True):
    """Année active + derniers trimestres/unités par langue (1=EN, 2=FR).

    within_year=True : ne garde que les lignes dont les dates tombent dans
    l'année active — les lignes pré-créées de l'année suivante (gabarits)
    sont ignorées. Retourne None si pas de connexion serveur ou d'erreur.
    """
    c = db.server_conn
    if not c:
        return None
    try:
        cur = c.cursor()
        cur.execute("""
            SELECT s_id, label, start_date, end_date, current_term_number,
                   "Current_unit_number"
            FROM larcauth_academicyear ORDER BY s_id DESC LIMIT 1
        """)
        r = cur.fetchone()
        if not r:
            return None
        annee = dict(zip(['s_id', 'label', 'start', 'end', 'term', 'unit'], r))
        ay_start, ay_end = annee['start'], annee['end']

        def _pick(rows, key_fn, date_fn):
            """Dernière ligne par clé (ORDER BY id DESC). Si within_year,
            préfère la ligne la plus récente dont les dates tombent dans
            l'année active ; sinon repli sur la plus récente."""
            buckets = {}
            for row in rows:
                b = buckets.setdefault(key_fn(row), {'latest': row,
                                                     'in_year': None})
                if within_year and b['in_year'] is None:
                    start, end = date_fn(row)
                    if start and end and start <= ay_end and end >= ay_start:
                        b['in_year'] = row
            return [b['in_year'] or b['latest'] for b in buckets.values()]

        cur.execute("""
            SELECT t."trim", t.fk_language_id, t.label, t.start_date, t.end_date
            FROM larcauth_term t
            WHERE t.fk_language_id IN (1, 2)
            ORDER BY t.id DESC
        """)
        trims = {}
        for trim, lang, label, start, end in _pick(
                cur.fetchall(), lambda r: (r[0], r[1]),
                lambda r: (r[3], r[4])):
            row = trims.setdefault(trim, {'trim': trim})
            if lang == 2:
                row['label_fr'], row['start_fr'], row['end_fr'] = label, start, end
            else:
                row['label_en'], row['start_en'], row['end_en'] = label, start, end

        cur.execute("""
            SELECT up.unit_nr, up.fk_language_id, up.label,
                   up.start_date, up.end_date
            FROM larcauth_unit_period up
            WHERE up.fk_language_id IN (1, 2)
            ORDER BY up.id DESC
        """)
        units = {}
        for nr, lang, label, start, end in _pick(
                cur.fetchall(), lambda r: (r[0], r[1]),
                lambda r: (r[3], r[4])):
            row = units.setdefault(nr, {'unit_nr': nr})
            if lang == 2:
                row['label_fr'], row['start_fr'], row['end_fr'] = label, start, end
            else:
                row['label_en'], row['start_en'], row['end_en'] = label, start, end

        return {'annee': annee,
                'trimestres': [trims[t] for t in sorted(trims)],
                'unites': [units[u] for u in sorted(units)]}
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log(f"get_temps: {e}")
        return None
