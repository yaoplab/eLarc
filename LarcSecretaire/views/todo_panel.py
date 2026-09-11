"""
TodoPanel — Liste de tâches partagée pour le secrétariat.

Kanban simplifié : À faire → En cours → Fait
Chaque tâche est liée à un élève et peut être attribuée à une secrétaire.
"""

import json as _json
from datetime import datetime

from larccommon.design_system import ds
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from larccommon.widgets.skeleton import M3Skeleton
from LarcSecretaire.common.database import db
from LarcSecretaire.common.logger import log
from LarcSecretaire.common.session import UserRole, session
from LarcSecretaire.common.theme import theme_manager
from phibuilder.widgets import (
    M3Button,
    M3Card,
    M3ComboBox,
    M3DateEdit,
    M3DialogButtonBox,
    M3Label,
    M3ScrollArea,
    M3TextEdit,
)
from phibuilder.widgets.button import ButtonVariant
from phibuilder.widgets.card import CardVariant
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QVBoxLayout,
    QWidget,
)

# Types de tâches
TASK_TYPES = {
    "photo": _("sec_main.kpi.no_photo"),
    "parent": _("sec_main.kpi.no_parent"),
    "email": _("sec_main.kpi.no_email"),
    "doc": _("sec_main.kpi.no_doc"),
    "custom": _("todo.custom"),
}

STATUS_LABELS = {
    "todo": _("todo.status.todo"),
    "doing": _("todo.status.doing"),
    "done": _("todo.status.done"),
}


