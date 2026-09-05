"""Panel i18n — éditeur fr.json / en.json."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidgetItem, QHeaderView, QAbstractItemView
from PySide6.QtCore import Qt, QSize
from phibuilder.widgets import M3Label, M3Button, M3TextField, M3TableWidget, M3ScrollArea
from phibuilder.widgets.button import ButtonVariant
from phibuilder.phi.scale import SpacingToken
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.icons import icon as md3_icon
from LarcConfig.common.db_access import load_json, save_json
from larccommon.safe_slot import safe_slot


class I18nPanel(M3ScrollArea):
    def __init__(self, user: dict):
        super().__init__(theme=theme_manager.phi_theme)
        self._user = user
        self._fr = {}
        self._en = {}
        self._load()

        phi = theme_manager.phi_theme
        c = phi.colors
        sp = phi.spacing.spacing

        container = QWidget()
        l = QVBoxLayout(container)
        l.setContentsMargins(sp(SpacingToken.LG), sp(SpacingToken.LG),
                             sp(SpacingToken.LG), sp(SpacingToken.LG))
        l.setSpacing(sp(SpacingToken.MD))

        l.addWidget(M3Label("Langues", theme=phi, style="headline_small"))

        # Table
        self._table = M3TableWidget(theme=phi)
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Cle", "Francais", "English"])
        hh = self._table.horizontalHeader()
        for i in range(3):
            hh.setSectionResizeMode(i, QHeaderView.Stretch)
        self._table.setAlternatingRowColors(False)
        self._table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self._table.cellChanged.connect(self._on_edit)
        self._refresh()
        l.addWidget(self._table)

        # Add row
        ar = QHBoxLayout()
        ar.setSpacing(sp(SpacingToken.SM))
        self._nk = M3TextField(placeholder="Nouvelle cle...", theme=phi)
        self._nk.setFixedHeight(ds.field_height)
        ar.addWidget(self._nk)
        self._nf = M3TextField(placeholder="Francais", theme=phi)
        self._nf.setFixedHeight(ds.field_height)
        ar.addWidget(self._nf)
        self._ne = M3TextField(placeholder="English", theme=phi)
        self._ne.setFixedHeight(ds.field_height)
        ar.addWidget(self._ne)

        add_btn = M3Button("+", theme=phi, variant=ButtonVariant.FILLED)
        add_btn.setFixedSize(ds.button_height + ds.space_xxs, ds.field_height)
        add_btn.clicked.connect(self._add)
        ar.addWidget(add_btn)

        save_btn = M3Button("Enregistrer", theme=phi, variant=ButtonVariant.TONAL)
        save_btn.setFixedHeight(ds.field_height)
        save_btn.clicked.connect(self._save)
        ar.addWidget(save_btn)

        l.addLayout(ar)
        self.setWidget(container)
        self.setWidgetResizable(True)

    def _load(self):
        self._fr = load_json('fr')
        self._en = load_json('en')

    def _refresh(self):
        self._table.blockSignals(True)
        self._table.setRowCount(len(self._fr))
        for i, k in enumerate(sorted(self._fr.keys())):
            self._table.setItem(i, 0, QTableWidgetItem(k))
            self._table.setItem(i, 1, QTableWidgetItem(self._fr.get(k, '')))
            self._table.setItem(i, 2, QTableWidgetItem(self._en.get(k, '')))
        self._table.blockSignals(False)

    @safe_slot("I18nPanel._on_edit")
    def _on_edit(self, row, col):
        if col < 1:
            return
        key = self._table.item(row, 0).text()
        val = self._table.item(row, col).text()
        if col == 1:
            self._fr[key] = val
        else:
            self._en[key] = val

    @safe_slot("I18nPanel._add")
    def _add(self):
        k = self._nk.text().strip()
        f = self._nf.text().strip()
        e = self._ne.text().strip()
        if not k or k in self._fr:
            return
        self._fr[k] = f or k
        self._en[k] = e or k
        self._nk.clear(); self._nf.clear(); self._ne.clear()
        self._refresh()

    @safe_slot("I18nPanel._save")
    def _save(self):
        save_json(self._fr, 'fr')
        save_json(self._en, 'en')
