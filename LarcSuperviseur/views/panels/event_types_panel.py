"""Administration des types d'événements (arbre, verrou strict).

Rôles : ADMIN + COORD (garde à l'intégration dans MainWindow).
Verrou strict : un type référencé dans student_event.event_type_id est
immuable — rows grisées, actions refusées (check Python + trigger DB 23513).
"""
import re

from larccommon.design_system import ds
from larccommon.widgets.themed_widget import ThemedDialog
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from phibuilder.widgets import (
    M3Button,
    M3Card,
    M3ComboBox,
    M3DialogButtonBox,
    M3Label,
    M3TableWidget,
    M3TextField,
)
from phibuilder.widgets.button import ButtonVariant
from phibuilder.widgets.card import CardVariant
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QDialog, QHBoxLayout, QMenu, QMessageBox, QVBoxLayout, QWidget

from LarcSuperviseur.common.theme import theme_manager
from LarcSuperviseur.views.core.event_type_repo import EventTypeRepo


class EventTypeEditDialog(ThemedDialog):
    """Ajout / renommage d'un type (modèle ParentEditDialog)."""

    def __init__(self, loader: EventTypeRepo, parent=None, mode="create",
                 node=None, roots=None):
        super().__init__(parent)
        self._loader = loader
        self._mode = mode
        self._node = node or {}
        self._roots = roots or []
        self.setWindowTitle(
            _("event_types.add_dialog_title") if mode == "create"
            else _("event_types.rename_dialog_title")
        )
        self.setMinimumWidth(ds.golden_width(500))
        p = theme_manager.palette

        outer = QVBoxLayout(self)
        outer.setSpacing(ds.space_md)
        outer.setContentsMargins(ds.space_lg, ds.space_lg, ds.space_lg, ds.space_lg)

        card = M3Card(variant=CardVariant.ELEVATED, parent=self)
        cl = card.content_layout()
        cl.setSpacing(ds.space_sm)

        cl.addWidget(M3Label(_("event_types.label_label"), style="label_small"))
        self._label = M3TextField(placeholder=_("event_types.label_label"))
        self._label.setFixedHeight(ds.field_height)
        self._label.setStyleSheet(ds.flat_input_qss())
        if mode == "rename":
            self._label.setText(node.get("label", ""))
        cl.addWidget(self._label)

        cl.addWidget(M3Label(_("event_types.code_label"), style="label_small"))
        self._code = M3TextField(placeholder=_("event_types.code_auto"))
        self._code.setFixedHeight(ds.field_height)
        self._code.setStyleSheet(ds.flat_input_qss())
        if mode == "rename":
            self._code.setText(node.get("code", ""))
        cl.addWidget(self._code)

        if mode == "create":
            cl.addWidget(M3Label(_("event_types.parent_label"), style="label_small"))
            self._parent = M3ComboBox()
            self._parent.setFixedHeight(ds.field_height)
            self._parent.addItem("—", None)
            for r in self._roots:
                self._parent.addItem(("    " * (r.get("depth", 0))) + (r.get("label") or ""), r.get("id"))
            cl.addWidget(self._parent)

            cl.addWidget(M3Label(_("event_types.absence_scope_label"), style="label_small"))
            self._scope = M3ComboBox()
            self._scope.setFixedHeight(ds.field_height)
            self._scope.addItem(_("event_types.absence_scope_none"), None)
            self._scope.addItem("École", "ecole")
            self._scope.addItem("Cours", "cours")
            cl.addWidget(self._scope)

        self._buttons = M3DialogButtonBox(
            M3DialogButtonBox.Ok | M3DialogButtonBox.Cancel, parent=self
        )
        self._buttons.accepted.connect(self._validate_and_save)
        self._buttons.rejected.connect(self.reject)
        outer.addWidget(card)
        outer.addWidget(self._buttons)
        self.setStyleSheet(f"EventTypeEditDialog {{ background: {p.surface}; }}")

    @safe_slot("EventTypeEditDialog.validate_and_save")
    def _validate_and_save(self):
        label = self._label.text().strip()
        if not label:
            QMessageBox.warning(self, _("common.dialog.error_title"), _("event_types.label_label"))
            return
        if self._mode == "rename":
            res = self._loader.rename_event_type(self._node["id"], label)
            if res["ok"]:
                self.accept()
            else:
                QMessageBox.warning(self, _("common.dialog.error_title"), res.get("error") or "?")
            return
        code = self._code.text().strip()
        if code and not re.fullmatch(r"[a-z0-9-]+", code):
            QMessageBox.warning(self, _("common.dialog.error_title"), _("event_types.error_code_invalid"))
            return
        parent_id = self._parent.currentData()
        res = self._loader.create_event_type(
            parent_id=parent_id,
            label=label,
            code=code or None,
            absence_scope=self._scope.currentData() if hasattr(self, "_scope") else None,
        )
        if res["ok"]:
            self.accept()
        else:
            QMessageBox.warning(self, _("common.dialog.error_title"), res.get("error") or "?")