def ensure_todo_table():
    if not db.is_server_connected:
        return
    """Cree la table secretary_todo si elle n existe pas deja."""
    conn = db.server_conn
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS secretary_todo (
                id          SERIAL PRIMARY KEY,
                student_id  INT,
                task_type   VARCHAR(32) DEFAULT 'custom',
                description TEXT,
                status      VARCHAR(16) DEFAULT 'todo',
                assigned_to INT,
                created_by  INT,
                created_at  TIMESTAMP DEFAULT NOW(),
                due_date    DATE,
                resolved_at TIMESTAMP,
                resolved_by INT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_todo_status ON secretary_todo(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_todo_assigned ON secretary_todo(assigned_to)")
        # Migrations: colonnes ajoutées après la création initiale
        for col, col_type in [("created_by", "INT"), ("due_date", "DATE"), ("log", "JSONB")]:
            cur.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='secretary_todo' AND column_name='{col}'
                    ) THEN
                        ALTER TABLE secretary_todo ADD COLUMN {col} {col_type};
                    END IF;
                END $$;
            """)
        conn.commit()
    except Exception as e:
        from larccommon.error_reporting import get_reporter
        get_reporter().report_exception()
        log(f"ensure_todo_table: {e}")
        try:
            conn.rollback()
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass


class TodoPanel(QWidget):
    """Panneau Kanban des tâches de secrétariat."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: dict[str, list[dict]] = {"todo": [], "doing": [], "done": []}
        ensure_todo_table()
        self._init_ui()
        self._load()

    def _init_ui(self):
        p = ds.p
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_md)

        # Titre + bouton Ajouter
        hdr = QHBoxLayout()
        title = M3Label(_("todo.title"), style="title_medium")
        hdr.addWidget(title)
        hdr.addStretch()
        add_btn = M3Button("+ " + _("todo.add"), variant=ButtonVariant.FILLED)
        add_btn.setMinimumHeight(ds.field_height + ds.space_xs)
        add_btn.clicked.connect(self._on_add)
        hdr.addWidget(add_btn)
        layout.addLayout(hdr)

        # 3 colonnes Kanban
        cols_layout = QHBoxLayout()
        cols_layout.setSpacing(ds.space_md)

        self._columns: dict[str, QVBoxLayout] = {}
        self._col_widgets: dict[str, QWidget] = {}
        self._count_labels: dict[str, M3Label] = {}

        statuses = [
            ("todo", _("todo.status.todo"), "error"),
            ("doing", _("todo.status.doing"), "tertiary"),
            ("done", _("todo.status.done"), "success"),
        ]
        for key, label, color in statuses:
            col_w = QWidget()
            col_w.setAttribute(Qt.WA_StyledBackground, True)
            col_w.setStyleSheet(f"background: {p.surface_variant}; border-radius: {ds.radius_md}px;")
            col_l = QVBoxLayout(col_w)
            col_l.setContentsMargins(0, ds.space_sm, 0, ds.space_sm)
            col_l.setSpacing(0)
            # En-tête (fixe)
            ch_w = QWidget()
            ch_w.setAttribute(Qt.WA_StyledBackground, True)
            ch_w.setStyleSheet(f"background: transparent; padding: 0 {ds.space_sm}px;")
            ch = QHBoxLayout(ch_w)
            ch.setContentsMargins(0, 0, 0, ds.space_xs)
            chdr = M3Label(label, style="title_small")
            chdr.setStyleSheet(f"color: {getattr(p, color)}; font-weight: bold;")
            ch.addWidget(chdr)
            ch.addStretch()
            cnt = M3Label("0", style="headline_small")
            cnt.setStyleSheet(f"color: {getattr(p, color)}; font-weight: bold;")
            ch.addWidget(cnt)
            col_l.addWidget(ch_w)
            self._count_labels[key] = cnt
            # Zone de cartes scrollable
            scroll = M3ScrollArea()
            scroll.setWidgetResizable(True)
            # PAS « transparent » : palette noire héritée sinon (bug contraste 2026-08-16)
            scroll.setStyleSheet(f"M3ScrollArea {{ background: {p.background}; border: none; }}")
            scroll.viewport().setStyleSheet(f"background: {p.background};")
            cards_w = QWidget()
            cards_w.setAttribute(Qt.WA_StyledBackground, True)
            cards_w.setStyleSheet(f"background: {p.background};")
            cards_layout = QVBoxLayout(cards_w)
            cards_layout.setContentsMargins(ds.space_sm, 0, ds.space_sm, 0)
            cards_layout.setSpacing(ds.space_xs)
            scroll.setWidget(cards_w)
            col_l.addWidget(scroll, 1)
            self._columns[key] = cards_layout
            self._col_widgets[key] = col_w
            cols_layout.addWidget(col_w, 1)

        layout.addLayout(cols_layout, 1)

        # Skeleton loading
        self._loading_skeleton = M3Skeleton.table(self, rows=5, cols=3)
        self._loading_skeleton.set_label(_("common.label.loading"))
        self._loading_skeleton.hide()
        layout.addWidget(self._loading_skeleton)

        ds.theme_changed.connect(self._restyle)

    @safe_slot("TodoPanel._restyle")
    def _restyle(self):
        p = ds.p
        for key, col_w in self._col_widgets.items():
            col_w.setStyleSheet(f"background: {p.surface_variant}; border-radius: {ds.radius_md}px;")

    # ── Données ──

    def _load(self):
        if not db.is_server_connected:
            return
        if getattr(self, "_loading", False):
            return
        self._loading = True
        try:
            conn = db.server_conn
            if not conn:
                return
            for key in self._col_widgets:
                self._col_widgets[key].hide()
            self._loading_skeleton.show()
            self._loading_skeleton.start()
            QApplication.processEvents()
            is_admin = session.role in (UserRole.ADMIN,)
            cur = conn.cursor()
            sql_base = """
                SELECT t.id, t.student_id, t.task_type, t.description, t.status,
                       t.assigned_to, t.created_at, t.due_date, t.resolved_at, t.log,
                       COALESCE(aec.last_name || ' ' || aec.first_name, '') AS student_name,
                       COALESCE(c.label, '') AS class_label,
                       COALESCE(creator.last_name || ' ' || creator.first_name, '') AS creator_name,
                       COALESCE(assignee.last_name || ' ' || assignee.first_name, '') AS assignee_name
                FROM secretary_todo t
                LEFT JOIN larcauth_aecuser aec ON aec.id = t.student_id
                LEFT JOIN larcauth_classroom c ON c.id = (
                    SELECT s_classroom_id FROM larcauth_student WHERE aecuser_ptr_id = t.student_id LIMIT 1
                )
                LEFT JOIN larcauth_aecuser creator ON creator.id = t.created_by
                LEFT JOIN larcauth_aecuser assignee ON assignee.id = t.assigned_to
            """
            if is_admin:
                cur.execute(sql_base + " ORDER BY t.created_at DESC")
            else:
                cur.execute(
                    sql_base + " WHERE (t.created_by = %s OR t.assigned_to = %s) ORDER BY t.created_at DESC",
                    (session.user_id, session.user_id))
            rows = cur.fetchall()
            self._tasks = {"todo": [], "doing": [], "done": []}
            for r in rows:
                raw_log = r[9]
                log_list = _json.loads(raw_log) if isinstance(raw_log, str) else (raw_log or [])
                task = {"id": r[0], "student_id": r[1], "type": r[2], "desc": r[3] or "",
                        "status": r[4], "assigned_to": r[5], "created_at": r[6],
                        "due_date": r[7], "resolved_at": r[8], "log": log_list,
                        "student_name": r[10] or "", "class_label": r[11] or "",
                        "creator_name": r[12] or "", "assignee_name": r[13] or ""}
                if task["status"] in self._tasks:
                    self._tasks[task["status"]].append(task)
            self._populate()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"TodoPanel._load: {e}")
        finally:
            self._loading_skeleton.stop()
            self._loading_skeleton.hide()
            for key in self._col_widgets:
                self._col_widgets[key].show()
            self._loading = False

    def _populate(self):
        """Reconstruit les cartes dans chaque colonne."""
        p = ds.p
        icon_sz = ds.icon_sm
        colors = {"todo": p.error, "doing": p.tertiary, "done": p.success}
        for status_key in ("todo", "doing", "done"):
            layout = self._columns[status_key]
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            tasks = self._tasks.get(status_key, [])
            self._count_labels[status_key].setText(str(len(tasks)))
            for task in tasks:
                card = M3Card(theme=theme_manager.phi_theme, variant=CardVariant.ELEVATED)
                card.setStyleSheet(
                    f"M3Card {{ background: {p.surface}; border: 1px solid {p.outline_variant}; "
                    f"border-radius: {ds.radius_sm}px; }}")
                cl = card.content_layout()
                cl.setSpacing(ds.space_xs)
                cl.setContentsMargins(ds.space_sm, ds.space_sm, ds.space_sm, ds.space_sm)
                # Type (seulement si pertinent, pas pour custom)
                ttype = TASK_TYPES.get(task["type"], "")
                if ttype and task["type"] != "custom":
                    type_lbl = M3Label(ttype, style="label_small")
                    type_lbl.setStyleSheet(f"color: {colors.get(status_key, p.primary)}; font-weight: bold;")
                    cl.addWidget(type_lbl)
                name_lbl = M3Label(task["student_name"] or f"#{task['student_id']}", style="body_medium")
                name_lbl.setStyleSheet(f"color: {p.text_strong}; font-weight: bold;")
                cl.addWidget(name_lbl)
                if task["class_label"]:
                    cls_lbl = M3Label(task["class_label"], style="body_small")
                    cls_lbl.setStyleSheet(f"color: {p.text_strong};")
                    cl.addWidget(cls_lbl)
                # Dates
                dates_row = QHBoxLayout()
                dates_row.setSpacing(ds.space_md)
                created = task.get("created_at")
                creator = task.get("creator_name", "")
                if created:
                    if hasattr(created, 'strftime'):
                        date_str = created.strftime("%d/%m %H:%M")
                    else:
                        date_str = str(created)[:16]
                    txt = date_str + (f" · {creator}" if creator else "")
                    date_lbl = M3Label(txt, style="label_small")
                    date_lbl.setStyleSheet(f"color: {p.text_disabled};")
                    dates_row.addWidget(date_lbl)
                due = task.get("due_date")
                if due:
                    if hasattr(due, 'strftime'):
                        due_str = due.strftime("%d/%m")
                    else:
                        due_str = str(due)[:10]
                    due_lbl = M3Label("⏰ " + due_str, style="label_small")
                    overdue = (hasattr(due, 'strftime') and due.strftime("%Y-%m-%d") < QDate.currentDate().toString("yyyy-MM-dd"))
                    due_color = p.error if overdue else p.tertiary
                    due_lbl.setStyleSheet(f"color: {due_color}; font-weight: bold;")
                    dates_row.addWidget(due_lbl)
                dates_row.addStretch()
                cl.addLayout(dates_row)
                # Log (commentaires des étapes précédentes)
                log_entries = task.get("log")
                if log_entries and isinstance(log_entries, list) and len(log_entries) > 0:
                    log_w = QWidget()
                    log_w.setAttribute(Qt.WA_StyledBackground, True)
                    log_w.setStyleSheet(f"background: {p.surface_variant}; border-radius: {ds.radius_xs}px; "
                                       f"padding: {ds.space_xxs}px; margin-top: {ds.space_xxs}px;")
                    log_l = QVBoxLayout(log_w)
                    log_l.setSpacing(ds.border_width * 2)
                    for le in log_entries[-3:]:  # 3 derniers commentaires
                        if isinstance(le, dict) and le.get("comment"):
                            status_icon = {"doing": "▶", "done": "✓", "todo": "←"}.get(le.get("action", ""), "")
                            txt = f"{status_icon} {le['comment']}"
                            lbl = M3Label(txt, style="label_small")
                            lbl.setStyleSheet(f"color: {p.text_strong}; font-size: {ds.font_label_sm}px;")
                            lbl.setWordWrap(True)
                            log_l.addWidget(lbl)
                    cl.addWidget(log_w)
                # Description
                if task.get("desc"):
                    desc_lbl = M3Label(task["desc"][:60], style="body_small")
                    desc_lbl.setStyleSheet(f"color: {p.text_strong};")
                    desc_lbl.setWordWrap(True)
                    cl.addWidget(desc_lbl)
                if status_key == "done" and task.get("resolved_at"):
                    resolved = task["resolved_at"]
                    if hasattr(resolved, 'strftime'):
                        res_str = resolved.strftime("%d/%m %H:%M")
                    else:
                        res_str = str(resolved)[:16]
                    res_lbl = M3Label("✓ " + res_str, style="label_small")
                    res_lbl.setStyleSheet(f"color: {p.success}; font-weight: bold;")
                    cl.addWidget(res_lbl)
                # Boutons d'action
                btn_row = QHBoxLayout()
                btn_row.setSpacing(ds.space_xxs)
                if status_key == "todo":
                    take_btn = M3Button(_("todo.take"), variant=ButtonVariant.TONAL)
                    take_btn.setFixedHeight(ds.table_row_min + ds.space_xs)
                    take_btn.clicked.connect(lambda checked, tid=task["id"]: self._move(tid, "doing"))
                    btn_row.addWidget(take_btn)
                elif status_key == "doing":
                    if task.get("assigned_to") == session.user_id:
                        done_btn = M3Button(_("todo.resolve"), variant=ButtonVariant.FILLED)
                        done_btn.setFixedHeight(ds.table_row_min + ds.space_xs)
                        done_btn.clicked.connect(lambda checked, tid=task["id"]: self._move(tid, "done"))
                        btn_row.addWidget(done_btn)
                    back_btn = M3Button(_("todo.back"), variant=ButtonVariant.OUTLINED)
                    back_btn.setFixedHeight(ds.table_row_min + ds.space_xs)
                    back_btn.clicked.connect(lambda checked, tid=task["id"]: self._move(tid, "todo"))
                    btn_row.addWidget(back_btn)
                elif status_key == "done":
                    reopen_btn = M3Button(_("todo.reopen"), variant=ButtonVariant.OUTLINED)
                    reopen_btn.setFixedHeight(ds.table_row_min + ds.space_xs)
                    reopen_btn.clicked.connect(lambda checked, t=task: self._reopen(t))
                    btn_row.addWidget(reopen_btn)
                btn_row.addStretch()
                # Bouton supprimer (uniquement les tâches résolues)
                if status_key == "done":
                    del_btn = M3Button("✕", variant=ButtonVariant.TEXT)
                    del_btn.setFixedSize(ds.space_md + ds.space_xxs, ds.space_md + ds.space_xxs)
                    del_btn.setCursor(Qt.PointingHandCursor)
                    del_btn.setToolTip(_("todo.delete"))
                    del_btn.setStyleSheet(
                        f"M3Button {{ color: {p.text_disabled}; border: none; background: transparent; "
                        f"font-size: {ds.font_body_sm}px; }}"
                        f"M3Button:hover {{ color: {p.error}; }}")
                    del_btn.clicked.connect(lambda checked, tid=task["id"]: self._delete(tid))
                    btn_row.addWidget(del_btn)
                cl.addLayout(btn_row)
                layout.addWidget(card)
            layout.addStretch()

    def _ask_comment(self, title: str) -> str:
        """Demande un commentaire optionnel, retourne la chaine (vide si annule ou vide)."""
        text, ok = QInputDialog.getText(self, title, _("todo.comment_prompt"))
        return text.strip() if ok and text.strip() else ""

    @safe_slot("TodoPanel._move")
    def _move(self, task_id: int, new_status: str):
        if not db.is_server_connected:
            return
        comment = self._ask_comment(_("todo.comment_title"))
        conn = db.server_conn
        if not conn:
            return
        entry = _json.dumps({
            "action": new_status,
            "comment": comment,
            "user": session.user_id,
            "at": datetime.now().isoformat(),
        })
        try:
            cur = conn.cursor()
            if new_status == "doing":
                cur.execute(
                    """UPDATE secretary_todo SET status='doing', assigned_to=%s,
                       log = COALESCE(log, '[]'::jsonb) || %s::jsonb
                       WHERE id=%s""",
                    (session.user_id, entry, task_id))
            elif new_status == "done":
                cur.execute(
                    """UPDATE secretary_todo SET status='done', resolved_at=NOW(),
                       resolved_by=%s,
                       log = COALESCE(log, '[]'::jsonb) || %s::jsonb
                       WHERE id=%s""",
                    (session.user_id, entry, task_id))
            else:
                cur.execute(
                    """UPDATE secretary_todo SET status='todo', assigned_to=NULL,
                       resolved_at=NULL, resolved_by=NULL,
                       log = COALESCE(log, '[]'::jsonb) || %s::jsonb
                       WHERE id=%s""",
                    (entry, task_id))
            conn.commit()
            self._load()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            conn.rollback()
            log(f"TodoPanel._move: {e}")

    @safe_slot("TodoPanel._reopen")
    def _reopen(self, task: dict):
        """Cree une NOUVELLE tache (copie) au lieu de modifier l'ancienne."""
        self._create_task(
            task.get("student_id"),
            task.get("type", "custom"),
            task.get("desc", ""),
            due_date=None)
        # Garder l'ancienne dans la colonne "Fait"

    @safe_slot("TodoPanel._delete")
    def _delete(self, task_id: int):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM secretary_todo WHERE id=%s", (task_id,))
            conn.commit()
            self._load()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            conn.rollback()
            log(f"TodoPanel._delete: {e}")

    @safe_slot("TodoPanel._on_add")
    def _on_add(self):
        """Ouvre un dialogue pour créer une tâche manuelle."""
        dlg = QDialog(self)
        dlg.setWindowTitle(_("todo.add"))
        dlg.setMinimumWidth(ds.window_width * 3 // 8)
        dlg.setStyleSheet(f"background: {ds.p.surface};")
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_sm)

        layout.addWidget(M3Label(_("todo.add_desc"), style="title_small"))

        # Type de tâche
        type_lbl = M3Label(_("todo.type_label"), style="label_small")
        type_lbl.setStyleSheet(f"color: {ds.p.text_strong}; font-weight: bold;")
        layout.addWidget(type_lbl)
        type_combo = M3ComboBox()
        type_combo.setMinimumWidth(ds.workspace_sidebar_width - ds.space_md)
        type_combo.setFixedHeight(ds.field_height)
        type_keys = []
        for key, label in TASK_TYPES.items():
            type_combo.addItem(label, key)
            type_keys.append(key)
        layout.addWidget(type_combo)

        desc_inp = M3TextEdit()
        desc_inp.setPlaceholderText(_("todo.desc_placeholder"))
        desc_inp.setFixedHeight(ds.space_md * 4)
        desc_inp.setStyleSheet(ds.flat_input_qss())
        layout.addWidget(desc_inp)

        # Date d'échéance
        due_row = QHBoxLayout()
        due_row.setSpacing(ds.space_sm)
        due_lbl = M3Label(_("todo.due_date"), style="label_small")
        due_lbl.setStyleSheet(f"color: {ds.p.text_strong}; font-weight: bold;")
        due_row.addWidget(due_lbl)
        due_inp = M3DateEdit()
        due_inp.setMinimumWidth(ds.icon_md * 5)
        due_inp.setDisplayFormat("yyyy-MM-dd")
        due_inp.setCalendarPopup(True)
        due_inp.setDate(QDate.currentDate().addDays(7))
        due_inp.setFixedHeight(ds.field_height)
        due_inp.setStyleSheet(
            f"QDateEdit {{ border: 1px solid {ds.p.outline}; border-radius: {ds.radius_xs}px; "
            f"padding: {ds.space_xxs}px {ds.space_xs}px; color: {ds.p.text_strong}; "
            f"background: {ds.p.surface}; }}"
            f"QDateEdit QLineEdit {{ color: {ds.p.text_strong}; background: {ds.p.surface}; }}")
        due_row.addWidget(due_inp)
        due_row.addStretch()
        layout.addLayout(due_row)

        buttons = M3DialogButtonBox(M3DialogButtonBox.Ok | M3DialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.Accepted:
            return
        desc = desc_inp.toPlainText().strip()
        if not desc:
            return
        chosen_type = type_combo.currentData() or "custom"
        due_str = due_inp.date().toString("yyyy-MM-dd") if due_inp.date().isValid() else None
        self._create_task(None, chosen_type, desc, due_str)

    def _create_task(self, student_id: int | None, task_type: str, desc: str, due_date: str | None = None):
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO secretary_todo (student_id, task_type, description, created_by, due_date) "
                "VALUES (%s, %s, %s, %s, %s)",
                (student_id, task_type, desc, session.user_id, due_date))
            conn.commit()
            self._load()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            conn.rollback()
            log(f"TodoPanel._create_task: {e}")

    def add_task_for_student(self, student_id: int, task_type: str, student_name: str = ""):
        """Ajoute une tâche pour un élève (appelé depuis l'extérieur, ex: KPI click)."""
        desc = f"{TASK_TYPES.get(task_type, task_type)} — {student_name}" if student_name else TASK_TYPES.get(task_type, task_type)
        self._create_task(student_id, task_type, desc)

    def reload(self):
        self._load()
