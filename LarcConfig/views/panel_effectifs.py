"""Panel « Classes & matières » — conteneur à onglets + en-tête commun.

En-tête commun (programme + classe + trimestre) : cf. plan 2026-09-19,
section 3. Onglets Classes (A), Élèves (B) et Anomalies (D).
"""
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from phibuilder.phi.scale import SpacingToken
from phibuilder.widgets import M3ComboBox, M3Label, M3TabWidget
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from LarcConfig.common import db_enrolment
from LarcConfig.common.enrolment_rules import TERM_SLOTS
from LarcConfig.views.effectifs_anomalies import AnomaliesPanel
from LarcConfig.views.effectifs_classes import ClassesPanel
from LarcConfig.views.effectifs_grille import GridPanel


class EffectifsPanel(QWidget):
    def __init__(self, user: dict):
        super().__init__()
        self._user = user
        self._classrooms = []  # classes du programme courant

        phi = theme_manager.phi_theme
        sp = phi.spacing.spacing

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QHBoxLayout()
        head.setContentsMargins(sp(SpacingToken.LG), sp(SpacingToken.MD),
                                 sp(SpacingToken.LG), sp(SpacingToken.MD))
        head.setSpacing(sp(SpacingToken.SM))

        self._programs = db_enrolment.get_programs()
        head.addWidget(M3Label("Programme", theme=phi, style="body_small"))
        self._program_combo = M3ComboBox([p['sigle'] for p in self._programs], theme=phi)
        self._program_combo.currentIndexChanged.connect(self._on_program_changed)
        head.addWidget(self._program_combo)

        head.addWidget(M3Label("Classe", theme=phi, style="body_small"))
        self._class_combo = M3ComboBox([], theme=phi)
        self._class_combo.currentIndexChanged.connect(self._on_classroom_changed)
        head.addWidget(self._class_combo)

        head.addWidget(M3Label("Trimestre", theme=phi, style="body_small"))
        self._term_combo = M3ComboBox([str(t) for t in sorted(TERM_SLOTS)], theme=phi)
        self._term_combo.currentIndexChanged.connect(self._on_term_changed)
        head.addWidget(self._term_combo)
        head.addStretch()
        lay.addLayout(head)

        self._tabs = M3TabWidget(theme=theme_manager.phi_theme)
        self._classes = ClassesPanel(user)
        self._grille = GridPanel(user)
        self._anomalies = AnomaliesPanel(user)
        self._tabs.addTab(self._classes, "Classes & matières")
        self._tabs.addTab(self._grille, "Élèves")
        self._tabs.addTab(self._anomalies, "Anomalies")
        lay.addWidget(self._tabs)

        if self._programs:
            self._on_program_changed(0)
        self._anomalies.set_term(TERM_SLOTS[1])

    def reload(self):
        if hasattr(self._classes, 'reload'):
            self._classes.reload()
        if hasattr(self._grille, 'reload'):
            self._grille.reload()
        if hasattr(self._anomalies, 'reload'):
            self._anomalies.reload()

    @safe_slot("EffectifsPanel._on_program_changed")
    def _on_program_changed(self, index: int):
        if not (0 <= index < len(self._programs)):
            return
        program_id = self._programs[index]['id']
        # Les classes désactivées sont des gabarits inutilisés cette année :
        # inutile de les proposer ici, ce panneau configure des classes en service.
        self._classrooms = [c for c in db_enrolment.get_classrooms(program_id=program_id) if c['enabled']]
        self._class_combo.blockSignals(True)
        self._class_combo.clear()
        for c in self._classrooms:
            self._class_combo.addItem(c['label'])
        self._class_combo.blockSignals(False)
        self._on_classroom_changed(0 if self._classrooms else -1)

    @safe_slot("EffectifsPanel._on_classroom_changed")
    def _on_classroom_changed(self, index: int):
        if not (0 <= index < len(self._classrooms)):
            return
        c = self._classrooms[index]
        term_id = TERM_SLOTS[sorted(TERM_SLOTS)[self._term_combo.currentIndex()]]
        program_sigle = c.get('program_sigle')
        self._classes.set_context(c['id'], c['label'], c['enabled'], term_id, program_sigle)
        self._grille.set_context(c['id'], c['label'], term_id, program_sigle)

    @safe_slot("EffectifsPanel._on_term_changed")
    def _on_term_changed(self, index: int):
        terms = sorted(TERM_SLOTS)
        if not (0 <= index < len(terms)):
            return
        term_id = TERM_SLOTS[terms[index]]
        self._on_classroom_changed(self._class_combo.currentIndex())
        self._anomalies.set_term(term_id)
