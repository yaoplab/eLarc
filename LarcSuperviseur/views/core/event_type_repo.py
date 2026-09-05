"""Accès aux types d'événements (arbre) — extrait de DataLoader (règle 1000 lignes).

Hérite de DataLoader : get_classroom_subjects, get_locations, get_term_id…
restent disponibles. Utilisé par EventGenerator et EventTypesPanel.
"""
import re

from larccommon.l10n import _

from LarcSuperviseur.common.logger import log
from LarcSuperviseur.common.session import session
from LarcSuperviseur.views.core.data_loader import DataLoader


class EventTypeRepo(DataLoader):
    # ------------------------------------------------------------------
    # Types d'événements — arbre (migration 2026-08-30)
    # ------------------------------------------------------------------
    @staticmethod
    def _lang() -> int:
        return getattr(session, "fk_language", 2)

    def get_event_types_nodes(self, lang: int | None = None) -> list[dict]:
        """Tous les nœuds de l'arbre + profondeur + usage_count (verrou UI)."""
        try:
            cur = self._cursor()
            cur.execute(
                """
                WITH RECURSIVE tree AS (
                    SELECT idtypeevent, parent_id, code, label, "Enabled",
                           absence_scope, context, sort_order, 0 AS depth
                    FROM larcauth_type_event
                    WHERE parent_id IS NULL
                      AND (fk_language = %s OR fk_language IS NULL)
                    UNION ALL
                    SELECT t.idtypeevent, t.parent_id, t.code, t.label, t."Enabled",
                           t.absence_scope, t.context, t.sort_order, tree.depth + 1
                    FROM larcauth_type_event t
                    JOIN tree ON t.parent_id = tree.idtypeevent
                )
                SELECT tr.idtypeevent, tr.parent_id, tr.code, tr.label, tr."Enabled",
                       tr.absence_scope, tr.context, tr.sort_order, tr.depth,
                       COALESCE(u.usage_count, 0) AS usage_count
                FROM tree tr
                LEFT JOIN (SELECT event_type_id, count(*) AS usage_count
                           FROM student_event GROUP BY event_type_id) u
                       ON u.event_type_id = tr.idtypeevent
                ORDER BY tr.depth, tr.sort_order, tr.label
                """,
                (lang or self._lang(),),
            )
            return [
                {
                    "id": r[0], "parent_id": r[1], "code": r[2] or "", "label": r[3] or "",
                    "enabled": bool(r[4]), "absence_scope": r[5], "context": r[6],
                    "sort_order": r[7], "depth": r[8], "usage_count": r[9],
                }
                for r in cur.fetchall()
            ]
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"EventTypeRepo.get_event_types_nodes: {e}")
            return []

    def get_event_types_roots(self) -> list[dict]:
        """Racines activées (wizard N0) : [{id, code, label, absence_scope, context}]."""
        try:
            cur = self._cursor()
            cur.execute(
                """
                SELECT idtypeevent, code, label, absence_scope, context
                FROM larcauth_type_event
                WHERE parent_id IS NULL AND "Enabled" = TRUE
                  AND (fk_language = %s OR fk_language IS NULL)
                ORDER BY sort_order, idtypeevent
                """,
                (self._lang(),),
            )
            return [
                {"id": r[0], "code": r[1] or "", "label": r[2] or "",
                 "absence_scope": r[3], "context": r[4]}
                for r in cur.fetchall()
            ]
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"EventTypeRepo.get_event_types_roots: {e}")
            return []

    def get_event_types_subtree(self, root_code: str) -> dict:
        """Sous-arbre sous la racine root_code, format legacy {cat: {n2: [n3]}}."""
        try:
            cur = self._cursor()
            cur.execute(
                """
                WITH RECURSIVE sub AS (
                    SELECT idtypeevent, parent_id, label, sort_order, 1 AS depth
                    FROM larcauth_type_event
                    WHERE code = %s AND (fk_language = %s OR fk_language IS NULL)
                      AND "Enabled" = TRUE
                    UNION ALL
                    SELECT t.idtypeevent, t.parent_id, t.label, t.sort_order, sub.depth + 1
                    FROM larcauth_type_event t
                    JOIN sub ON t.parent_id = sub.idtypeevent
                    WHERE t."Enabled" = TRUE
                )
                SELECT idtypeevent, parent_id, label, depth FROM sub
                ORDER BY depth, sort_order
                """,
                (root_code, self._lang()),
            )
            rows = cur.fetchall()
            if not rows:
                return {}
            tree = {rows[0][2]: {}}
            l2_by_id = {}
            for nid, pid, label, depth in rows[1:]:
                if depth == 2:
                    tree[rows[0][2]].setdefault(label, [])
                    l2_by_id[nid] = label
                elif depth == 3:
                    n2 = l2_by_id.get(pid)
                    if n2:
                        tree[rows[0][2]].setdefault(n2, []).append(label)
            return tree
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"EventTypeRepo.get_event_types_subtree: {e}")
            return {}

    def get_event_types_children(self, parent_id: int) -> list[dict]:
        """Enfants directs activés d'un nœud (wizard N1/N2)."""
        try:
            cur = self._cursor()
            cur.execute(
                """
                SELECT idtypeevent, code, label, absence_scope, context
                FROM larcauth_type_event
                WHERE parent_id = %s AND "Enabled" = TRUE
                  AND NULLIF(BTRIM(label), '') IS NOT NULL
                ORDER BY sort_order, idtypeevent
                """,
                (parent_id,),
            )
            return [
                {"id": r[0], "code": r[1] or "", "label": r[2] or "",
                 "absence_scope": r[3], "context": r[4]}
                for r in cur.fetchall()
            ]
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"EventTypeRepo.get_event_types_children: {e}")
            return []

    def get_event_type_usage(self, type_id: int) -> int:
        try:
            cur = self._cursor()
            cur.execute("SELECT count(*) FROM student_event WHERE event_type_id = %s", (type_id,))
            r = cur.fetchone()
            return int(r[0]) if r else 0
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"EventTypeRepo.get_event_type_usage: {e}")
            return 0

    def _audit_event_type(self, type_id: int, field: str, value: str) -> None:
        try:
            from larccommon.audit_context import attach, refresh
            refresh()
            attach(self.conn)
            cur = self._cursor()
            cur.execute(
                """INSERT INTO audit_log
                       (app_name, user_id, user_name, source, table_name,
                        operation, row_id, field, new_value)
                   VALUES ('LarcSuperviseur', %s, %s, 'app', 'larcauth_type_event',
                           'EVENT', %s, %s, %s)""",
                (session.user_id, getattr(session, "full_name", None),
                 type_id, field, str(value)[:500]),
            )
            self.conn.commit()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"EventTypeRepo._audit_event_type: {e}")

    @staticmethod
    def _slugify(label: str) -> str:
        """Slug translittéré (é→e, ç→c…) — cohérent avec larc_slugify SQL."""
        s = (label or "").lower()
        for a, b in [("à", "a"), ("â", "a"), ("ä", "a"), ("é", "e"), ("è", "e"),
                     ("ê", "e"), ("ë", "e"), ("î", "i"), ("ï", "i"), ("ô", "o"),
                     ("ö", "o"), ("ù", "u"), ("û", "u"), ("ü", "u"), ("ç", "c"),
                     ("ñ", "n")]:
            s = s.replace(a, b)
        return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "type"

    def create_event_type(self, parent_id, label, code=None, enabled=True,
                          absence_scope=None) -> dict:
        """Crée un type. Code auto (slug + préfixe parent + suffixe si collision)."""
        try:
            cur = self._cursor()
            base = code or self._slugify(label)
            candidate, i = base, 2
            cur.execute("SELECT 1 FROM larcauth_type_event WHERE code = %s AND fk_language = %s",
                        (candidate, self._lang()))
            while cur.fetchone():
                candidate = f"{base}-{i}"
                i += 1
                cur.execute("SELECT 1 FROM larcauth_type_event WHERE code = %s AND fk_language = %s",
                            (candidate, self._lang()))
            cur.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM larcauth_type_event "
                        "WHERE parent_id IS NOT DISTINCT FROM %s", (parent_id,))
            next_sort = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO larcauth_type_event
                       (type_event, "Enabled", fk_language, parent_id, code, label,
                        sort_order, absence_scope)
                   VALUES (NULL, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING idtypeevent""",
                (enabled, self._lang(), parent_id, candidate, label, next_sort, absence_scope),
            )
            new_id = cur.fetchone()[0]
            self.conn.commit()
            self._audit_event_type(new_id, "create", label)
            return {"ok": True, "id": new_id, "error": None}
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"EventTypeRepo.create_event_type: {e}")
            self.conn.rollback()
            return {"ok": False, "id": None, "error": str(e)}

    def rename_event_type(self, type_id: int, new_label: str) -> dict:
        try:
            if self.get_event_type_usage(type_id) > 0:
                return {"ok": False, "id": type_id, "error": _("event_types.locked_used")}
            cur = self._cursor()
            cur.execute("SELECT label FROM larcauth_type_event WHERE idtypeevent = %s", (type_id,))
            r = cur.fetchone()
            if not r:
                return {"ok": False, "id": type_id, "error": _("event_types.not_found")}
            cur.execute("UPDATE larcauth_type_event SET label = %s WHERE idtypeevent = %s",
                        (new_label, type_id))
            self.conn.commit()
            self._audit_event_type(type_id, "label", f"{r[0]} → {new_label}")
            return {"ok": True, "id": type_id, "error": None}
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"EventTypeRepo.rename_event_type: {e}")
            self.conn.rollback()
            return {"ok": False, "id": type_id, "error": str(e)}

    def disable_event_type(self, type_id: int, disabled: bool = True) -> dict:
        try:
            if self.get_event_type_usage(type_id) > 0:
                return {"ok": False, "id": type_id, "error": _("event_types.locked_used")}
            cur = self._cursor()
            cur.execute('UPDATE larcauth_type_event SET "Enabled" = %s WHERE idtypeevent = %s',
                        (not disabled, type_id))
            self.conn.commit()
            self._audit_event_type(type_id, "Enabled", "FALSE" if disabled else "TRUE")
            return {"ok": True, "id": type_id, "error": None}
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"EventTypeRepo.disable_event_type: {e}")
            self.conn.rollback()
            return {"ok": False, "id": type_id, "error": str(e)}

    def move_event_type(self, type_id: int, new_parent_id, position=None) -> dict:
        try:
            if self.get_event_type_usage(type_id) > 0:
                return {"ok": False, "id": type_id, "error": _("event_types.locked_used")}
            if new_parent_id is not None:
                seen = set()
                p = new_parent_id
                while p:
                    if p == type_id:
                        return {"ok": False, "id": type_id, "error": _("event_types.cycle")}
                    if p in seen:
                        break
                    seen.add(p)
                    cur = self._cursor()
                    cur.execute("SELECT parent_id FROM larcauth_type_event WHERE idtypeevent = %s", (p,))
                    r = cur.fetchone()
                    p = r[0] if r else None
            cur = self._cursor()
            cur.execute("UPDATE larcauth_type_event SET parent_id = %s WHERE idtypeevent = %s",
                        (new_parent_id, type_id))
            self.conn.commit()
            self._audit_event_type(type_id, "parent_id", str(new_parent_id))
            return {"ok": True, "id": type_id, "error": None}
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"EventTypeRepo.move_event_type: {e}")
            self.conn.rollback()
            return {"ok": False, "id": type_id, "error": str(e)}

    def reorder_event_type(self, type_id: int, direction: int) -> dict:
        """direction : -1 monter, +1 descendre — swap sort_order avec le frère adjacent."""
        try:
            if self.get_event_type_usage(type_id) > 0:
                return {"ok": False, "id": type_id, "error": _("event_types.locked_used")}
            cur = self._cursor()
            cur.execute("SELECT parent_id, sort_order FROM larcauth_type_event WHERE idtypeevent = %s",
                        (type_id,))
            r = cur.fetchone()
            if not r:
                return {"ok": False, "id": type_id, "error": _("event_types.not_found")}
            parent_id, so = r
            if direction < 0:
                cur.execute("SELECT idtypeevent, sort_order FROM larcauth_type_event "
                            "WHERE parent_id IS NOT DISTINCT FROM %s AND sort_order < %s "
                            "ORDER BY sort_order DESC LIMIT 1", (parent_id, so))
            else:
                cur.execute("SELECT idtypeevent, sort_order FROM larcauth_type_event "
                            "WHERE parent_id IS NOT DISTINCT FROM %s AND sort_order > %s "
                            "ORDER BY sort_order ASC LIMIT 1", (parent_id, so))
            other = cur.fetchone()
            if not other:
                return {"ok": True, "id": type_id, "error": None}  # déjà en bordure
            cur.execute("UPDATE larcauth_type_event SET sort_order = %s WHERE idtypeevent = %s",
                        (other[1], type_id))
            cur.execute("UPDATE larcauth_type_event SET sort_order = %s WHERE idtypeevent = %s",
                        (so, other[0]))
            self.conn.commit()
            self._audit_event_type(type_id, "sort_order", f"{so}↔{other[1]}")
            return {"ok": True, "id": type_id, "error": None}
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"EventTypeRepo.reorder_event_type: {e}")
            self.conn.rollback()
            return {"ok": False, "id": type_id, "error": str(e)}

    def resolve_event_type_id(self, path: str, lang: int | None = None) -> int | None:
        """Chemin canonique ('Absence > Absent de l'école > Maladie') → id feuille.
        Langue de session d'abord, puis n'importe quelle langue."""
        try:
            parts = [p.strip() for p in (path or "").split(">") if p.strip()]
            if not parts:
                return None
            lang = lang or self._lang()
            cur = self._cursor()

            def _find(label: str, parent_id) -> int | None:
                if parent_id is None:
                    cur.execute(
                        """SELECT idtypeevent FROM larcauth_type_event
                           WHERE label = %s AND "Enabled" = TRUE
                             AND (parent_id IS NULL OR parent_id IN
                                  (SELECT idtypeevent FROM larcauth_type_event WHERE parent_id IS NULL))
                           ORDER BY (fk_language = %s) DESC LIMIT 1""",
                        (label, lang),
                    )
                else:
                    cur.execute(
                        """SELECT idtypeevent FROM larcauth_type_event
                           WHERE parent_id = %s AND label = %s AND "Enabled" = TRUE
                           ORDER BY (fk_language = %s) DESC LIMIT 1""",
                        (parent_id, label, lang),
                    )
                r = cur.fetchone()
                return r[0] if r else None

            node_id = _find(parts[0], None)
            if node_id is None:
                return None
            for label in parts[1:]:
                node_id = _find(label, node_id)
                if node_id is None:
                    return None
            return node_id
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"EventTypeRepo.resolve_event_type_id: {e}")
            return None

    def resolve_path_from_ids(self, type_id: int) -> str:
        """Chemin canonique (labels) racine → nœud, ex. 'Bureau BI > Violence > Auteur'."""
        try:
            cur = self._cursor()
            labels = []
            nid = type_id
            for _i in range(10):
                cur.execute("SELECT label, parent_id FROM larcauth_type_event WHERE idtypeevent = %s",
                            (nid,))
                r = cur.fetchone()
                if not r:
                    break
                labels.append(r[0] or "")
                nid = r[1]
                if nid is None:
                    break
            return " > ".join(reversed(labels))
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"EventTypeRepo.resolve_path_from_ids: {e}")
            return ""
