"""Onglet Anomalies — Phase 0 : diagnostic en lecture seule (A1-A6).

Aucune écriture : les corrections proposées avec aperçu/confirmation
viendront dans une phase ultérieure (cf. plan 2026-09-19, section 3/onglet D).
"""
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from phibuilder.phi.scale import SpacingToken
from phibuilder.widgets import M3Label, M3ScrollArea, M3TableWidget
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidgetItem, QVBoxLayout, QWidget

from LarcConfig.common import db_enrolment

_DETAIL_ROW_CAP = 300


def _a6(term_id=None):
    return db_enrolment.get_anomaly_a6()


_ANOMALIES = [
    ('A1', "Inscription active sur une matière-classe désactivée", db_enrolment.get_anomaly_a1),
    ('A2', "Inscription active d'un élève désactivé", db_enrolment.get_anomaly_a2),
    ('A3', "Matière-classe active sans aucun élève inscrit", db_enrolment.get_anomaly_a3),
    ('A4', "Matière-classe active dont le libellé diffère de sa levelsubject", db_enrolment.get_anomaly_a4),
    ('A5', "Matière-classe active sans enseignant réel", db_enrolment.get_anomaly_a5),
    ('A6', "Élève actif : matières différentes entre T1 et T2", _a6),
]


class AnomaliesPanel(M3ScrollArea):
    def __init__(self, user: dict):
        super().__init__(theme=theme_manager.phi_theme)
        phi = theme_manager.phi_theme
        sp = phi.spacing.spacing

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(sp(SpacingToken.LG), sp(SpacingToken.LG),
                                sp(SpacingToken.LG), sp(SpacingToken.LG))
        lay.setSpacing(sp(SpacingToken.MD))
        lay.addWidget(M3Label("Anomalies (lecture seule)", theme=phi, style="headline_small"))
        lay.addWidget(M3Label(
            "Phase 0 — diagnostic uniquement, aucune écriture. "
            "Sélectionner une ligne pour voir le détail.",
            theme=phi, style="body_small"))

        self._summary = M3TableWidget(theme=phi)
        self._summary.setColumnCount(3)
        self._summary.setHorizontalHeaderLabels(["Code", "Anomalie", "Nombre"])
        h = self._summary.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._summary.setAlternatingRowColors(False)
        self._summary.currentCellChanged.connect(self._on_row_selected)
        lay.addWidget(self._summary)

        self._detail_lbl = M3Label("Détail", theme=phi, style="title_medium")
        lay.addWidget(self._detail_lbl)
        self._detail = M3TableWidget(theme=phi)
        self._detail.setAlternatingRowColors(False)
        lay.addWidget(self._detail)

        self.setWidget(container)
        self.setWidgetResizable(True)

        self._rows_cache = {}
        self._term_id = None  # None = tous les trimestres (défaut Phase 0)
        self.reload()

    def set_term(self, term_id):
        """Restreint A1-A5 à un trimestre (A6 compare toujours T1 et T2)."""
        self._term_id = term_id
        self.reload()

    def _ro(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    @safe_slot("AnomaliesPanel.reload")
    def reload(self):
        self._summary.blockSignals(True)
        self._summary.setRowCount(len(_ANOMALIES))
        for i, (code, desc, fn) in enumerate(_ANOMALIES):
            rows = fn(term_id=self._term_id)
            self._rows_cache[code] = rows
            self._summary.setItem(i, 0, self._ro(code))
            self._summary.setItem(i, 1, self._ro(desc))
            self._summary.setItem(i, 2, self._ro(str(len(rows))))
        self._summary.blockSignals(False)
        if self._summary.rowCount():
            self._summary.selectRow(0)
            self._fill_detail(_ANOMALIES[0][0])

    @safe_slot("AnomaliesPanel._on_row_selected")
    def _on_row_selected(self, row, *_args):
        if row < 0 or row >= len(_ANOMALIES):
            return
        self._fill_detail(_ANOMALIES[row][0])

    def _fill_detail(self, code: str):
        rows = self._rows_cache.get(code, [])
        total = len(rows)
        self._detail_lbl.setText(
            f"Détail {code} — {total} ligne(s)"
            + (f" (affichage limité aux {_DETAIL_ROW_CAP} premières)" if total > _DETAIL_ROW_CAP else ""))
        shown = rows[:_DETAIL_ROW_CAP]
        if not shown:
            self._detail.setColumnCount(1)
            self._detail.setRowCount(1)
            self._detail.setHorizontalHeaderLabels(["—"])
            self._detail.setItem(0, 0, self._ro("Aucune ligne"))
            return
        cols = list(shown[0].keys())
        self._detail.setColumnCount(len(cols))
        self._detail.setHorizontalHeaderLabels(cols)
        self._detail.setRowCount(len(shown))
        for i, r in enumerate(shown):
            for j, col in enumerate(cols):
                self._detail.setItem(i, j, self._ro(str(r.get(col, ''))))
