"""HRDatabase — couche d'accès aux données RH centralisée."""
from __future__ import annotations

import json
from typing import Any
from datetime import date, datetime

from larccommon.database import db
from larccommon.session import session


def _audit_by() -> int | None:
    """ID de l'utilisateur connecté — pour created_by/modified_by (audit RH)."""
    uid = getattr(session, "user_id", None)
    return int(uid) if uid else None


class HRDatabase:

    # ------------------------------------------------------------------
    # Staff — recherche et lecture
    # ------------------------------------------------------------------

    @staticmethod
    def get_staff_full(staff_id: int) -> dict[str, Any] | None:
        conn = db.server_conn
        if not conn:
            return None
        cur = conn.cursor()
        cur.execute("""
            SELECT a.id, a.first_name, a.last_name, a.email, a.tel_maison,
                   a.tel_smartphone_1, a.emailperso, a.date_of_birth, a.fk_gender_id,
                   a.is_active, a.date_entree, a.fk_language,
                   a.civility, a.nationality, a.marital_status, a.children_count,
                   a.emergency_contact_name, a.emergency_contact_phone,
                   a.blood_type, a.cnss_number, a.tax_id,
                   a.id_document_type, a.id_document_number, a.id_document_expiry,
                   a.matricule, a.professional_category, a.emp_status,
                   a.departure_date, a.departure_reason,
                   a.fk_campus_id, a.fk_supervisor_id,
                   t.is_teacher, t.is_coordonator, t.is_adm, t.is_secretary,
                   s.type_DRH, s.type_Comptable, s.type_ressources_Humaines,
                   s.type_Bulletin_Releves, s.hire_date
            FROM larcauth_aecuser a
            LEFT JOIN larcauth_teachadm t ON t.aecuser_ptr_id = a.id
            LEFT JOIN larcauth_staff s ON s.aecuser_ptr_id = a.id
            WHERE a.id = %s
        """, (staff_id,))
        row = cur.fetchone()
        if not row:
            return None
        return HRDatabase._row_to_staff(row)

    @staticmethod
    def search_staff(id_lo: int, id_hi: int, is_staff: bool = False,
                     search_text: str = "", filters: dict | None = None,
                     conn=None) -> list[dict[str, Any]]:
        # conn optionnel : connexion DÉDIÉE (threads de chargement — la
        # connexion globale n'est pas thread-safe)
        conn = conn or db.server_conn
        if not conn:
            return []
        cur = conn.cursor()

        if is_staff:
            base_cols = """
                a.id, a.first_name, a.last_name, a.email,
                s.type_DRH, s.type_Comptable, s.type_ressources_Humaines,
                s.type_Bulletin_Releves, a.emp_status, a.fk_campus_id,
                a.professional_category, a.matricule,
                c.label AS campus_label, COALESCE(c.color, '#1565C0') AS campus_color,
                EXISTS (SELECT 1 FROM staff_leave_request lr
                        WHERE lr.staff_id = a.id AND lr.status = 'valide'
                          AND CURRENT_DATE BETWEEN lr.date_debut AND lr.date_fin
                          AND EXISTS (SELECT 1 FROM larcauth_agenda g
                                      WHERE g.date_all = CURRENT_DATE
                                        AND g.working_day = TRUE))
            """
            query = f"""
                SELECT {base_cols}
                FROM larcauth_aecuser a
                JOIN larcauth_staff s ON s.aecuser_ptr_id = a.id
                LEFT JOIN larcauth_campus c ON a.fk_campus_id = c.id
                WHERE a.id BETWEEN %s AND %s AND s.enabled = true
            """
        else:
            base_cols = """
                a.id, a.first_name, a.last_name, a.email,
                t.is_teacher, t.is_coordonator, t.is_adm,
                s.type_DRH, s.type_Comptable, s.type_ressources_Humaines,
                s.type_Bulletin_Releves, a.emp_status, a.fk_campus_id,
                a.professional_category, a.matricule,
                c.label AS campus_label, COALESCE(c.color, '#1565C0') AS campus_color,
                EXISTS (SELECT 1 FROM staff_leave_request lr
                        WHERE lr.staff_id = a.id AND lr.status = 'valide'
                          AND CURRENT_DATE BETWEEN lr.date_debut AND lr.date_fin
                          AND EXISTS (SELECT 1 FROM larcauth_agenda g
                                      WHERE g.date_all = CURRENT_DATE
                                        AND g.working_day = TRUE))
            """
            query = f"""
                SELECT {base_cols}
                FROM larcauth_aecuser a
                JOIN larcauth_teachadm t ON t.aecuser_ptr_id = a.id
                LEFT JOIN larcauth_staff s ON s.aecuser_ptr_id = a.id
                LEFT JOIN larcauth_campus c ON a.fk_campus_id = c.id
                WHERE a.id BETWEEN %s AND %s AND t.enabled = true
            """

        params: list[Any] = [id_lo, id_hi]

        ft = (search_text or "").strip().lower()
        if ft:
            query += (" AND (LOWER(a.first_name) LIKE %s OR LOWER(a.last_name) LIKE %s"
                      " OR LOWER(a.email) LIKE %s"
                      " OR LOWER(a.first_name || ' ' || a.last_name) LIKE %s"
                      " OR LOWER(a.matricule) LIKE %s)")
            like = f"%{ft}%"
            params.extend([like, like, like, like, like])

        if filters:
            if filters.get("campus_id"):
                query += " AND a.fk_campus_id = %s"
                params.append(filters["campus_id"])
            if filters.get("status"):
                query += " AND a.emp_status = %s"
                params.append(filters["status"])

        sort = (filters or {}).get("sort", "name")
        if sort == "name":
            query += " ORDER BY a.last_name, a.first_name"
        elif sort == "seniority":
            query += " ORDER BY a.date_entree ASC"
        elif sort == "hire_date":
            query += " ORDER BY COALESCE(s.hire_date, a.date_entree) DESC"

        cur.execute(query, params)
        return [HRDatabase._row_to_staff_compact(r, is_staff) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Staff — sauvegarde
    # ------------------------------------------------------------------

    @staticmethod
    def save_staff(staff_id: int, data: dict[str, Any]) -> bool:
        conn = db.server_conn
        if not conn:
            return False
        cur = conn.cursor()
        try:
            aec_fields = [
                'first_name', 'last_name', 'email', 'tel_maison', 'tel_smartphone_1',
                'emailperso', 'date_of_birth', 'fk_gender_id', 'date_entree',
                'civility', 'nationality', 'marital_status', 'children_count',
                'emergency_contact_name', 'emergency_contact_phone',
                'blood_type', 'cnss_number', 'tax_id',
                'id_document_type', 'id_document_number', 'id_document_expiry',
                'matricule', 'professional_category', 'emp_status',
                'departure_date', 'departure_reason', 'fk_campus_id', 'fk_supervisor_id',
            ]
            sets = []
            vals: list[Any] = []
            for f in aec_fields:
                if f in data:
                    sets.append(f"{f} = %s")
                    vals.append(data[f])
            if sets:
                vals.append(staff_id)
                cur.execute(f"UPDATE larcauth_aecuser SET {', '.join(sets)} WHERE id = %s", vals)

            # Update teachadm or staff liaison
            is_staff = data.get("is_staff", False)
            if is_staff:
                staff_role_fields = ['type_DRH', 'type_Comptable', 'type_ressources_Humaines', 'type_Bulletin_Releves']
                role_vals = [data.get(f, False) for f in staff_role_fields]
                cur.execute(f"""
                    INSERT INTO larcauth_staff (aecuser_ptr_id, enabled, hire_date,
                        {', '.join(staff_role_fields)})
                    VALUES (%s, TRUE, %s, {', '.join('%s' for _ in staff_role_fields)})
                    ON CONFLICT (aecuser_ptr_id) DO UPDATE SET
                        enabled = TRUE, hire_date = %s,
                        {', '.join(f'{f} = %s' for f in staff_role_fields)}
                """, [staff_id, data.get('hire_date')] + role_vals + [data.get('hire_date')] + role_vals)
            else:
                teach_fields = ['is_teacher', 'is_coordonator', 'is_adm', 'is_secretary']
                teach_vals = [data.get(f, False) for f in teach_fields]
                cur.execute(f"""
                    INSERT INTO larcauth_teachadm (aecuser_ptr_id, enabled,
                        {', '.join(teach_fields)})
                    VALUES (%s, TRUE, {', '.join('%s' for _ in teach_fields)})
                    ON CONFLICT (aecuser_ptr_id) DO UPDATE SET
                        enabled = TRUE,
                        {', '.join(f'{f} = %s' for f in teach_fields)}
                """, [staff_id] + teach_vals + teach_vals)

            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def create_staff(id_lo: int, id_hi: int, data: dict[str, Any]) -> int | None:
        """Active un slot gabarit existant (UPDATE uniquement — jamais d'INSERT).

        Pattern LarcSecretaire : les lignes larcauth_aecuser sont pré-allouées.
        La création = UPDATE d'un slot avec is_active=FALSE + last_name LIKE 'Name of %'.
        """
        conn = db.server_conn
        if not conn:
            return None
        cur = conn.cursor()
        try:
            # Trouver un slot libre dans la plage
            cur.execute("""
                SELECT id FROM larcauth_aecuser
                WHERE id BETWEEN %s AND %s AND is_active = FALSE
                AND (first_name LIKE 'ID%%' OR last_name LIKE 'ID%%')
                ORDER BY id LIMIT 1
                FOR UPDATE
            """, (id_lo, id_hi))
            row = cur.fetchone()
            if not row:
                return None  # plus de slot → lancer migration_staff_gabarit.sql
            new_id = row[0]

            username = (data.get('email') or '').strip() or f"staff.{new_id}"
            is_staff_flag = data.get("is_staff", id_lo >= 4001)

            cur.execute("""
                UPDATE larcauth_aecuser SET
                    first_name = %s, last_name = %s, email = %s,
                    username = %s, is_active = TRUE, is_staff = %s,
                    emp_status = 'actif',
                    date_joined = COALESCE(date_joined, NOW()),
                    date_entree = COALESCE(%s, date_entree, NOW()),
                    updated = NOW()
                WHERE id = %s
            """, (data['first_name'], data['last_name'], data.get('email', ''),
                  username, is_staff_flag,
                  data.get('hire_date') or data.get('date_entree'),
                  new_id))

            # Liaison table
            if is_staff_flag:
                cur.execute("""
                    INSERT INTO larcauth_staff (aecuser_ptr_id, enabled, hire_date,
                        type_DRH, type_Comptable, type_ressources_Humaines, type_Bulletin_Releves)
                    VALUES (%s, TRUE, %s, %s, %s, %s, %s)
                    ON CONFLICT (aecuser_ptr_id) DO UPDATE SET enabled = TRUE, hire_date = %s,
                        type_DRH = %s, type_Comptable = %s,
                        type_ressources_Humaines = %s, type_Bulletin_Releves = %s
                """, ([new_id, data.get('hire_date')] +
                      [data.get(f, False) for f in ['type_DRH', 'type_Comptable', 'type_ressources_Humaines', 'type_Bulletin_Releves']] +
                      [data.get('hire_date')] +
                      [data.get(f, False) for f in ['type_DRH', 'type_Comptable', 'type_ressources_Humaines', 'type_Bulletin_Releves']]))
            else:
                cur.execute("""
                    INSERT INTO larcauth_teachadm (aecuser_ptr_id, enabled, is_teacher, is_coordonator, is_adm, is_secretary)
                    VALUES (%s, TRUE, %s, %s, %s, %s)
                    ON CONFLICT (aecuser_ptr_id) DO UPDATE SET enabled = TRUE,
                        is_teacher = %s, is_coordonator = %s, is_adm = %s, is_secretary = %s
                """, ([new_id] + [data.get(f, False) for f in ['is_teacher', 'is_coordonator', 'is_adm', 'is_secretary']] +
                      [data.get(f, False) for f in ['is_teacher', 'is_coordonator', 'is_adm', 'is_secretary']]))

            return new_id
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return None

    # ------------------------------------------------------------------
    # Degrees
    # ------------------------------------------------------------------

    @staticmethod
    def get_degrees(staff_id: int) -> list[dict[str, Any]]:
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        cur.execute(
            "SELECT id, degree_type, institution, year_obtained, country, field_of_study "
            "FROM staff_degree WHERE staff_id = %s ORDER BY year_obtained DESC",
            (staff_id,))
        return [{"id": r[0], "degree_type": r[1], "institution": r[2],
                 "year_obtained": r[3], "country": r[4], "field_of_study": r[5]}
                for r in cur.fetchall()]

    @staticmethod
    def save_degree(staff_id: int, data: dict[str, Any]) -> bool:
        conn = db.server_conn
        if not conn:
            return False
        cur = conn.cursor()
        try:
            if data.get("id"):
                cur.execute("""
                    UPDATE staff_degree SET degree_type=%s, institution=%s, year_obtained=%s,
                    country=%s, field_of_study=%s WHERE id=%s AND staff_id=%s
                """, (data["degree_type"], data.get("institution"), data.get("year_obtained"),
                      data.get("country"), data.get("field_of_study"), data["id"], staff_id))
            else:
                cur.execute("""
                    INSERT INTO staff_degree (staff_id, degree_type, institution, year_obtained, country, field_of_study, created_by, modified_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (staff_id, data["degree_type"], data.get("institution"),
                      data.get("year_obtained"), data.get("country"), data.get("field_of_study"),
                      _audit_by(), _audit_by()))
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def delete_degree(degree_id: int, staff_id: int) -> bool:
        conn = db.server_conn
        if not conn:
            return False
        cur = conn.cursor()
        cur.execute("DELETE FROM staff_degree WHERE id = %s AND staff_id = %s", (degree_id, staff_id))
        return True

    # ------------------------------------------------------------------
    # Languages
    # ------------------------------------------------------------------

    @staticmethod
    def get_languages(staff_id: int) -> list[dict[str, Any]]:
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        cur.execute(
            "SELECT id, language, proficiency FROM staff_language WHERE staff_id = %s ORDER BY language",
            (staff_id,))
        return [{"id": r[0], "language": r[1], "proficiency": r[2]} for r in cur.fetchall()]

    @staticmethod
    def save_language(staff_id: int, data: dict[str, Any]) -> bool:
        conn = db.server_conn
        if not conn:
            return False
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO staff_language (staff_id, language, proficiency, created_by, modified_by)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (staff_id, language) DO UPDATE SET proficiency = %s, modified_by = %s
            """, (staff_id, data["language"], data.get("proficiency", "B1"),
                  _audit_by(), _audit_by(),
                  data.get("proficiency", "B1"), _audit_by()))
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def delete_language(staff_id: int, language: str) -> bool:
        conn = db.server_conn
        if not conn:
            return False
        cur = conn.cursor()
        cur.execute("DELETE FROM staff_language WHERE staff_id = %s AND language = %s", (staff_id, language))
        return True

    # ------------------------------------------------------------------
    # Contracts
    # ------------------------------------------------------------------

    @staticmethod
    def get_contracts(staff_id: int) -> list[dict[str, Any]]:
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id, c.contract_type, c.date_debut, c.date_fin, c.periode_essai,
                   c.periode_essai_fin, c.salaire_brut, c.volume_horaire,
                   c.classification, c.echelon, c.statut, c.notes, c.created_at,
                   COALESCE(u.last_name || ' ' || u.first_name, '—') AS modified_by_name
            FROM staff_contract c
            LEFT JOIN larcauth_aecuser u ON u.id = c.modified_by
            WHERE c.staff_id = %s ORDER BY c.date_debut DESC
        """, (staff_id,))
        cols = ["id", "contract_type", "date_debut", "date_fin", "periode_essai",
                "periode_essai_fin", "salaire_brut", "volume_horaire",
                "classification", "echelon", "statut", "notes", "created_at",
                "modified_by_name"]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    @staticmethod
    def save_contract(data: dict[str, Any]) -> bool:
        conn = db.server_conn
        if not conn:
            return False
        cur = conn.cursor()
        try:
            fields = ['staff_id', 'contract_type', 'date_debut', 'date_fin',
                      'periode_essai', 'periode_essai_fin', 'salaire_brut',
                      'volume_horaire', 'classification', 'echelon', 'statut', 'notes']
            if data.get("id"):
                cur.execute(f"""
                    UPDATE staff_contract SET {', '.join(f'{f}=%s' for f in fields)}, updated_at=NOW(), modified_by=%s
                    WHERE id=%s
                """, [data.get(f) for f in fields] + [_audit_by(), data["id"]])
            else:
                fields2 = fields + ['created_by', 'modified_by']
                placeholders = ', '.join('%s' for _ in fields2)
                cur.execute(f"""
                    INSERT INTO staff_contract ({', '.join(fields2)})
                    VALUES ({placeholders})
                """, [data.get(f) for f in fields] + [_audit_by(), _audit_by()])
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return False

    # ------------------------------------------------------------------
    # Leave
    # ------------------------------------------------------------------

    @staticmethod
    def get_leave_balance(staff_id: int, year: int | None = None) -> list[dict[str, Any]]:
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        if year is None:
            year = date.today().year
        cur.execute("""
            SELECT id, year, leave_type, total_days, used_days,
                   (total_days - used_days) AS remaining
            FROM staff_leave_balance WHERE staff_id = %s AND year = %s
            ORDER BY leave_type
        """, (staff_id, year))
        cols = ["id", "year", "leave_type", "total_days", "used_days", "remaining"]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    @staticmethod
    def ensure_annual_leave(staff_id: int, year: int | None = None) -> bool:
        """Crédite automatiquement 30 jours de congé annuel si pas encore initialisé."""
        conn = db.server_conn
        if not conn:
            return False
        if year is None:
            year = date.today().year
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO staff_leave_balance (staff_id, year, leave_type, total_days, used_days, created_by, modified_by)
                VALUES (%s, %s, 'CA', 30, 0, %s, %s)
                ON CONFLICT (staff_id, year, leave_type) DO NOTHING
            """, (staff_id, year, _audit_by(), _audit_by()))
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def get_leave_requests(staff_id: int | None = None,
                           status: str | None = None) -> list[dict[str, Any]]:
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        query = """
            SELECT r.id, r.staff_id, a.first_name, a.last_name, r.leave_type,
                   r.date_debut, r.date_fin, r.nb_days, r.motif, r.attachment_path,
                   r.status, r.requested_at, r.validated_by, r.validated_at, r.validation_note,
                   COALESCE(u.last_name || ' ' || u.first_name, '—') AS created_by_name
            FROM staff_leave_request r
            JOIN larcauth_aecuser a ON a.id = r.staff_id
            LEFT JOIN larcauth_aecuser u ON u.id = r.created_by
        """
        params: list[Any] = []
        conditions = []
        if staff_id is not None:
            conditions.append("r.staff_id = %s")
            params.append(staff_id)
        if status is not None:
            conditions.append("r.status = %s")
            params.append(status)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY r.requested_at DESC LIMIT 100"
        cur.execute(query, params)
        cols = ["id", "staff_id", "first_name", "last_name", "leave_type",
                "date_debut", "date_fin", "nb_days", "motif", "attachment_path",
                "status", "requested_at", "validated_by", "validated_at",
                "validation_note", "created_by_name"]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    @staticmethod
    def save_leave_request(data: dict[str, Any]) -> bool:
        conn = db.server_conn
        if not conn:
            return False
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO staff_leave_request
                    (staff_id, leave_type, date_debut, date_fin, nb_days, motif,
                     attachment_path, status, created_by, modified_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'en_attente', %s, %s)
            """, (data["staff_id"], data["leave_type"], data["date_debut"],
                  data["date_fin"], data["nb_days"], data.get("motif"),
                  data.get("attachment_path"), _audit_by(), _audit_by()))
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def validate_leave_request(request_id: int, validated_by: int,
                               approved: bool, note: str = "") -> bool:
        conn = db.server_conn
        if not conn:
            return False
        cur = conn.cursor()
        try:
            new_status = 'valide' if approved else 'refuse'
            cur.execute("""
                UPDATE staff_leave_request
                SET status = %s, validated_by = %s, validated_at = NOW(),
                    validation_note = %s, modified_by = %s
                WHERE id = %s
            """, (new_status, validated_by, note, _audit_by(), request_id))

            if approved:
                cur.execute("""
                    UPDATE staff_leave_balance
                    SET used_days = used_days + sub.nb_days
                    FROM (SELECT staff_id, leave_type, nb_days FROM staff_leave_request WHERE id = %s) AS sub
                    WHERE staff_leave_balance.staff_id = sub.staff_id
                    AND staff_leave_balance.leave_type = sub.leave_type
                    AND staff_leave_balance.year = EXTRACT(YEAR FROM (SELECT date_debut FROM staff_leave_request WHERE id = %s))::INTEGER
                """, (request_id, request_id))
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def revoke_leave_request(request_id: int) -> bool:
        """Révoque une validation : remet en attente et annule l'impact sur le solde."""
        conn = db.server_conn
        if not conn:
            return False
        cur = conn.cursor()
        try:
            # Restore balance if it was approved
            cur.execute("""
                UPDATE staff_leave_balance
                SET used_days = used_days - sub.nb_days
                FROM (SELECT staff_id, leave_type, nb_days, status FROM staff_leave_request WHERE id = %s) AS sub
                WHERE staff_leave_balance.staff_id = sub.staff_id
                AND staff_leave_balance.leave_type = sub.leave_type
                AND staff_leave_balance.year = EXTRACT(YEAR FROM (SELECT date_debut FROM staff_leave_request WHERE id = %s))::INTEGER
                AND sub.status = 'valide'
            """, (request_id, request_id))

            # Reset to en_attente
            cur.execute("""
                UPDATE staff_leave_request
                SET status = 'en_attente', validated_by = NULL,
                    validated_at = NULL, validation_note = NULL
                WHERE id = %s AND status IN ('valide', 'refuse')
            """, (request_id,))
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return False

    # ------------------------------------------------------------------
    # Dashboard / KPIs
    # ------------------------------------------------------------------

    @staticmethod
    def get_dashboard_kpis() -> dict[str, Any]:
        conn = db.server_conn
        if not conn:
            return {}
        cur = conn.cursor()

        def _safe_count(label: str, query: str, params=None) -> int:
            try:
                cur.execute(query, params or ())
                return cur.fetchone()[0] or 0
            except Exception:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                import traceback
                traceback.print_exc()
                return -1

        # NB : PAS de filtre a.is_active — c'est un droit de CONNEXION, pas un
        # statut d'emploi. La grille du personnel affiche enabled + actif +
        # non parti ; le KPI doit être cohérent avec elle (sinon « Effectif
        # actif » = 9 alors que l'app liste 62 personnes, bug signalé 2026-08-16).
        # Plages de personnel uniquement (1001-5000) : les IDs hors plages
        # sont des gabarits (« - Sans », « - En Attente ») — sinon le total
        # dépasse la somme des catégories (35+14+11+0 = 60 ≠ 62).
        total_active = _safe_count("total_active", """
            SELECT COUNT(*) FROM (
                SELECT a.id FROM larcauth_aecuser a
                JOIN larcauth_teachadm t ON t.aecuser_ptr_id = a.id
                WHERE t.enabled = TRUE
                  AND a.emp_status = 'actif' AND a.departure_date IS NULL
                  AND a.id BETWEEN 1001 AND 5000
                UNION
                SELECT a.id FROM larcauth_aecuser a
                JOIN larcauth_staff s ON s.aecuser_ptr_id = a.id
                WHERE s.enabled = TRUE
                  AND a.emp_status = 'actif' AND a.departure_date IS NULL
                  AND a.id BETWEEN 1001 AND 5000
            ) AS staff
        """)
        active_contracts = _safe_count("active_contracts",
            "SELECT COUNT(*) FROM staff_contract WHERE statut = 'actif'")
        pending_leave = _safe_count("pending_leave",
            "SELECT COUNT(*) FROM staff_leave_request WHERE status = 'en_attente'")
        expiring = _safe_count("expiring_contracts",
            "SELECT COUNT(*) FROM staff_contract WHERE statut = 'actif'"
            " AND date_fin IS NOT NULL AND date_fin <= CURRENT_DATE + INTERVAL '30 days'")
        absent_today = _safe_count("absent_today",
            "SELECT COUNT(*) FROM staff_leave_request lr WHERE lr.status = 'valide'"
            " AND CURRENT_DATE BETWEEN lr.date_debut AND lr.date_fin"
            " AND EXISTS (SELECT 1 FROM larcauth_agenda g"
            "             WHERE g.date_all = CURRENT_DATE AND g.working_day = TRUE)")
        return {
            "total_active": total_active,
            "active_contracts": active_contracts,
            "pending_leave": pending_leave,
            "expiring_contracts": expiring,
            "absent_today": absent_today,
        }

    @staticmethod
    def get_headcount_by_campus() -> list[dict[str, Any]]:
        """Effectif présent par campus (label, color, count).

        Présent = actif (emp_status='actif', non parti, enabled)
        − absents du jour (congé valide couvrant aujourd'hui).
        """
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT c.label, COALESCE(c.color, '#1565C0'), COUNT(DISTINCT a.id)
                FROM larcauth_aecuser a
                JOIN larcauth_campus c ON a.fk_campus_id = c.id
                LEFT JOIN larcauth_teachadm t ON t.aecuser_ptr_id = a.id
                LEFT JOIN larcauth_staff s ON s.aecuser_ptr_id = a.id
                WHERE a.emp_status = 'actif' AND a.departure_date IS NULL
                  AND (t.enabled = TRUE OR s.enabled = TRUE)
                  AND NOT EXISTS (
                      SELECT 1 FROM staff_leave_request lr
                      WHERE lr.staff_id = a.id AND lr.status = 'valide'
                        AND CURRENT_DATE BETWEEN lr.date_debut AND lr.date_fin
                        AND EXISTS (SELECT 1 FROM larcauth_agenda g
                                    WHERE g.date_all = CURRENT_DATE
                                      AND g.working_day = TRUE)
                  )
                GROUP BY c.id, c.label, c.color
                ORDER BY COUNT(DISTINCT a.id) DESC
            """)
            cols = ["label", "color", "count"]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return []

    # Données indispensables à vérifier/valider dans la fiche employé
    # (validation 100 % manuelle : le RH coche même si l'info n'existe pas)
    # Les DOCUMENTS en font partie : cocher les 5 champs ne suffit pas —
    # CV, contrat signé et diplôme doivent être cochés aussi pour que le
    # dossier soit COMPLET (cohérence dashboard ↔ checkboxes, 2026-08-16).
    DOSSIER_CHECK_ITEMS: list[tuple[str, str]] = [
        ("matricule", "Matricule"),
        ("cnss", "N° CNSS"),
        ("piece_identite", "Pièce d'identité"),
        ("urgence_nom", "Contact urgence (nom)"),
        ("urgence_tel", "Contact urgence (tél)"),
        ("diplome", "Diplôme"),
        ("contrat_signe", "Contrat signé"),
        ("cv", "CV"),
    ]

    @staticmethod
    def get_dossier_checks(staff_id: int) -> dict[str, dict]:
        conn = db.server_conn
        if not conn:
            return {}
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT item_key, validated, validated_by, validated_at "
                "FROM staff_dossier_check WHERE staff_id = %s",
                (staff_id,))
            out = {}
            for key, val, by, at in cur.fetchall():
                out[key] = {"validated": val, "validated_by": by, "validated_at": at}
            return out
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return {}

    @staticmethod
    def set_dossier_check(staff_id: int, item_key: str, validated: bool,
                          validated_by: str = "") -> bool:
        conn = db.server_conn
        if not conn:
            return False
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO staff_dossier_check (staff_id, item_key, validated, validated_by, validated_at, created_by, modified_by)
                VALUES (%s, %s, %s, %s, NOW(), %s, %s)
                ON CONFLICT (staff_id, item_key)
                DO UPDATE SET validated = %s, validated_by = %s, validated_at = NOW(), modified_by = %s
            """, (staff_id, item_key, validated, validated_by or None,
                  _audit_by(), _audit_by(),
                  validated, validated_by or None, _audit_by()))
            # Sync de l'état PRÉ-CALCULÉ (dashboard) — le dashboard lit
            # staff_dossier_status en 1 SELECT, jamais de recalcul par refresh
            n_items = len(HRDatabase.DOSSIER_CHECK_ITEMS)
            cur.execute("""
                INSERT INTO staff_dossier_status (staff_id, validated_count, total_items, complete)
                VALUES (%s,
                        (SELECT COUNT(*) FROM staff_dossier_check dc
                         WHERE dc.staff_id = %s AND dc.validated = TRUE),
                        %s,
                        (SELECT COUNT(*) FROM staff_dossier_check dc
                         WHERE dc.staff_id = %s AND dc.validated = TRUE) = %s)
                ON CONFLICT (staff_id) DO UPDATE SET
                    validated_count = EXCLUDED.validated_count,
                    total_items     = EXCLUDED.total_items,
                    complete        = EXCLUDED.complete,
                    updated_at      = NOW()
            """, (staff_id, staff_id, n_items, staff_id, n_items))
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def dossier_validation_progress(staff_id: int) -> dict:
        checks = HRDatabase.get_dossier_checks(staff_id)
        total = len(HRDatabase.DOSSIER_CHECK_ITEMS)
        done = sum(1 for k, _ in HRDatabase.DOSSIER_CHECK_ITEMS
                   if checks.get(k, {}).get("validated"))
        return {"validated": done, "total": total,
                "pct": round(done / total * 100) if total else 0}

    @staticmethod
    def get_dossier_check_stats() -> tuple[int, list[dict[str, Any]]]:
        """(total actif, par item : dossiers NON encore vérifiés).

        Aligné sur DOSSIER_CHECK_ITEMS — mêmes libellés que la carte de
        vérification de la fiche (cohérent avec les checkboxes).
        """
        conn = db.server_conn
        if not conn:
            return 0, []
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT COUNT(*) FROM larcauth_aecuser a
                LEFT JOIN larcauth_teachadm t ON t.aecuser_ptr_id = a.id
                LEFT JOIN larcauth_staff s ON s.aecuser_ptr_id = a.id
                WHERE a.emp_status = 'actif' AND a.departure_date IS NULL
                  AND (t.enabled = TRUE OR s.enabled = TRUE)
            """)
            total = cur.fetchone()[0] or 0
            out = []
            for key, label in HRDatabase.DOSSIER_CHECK_ITEMS:
                cur.execute(
                    "SELECT COUNT(*) FROM staff_dossier_check dc "
                    "WHERE dc.item_key = %s AND dc.validated = TRUE",
                    (key,))
                validated = cur.fetchone()[0] or 0
                out.append({"label": label, "missing": max(total - validated, 0)})
            return total, out
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return 0, []

    # ── Présence RH (qui travaille en ce moment) ──

    @staticmethod
    def set_session_online(user_id: int, app: str = "LarcRH") -> bool:
        """Heartbeat : marque l'utilisateur en ligne (last_seen = NOW)."""
        conn = db.server_conn
        if not conn or not user_id:
            return False
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO rh_user_sessions (user_id, app, logged_in_at, last_seen)
                VALUES (%s, %s, NOW(), NOW())
                ON CONFLICT (user_id)
                DO UPDATE SET last_seen = NOW(), app = EXCLUDED.app
            """, (user_id, app))
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def set_session_offline(user_id: int) -> bool:
        """Déconnexion : retire la session."""
        conn = db.server_conn
        if not conn or not user_id:
            return False
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM rh_user_sessions WHERE user_id = %s", (user_id,))
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def get_online_sessions() -> list[dict[str, Any]]:
        """Sessions actives (last_seen < 10 min) avec le nom de l'utilisateur."""
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT s.user_id, s.app, s.last_seen,
                       COALESCE(u.last_name || ' ' || u.first_name, '—') AS full_name
                FROM rh_user_sessions s
                LEFT JOIN larcauth_aecuser u ON u.id = s.user_id
                WHERE s.last_seen > NOW() - INTERVAL '10 minutes'
                ORDER BY s.last_seen DESC
            """)
            cols = ["user_id", "app", "last_seen", "full_name"]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return []

    @staticmethod
    def is_working_day(date: str | None = None) -> bool:
        """Le jour est-il OUVRÉ (larcauth_agenda.working_day = TRUE) ?

        C'est le « enabled » du jour : hors jour ouvré, la génération
        d'événements est interdite et l'absence du jour ne s'applique pas.
        """
        conn = db.server_conn
        if not conn:
            return False
        cur = conn.cursor()
        try:
            if date:
                cur.execute(
                    "SELECT working_day FROM larcauth_agenda WHERE date_all = %s LIMIT 1",
                    (date,))
            else:
                cur.execute(
                    "SELECT working_day FROM larcauth_agenda "
                    "WHERE date_all = CURRENT_DATE LIMIT 1")
            row = cur.fetchone()
            return bool(row[0]) if row else False
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def get_headcount_by_category() -> list[dict[str, Any]]:
        """Effectif présent par catégorie LarcRH (plages d'IDs de la sidebar).

        Fallback du dashboard quand aucun fk_campus_id n'est renseigné —
        mêmes filtres que get_headcount_by_campus (actif, non parti, enabled,
        hors absents du jour).
        """
        cats = [
            ("Collège / Lycée", 1001, 2000),
            ("Primaire", 2001, 3000),
            ("Maternelle", 3001, 4000),
            ("Staff non enseignant", 4001, 5000),
        ]
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        out: list[dict[str, Any]] = []
        for label, lo, hi in cats:
            cur.execute("""
                SELECT COUNT(*) FROM (
                    SELECT a.id FROM larcauth_aecuser a
                    JOIN larcauth_teachadm t ON t.aecuser_ptr_id = a.id
                    WHERE a.id BETWEEN %s AND %s AND t.enabled = TRUE
                      AND a.emp_status = 'actif' AND a.departure_date IS NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM staff_leave_request lr
                          WHERE lr.staff_id = a.id AND lr.status = 'valide'
                            AND CURRENT_DATE BETWEEN lr.date_debut AND lr.date_fin
                            AND EXISTS (SELECT 1 FROM larcauth_agenda g
                                        WHERE g.date_all = CURRENT_DATE
                                          AND g.working_day = TRUE))
                    UNION
                    SELECT a.id FROM larcauth_aecuser a
                    JOIN larcauth_staff s ON s.aecuser_ptr_id = a.id
                    WHERE a.id BETWEEN %s AND %s AND s.enabled = TRUE
                      AND a.emp_status = 'actif' AND a.departure_date IS NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM staff_leave_request lr
                          WHERE lr.staff_id = a.id AND lr.status = 'valide'
                            AND CURRENT_DATE BETWEEN lr.date_debut AND lr.date_fin
                            AND EXISTS (SELECT 1 FROM larcauth_agenda g
                                        WHERE g.date_all = CURRENT_DATE
                                          AND g.working_day = TRUE))
                ) AS x
            """, (lo, hi, lo, hi))
            out.append({"label": label, "count": cur.fetchone()[0]})
        return out

    @staticmethod
    def get_contracts_by_type() -> list[dict[str, Any]]:
        """Contrats actifs groupés par type."""
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT contract_type, COUNT(*) AS cnt
                FROM staff_contract WHERE statut = 'actif'
                GROUP BY contract_type ORDER BY cnt DESC
            """)
            cols = ["type", "count"]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return []

    @staticmethod
    def get_absence_rate_30d() -> dict[str, Any]:
        """Taux d'absentéisme sur 30 jours glissants + période précédente (delta)."""
        conn = db.server_conn
        if not conn:
            return {"rate": 0, "delta": 0, "days_with_absence": 0, "total_events": 0}
        cur = conn.cursor()
        try:
            # Jours avec au moins une absence sur les 30 derniers jours
            cur.execute("""
                SELECT COUNT(DISTINCT DATE(event_at))
                FROM staff_event
                WHERE event_type LIKE 'Absence%%'
                  AND event_at >= CURRENT_DATE - INTERVAL '30 days'
                  AND event_at < CURRENT_DATE
            """)
            days_current = cur.fetchone()[0] or 0
            # Période précédente (30–60 jours)
            cur.execute("""
                SELECT COUNT(DISTINCT DATE(event_at))
                FROM staff_event
                WHERE event_type LIKE 'Absence%%'
                  AND event_at >= CURRENT_DATE - INTERVAL '60 days'
                  AND event_at < CURRENT_DATE - INTERVAL '30 days'
            """)
            days_previous = cur.fetchone()[0] or 0
            # Total events current period
            cur.execute("""
                SELECT COUNT(*) FROM staff_event
                WHERE event_type LIKE 'Absence%%'
                  AND event_at >= CURRENT_DATE - INTERVAL '30 days'
                  AND event_at < CURRENT_DATE
            """)
            total_events = cur.fetchone()[0] or 0

            rate = round(days_current / 30.0 * 100, 1) if days_current > 0 else 0.0
            prev_rate = round(days_previous / 30.0 * 100, 1) if days_previous > 0 else 0.0
            delta = round(rate - prev_rate, 1)
            return {"rate": rate, "delta": delta, "days_with_absence": days_current,
                    "total_events": total_events}
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return {"rate": 0, "delta": 0, "days_with_absence": 0, "total_events": 0}

    @staticmethod
    def get_overdue_tasks() -> int:
        """Nombre de tâches en retard (due_date passée, non terminées)."""
        conn = db.server_conn
        if not conn:
            return 0
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT COUNT(*) FROM staff_todo
                WHERE due_date IS NOT NULL AND due_date < CURRENT_DATE
                  AND status != 'done'
            """)
            return cur.fetchone()[0] or 0
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return 0

    @staticmethod
    def get_completeness_stats() -> dict[str, Any]:
        """Score de complétude — aligné sur la carte de vérification (checkboxes).

        Un dossier est COMPLET quand les N items de staff_dossier_check sont
        tous « Vérifiés et Validés » (validation manuelle du RH) — même
        source que la carte de la fiche employé.
        """
        conn = db.server_conn
        if not conn:
            return {"total": 0, "complete": 0, "incomplete": 0, "pct": 0}
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT COUNT(*) FROM larcauth_aecuser a
                LEFT JOIN larcauth_teachadm t ON t.aecuser_ptr_id = a.id
                LEFT JOIN larcauth_staff s ON s.aecuser_ptr_id = a.id
                WHERE a.emp_status = 'actif' AND a.departure_date IS NULL
                  AND (t.enabled = TRUE OR s.enabled = TRUE)
            """)
            total = cur.fetchone()[0] or 0
            # Lecture de l'état PRÉ-CALCULÉ (staff_dossier_status) — 1 SELECT
            cur.execute("""
                SELECT COUNT(*) FROM staff_dossier_status ds
                JOIN larcauth_aecuser a ON a.id = ds.staff_id
                LEFT JOIN larcauth_teachadm t ON t.aecuser_ptr_id = a.id
                LEFT JOIN larcauth_staff s ON s.aecuser_ptr_id = a.id
                WHERE ds.complete = TRUE
                  AND a.emp_status = 'actif' AND a.departure_date IS NULL
                  AND (t.enabled = TRUE OR s.enabled = TRUE)
            """)
            complete = cur.fetchone()[0] or 0
            incomplete = total - complete
            pct = round(complete / total * 100) if total > 0 else 0
            return {"total": total, "complete": complete, "incomplete": incomplete, "pct": pct}
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return {"total": 0, "complete": 0, "incomplete": 0, "pct": 0}

    @staticmethod
    def get_expiring_id_docs() -> int:
        """Pièces d'identité expirées ou expirant dans les 30 jours."""
        conn = db.server_conn
        if not conn:
            return 0
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT COUNT(*) FROM larcauth_aecuser a
                LEFT JOIN larcauth_teachadm t ON t.aecuser_ptr_id = a.id
                LEFT JOIN larcauth_staff s ON s.aecuser_ptr_id = a.id
                WHERE a.emp_status = 'actif' AND a.departure_date IS NULL
                  AND (t.enabled = TRUE OR s.enabled = TRUE)
                  AND a.id_document_expiry IS NOT NULL
                  AND a.id_document_expiry <= CURRENT_DATE + INTERVAL '30 days'
            """)
            return cur.fetchone()[0] or 0
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return 0

    @staticmethod
    def get_trial_periods_ending() -> int:
        """Périodes d'essai se terminant dans les 15 jours."""
        conn = db.server_conn
        if not conn:
            return 0
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT COUNT(*) FROM staff_contract
                WHERE statut = 'actif' AND periode_essai_fin IS NOT NULL
                  AND periode_essai_fin BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '15 days'
            """)
            return cur.fetchone()[0] or 0
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return 0

    @staticmethod
    def get_missing_fields_stats() -> list[dict[str, Any]]:
        """Top 5 des champs les plus souvent manquants — UNIQUEMENT le personnel
        (enseignants + staff), jamais les élèves (bug 2026-08-16 : comptait
        les 4655 utilisateurs de la base)."""
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        try:
            fields = [
                ("N° CNSS", "cnss_number"),
                ("Matricule", "matricule"),
                ("Contact urgence (nom)", "emergency_contact_name"),
                ("Contact urgence (tél)", "emergency_contact_phone"),
                ("Pièce d'identité", "id_document_number"),
                ("Date de naissance", "date_of_birth"),
                ("Nationalité", "nationality"),
                ("Situation familiale", "marital_status"),
            ]
            result = []
            for label, col in fields:
                # DATE columns can't be compared to ''
                if col == 'date_of_birth':
                    cond = f"a.{col} IS NULL"
                else:
                    cond = f"(a.{col} IS NULL OR a.{col} = '')"
                cur.execute(f"""
                    SELECT COUNT(*) FROM larcauth_aecuser a
                    LEFT JOIN larcauth_teachadm t ON t.aecuser_ptr_id = a.id
                    LEFT JOIN larcauth_staff s ON s.aecuser_ptr_id = a.id
                    WHERE a.emp_status = 'actif' AND a.departure_date IS NULL
                      AND (t.enabled = TRUE OR s.enabled = TRUE)
                      AND {cond}
                """)
                missing = cur.fetchone()[0] or 0
                result.append({"label": label, "missing": missing})
            result.sort(key=lambda x: x["missing"], reverse=True)
            return result[:5]
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return []

    @staticmethod
    def get_missing_docs_stats() -> list[dict[str, Any]]:
        """Employés actifs sans document dans les catégories obligatoires."""
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        try:
            # NB : « Pièce d'identité » retirée — déjà couverte par l'item
            # de vérification (checkboxes) ; évite le doublon dans la
            # section Complétude du dashboard.
            categories = [
                ("diplomas", "Diplôme"),
                ("contracts", "Contrat signé"),
                ("other", "CV"),
            ]
            result = []
            for cat_key, cat_label in categories:
                cur.execute("""
                    SELECT COUNT(*) FROM larcauth_aecuser a
                    LEFT JOIN larcauth_teachadm t ON t.aecuser_ptr_id = a.id
                    LEFT JOIN larcauth_staff s ON s.aecuser_ptr_id = a.id
                    WHERE a.emp_status = 'actif' AND a.departure_date IS NULL
                      AND (t.enabled = TRUE OR s.enabled = TRUE)
                      AND NOT EXISTS (
                        SELECT 1 FROM staff_document d
                        WHERE d.staff_id = a.id AND d.category_key = %s
                      )
                """, (cat_key,))
                missing = cur.fetchone()[0] or 0
                result.append({"label": cat_label, "missing": missing})
            result.sort(key=lambda x: x["missing"], reverse=True)
            return result
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return []

    @staticmethod
    def get_professional_categories() -> list[str]:
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        cur.execute("""
            SELECT label_fr FROM staff_professional_category
            WHERE enabled = true ORDER BY is_education DESC, label_fr
        """)
        return [r[0] for r in cur.fetchall()]

    @staticmethod
    def get_campuses() -> list[dict[str, Any]]:
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        cur.execute("SELECT id, label FROM larcauth_campus ORDER BY label")
        return [{"id": r[0], "label": r[1]} for r in cur.fetchall()]

    @staticmethod
    def get_campus_full(campus_id: int) -> dict[str, Any] | None:
        conn = db.server_conn
        if not conn:
            return None
        cur = conn.cursor()
        cur.execute("""
            SELECT id, label, adress, city, country, tel_1, email_1
            FROM larcauth_campus WHERE id = %s
        """, (campus_id,))
        r = cur.fetchone()
        if not r:
            return None
        cols = ["id", "label", "adress", "city", "country", "tel_1", "email_1"]
        return dict(zip(cols, r))

    @staticmethod
    def get_available_supervisors(campus_id: int | None = None) -> list[dict[str, Any]]:
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        query = """
            SELECT id, first_name, last_name
            FROM larcauth_aecuser
            WHERE is_active = TRUE AND (type_coordonator = TRUE OR type_director = TRUE)
        """
        params: list[Any] = []
        if campus_id:
            query += " AND fk_campus_id = %s"
            params.append(campus_id)
        query += " ORDER BY last_name, first_name"
        cur.execute(query, params)
        return [{"id": r[0], "full_name": f"{r[2]} {r[1]}"} for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Helpers internes
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_staff(row: tuple) -> dict[str, Any]:
        return {
            "id": row[0], "first_name": row[1], "last_name": row[2], "email": row[3],
            "tel_maison": row[4], "tel_smartphone_1": row[5], "emailperso": row[6],
            "date_of_birth": row[7], "fk_gender_id": row[8],
            "is_active": row[9], "date_entree": row[10], "fk_language": row[11],
            "civility": row[12], "nationality": row[13], "marital_status": row[14],
            "children_count": row[15], "emergency_contact_name": row[16],
            "emergency_contact_phone": row[17], "blood_type": row[18],
            "cnss_number": row[19], "tax_id": row[20],
            "id_document_type": row[21], "id_document_number": row[22],
            "id_document_expiry": row[23], "matricule": row[24],
            "professional_category": row[25], "emp_status": row[26],
            "departure_date": row[27], "departure_reason": row[28],
            "fk_campus_id": row[29], "fk_supervisor_id": row[30],
            "is_teacher": row[31], "is_coordonator": row[32], "is_adm": row[33],
            "is_secretary": row[34], "type_DRH": row[35], "type_Comptable": row[36],
            "type_ressources_Humaines": row[37], "type_Bulletin_Releves": row[38],
            "hire_date": row[39],
            "full_name": f"{row[2]} {row[1]}",
            "is_staff": row[35] is not None or row[36] is not None or row[37] is not None or row[38] is not None,
        }

    @staticmethod
    def _row_to_staff_compact(row: tuple, is_staff: bool) -> dict[str, Any]:
        if is_staff:
            # Staff: 0=id,1=first,2=last,3=email,4=DRH,5=Compt,6=RH,7=Bull,
            # 8=status,9=campus_id,10=pro_cat,11=matricule,12=campus_label,
            # 13=campus_color,14=absent_today
            d = {
                "id": row[0], "first_name": row[1], "last_name": row[2],
                "email": row[3], "full_name": f"{row[2]} {row[1]}",
                "is_staff": True, "emp_status": row[8], "fk_campus_id": row[9],
                "type_DRH": row[4], "type_Comptable": row[5],
                "type_ressources_Humaines": row[6], "type_Bulletin_Releves": row[7],
                "professional_category": row[10], "matricule": row[11],
                "campus_label": row[12], "campus_color": row[13],
                "absent_today": bool(row[14]),
            }
        else:
            # Teachadm: 0=id,1=first,2=last,3=email,4=teach,5=coord,6=adm,
            # 7-10=staff_roles,11=status,12=campus_id,13=pro_cat,14=matricule,
            # 15=campus_label,16=campus_color,17=absent_today
            d = {
                "id": row[0], "first_name": row[1], "last_name": row[2],
                "email": row[3], "full_name": f"{row[2]} {row[1]}",
                "is_staff": False, "emp_status": row[11], "fk_campus_id": row[12],
                "is_teacher": row[4], "is_coordonator": row[5], "is_adm": row[6],
                "professional_category": row[13], "matricule": row[14],
                "campus_label": row[15], "campus_color": row[16],
                "absent_today": bool(row[17]),
            }
        return d

    # ------------------------------------------------------------------
    # Detail categories (sidebar dynamique)
    # ------------------------------------------------------------------

    @staticmethod
    def get_detail_categories() -> list[dict[str, Any]]:
        conn = db.server_conn
        if not conn:
            return _FALLBACK_CATEGORIES
        cur = conn.cursor()
        cur.execute("""
            SELECT category_key, label_fr, icon_name, sort_order
            FROM staff_detail_category
            WHERE enabled = true ORDER BY sort_order
        """)
        rows = cur.fetchall()
        if not rows:
            return _FALLBACK_CATEGORIES
        return [
            {"key": r[0], "label": r[1], "icon": r[2], "order": r[3]}
            for r in rows
        ]

    @staticmethod
    def add_detail_category(category_key: str, label_fr: str,
                            icon_name: str = "folder") -> bool:
        conn = db.server_conn
        if not conn:
            return False
        cur = conn.cursor()
        try:
            cur.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM staff_detail_category")
            next_order = cur.fetchone()[0]
            cur.execute("""
                INSERT INTO staff_detail_category (category_key, label_fr, icon_name, sort_order, created_by, modified_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (category_key) DO UPDATE SET enabled = true, label_fr = %s, icon_name = %s
            """, (category_key, label_fr, icon_name, next_order, label_fr, icon_name))
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def delete_detail_category(category_key: str) -> tuple[bool, str]:
        """Supprime une categorie. Retourne (ok, message). Refuse si documents associes."""
        conn = db.server_conn
        if not conn:
            return False, "Base de donnees non disponible"
        cur = conn.cursor()

        # Verifier si des documents utilisent cette categorie
        cur.execute("SELECT COUNT(*) FROM staff_document WHERE category_key = %s", (category_key,))
        doc_count = cur.fetchone()[0]
        if doc_count > 0:
            return False, f"Impossible de supprimer : {doc_count} document(s) associe(s) a cette categorie."

        cur.execute(
            "UPDATE staff_detail_category SET enabled = false WHERE category_key = %s",
            (category_key,))
        return True, ""

    # ------------------------------------------------------------------
    # Documents (métadonnées)
    # ------------------------------------------------------------------

    @staticmethod
    def get_document_meta(staff_id: int, category_key: str) -> dict[str, dict]:
        """Retourne {file_name: {label, description}} pour tous les fichiers du dossier."""
        conn = db.server_conn
        if not conn:
            return {}
        cur = conn.cursor()
        cur.execute("""
            SELECT file_name, label, description
            FROM staff_document
            WHERE staff_id = %s AND category_key = %s
        """, (staff_id, category_key))
        return {r[0]: {"label": r[1] or "", "description": r[2] or ""} for r in cur.fetchall()}

    @staticmethod
    def save_document_meta(staff_id: int, category_key: str,
                           file_name: str, label: str, description: str) -> bool:
        conn = db.server_conn
        if not conn:
            return False
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO staff_document (staff_id, category_key, file_name, label, description, created_by, modified_by)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (staff_id, category_key, file_name)
                DO UPDATE SET label = %s, description = %s, uploaded_at = NOW()
            """, (staff_id, category_key, file_name, label, description, label, description))
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def delete_document_meta(staff_id: int, category_key: str, file_name: str) -> bool:
        conn = db.server_conn
        if not conn:
            return False
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM staff_document
            WHERE staff_id = %s AND category_key = %s AND file_name = %s
        """, (staff_id, category_key, file_name))
        return True

    # ------------------------------------------------------------------
    # Letters — Modèles et courriers générés
    # ------------------------------------------------------------------

    @staticmethod
    def get_letter_templates(family: str | None = None,
                             search: str = "",
                             active_only: bool = True) -> list[dict[str, Any]]:
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        query = """
            SELECT id, family, code, title, description,
                   body_text, source_code,
                   COALESCE(variables, '{}') AS variables,
                   version, is_active, is_builtin, created_at
            FROM hr_letter_template
        """
        conditions: list[str] = []
        params: list[Any] = []
        if active_only:
            conditions.append("is_active = TRUE")
        if family:
            conditions.append("family = %s")
            params.append(family)
        if search:
            conditions.append("(title ILIKE %s OR description ILIKE %s)")
            like = f"%{search}%"
            params.extend([like, like])
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY is_builtin ASC, family, code"
        cur.execute(query, params)
        cols = ["id", "family", "code", "title", "description",
                "body_text", "source_code",
                "variables", "version", "is_active", "is_builtin", "created_at"]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    @staticmethod
    def get_letter_template_by_id(template_id: int) -> dict[str, Any] | None:
        conn = db.server_conn
        if not conn:
            return None
        cur = conn.cursor()
        cur.execute("""
            SELECT id, family, code, title, description, docx_data,
                   body_text, source_code,
                   COALESCE(variables, '{}') AS variables,
                   version, is_active, is_builtin, created_at
            FROM hr_letter_template WHERE id = %s
        """, (template_id,))
        r = cur.fetchone()
        if not r:
            return None
        cols = ["id", "family", "code", "title", "description", "docx_data",
                "body_text", "source_code",
                "variables", "version", "is_active", "is_builtin", "created_at"]
        return dict(zip(cols, r))

    @staticmethod
    def save_letter_template(data: dict[str, Any]) -> int | None:
        conn = db.server_conn
        if not conn:
            return None
        cur = conn.cursor()
        try:
            if data.get("id"):
                sets = [
                    "title = %s", "description = %s", "docx_data = %s",
                    "variables = %s", "version = version + 1", "updated_at = NOW()",
                ]
                params: list[Any] = [
                    data["title"], data.get("description"), data.get("docx_data"),
                    data.get("variables", []),
                ]
                # body_text : écrit seulement si la clé est présente ; clear_body
                # force NULL (restauration vers le corps fonction d'origine)
                if "body_text" in data:
                    sets.append("body_text = %s")
                    params.append(data["body_text"])
                elif data.get("clear_body"):
                    sets.append("body_text = NULL")
                # source_code : écrit seulement si la clé est présente
                if "source_code" in data:
                    sets.append("source_code = %s")
                    params.append(data["source_code"])
                cur.execute(
                    f"UPDATE hr_letter_template SET {', '.join(sets)} "
                    "WHERE id = %s AND NOT is_builtin",
                    params + [data["id"]])
                return data["id"]
            else:
                cur.execute("""
                    INSERT INTO hr_letter_template (family, code, title, description,
                        body_text, source_code,
                        docx_data, variables, is_builtin, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s)
                    RETURNING id
                """, (data.get("family", "F"), data.get("code", ""), data["title"],
                      data.get("description"), data.get("body_text"),
                      data.get("source_code"), data.get("docx_data"),
                      data.get("variables", []), data.get("created_by")))
                row = cur.fetchone()
                return row[0] if row else None
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def toggle_letter_template(template_id: int, active: bool) -> bool:
        conn = db.server_conn
        if not conn:
            return False
        cur = conn.cursor()
        cur.execute("UPDATE hr_letter_template SET is_active = %s, updated_at = NOW() WHERE id = %s",
                    (active, template_id))
        return True

    @staticmethod
    def save_generated_letter(staff_id: int, template_id: int, file_path: str,
                              reference: str = "", generated_by: int | None = None) -> int | None:
        conn = db.server_conn
        if not conn:
            return None
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO hr_generated_letter (staff_id, template_id, file_path, reference, generated_by)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (staff_id, template_id, file_path, reference, generated_by))
            row = cur.fetchone()
            return row[0] if row else None
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def get_generated_letters(staff_id: int | None = None,
                              limit: int = 50) -> list[dict[str, Any]]:
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        query = """
            SELECT g.id, g.staff_id, g.template_id, g.file_path, g.reference,
                   g.generated_at, g.generated_by, g.status,
                   t.title AS template_title, t.family, t.code,
                   a.first_name, a.last_name
            FROM hr_generated_letter g
            JOIN hr_letter_template t ON t.id = g.template_id
            JOIN larcauth_aecuser a ON a.id = g.staff_id
        """
        params: list[Any] = []
        if staff_id is not None:
            query += " WHERE g.staff_id = %s"
            params.append(staff_id)
        query += " ORDER BY g.generated_at DESC LIMIT %s"
        params.append(limit)
        cur.execute(query, params)
        cols = ["id", "staff_id", "template_id", "file_path", "reference",
                "generated_at", "generated_by", "status", "template_title",
                "family", "code", "first_name", "last_name"]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    @staticmethod
    def update_generated_letter_status(letter_id: int, status: str) -> bool:
        conn = db.server_conn
        if not conn:
            return False
        cur = conn.cursor()
        cur.execute("UPDATE hr_generated_letter SET status = %s WHERE id = %s",
                    (status, letter_id))
        return True

    # ------------------------------------------------------------------
    # Todo / Kanban
    # ------------------------------------------------------------------

    @staticmethod
    def ensure_todo_table():
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS staff_todo (
                    id          SERIAL PRIMARY KEY,
                    staff_id    INT,
                    task_type   VARCHAR(32) DEFAULT 'custom',
                    description TEXT,
                    status      VARCHAR(16) DEFAULT 'todo',
                    assigned_to INT,
                    created_by  INT,
                    created_at  TIMESTAMP DEFAULT NOW(),
                    due_date    DATE,
                    resolved_at TIMESTAMP,
                    resolved_by INT,
                    log         JSONB
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_staff_todo_status ON staff_todo(status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_staff_todo_assigned ON staff_todo(assigned_to)")
            conn.commit()
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            try:
                conn.rollback()
            except Exception:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                pass

    @staticmethod
    def get_todos() -> list[dict[str, Any]]:
        conn = db.server_conn
        if not conn:
            return []
        cur = conn.cursor()
        cur.execute("""
            SELECT t.id, t.staff_id, t.task_type, t.description, t.status,
                   t.assigned_to, t.created_by, t.created_at, t.due_date,
                   t.resolved_at, t.resolved_by, t.log
            FROM staff_todo t
            ORDER BY t.created_at DESC
        """)
        cols = ["id", "staff_id", "task_type", "description", "status",
                "assigned_to", "created_by", "created_at", "due_date",
                "resolved_at", "resolved_by", "log"]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    @staticmethod
    def create_todo(description: str, task_type: str,
                    due_date: str | None = None,
                    staff_id: int | None = None,
                    created_by: int | None = None) -> bool:
        conn = db.server_conn
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO staff_todo (description, task_type, due_date, staff_id, created_by) "
                "VALUES (%s, %s, %s, %s, %s)",
                (description, task_type, due_date, staff_id, created_by))
            conn.commit()
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            conn.rollback()
            return False

    @staticmethod
    def move_todo(task_id: int, new_status: str, comment: str = "",
                  user_id: int = 0) -> bool:
        conn = db.server_conn
        if not conn:
            return False
        import json
        entry = json.dumps({
            "action": new_status,
            "comment": comment,
            "user": user_id,
            "at": datetime.now().isoformat(),
        })
        try:
            cur = conn.cursor()
            if new_status == "doing":
                cur.execute(
                    """UPDATE staff_todo SET status='doing', assigned_to=%s,
                       log = COALESCE(log, '[]'::jsonb) || %s::jsonb
                       WHERE id=%s""",
                    (user_id, entry, task_id))
            elif new_status == "done":
                cur.execute(
                    """UPDATE staff_todo SET status='done', resolved_at=NOW(),
                       resolved_by=%s,
                       log = COALESCE(log, '[]'::jsonb) || %s::jsonb
                       WHERE id=%s""",
                    (user_id, entry, task_id))
            else:
                cur.execute(
                    """UPDATE staff_todo SET status='todo', assigned_to=NULL,
                       resolved_at=NULL, resolved_by=NULL,
                       log = COALESCE(log, '[]'::jsonb) || %s::jsonb
                       WHERE id=%s""",
                    (entry, task_id))
            conn.commit()
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            conn.rollback()
            return False

    @staticmethod
    def delete_todo(task_id: int) -> bool:
        conn = db.server_conn
        if not conn:
            return False
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM staff_todo WHERE id=%s", (task_id,))
            conn.commit()
            return True
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            conn.rollback()
            return False


_FALLBACK_CATEGORIES = [
    {"key": "personal",  "label": "Fiche personnelle",  "icon": "person",      "order": 0},
    {"key": "degrees",   "label": "Diplômes & Langues", "icon": "school",      "order": 1},
    {"key": "contracts", "label": "Contrats",           "icon": "assignment",  "order": 2},
    {"key": "leave",     "label": "Congés",             "icon": "event",       "order": 3},
    {"key": "documents", "label": "Documents",          "icon": "folder",      "order": 4},
    {"key": "letters",   "label": "Courriers",          "icon": "subject",        "order": 5},
    {"key": "events",    "label": "Événements",         "icon": "history",     "order": 6},
]
