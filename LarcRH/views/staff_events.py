"""StaffEventDialog → wrapper pour EventGeneratorDialog (polymorphe).

Refactorisé pour utiliser EventGeneratorDialog unifiée (Student/Staff).
"""
from PySide6.QtWidgets import QMessageBox

from larccommon.dialogs import EventGeneratorDialog, EventData, MemberType
from larccommon.database import db
from larccommon.l10n import _
from larccommon.logger import log
from larccommon.session import session


def open_staff_event_generator(staff_data: dict, parent=None):
    """
    Ouvre le wizard d'événement pour un staff member.

    Args:
        staff_data: dict avec au moins 'id' et 'full_name'
        parent: widget parent pour le dialogue modal
    """
    staff_id = staff_data.get("id")
    if not staff_id:
        QMessageBox.warning(parent, _("common.error"), _("staff.error_invalid"))
        return

    # Vérifier que le jour est ouvré
    if not _is_working_day():
        QMessageBox.warning(
            parent,
            _("common.error"),
            _("event.error_not_working_day"),
        )
        return

    # Ouvrir le wizard polymorphe
    dlg = EventGeneratorDialog(staff_id, MemberType.STAFF, parent)
    dlg.event_created.connect(lambda evt: _insert_staff_event(evt, parent))
    dlg.exec()


def _is_working_day() -> bool:
    """Vérifie que le jour courant est ouvré."""
    try:
        from datetime import datetime
        conn = db.server_conn
        if not conn:
            return True

        today = datetime.now().date()
        cur = conn.cursor()
        cur.execute(
            "SELECT working_day FROM larcauth_agenda WHERE agenda_date = %s",
            (today,),
        )
        row = cur.fetchone()
        return bool(row[0]) if row else True
    except Exception as e:
        log(f"_is_working_day: {e}")
        return True


def _insert_staff_event(evt: EventData, parent=None):
    """Insère l'événement staff créé dans la table staff_event."""
    try:
        conn = db.server_conn
        if not conn:
            QMessageBox.critical(parent, _("common.error"), _("common.db_error"))
            return

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO staff_event
            (staff_id, event_type, event_at, note, created_by, created_location, source)
            VALUES (%s, %s, %s, %s, %s, %s, 'EventGeneratorDialog')
            """,
            (
                evt.member_id,
                evt.type_path,
                evt.event_at,
                evt.note,
                session.user_id,
                evt.created_location,
            ),
        )
        conn.commit()

        QMessageBox.information(parent, _("common.success"), _("event.saved_success"))
        _refresh_parent_grid(parent)

    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log(f"_insert_staff_event: {e}")
        QMessageBox.critical(parent, _("common.error"), _("event.save_error"))
        if conn:
            conn.rollback()


def _refresh_parent_grid(widget):
    """Remonte l'arborescence pour trouver et rafraîchir StaffGrid."""
    while widget:
        from LarcRH.views.staff_grid import StaffGrid
        if isinstance(widget, StaffGrid):
            widget.refresh()
            return
        widget = widget.parent() if hasattr(widget, "parent") else None
