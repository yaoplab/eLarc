"""Fenêtre principale LarcDocs — navigation + panels chargés à la demande."""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget
from PySide6.QtCore import Qt, QSize
from phibuilder.widgets import M3Button, M3Label, M3Frame
from phibuilder.widgets.button import ButtonVariant
from phibuilder.phi.scale import SpacingToken
from larccommon.theme import theme_manager
from larccommon.icons import icon as md3_icon

_SECTIONS = [
    ('docs_user', 'Documentation utilisateur', 'school'),
    ('docs_tech', 'Documentation technique', 'description'),
    ('ad_web', 'Publicité Web', 'cloud'),
    ('ad_print', 'Publicité Imprimable', 'subject'),
]


class DocsWindow(QWidget):
    def __init__(self, user: dict):
        super().__init__()
        self._user = user
        self._panels = {}
        self._current = None
        self._btns = {}

        phi = theme_manager.phi_theme
        c = phi.colors
        sp = phi.spacing.spacing

        self.setWindowTitle(f"LarcDocs — {user.get('first_name','')} {user.get('last_name','')}")
        self.setObjectName("root")
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(f"QWidget#root {{ background: {c.background}; }}")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        side = M3Frame(theme=phi)
        side.setFixedWidth(250)
        side.setStyleSheet(f"background: {c.surface}; border-right: 1px solid {c.outline_variant};")
        sl = QVBoxLayout(side)
        sl.setContentsMargins(sp(SpacingToken.SM), sp(SpacingToken.MD),
                              sp(SpacingToken.SM), sp(SpacingToken.MD))
        sl.setSpacing(sp(SpacingToken.XS))

        sl.addWidget(M3Label("LarcDocs", theme=phi, style="headline_small"))
        sl.addWidget(M3Label(f"{user.get('first_name','')} {user.get('last_name','')}",
                             theme=phi, style="body_small"))
        sl.addSpacing(sp(SpacingToken.MD))

        for key, label, icon_name in _SECTIONS:
            btn = M3Button(label, theme=phi, variant=ButtonVariant.TEXT)
            btn.setIcon(md3_icon(icon_name, color=c.on_surface, size=theme_manager.image.icon_btn))
            btn.setIconSize(QSize(theme_manager.image.icon_btn, theme_manager.image.icon_btn))
            btn.setFixedHeight(40)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self._switch(k))
            self._btns[key] = btn
            sl.addWidget(btn)

        sl.addStretch()

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {c.background};")

        outer.addWidget(side)
        outer.addWidget(self._stack, 1)

        self._switch('docs_user')

    def _switch(self, section: str):
        if self._current == section:
            return
        self._current = section
        c = theme_manager.phi_theme.colors
        for k, btn in self._btns.items():
            bg = c.primary_container if k == section else 'transparent'
            btn.setStyleSheet(
                f"M3Button {{ background: {bg}; text-align: left; padding-left: 8px; "
                f"border-radius: 4px; }}")
        if section not in self._panels:
            panel = self._create(section)
            if panel:
                self._panels[section] = panel
                self._stack.addWidget(panel)
        if section in self._panels:
            self._stack.setCurrentWidget(self._panels[section])

    def _create(self, section: str):
        from LarcDocs.views.panel_docs_user import DocsUserPanel
        from LarcDocs.views.panel_docs_tech import DocsTechPanel
        from LarcDocs.views.panel_ad_web import AdWebPanel
        from LarcDocs.views.panel_ad_print import AdPrintPanel
        return {
            'docs_user': DocsUserPanel,
            'docs_tech': DocsTechPanel,
            'ad_web': AdWebPanel,
            'ad_print': AdPrintPanel,
        }[section](self._user)

