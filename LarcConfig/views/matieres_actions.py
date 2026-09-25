"""Bouton « Imprimer / Exporter » du panneau « Matières par classe ».

Un menu, quatre sorties pour la classe et le trimestre affichés (les 3 pages
de données : Classes & matières, Élèves, Autres-matières) : impression, PDF,
Excel, sauvegarde JSON des données. Le rapport est reconstruit depuis la base
à chaque action — jamais depuis l'écran.
"""
from __future__ import annotations

from typing import Callable

from larccommon.safe_slot import safe_slot
from larccommon.theme import theme_manager
from phibuilder.widgets import M3Button, M3Menu
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QFileDialog, QMessageBox

from LarcConfig.common import matieres_export, matieres_print
from LarcConfig.common.matieres_report import Report


class ReportMenuButton(M3Button):
    """`get_report()` retourne le Report courant, ou None si aucune classe."""

    def __init__(self, get_report: Callable[[], Report | None], parent=None):
        phi = theme_manager.phi_theme
        super().__init__("Imprimer / Exporter…", theme=phi, parent=parent)
        self._get_report = get_report
        self._menu = M3Menu(theme=phi, parent=self)
        self._menu.addAction("Imprimer…", self._on_print)
        self._menu.addSeparator()
        self._menu.addAction("Enregistrer en PDF…", self._on_pdf)
        self._menu.addAction("Exporter vers Excel…", self._on_excel)
        self._menu.addAction("Sauvegarder les données (JSON)…", self._on_backup)
        self.setMenu(self._menu)

    def _report(self) -> Report | None:
        report = self._get_report()
        if report is None:
            QMessageBox.information(self, "Aucune classe", "Choisissez d'abord une classe.")
        return report

    def _ask_path(self, report: Report, title: str, ext: str, label: str) -> str | None:
        path, _filter = QFileDialog.getSaveFileName(self, title, f"{report.file_stem}.{ext}", f"{label} (*.{ext})")
        if not path:
            return None
        return path if path.lower().endswith(f".{ext}") else f"{path}.{ext}"

    def _write(self, report: Report, title: str, ext: str, label: str, writer) -> None:
        path = self._ask_path(report, title, ext, label)
        if path is None:
            return
        try:
            ok = writer(report, path)
        except OSError as exc:      # fichier ouvert dans une autre application, dossier protégé…
            QMessageBox.warning(self, "Enregistrement impossible", f"Le fichier n'a pas pu être écrit :\n{exc}")
            return
        if ok is False:
            QMessageBox.warning(self, "Enregistrement impossible",
                                "Le fichier n'a pas pu être écrit (est-il ouvert dans une autre application ?).")
            return
        QMessageBox.information(self, "Enregistrement terminé", f"Fichier créé :\n{path}")

    @safe_slot("ReportMenuButton._on_print")
    def _on_print(self):
        report = self._report()
        if report is None:
            return
        printer = QPrinter(QPrinter.HighResolution)
        printer.setDocName(report.title)
        matieres_print.configure_printer(printer)
        if QPrintDialog(printer, self).exec() != QPrintDialog.Accepted:
            return
        if not matieres_print.paint_report(report, printer):
            QMessageBox.warning(self, "Impression impossible", "L'impression n'a pas pu démarrer.")

    @safe_slot("ReportMenuButton._on_pdf")
    def _on_pdf(self):
        report = self._report()
        if report is not None:
            self._write(report, "Enregistrer en PDF", "pdf", "PDF", matieres_print.save_pdf)

    @safe_slot("ReportMenuButton._on_excel")
    def _on_excel(self):
        report = self._report()
        if report is not None:
            self._write(report, "Exporter vers Excel", "xlsx", "Excel", matieres_export.export_xlsx)

    @safe_slot("ReportMenuButton._on_backup")
    def _on_backup(self):
        report = self._report()
        if report is not None:
            self._write(report, "Sauvegarder les données", "json", "JSON", matieres_export.export_backup_json)
