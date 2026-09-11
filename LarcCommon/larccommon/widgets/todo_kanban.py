"""TodoKanban — Kanban partagé (À faire → En cours → Fait).

Composant réutilisable par toutes les apps Larc.
Chaque app fournit ses callbacks DB et sa configuration.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QInputDialog, QVBoxLayout, QWidget,
)

from larccommon.design_system import ds
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from phibuilder.phi.scale import SpacingToken
from phibuilder.widgets.card import M3Card, CardVariant
from phibuilder.widgets.button import M3Button, ButtonVariant
from phibuilder.widgets.combo import M3ComboBox
from phibuilder.widgets.dateedit import M3DateEdit
from phibuilder.widgets.dialogbuttonbox import M3DialogButtonBox
from phibuilder.widgets.label import M3Label
from phibuilder.widgets.scrollarea import M3ScrollArea
from phibuilder.widgets.textedit import M3TextEdit

STATUSES = [
    ("todo",  "À faire",  "error"),
    ("doing", "En cours", "tertiary"),
    ("done",  "Fait",     "success"),
]

# ── Callback signatures ──
# load_fn() -> list[dict]
# create_fn(description, task_type, due_date, entity_id) -> bool
# move_fn(task_id, new_status, comment, user_id) -> bool
# delete_fn(task_id) -> bool
# reopen_fn(task, user_id) -> bool

class TodoKanban(QWidget):
    """Kanban générique — 3 colonnes, personnalisable par callback."""

    def __init__(
        self,
        *,
        load_fn: Callable[[], list[dict]],
        create_fn: Callable[[str, str, str | None, int | None], bool],
        move_fn: Callable[[int, str, str, int], bool],
        delete_fn: Callable[[int], bool],
        reopen_fn: Callable[[dict, int], bool] | None = None,
        task_types: dict[str, str] | None = None,
        user_id: int = 0,
        parent=None,
    ):
        """
        Args:
            load_fn: retourne la liste des tâches [{id, desc, status, type, created_at, ...}]
            create_fn: (desc, task_type, due_date, entity_id) -> bool
            move_fn: (task_id, new_status, comment, user_id) -> bool
            delete_fn: (task_id) -> bool
            reopen_fn: (task, user_id) -> bool (optionnel, sinon crée une copie)
            task_types: dict {key: label} (ex: {"custom": "Manuel", "urgent": "Urgent"})
            user_id: ID de l'utilisateur courant
        """
        super().__init__(parent)
        self._load_fn = load_fn
        self._create_fn = create_fn
        self._move_fn = move_fn
        self._delete_fn = delete_fn
        self._reopen_fn = reopen_fn
        self._task_types = task_types or {"custom": "Manuel"}
        self._user_id = user_id
        self._tasks: dict[str, list[dict]] = {"todo": [], "doing": [], "done": []}
        self._init_ui()
        self.reload()

    def _init_ui(self):
        p = ds.p
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_md)

        # ── Header ──
        hdr = QHBoxLayout()
        title = M3Label("Tâches RH", style="title_medium")
        hdr.addWidget(title)
        hdr.addStretch()
        add_btn = M3Button("+ Ajouter", variant=ButtonVariant.FILLED)
        add_btn.setMinimumHeight(ds.field_height + ds.space_xs)
        add_btn.clicked.connect(self._on_add)
        hdr.addWidget(add_btn)
        layout.addLayout(hdr)

        # ── 3 colonnes ──
        cols_layout = QHBoxLayout()
        cols_layout.setSpacing(ds.space_md)

        self._columns: dict[str, QVBoxLayout] = {}
        self._col_widgets: dict[str, QWidget] = {}
        self._count_labels: dict[str, M3Label] = {}

        for key, label_text, color in STATUSES:
            col_w = QWidget()
            col_w.setAttribute(Qt.WA_StyledBackground, True)
            col_w.setStyleSheet(
                f"background: {p.surface_variant}; border-radius: {ds.radius_md}px;")
            col_l = QVBoxLayout(col_w)
            col_l.setContentsMargins(0, ds.space_sm, 0, ds.space_sm)
            col_l.setSpacing(0)

            # En-tête colonne
            ch_w = QWidget()
            ch_w.setAttribute(Qt.WA_StyledBackground, True)
            ch_w.setStyleSheet(f"background: transparent; padding: 0 {ds.space_sm}px;")
            ch = QHBoxLayout(ch_w)
            ch.setContentsMargins(0, 0, 0, ds.space_xs)
            chdr = M3Label(label_text, style="title_small")
            chdr.setStyleSheet(f"color: {getattr(p, color)}; font-weight: bold;")
            ch.addWidget(chdr)
            ch.addStretch()
            cnt = M3Label("0", style="headline_small")
            cnt.setStyleSheet(f"color: {getattr(p, color)}; font-weight: bold;")
            ch.addWidget(cnt)
            col_l.addWidget(ch_w)
            self._count_labels[key] = cnt

            # Zone scrollable des cartes
            scroll = M3ScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("M3ScrollArea { background: transparent; border: none; }")
            scroll.viewport().setStyleSheet("background: transparent;")
            cards_w = QWidget()
            cards_w.setAttribute(Qt.WA_StyledBackground, True)
            cards_w.setStyleSheet("background: transparent;")
            cards_layout = QVBoxLayout(cards_w)
            cards_layout.setContentsMargins(ds.space_sm, 0, ds.space_sm, 0)
            cards_layout.setSpacing(ds.space_xs)
            scroll.setWidget(cards_w)
            col_l.addWidget(scroll, 1)
            self._columns[key] = cards_layout
            self._col_widgets[key] = col_w
            cols_layout.addWidget(col_w, 1)

        layout.addLayout(cols_layout, 1)
        ds.theme_changed.connect(self._restyle)

    @safe_slot("TodoKanban._restyle")
    def _restyle(self):
        p = ds.p
        for col_w in self._col_widgets.values():
            col_w.setStyleSheet(
                f"background: {p.surface_variant}; border-radius: {ds.radius_md}px;")

    # ── Data ──

    def reload(self):
        try:
            tasks = self._load_fn() or []
            self._tasks = {"todo": [], "doing": [], "done": []}
            for t in tasks:
                status = t.get("status", "todo")
                if status in self._tasks:
                    self._tasks[status].append(t)
            self._populate()
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            import traceback
            traceback.print_exc()

    def _populate(self):
        p = ds.p
        s = theme_manager.font_size
        colors = {"todo": p.error, "doing": p.tertiary, "done": p.success}
        for key in ("todo", "doing", "done"):
            layout = self._columns[key]
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            tasks = self._tasks.get(key, [])
            self._count_labels[key].setText(str(len(tasks)))
            for task in tasks:
                card = M3Card(theme=theme_manager.phi_theme, variant=CardVariant.ELEVATED)
                card.setStyleSheet(
                    f"M3Card {{ background: {p.surface}; "
                    f"border: 1px solid {p.outline_variant}; "
                    f"border-radius: {ds.radius_sm}px; }}")
                cl = card.content_layout()
                cl.setSpacing(ds.space_xxs)
                cl.setContentsMargins(ds.space_sm, ds.space_sm, ds.space_sm, ds.space_sm)

                # Type badge
                ttype = task.get("type", "custom")
                if ttype in self._task_types:
                    badge = M3Label(self._task_types[ttype], style="label_small")
                    badge.setStyleSheet(
                        f"color: {colors.get(key, p.primary)}; font-weight: bold;")
                    cl.addWidget(badge)

                # Description
                desc = task.get("desc") or task.get("description") or ""
                if desc:
                    desc_lbl = M3Label(desc[:100], style="body_medium")
                    desc_lbl.setStyleSheet(f"color: {p.text_strong}; font-weight: bold;")
                    desc_lbl.setWordWrap(True)
                    cl.addWidget(desc_lbl)

                # Meta row: date + author
                meta = []
                created = task.get("created_at")
                if created:
                    if hasattr(created, "strftime"):
                        meta.append(created.strftime("%d/%m %H:%M"))
                    else:
                        meta.append(str(created)[:16])
                creator = task.get("creator_name", "")
                if creator:
                    meta.append(creator)
                if meta:
                    meta_lbl = M3Label(" · ".join(meta), style="label_small")
                    meta_lbl.setStyleSheet(f"color: {p.text_strong};")
                    cl.addWidget(meta_lbl)

                # Due date
                due = task.get("due_date")
                if due:
                    if hasattr(due, "strftime"):
                        due_str = due.strftime("%d/%m")
                    else:
                        due_str = str(due)[:10]
                    overdue = (
                        hasattr(due, "strftime")
                        and due.strftime("%Y-%m-%d")
                        < QDate.currentDate().toString("yyyy-MM-dd")
                    )
                    due_lbl = M3Label("⏰ " + due_str, style="label_small")
                    due_lbl.setStyleSheet(
                        f"color: {p.error if overdue else p.tertiary}; font-weight: bold;")
                    cl.addWidget(due_lbl)

                # Done timestamp
                if key == "done" and task.get("resolved_at"):
                    res = task["resolved_at"]
                    if hasattr(res, "strftime"):
                        res_str = res.strftime("%d/%m %H:%M")
                    else:
                        res_str = str(res)[:16]
                    res_lbl = M3Label("✓ " + res_str, style="label_small")
                    res_lbl.setStyleSheet(f"color: {p.success}; font-weight: bold;")
                    cl.addWidget(res_lbl)

                # Action buttons
                btn_row = QHBoxLayout()
                btn_row.setSpacing(ds.space_xxs)
                if key == "todo":
                    take = M3Button("Prendre", variant=ButtonVariant.TONAL)
                    take.setFixedHeight(ds.field_height - ds.space_xxs)
                    take.clicked.connect(
                        lambda ch, tid=task["id"]: self._move_task(tid, "doing"))
                    btn_row.addWidget(take)
                elif key == "doing":
                    done = M3Button("Terminer", variant=ButtonVariant.FILLED)
                    done.setFixedHeight(ds.field_height - ds.space_xxs)
                    done.clicked.connect(
                        lambda ch, tid=task["id"]: self._move_task(tid, "done"))
                    btn_row.addWidget(done)
                    back = M3Button("← Retour", variant=ButtonVariant.OUTLINED)
                    back.setFixedHeight(ds.field_height - ds.space_xxs)
                    back.clicked.connect(
                        lambda ch, tid=task["id"]: self._move_task(tid, "todo"))
                    btn_row.addWidget(back)
                elif key == "done":
                    reopen = M3Button("Rouvrir", variant=ButtonVariant.OUTLINED)
                    reopen.setFixedHeight(ds.field_height - ds.space_xxs)
                    reopen.clicked.connect(
                        lambda ch, t=task: self._reopen_task(t))
                    btn_row.addWidget(reopen)
                    del_btn = M3Button("Suppr.", variant=ButtonVariant.TEXT)
                    del_btn.setFixedHeight(ds.field_height - ds.space_xxs)
                    del_btn.setCursor(Qt.PointingHandCursor)
                    del_btn.clicked.connect(
                        lambda ch, tid=task["id"]: self._delete_task(tid))
                    btn_row.addWidget(del_btn)
                btn_row.addStretch()
                cl.addLayout(btn_row)
                layout.addWidget(card)
            layout.addStretch()

    # ── Actions ──

    @safe_slot("TodoKanban._on_add")
    def _on_add(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Nouvelle tâche")
        dlg.setMinimumWidth(ds.window_width // 3)
        dlg.setStyleSheet(f"background: {ds.p.surface};")
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_sm)

        layout.addWidget(M3Label("Nouvelle tâche", style="title_small"))

        type_combo = M3ComboBox()
        type_combo.setFixedHeight(ds.field_height)
        for key, label in self._task_types.items():
            type_combo.addItem(label, key)
        layout.addWidget(type_combo)

        desc = M3TextEdit()
        desc.setPlaceholderText("Description de la tâche...")
        desc.setFixedHeight(ds.space_md * 4)
        desc.setStyleSheet(ds.flat_input_qss())
        layout.addWidget(desc)

        due_inp = M3DateEdit()
        due_inp.setDisplayFormat("yyyy-MM-dd")
        due_inp.setCalendarPopup(True)
        due_inp.setDate(QDate.currentDate().addDays(7))
        due_inp.setFixedHeight(ds.field_height)
        layout.addWidget(due_inp)

        buttons = M3DialogButtonBox(M3DialogButtonBox.Ok | M3DialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.Accepted:
            return
        text = desc.toPlainText().strip()
        if not text:
            return
        task_type = type_combo.currentData() or "custom"
        due = due_inp.date().toString("yyyy-MM-dd") if due_inp.date().isValid() else None
        if self._create_fn(text, task_type, due, None):
            self.reload()

    @safe_slot("TodoKanban._move_task")
    def _move_task(self, task_id: int, new_status: str):
        text, ok = QInputDialog.getText(self, "Commentaire", "Commentaire (optionnel) :")
        comment = text.strip() if ok else ""
        if self._move_fn(task_id, new_status, comment, self._user_id):
            self.reload()

    @safe_slot("TodoKanban._delete_task")
    def _delete_task(self, task_id: int):
        if self._delete_fn(task_id):
            self.reload()

    @safe_slot("TodoKanban._reopen_task")
    def _reopen_task(self, task: dict):
        if self._reopen_fn:
            if self._reopen_fn(task, self._user_id):
                self.reload()
        else:
            # Default: create a copy
            if self._create_fn(
                task.get("desc", ""),
                task.get("type", "custom"),
                task.get("due_date"),
                task.get("staff_id"),
            ):
                self.reload()
