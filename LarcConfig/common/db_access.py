"""Accès DB + JSON pour LarcConfig."""
import json, os, hashlib
from larccommon.database import db
from larccommon.logger import log_error
from larccommon.session import session

L10N_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'LarcCommon', 'larccommon', 'l10n'))
FR_PATH = os.path.join(L10N_DIR, 'fr.json')
EN_PATH = os.path.join(L10N_DIR, 'en.json')


def load_json(lang='fr'):
    p = FR_PATH if lang == 'fr' else EN_PATH
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def save_json(data, lang='fr'):
    p = FR_PATH if lang == 'fr' else EN_PATH
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _conn():
    if not db.is_server_connected:
        return
    c = db.server_conn
    if not c:
        db.connect_intranet()
        c = db.server_conn
    return c


def get_roles():
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        cur.execute("""
            SELECT id, last_name, first_name, email,
                   type_supervisor, type_coordonator, type_secretary, is_adm
            FROM larcauth_aecuser ORDER BY last_name
        """)
        rows = []
        for r in cur.fetchall():
            roles = []
            if r[7]: roles.append('Admin')
            if r[5]: roles.append('Coord')
            if r[4]: roles.append('Superviseur')
            if r[6]: roles.append('Secretaire')
            rows.append({
                'id': r[0], 'last_name': r[1], 'first_name': r[2],
                'email': r[3], 'roles': ', '.join(roles) if roles else '—'
            })
        return rows
    except:
        return []


def get_event_types():
    """Types d'événements — larcauth_event_type_config (arbre à 4 niveaux)."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        cur.execute("""
            WITH RECURSIVE tree AS (
                SELECT id, code, label, category, parent_id, is_active, 0 AS depth
                FROM larcauth_event_type_config
                WHERE parent_id IS NULL
                UNION ALL
                SELECT te.id, te.code, te.label, te.category, te.parent_id, te.is_active,
                       tree.depth + 1
                FROM larcauth_event_type_config te
                JOIN tree ON te.parent_id = tree.id
            )
            SELECT id, code, label, category, parent_id, depth, is_active
            FROM tree
            ORDER BY category, depth,
                     COALESCE(parent_id, 0), id
        """)
        return [
            dict(zip(['id', 'code', 'label', 'category', 'parent_id', 'depth', 'enabled'], r))
            for r in cur.fetchall()
        ]
    except Exception:
        return []


def get_locations():
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        cur.execute("SELECT id, fk_etablissement, nom_lieu FROM larcauth_lieu ORDER BY nom_lieu")
        return [dict(zip(['id', 'fk_etab', 'nom'], r)) for r in cur.fetchall()]
    except:
        return []


def get_logs(limit=200):
    """Journal d'audit (audit_log) — ancien audit_trail laissé en archive."""
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        cur.execute("""
            SELECT id, user_name, operation, table_name, row_id,
                   COALESCE(new_value, old_value), ts
            FROM audit_log ORDER BY ts DESC LIMIT %s
        """, (limit,))
        return [dict(zip(['id', 'user', 'action', 'target_type', 'target_id', 'detail', 'at'], r))
                for r in cur.fetchall()]
    except:
        return []


def _filters(sql: str, params: list, app_name=None, user_id=None,
             table_name=None, date_from=None, date_to=None, limit=500) -> tuple:
    if app_name:
        sql += " AND app_name = %s"; params.append(app_name)
    if user_id:
        sql += " AND user_id = %s"; params.append(user_id)
    if table_name:
        sql += " AND table_name = %s"; params.append(table_name)
    if date_from:
        sql += " AND ts >= %s::date"; params.append(date_from)
    if date_to:
        sql += " AND ts < (%s::date + interval '1 day')"; params.append(date_to)
    sql += " ORDER BY ts DESC LIMIT %s"; params.append(limit)
    return sql, params


def get_errors(app_name=None, user_id=None, date_from=None, date_to=None, limit=500):
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        sql = """SELECT id, ts, app_name, level, user_name, module, message
                 FROM error_log WHERE 1=1"""
        sql, params = _filters(sql, [], app_name, user_id, None, date_from, date_to, limit)
        cur.execute(sql, params)
        return [dict(zip(['id', 'ts', 'app', 'level', 'user', 'module', 'message'], r))
                for r in cur.fetchall()]
    except:
        return []


def get_error_detail(error_id):
    c = _conn()
    if not c:
        return None
    try:
        cur = c.cursor()
        cur.execute("""
            SELECT id, ts, app_name, app_version, user_id, user_name, role,
                   conn_mode, level, module, func, line, message, traceback,
                   context
            FROM error_log WHERE id = %s
        """, (error_id,))
        r = cur.fetchone()
        if not r:
            return None
        return dict(zip(['id', 'ts', 'app', 'version', 'user_id', 'user',
                         'role', 'conn_mode', 'level', 'module', 'func',
                         'line', 'message', 'traceback', 'context'], r))
    except:
        return None


