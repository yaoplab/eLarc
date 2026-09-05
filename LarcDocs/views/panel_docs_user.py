"""Panel Documentation utilisateur."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QRadioButton, QButtonGroup
from PySide6.QtCore import Qt
from phibuilder.widgets import M3Label, M3ScrollArea, M3ComboBox, M3Button, M3TextEdit, M3Frame
from phibuilder.widgets.button import ButtonVariant
from phibuilder.phi.scale import SpacingToken
from larccommon.theme import theme_manager
from larccommon.icons import icon as md3_icon
from LarcDocs.common.templates import get_app_list, gen_user_doc, gen_auto_user_doc
from LarcDocs.common.user_guide import gen_user_guide, get_apps_with_guide
from LarcDocs.common.exporter import export_markdown, export_html, export_pdf_from_html, copy_to_clipboard


class DocsUserPanel(M3ScrollArea):
    def __init__(self, user: dict):
        super().__init__(theme=theme_manager.phi_theme)
        phi = theme_manager.phi_theme
        c = phi.colors
        sp = phi.spacing.spacing
        self._generated = ""

        container = QWidget()
        l = QVBoxLayout(container)
        l.setContentsMargins(sp(SpacingToken.LG), sp(SpacingToken.LG),
                             sp(SpacingToken.LG), sp(SpacingToken.LG))
        l.setSpacing(sp(SpacingToken.MD))

        l.addWidget(M3Label("Documentation utilisateur", theme=phi, style="headline_small"))
        l.addWidget(M3Label("Générer un manuel utilisateur pour une application Larc.",
                            theme=phi, style="body_small"))

        sel_row = QHBoxLayout()
        sel_row.setSpacing(sp(SpacingToken.SM))
        sel_row.addWidget(M3Label("Application :", theme=phi, style="body_small"))
        self._app_combo = M3ComboBox(theme=phi)
        self._app_combo.addItems(get_app_list())
        self._app_combo.setFixedWidth(250)
        sel_row.addWidget(self._app_combo)
        sel_row.addStretch()
        l.addLayout(sel_row)

        mode_label = M3Label("Mode de génération :", theme=phi, style="body_small")
        l.addWidget(mode_label)

        self._btn_group = QButtonGroup(self)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(sp(SpacingToken.LG))

        modes = [
            ('manuel', 'Manuel', 'Template codé'),
            ('auto', 'Analyse auto', 'Code + AGENTS.md'),
            ('guide', 'Guide illustré', 'Pas-à-pas + captures'),
        ]
        for key, label, tooltip in modes:
            rb = QRadioButton(label)
            rb.setToolTip(tooltip)
            rb.setStyleSheet(f"color: {c.on_surface}; font-size: 13px; spacing: 4px;")
            mode_row.addWidget(rb)
            self._btn_group.addButton(rb)
            setattr(self, f'_rb_{key}', rb)

        self._rb_manuel.setChecked(True)
        mode_row.addStretch()
        l.addLayout(mode_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(sp(SpacingToken.SM))
        gen_btn = M3Button("Générer", theme=phi, variant=ButtonVariant.FILLED)
        gen_btn.setIcon(md3_icon('bolt', color=c.on_primary, size=theme_manager.image.icon_btn))
        gen_btn.clicked.connect(self._generate)
        btn_row.addWidget(gen_btn)
        btn_row.addStretch()
        l.addLayout(btn_row)

        l.addWidget(M3Label("Aperçu :", theme=phi, style="title_small"))
        self._preview = M3TextEdit(theme=phi)
        self._preview.setReadOnly(False)
        self._preview.setMinimumHeight(300)
        l.addWidget(self._preview, 1)

        exp_frame = M3Frame(theme=phi)
        exp_frame.setStyleSheet(f"M3Frame {{ background: {c.surface_container}; border-radius: 8px; padding: 8px; }}")
        exp_layout = QHBoxLayout(exp_frame)
        exp_layout.setContentsMargins(sp(SpacingToken.SM), sp(SpacingToken.SM),
                                      sp(SpacingToken.SM), sp(SpacingToken.SM))
        exp_layout.setSpacing(sp(SpacingToken.SM))

        for label_text, icon_name, slot in [
            ("Exporter .md", 'save', self._export_md),
            ("Exporter .html", 'cloud', self._export_html),
            ("Aperçu PDF", 'visibility', self._preview_pdf),
            ("Copier", 'subject', self._copy),
        ]:
            btn = M3Button(label_text, theme=phi, variant=ButtonVariant.OUTLINED)
            btn.setIcon(md3_icon(icon_name, color=c.primary, size=theme_manager.image.icon_btn))
            btn.clicked.connect(slot)
            exp_layout.addWidget(btn)

        exp_layout.addStretch()
        l.addWidget(exp_frame)

        self.setWidget(container)
        self.setWidgetResizable(True)

    def _generate(self):
        app = self._app_combo.currentText()
        if self._rb_guide.isChecked() and app in get_apps_with_guide():
            self._generated = gen_user_guide(app)
        elif self._rb_auto.isChecked():
            self._generated = gen_auto_user_doc(app)
        else:
            self._generated = gen_user_doc(app)
        self._preview.setPlainText(self._generated)

    def _export_md(self):
        text = self._preview.toPlainText() or self._generated
        path, _ = QFileDialog.getSaveFileName(self, "Exporter Markdown", "documentation_utilisateur.md",
                                               "Markdown (*.md);;Tous (*.*)")
        if path:
            export_markdown(text, path)

    def _export_html(self):
        text = self._preview.toPlainText() or self._generated
        path, _ = QFileDialog.getSaveFileName(self, "Exporter HTML", "documentation_utilisateur.html",
                                               "HTML (*.html);;Tous (*.*)")
        if path:
            export_html(text, path)

    def _preview_pdf(self):
        text = self._preview.toPlainText() or self._generated
        if text:
            export_pdf_from_html(text, "")

    def _copy(self):
        text = self._preview.toPlainText() or self._generated
        if text:
            copy_to_clipboard(text)

