"""Panel Documentation technique."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox, QCheckBox
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from phibuilder.widgets import M3Label, M3ScrollArea, M3ComboBox, M3Button, M3TextEdit, M3Frame
from phibuilder.widgets.button import ButtonVariant
from phibuilder.phi.scale import SpacingToken
from larccommon.theme import theme_manager
from larccommon.icons import icon as md3_icon
from LarcDocs.common.templates import get_app_list, gen_tech_doc, gen_tech_doc_latex, gen_auto_tech_doc
from LarcDocs.common.exporter import (export_markdown, export_html, export_pdf_from_html,
                                       copy_to_clipboard, export_latex, compile_latex,
                                       check_latex_available)


class DocsTechPanel(M3ScrollArea):
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

        l.addWidget(M3Label("Documentation technique", theme=phi, style="headline_small"))
        l.addWidget(M3Label("Générer la documentation technique : architecture, base de données, modules.",
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

        btn_row = QHBoxLayout()
        btn_row.setSpacing(sp(SpacingToken.SM))
        gen_btn = M3Button("Générer", theme=phi, variant=ButtonVariant.FILLED)
        gen_btn.setIcon(md3_icon('bolt', color=c.on_primary, size=theme_manager.image.icon_btn))
        gen_btn.clicked.connect(self._generate)
        btn_row.addWidget(gen_btn)
        self._auto_cb = QCheckBox("Analyse automatique (code source + AGENTS.md)")
        self._auto_cb.setStyleSheet(f"color: {c.on_surface}; font-size: 13px;")
        btn_row.addWidget(self._auto_cb)
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
            ("LaTeX", 'description', self._export_latex),
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
        if self._auto_cb.isChecked():
            self._generated = gen_auto_tech_doc(app)
        else:
            self._generated = gen_tech_doc(app)
        self._preview.setPlainText(self._generated)

    def _export_md(self):
        text = self._preview.toPlainText() or self._generated
        path, _ = QFileDialog.getSaveFileName(self, "Exporter Markdown", "documentation_technique.md",
                                               "Markdown (*.md);;Tous (*.*)")
        if path:
            export_markdown(text, path)

    def _export_html(self):
        text = self._preview.toPlainText() or self._generated
        path, _ = QFileDialog.getSaveFileName(self, "Exporter HTML", "documentation_technique.html",
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

    def _export_latex(self):
        import os
        app = self._app_combo.currentText()
        latex_content = gen_tech_doc_latex(app)
        path, _ = QFileDialog.getSaveFileName(self, "Exporter LaTeX", "documentation_technique.tex",
                                               "LaTeX (*.tex);;Tous (*.*)")
        if not path:
            return
        export_latex(latex_content, path)

        if check_latex_available():
            reply = QMessageBox.question(
                self, "Compilation LaTeX",
                "Compiler le fichier .tex en PDF avec pdflatex ?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                if compile_latex(path):
                    pdf_path = os.path.splitext(path)[0] + '.pdf'
                    QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(pdf_path)))
                    QMessageBox.information(self, "Succès", f"PDF généré avec succès.")
                else:
                    QMessageBox.warning(self, "Erreur",
                        "Échec de la compilation LaTeX.\n"
                        "Vérifiez que pdflatex est bien installé (MiKTeX ou TeX Live).")
        else:
            QMessageBox.information(self, "LaTeX exporté",
                "Fichier .tex exporté avec succès.\n\n"
                "Pour compiler en PDF, installez MiKTeX (https://miktex.org)\n"
                "ou TeX Live (https://tug.org/texlive) puis lancez :\n"
                f"  pdflatex \"{os.path.basename(path)}\"")

