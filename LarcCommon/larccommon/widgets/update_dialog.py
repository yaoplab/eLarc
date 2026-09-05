"""UpdateDialog — dialogue de mise à jour douce (R3, mode informé)."""
from PySide6.QtWidgets import QHBoxLayout, QTextEdit

from phibuilder.widgets import M3Dialog, M3Button, M3Label
from phibuilder.phi.scale import SpacingToken
from larccommon.design_system import ds
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager


class UpdateDialog(M3Dialog):
    """Propose d'installer la mise à jour (notes visibles) ou de la différer."""

    def __init__(self, info, on_install, parent=None):
        phi = theme_manager.phi_theme
        sp = phi.spacing.spacing
        super().__init__(parent=parent,
                         title=f"{_('update.dialog.title')} — v{info.target}")

        self._on_install = on_install
        self._result = None  # 'install' | 'later' | None

        # Notes de version (lecture seule)
        notes = QTextEdit()
        notes.setReadOnly(True)
        notes.setPlainText(info.notes or _("update.dialog.notes"))
        notes.setFixedHeight(ds.space_xxxl)
        notes.setStyleSheet(
            f"background: transparent; border: 1px solid "
            f"{theme_manager.palette.outline}; border-radius: {ds.radius_xs}px; "
            f"padding: {ds.space_md}px; color: "
            f"{theme_manager.palette.text_strong}; font-size: {ds.font_small}px;"
        )
        self.layout().addWidget(
            M3Label(_("update.dialog.notes"), theme=phi, style="label_medium"))
        self.layout().addWidget(notes)

        # Boutons
        btns = QHBoxLayout()
        btns.setSpacing(sp(SpacingToken.SM))
        btn_later = M3Button(theme=phi, text=_("update.dialog.later"))
        btn_install = M3Button(theme=phi, text=_("update.dialog.install"))
        btn_later.setFixedHeight(ds.button_height)
        btn_install.setFixedHeight(ds.button_height)
        btn_later.clicked.connect(self._later)
        btn_install.clicked.connect(self._install)
        btns.addStretch(1)
        btns.addWidget(btn_later)
        btns.addWidget(btn_install)
        self.layout().addLayout(btns)

    @safe_slot("UpdateDialog.later")
    def _later(self):
        self._result = 'later'
        self.accept()

    @safe_slot("UpdateDialog.install")
    def _install(self):
        self._result = 'install'
        self.accept()

    def result_choice(self):
        return self._result
