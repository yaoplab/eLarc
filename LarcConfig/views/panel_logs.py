"""Panel Logs — Erreurs (error_log) + Audit (audit_log), filtrables."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QHeaderView, QTableWidgetItem,
    QTextEdit,
)
from phibuilder.widgets import (
    M3Label, M3TableWidget, M3ScrollArea, M3ComboBox, M3DateEdit, M3Button,
    M3TabWidget,
)
from phibuilder.phi.scale import SpacingToken
from larccommon.design_system import ds
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from LarcConfig.common.db_access import (
    get_errors, get_error_detail, get_audit, get_audit_meta,
)

_DATE_FMT = 'yyyy-MM-dd'


class _FilterBar(QWidget):
    """Barre de filtres commune : app / user / table / dates + rafraîchir."""

    def __init__(self, with_table: bool, parent=None):
        super().__init__(parent)
        phi = theme_manager.phi_theme
        sp = phi.spacing.spacing
        l = QHBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(sp(SpacingToken.SM))

        self.combo_app = M3ComboBox(theme=phi)
        self.combo_user = M3ComboBox(theme=phi)
        self.combo_table = M3ComboBox(theme=phi) if with_table else None
        self.date_from = M3DateEdit(theme=phi)
        self.date_to = M3DateEdit(theme=phi)
        self.btn_refresh = M3Button(theme=phi, text=_("panel.logs.refresh"))

        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat(_DATE_FMT)
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat(_DATE_FMT)
        self.date_from.setSpecialValueText(_("panel.logs.any_date"))
        self.date_to.setSpecialValueText(_("panel.logs.any_date"))

        for w in (self.combo_app, self.combo_user):
            w.setFixedWidth(ds.space_xxxl + ds.space_md + ds.space_xxs)
            w.setFixedHeight(ds.field_height)
        if self.combo_table is not None:
            self.combo_table.setFixedWidth(ds.space_xxxl + ds.button_height + ds.space_lg)
            self.combo_table.setFixedHeight(ds.field_height)
        for w in (self.date_from, self.date_to):
            w.setFixedWidth(ds.space_xxxl - ds.space_xs)
            w.setFixedHeight(ds.field_height)
        self.btn_refresh.setFixedHeight(ds.button_height)

        l.addWidget(M3Label(_("panel.logs.filter_app"), theme=phi))
        l.addWidget(self.combo_app)
        l.addWidget(M3Label(_("panel.logs.filter_user"), theme=phi))
        l.addWidget(self.combo_user)
        if self.combo_table is not None:
            l.addWidget(M3Label(_("panel.logs.filter_table"), theme=phi))
            l.addWidget(self.combo_table)
        l.addWidget(M3Label(_("panel.logs.filter_from"), theme=phi))
        l.addWidget(self.date_from)
        l.addWidget(M3Label(_("panel.logs.filter_to"), theme=phi))
        l.addWidget(self.date_to)
        l.addStretch(1)
        l.addWidget(self.btn_refresh)

    def populate(self, apps, users, tables=None):
        self.combo_app.blockSignals(True)
        self.combo_user.blockSignals(True)
        try:
            self.combo_app.clear()
            self.combo_app.addItem(_("panel.logs.all"), '')
            for a in apps:
                self.combo_app.addItem(a, a)
            self.combo_user.clear()
            self.combo_user.addItem(_("panel.logs.all"), '')
            for u in users:
                self.combo_user.addItem(u, u)
            if self.combo_table is not None:
                self.combo_table.clear()
                self.combo_table.addItem(_("panel.logs.all"), '')
                for t in tables or []:
                    self.combo_table.addItem(t, t)
        finally:
            self.combo_app.blockSignals(False)
            self.combo_user.blockSignals(False)

    def params(self):
        def val(combo):
            return combo.itemData(combo.currentIndex()) or None
        return (val(self.combo_app), val(self.combo_user),
                val(self.combo_table) if self.combo_table is not None else None,
                self.date_from.date().toString(_DATE_FMT),
                self.date_to.date().toString(_DATE_FMT))


class _ErrorsTab(QWidget):
    COLUMNS = ["Date", "App", "Niveau", "Utilisateur", "Module", "Message"]

    def __init__(self, parent=None):
        super().__init__(parent)
        phi = theme_manager.phi_theme
        sp = phi.spacing.spacing
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(sp(SpacingToken.SM))

        self.filters = _FilterBar(with_table=False)
        self.table = M3TableWidget(theme=phi)
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(
            [_(f"panel.logs.col_{c.lower()}") for c in self.COLUMNS])
        h = self.table.horizontalHeader()
        for i in range(len(self.COLUMNS)):
            h.setSectionResizeMode(i, QHeaderView.Stretch)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setFixedHeight(ds.space_xxxl + ds.button_height + ds.space_lg)
        self._restyle_detail()

        l.addWidget(self.filters)
        l.addWidget(self.table, 1)
        l.addWidget(self.detail)

        self.filters.btn_refresh.clicked.connect(self.reload)
        self.table.itemSelectionChanged.connect(self._show_detail)
        ds.theme_changed.connect(self._restyle_detail)

    @safe_slot("LogsPanel.Errors.restyle_detail")
    def _restyle_detail(self):
        self.detail.setStyleSheet(
            f"background: transparent; border: 1px solid "
            f"{theme_manager.palette.outline}; border-radius: {ds.radius_xs}px; "
            f"padding: {ds.space_md}px; color: "
            f"{theme_manager.palette.text_strong}; font-size: {ds.font_small}px;"
        )

    @safe_slot("LogsPanel.Errors.reload")
    def reload(self):
        app, user, _t, frm, to = self.filters.params()
        rows = get_errors(app, user, frm, to)
        self._last_rows = rows
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(
                r['ts'].strftime('%d/%m/%Y %H:%M') if r.get('ts') else ''))
            self.table.setItem(i, 1, QTableWidgetItem(r.get('app', '') or ''))
            self.table.setItem(i, 2, QTableWidgetItem(r.get('level', '') or ''))
            self.table.setItem(i, 3, QTableWidgetItem(r.get('user', '') or ''))
            self.table.setItem(i, 4, QTableWidgetItem(r.get('module', '') or ''))
            self.table.setItem(i, 5, QTableWidgetItem(r.get('message', '') or ''))
        self.table.resizeColumnsToContents()

    @safe_slot("LogsPanel.Errors.detail")
    def _show_detail(self):
        row = self.table.currentRow()
        rows = getattr(self, '_last_rows', [])
        if row < 0 or row >= len(rows):
            return
        detail = get_error_detail(rows[row]['id'])
        if not detail:
            return
        self.detail.setPlainText(
            f"{detail.get('ts')} — {detail.get('app')} v{detail.get('version') or '?'}\n"
            f"{detail.get('user') or ''} ({detail.get('role') or ''}) "
            f"[{detail.get('conn_mode') or ''}]\n"
            f"{detail.get('module') or ''}.{detail.get('func') or ''} "
            f"l.{detail.get('line') or 0}\n\n"
            f"{detail.get('message')}\n\n"
            f"{detail.get('traceback') or ''}"
        )


class _AuditTab(QWidget):
    COLUMNS = ["Date", "Utilisateur", "App", "Table", "Op", "Ligne",
               "Champ", "Ancienne", "Nouvelle"]

    def __init__(self, parent=None):
        super().__init__(parent)
        phi = theme_manager.phi_theme
        sp = phi.spacing.spacing
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(sp(SpacingToken.SM))

        self.filters = _FilterBar(with_table=True)
        self.table = M3TableWidget(theme=phi)
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(
            [_(f"panel.logs.col_{c.lower()}") for c in self.COLUMNS])
        h = self.table.horizontalHeader()
        for i in range(len(self.COLUMNS)):
            h.setSectionResizeMode(i, QHeaderView.Stretch)

        l.addWidget(self.filters)
        l.addWidget(self.table, 1)

        self.filters.btn_refresh.clicked.connect(self.reload)

    @safe_slot("LogsPanel.Audit.reload")
    def reload(self):
        app, user, table, frm, to = self.filters.params()
        rows = get_audit(app, user, table, frm, to)
        self._last_rows = rows
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(
                r['ts'].strftime('%d/%m/%Y %H:%M') if r.get('ts') else ''))
            self.table.setItem(i, 1, QTableWidgetItem(r.get('user', '') or ''))
            self.table.setItem(i, 2, QTableWidgetItem(r.get('app', '') or ''))
            self.table.setItem(i, 3, QTableWidgetItem(r.get('table', '') or ''))
            self.table.setItem(i, 4, QTableWidgetItem(r.get('op', '') or ''))
            self.table.setItem(i, 5, QTableWidgetItem(str(r.get('row', '')) or ''))
            self.table.setItem(i, 6, QTableWidgetItem(r.get('field', '') or ''))
            self.table.setItem(i, 7, QTableWidgetItem(
                (r.get('old') or '')[:120] if r.get('old') else ''))
            self.table.setItem(i, 8, QTableWidgetItem(
                (r.get('new') or '')[:120] if r.get('new') else ''))
        self.table.resizeColumnsToContents()


class LogsPanel(M3ScrollArea):
    def __init__(self, user: dict = None):
        super().__init__(theme=theme_manager.phi_theme)
        phi = theme_manager.phi_theme
        sp = phi.spacing.spacing

        container = QWidget()
        l = QVBoxLayout(container)
        l.setContentsMargins(sp(SpacingToken.LG), sp(SpacingToken.LG),
                             sp(SpacingToken.LG), sp(SpacingToken.LG))
        l.setSpacing(sp(SpacingToken.MD))
        l.addWidget(M3Label(_("panel.logs.title"), theme=phi,
                            style="headline_small"))

        self.tabs = M3TabWidget(theme=phi)
        self.errors_tab = _ErrorsTab()
        self.audit_tab = _AuditTab()
        self.tabs.addTab(self.errors_tab, _("panel.logs.tab_erreurs"))
        self.tabs.addTab(self.audit_tab, _("panel.logs.tab_audit"))
        l.addWidget(self.tabs, 1)

        self.setWidget(container)
        self.setWidgetResizable(True)

        apps, tables, users = get_audit_meta()
        self.errors_tab.filters.populate(apps, users)
        self.audit_tab.filters.populate(apps, users, tables)
        self.errors_tab.reload()
        self.audit_tab.reload()