def get_audit(user_id=None, table_name=None, date_from=None, date_to=None, limit=500):
    c = _conn()
    if not c:
        return []
    try:
        cur = c.cursor()
        sql = """SELECT id, ts, user_name, app_name, table_name, operation,
                        row_id, field, old_value, new_value
                 FROM audit_log WHERE 1=1"""
        sql, params = _filters(sql, [], None, user_id, table_name, date_from, date_to, limit)
        cur.execute(sql, params)
        return [dict(zip(['id', 'ts', 'user', 'app', 'table', 'op', 'row',
                          'field', 'old', 'new'], r))
                for r in cur.fetchall()]
    except:
        return []


# ---------------------------------------------------------------
# Le temps — année scolaire, trimestres, unités (FR/EN)
# Les lignes de larcauth_term / larcauth_unit_period s'accumulent par
# année (pas de FK année) : les apps lisent la DERNIÈRE (ORDER BY id DESC
# LIMIT 1) → lecture/écriture via MAX(id) par (trim|unit_nr, langue).
# ---------------------------------------------------------------

def get_temps(within_year: bool = False):
    """Année active + derniers trimestres/unités par langue (1=EN, 2=FR).

    within_year=True : ne garde que les lignes dont les dates tombent dans
    l'année active — les lignes pré-créées de l'année suivante (ex. termes
    « T3 2027 » vides) sont ignorées pour l'affichage du dashboard."""
    c = _conn()
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
            l'année active (ex. « 3e Trimestre » 2025-2026 plutôt que le
            gabarit « T3 2027 ») ; sinon repli sur la plus récente."""
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
        log_error(f"get_temps: {e}")
        return None


def save_annee(label, start, end, term, unit):
    """Met à jour l'année active (MAX(s_id)). Retourne False si échec."""
    c = _conn()
    if not c:
        return False
    try:
        cur = c.cursor()
        cur.execute("""
            UPDATE larcauth_academicyear
            SET label = %s, start_date = %s, end_date = %s,
                current_term_number = %s, "Current_unit_number" = %s
            WHERE s_id = (SELECT MAX(s_id) FROM larcauth_academicyear)
        """, (label, start, end, term, unit))
        return True
    except:
        return False


def save_trimestre(trim, label_fr, label_en, start_fr, end_fr,
                   start_en, end_en):
    """UPDATE-first sur la dernière ligne (trim, langue) ; INSERT si absente."""
    c = _conn()
    if not c:
        return False
    try:
        cur = c.cursor()
        for lang, label, start, end in ((2, label_fr, start_fr, end_fr),
                                        (1, label_en, start_en, end_en)):
            cur.execute("""
                UPDATE larcauth_term SET label = %s, start_date = %s,
                       end_date = %s
                WHERE "trim" = %s AND fk_language_id = %s
                  AND id = (SELECT MAX(id) FROM larcauth_term
                            WHERE "trim" = %s AND fk_language_id = %s)
            """, (label, start, end, trim, lang, trim, lang))
            if cur.rowcount == 0:
                cur.execute("""
                    INSERT INTO larcauth_term
                        ("trim", fk_language_id, label, start_date, end_date,
                         created, updated)
                    VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                """, (trim, lang, label, start, end))
        return True
    except:
        return False


def save_unite(unit_nr, label_fr, label_en, start_fr, end_fr,
               start_en, end_en):
    """UPDATE-first sur la dernière ligne (unit_nr, langue) ; INSERT si absente."""
    c = _conn()
    if not c:
        return False
    try:
        cur = c.cursor()
        for lang, label, start, end in ((2, label_fr, start_fr, end_fr),
                                        (1, label_en, start_en, end_en)):
            cur.execute("""
                UPDATE larcauth_unit_period SET label = %s, start_date = %s,
                       end_date = %s
                WHERE unit_nr = %s AND fk_language_id = %s
                  AND id = (SELECT MAX(id) FROM larcauth_unit_period
                            WHERE unit_nr = %s AND fk_language_id = %s)
            """, (label, start, end, unit_nr, lang, unit_nr, lang))
            if cur.rowcount == 0:
                cur.execute("""
                    INSERT INTO larcauth_unit_period
                        (unit_nr, fk_language_id, label, start_date, end_date,
                         created, updated)
                    VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                """, (unit_nr, lang, label, start, end))
        return True
    except:
        return False