class EventTypesPanel(QWidget):
    """Gestion arbre des types : ajout, renommage, désactivation, ordre."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loader = EventTypeRepo()
        self._nodes = []
        self._build_ui()
        self.refresh()
        ds.theme_changed.connect(self._restyle)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(ds.space_lg, ds.space_lg, ds.space_lg, ds.space_lg)
        outer.setSpacing(ds.space_md)

        outer.addWidget(M3Label(_("event_types.title"), style="title_medium"))

        bar = QHBoxLayout()
        bar.setSpacing(ds.space_sm)
        self._btn_add_root = M3Button(_("event_types.add_root"), variant=ButtonVariant.FILLED)
        self._btn_add_child = M3Button(_("event_types.add_child"), variant=ButtonVariant.TONAL)
        self._btn_rename = M3Button(_("event_types.rename"), variant=ButtonVariant.TONAL)
        self._btn_disable = M3Button(_("event_types.disable"), variant=ButtonVariant.TONAL)
        self._btn_up = M3Button(_("event_types.reorder_up"), variant=ButtonVariant.TEXT)
        self._btn_down = M3Button(_("event_types.reorder_down"), variant=ButtonVariant.TEXT)
        for b in (self._btn_add_root, self._btn_add_child, self._btn_rename,
                  self._btn_disable, self._btn_up, self._btn_down):
            b.setMinimumHeight(ds.button_height)
            bar.addWidget(b)
        bar.addStretch()
        outer.addLayout(bar)

        self._table = M3TableWidget(0, 4)
        self._table.set_headers([_("event_types.code_label"), _("event_types.label_label"),
                                 _("event_types.usage"), _("event_types.state_active")])
        self._table.setEditTriggers(M3TableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(M3TableWidget.SelectRows)
        self._table.setSelectionMode(M3TableWidget.SingleSelection)
        self._table.setSortingEnabled(False)
        self._table.verticalHeader().setDefaultSectionSize(ds.table_row_min)
        self._table.setStyleSheet(ds.table_qss())
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._table.itemSelectionChanged.connect(self._update_actions)
        outer.addWidget(self._table, 1)

        self._btn_add_root.clicked.connect(self._on_add_root)
        self._btn_add_child.clicked.connect(self._on_add_child)
        self._btn_rename.clicked.connect(self._on_rename)
        self._btn_disable.clicked.connect(self._on_disable)
        self._btn_up.clicked.connect(lambda checked: self._on_reorder(-1))
        self._btn_down.clicked.connect(lambda checked: self._on_reorder(1))

    @safe_slot("EventTypesPanel._restyle")
    def _restyle(self):
        try:
            self._table.setStyleSheet(ds.table_qss())
        except RuntimeError:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass

    def refresh(self):
        self._nodes = self._loader.get_event_types_nodes()
        self._rebuild_table()
        self._update_actions()

    def _rebuild_table(self):
        p = theme_manager.palette
        self._table.setRowCount(0)
        for node in self._nodes:
            indent = "    " * node["depth"]
            items = [
                node["code"],
                f"{indent}{node['label']}",
                str(node["usage_count"]),
                _("event_types.state_active") if node["enabled"] else _("event_types.state_disabled"),
            ]
            self._table.add_row(items)
            row = self._table.rowCount() - 1
            locked = node["usage_count"] > 0
            for col in range(4):
                item = self._table.item(row, col)
                if item is None:
                    continue
                if locked:
                    item.setForeground(QBrush(QColor(p.text_disabled)))
                    item.setToolTip(_("event_types.locked_tooltip"))
                if col == 0:
                    item.setData(Qt.UserRole, node["id"])

    def _selected_node(self) -> dict | None:
        idx = self._table.currentRow()
        if idx < 0:
            return None
        item = self._table.item(idx, 0)
        if item is None:
            return None
        nid = item.data(Qt.UserRole)
        return next((n for n in self._nodes if n["id"] == nid), None)

    @safe_slot("EventTypesPanel._update_actions")
    def _update_actions(self):
        node = self._selected_node()
        locked = bool(node and node["usage_count"] > 0)
        can_edit = node is not None and not locked
        self._btn_rename.setEnabled(can_edit)
        self._btn_disable.setEnabled(can_edit)
        self._btn_up.setEnabled(can_edit)
        self._btn_down.setEnabled(can_edit)
        self._btn_add_child.setEnabled(node is not None)

    @safe_slot("EventTypesPanel.on_add_root")
    def _on_add_root(self):
        dlg = EventTypeEditDialog(self._loader, self, mode="create", roots=self._nodes)
        if dlg.exec() == QDialog.Accepted:
            self.refresh()

    @safe_slot("EventTypesPanel.on_add_child")
    def _on_add_child(self):
        node = self._selected_node()
        if node is None:
            return
        dlg = EventTypeEditDialog(self._loader, self, mode="create", node=node, roots=self._nodes)
        if dlg.exec() == QDialog.Accepted:
            self.refresh()

    @safe_slot("EventTypesPanel.on_rename")
    def _on_rename(self):
        node = self._selected_node()
        if node is None:
            return
        dlg = EventTypeEditDialog(self._loader, self, mode="rename", node=node)
        if dlg.exec() == QDialog.Accepted:
            self.refresh()

    @safe_slot("EventTypesPanel.on_disable")
    def _on_disable(self):
        node = self._selected_node()
        if node is None:
            return
        if QMessageBox.question(
            self, _("event_types.disable"), _("event_types.confirm_disable"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        res = self._loader.disable_event_type(node["id"], disabled=node["enabled"])
        if res["ok"]:
            self.refresh()
        else:
            QMessageBox.warning(self, _("common.dialog.error_title"), res.get("error") or "?")

    @safe_slot("EventTypesPanel.on_reorder")
    def _on_reorder(self, direction: int):
        node = self._selected_node()
        if node is None:
            return
        res = self._loader.reorder_event_type(node["id"], direction)
        if res["ok"]:
            self.refresh()
        else:
            QMessageBox.warning(self, _("common.dialog.error_title"), res.get("error") or "?")

    @safe_slot("EventTypesPanel.on_context_menu")
    def _on_context_menu(self, pos):
        node = self._selected_node()
        if node is None:
            return
        locked = node["usage_count"] > 0
        menu = QMenu(self)
        add_child = menu.addAction(_("event_types.add_child"))
        rename = menu.addAction(_("event_types.rename"))
        disable = menu.addAction(_("event_types.disable"))
        up = menu.addAction(_("event_types.reorder_up"))
        down = menu.addAction(_("event_types.reorder_down"))
        for action in (rename, disable, up, down):
            action.setEnabled(not locked)
        chosen = menu.exec(self._table.viewport().mapToGlobal(pos))
        if chosen == add_child:
            self._on_add_child()
        elif chosen == rename:
            self._on_rename()
        elif chosen == disable:
            self._on_disable()
        elif chosen == up:
            self._on_reorder(-1)
        elif chosen == down:
            self._on_reorder(1)