def get_stats(term_id=None):
    """Élèves et matières par classe, groupés par programme (PEI/DP/PP),
    pour le trimestre courant — cohérent avec l'année scolaire affichée.
    Liste de programmes, None si échec."""
    c = _conn()
    if not c:
        return None
    try:
        cur = c.cursor()

        # Année active : bornes + trimestre courant (pour résoudre le
        # trimestre des stats dans la même année que celle affichée).
        cur.execute("""
            SELECT current_term_number, start_date, end_date
            FROM larcauth_academicyear ORDER BY s_id DESC LIMIT 1
        """)
        ay = cur.fetchone()
        current_trim, ay_start, ay_end = ay if ay else (None, None, None)

        def _term_has_data(tid):
            cur.execute("""
                SELECT COUNT(*) FROM larcauth_classroom_termsubject
                WHERE enabled = TRUE AND fk_term_id = %s
            """, (tid,))
            return cur.fetchone()[0] > 0

        # 1) term_id passé / session.term_id — seulement s'il porte des données
        term_id = term_id or (getattr(session, 'term_id', 0) or 0)
        if term_id and not _term_has_data(term_id):
            term_id = 0
        # 2) trimestre courant de l'année active (dernière ligne du trim)
        if not term_id and current_trim:
            cur.execute("""
                SELECT id FROM larcauth_term WHERE "trim" = %s
                ORDER BY id DESC LIMIT 1
            """, (current_trim,))
            r = cur.fetchone()
            if r and _term_has_data(r[0]):
                term_id = r[0]
        # 3) trimestre chevauchant l'année active
        if not term_id and ay_start and ay_end:
            cur.execute("""
                SELECT id FROM larcauth_term
                WHERE start_date <= %s AND end_date >= %s
                ORDER BY id DESC LIMIT 1
            """, (ay_end, ay_start))
            r = cur.fetchone()
            if r and _term_has_data(r[0]):
                term_id = r[0]
        # 4) dernier recours : le trimestre qui porte le plus de données
        if not term_id:
            cur.execute("""
                SELECT cts.fk_term_id FROM larcauth_classroom_termsubject cts
                WHERE cts.enabled = TRUE
                GROUP BY cts.fk_term_id ORDER BY COUNT(*) DESC LIMIT 1
            """)
            r = cur.fetchone()
            term_id = r[0] if r else 0

        # Élèves et matières par classe, par LIGNE de programme réelle :
        # PEI et MYP (même s_id, sections de langue différentes) doivent
        # rester séparés dans l'affichage
        cur.execute("""
            SELECT c.id, c.label, p.sigle,
                   COUNT(DISTINCT s.aecuser_ptr_id) AS eleves,
                   COUNT(DISTINCT cts.id) AS matieres
            FROM larcauth_classroom c
            JOIN larcauth_level l ON l.id = c.fk_level_id
            JOIN larcauth_program p ON p.id = l.fk_program_id
            LEFT JOIN larcauth_student s
              ON s.s_classroom_id = c.id AND s.enabled = TRUE
            LEFT JOIN larcauth_classroom_termsubject cts
              ON cts.fk_classroom_id = c.id AND cts.fk_term_id = %s
             AND cts.enabled = TRUE
            WHERE c.enabled = TRUE
            GROUP BY c.id, c.label, p.s_id, p.sigle
            ORDER BY p.s_id, p.sigle, c.label
        """, (term_id,))

        programs = {}
        for cid, label, sigle, eleves, matieres in cur.fetchall():
            pr = programs.setdefault(sigle, {'sigle': sigle, 'classes': []})
            pr['classes'].append({'id': cid, 'label': label,
                                  'eleves': eleves, 'matieres': matieres})

        # Collège/Lycée uniquement (PP/PYP exclus) — ordre canonique :
        # PEI, MYP, DPFr, DPEn
        order = {'PEI': 0, 'MYP': 1, 'DPFr': 2, 'DPEn': 3}
        result = []
        for sigle, pr in sorted(programs.items(),
                                key=lambda kv: order.get(kv[0], 99)):
            if sigle in ('PP', 'PYP'):
                continue
            result.append({
                's_id': order.get(sigle, 99), 'name': sigle, 'sigle': sigle,
                'classes': pr['classes'],
                'total_classes': len(pr['classes']),
                'total_eleves': sum(x['eleves'] for x in pr['classes']),
                'total_matieres': sum(x['matieres'] for x in pr['classes']),
            })
        return result
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log_error(f"get_stats: {e}")
        return None


def get_audit_meta():
    """Listes distinctes pour les combos : apps, tables, utilisateurs."""
    c = _conn()
    if not c:
        return {}, {}, {}
    try:
        cur = c.cursor()
        cur.execute("SELECT DISTINCT app_name FROM error_log ORDER BY 1")
        apps = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT table_name FROM audit_log ORDER BY 1")
        tables = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT user_name FROM audit_log "
                    "WHERE user_name <> '' ORDER BY 1")
        users = [r[0] for r in cur.fetchall()]
        return apps, tables, users
    except:
        return [], [], []
