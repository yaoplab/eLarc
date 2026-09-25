"""Mise en page papier du rapport « Matières par classe » (impression et PDF).

Même code pour l'imprimante et le fichier PDF : les deux sont un QPrinter.
Le corps est un QTextDocument (HTML, police Arial) paginé à la main pour
répéter sur CHAQUE page un en-tête (logo + titre + trait) et un pied de page
(école, date d'édition, numéro de page) — QTextDocument ne sait pas le faire seul.
Une page de données = une page (ou plus, en-têtes de colonnes répétés) du document.
"""
from __future__ import annotations

from html import escape

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPageLayout, QPageSize, QPainter, QPen, QTextDocument
from PySide6.QtPrintSupport import QPrinter

from LarcConfig.common.matieres_export import LOGO_PATH
from LarcConfig.common.matieres_report import SCHOOL_NAME, Report, Table

FONT_FAMILY = "Arial"
_BLUE = "#1F4E9C"
_LIGHT = "#DCE8F8"
_BAND = "#F5F8FD"
_GREY = "#6B7280"
_RULE = "#C9CED6"
_WARN_BG = "#FDE8E8"
_WARN_FG = "#B42318"

_MARGINS_MM = QMarginsF(14, 10, 14, 10)
_HEADER_MM = 22.0
_FOOTER_MM = 9.0


def configure_printer(printer: QPrinter) -> None:
    """A4 paysage, marges fixes — les tableaux d'élèves sont larges."""
    printer.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Landscape,
                                      _MARGINS_MM, QPageLayout.Millimeter))


def _table_html(t: Table, show_title: bool) -> str:
    out = [f'<p class="tt">{escape(t.title)}</p>'] if show_title else []
    if not t.rows:
        out.append(f'<p class="empty">{escape(t.empty_text)}</p>')
        return "".join(out)
    out.append('<table width="100%" cellspacing="0" cellpadding="4" border="0">')
    # 1re colonne (noms d'élèves) élargie pour éviter que les noms passent à la ligne
    first_w = ' width="17%"' if len(t.columns) > 3 else ""
    out.append("<thead><tr>" + "".join(
        f'<th align="{"center" if (t.aligns[i] if i < len(t.aligns) else "l") == "c" else "left"}"'
        f'{first_w if i == 0 else ""}>{escape(c)}</th>' for i, c in enumerate(t.columns)) + "</tr></thead>")
    for r, row in enumerate(t.rows):
        flag = t.flags[r] if r < len(t.flags) else ""
        bg = _WARN_BG if flag == "warn" else (_BAND if r % 2 else "#FFFFFF")
        cells = []
        for i, v in enumerate(row):
            align = "center" if (t.aligns[i] if i < len(t.aligns) else "l") == "c" else "left"
            style = f"background-color:{bg};"
            if flag == "warn" and i == len(row) - 1:
                style += f"color:{_WARN_FG};"
            cells.append(f'<td align="{align}" style="{style}">{escape(v)}</td>')
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</table>")
    if t.note:
        out.append(f'<p class="note">{escape(t.note)}</p>')
    return "".join(out)


def report_html(report: Report) -> str:
    css = (
        f"body {{ font-family:'{FONT_FAMILY}'; font-size:7.5pt; color:#111827; }}"
        f"h1 {{ font-size:15pt; color:{_BLUE}; margin:8pt 0 6pt 0; }}"
        f".tt {{ font-size:11pt; font-weight:bold; color:{_BLUE}; margin:10pt 0 4pt 0; }}"
        f"th {{ background-color:{_BLUE}; color:#FFFFFF; font-weight:bold; font-size:7.5pt; }}"
        f"td {{ font-size:7.5pt; border-bottom:0.5pt solid {_RULE}; }}"
        f".note {{ font-size:8pt; color:{_GREY}; font-style:italic; margin-top:3pt; }}"
        f".empty {{ font-size:7.5pt; color:{_GREY}; font-style:italic; }}"
    )
    body = []
    for i, section in enumerate(report.sections):
        brk = ' style="page-break-before:always;"' if i else ""
        body.append(f"<h1{brk}>{escape(section.title)}</h1>")
        body.extend(_table_html(t, show_title=len(section.tables) > 1) for t in section.tables)
    return f"<html><head><style>{css}</style></head><body>{''.join(body)}</body></html>"


def paint_report(report: Report, printer: QPrinter) -> bool:
    """Peint tout le rapport sur `printer` (imprimante ou fichier PDF)."""
    doc = QTextDocument()
    doc.setDefaultFont(QFont(FONT_FAMILY, 7.5))
    doc.documentLayout().setPaintDevice(printer)
    doc.setHtml(report_html(report))

    page = printer.pageRect(QPrinter.DevicePixel)
    dpi = printer.resolution()
    px_mm = dpi / 25.4
    head_h, foot_h = _HEADER_MM * px_mm, _FOOTER_MM * px_mm
    body = QSizeF(page.width(), page.height() - head_h - foot_h)
    doc.setPageSize(body)

    logo = QImage(LOGO_PATH)
    painter = QPainter()
    if not painter.begin(printer):
        return False
    try:
        total = max(doc.pageCount(), 1)
        for n in range(total):
            if n:
                printer.newPage()
            _paint_header(painter, report, page, head_h, px_mm, logo)
            _paint_footer(painter, report, page, foot_h, n + 1, total, px_mm)
            painter.save()
            painter.translate(0, head_h - n * body.height())
            doc.drawContents(painter, QRectF(0, n * body.height(), body.width(), body.height()))
            painter.restore()
    finally:
        painter.end()
    return True


def _paint_header(painter, report: Report, page: QRectF, head_h: float, px_mm: float, logo: QImage):
    logo_h = 15 * px_mm
    x = 0.0
    if not logo.isNull():
        logo_w = logo_h * logo.width() / logo.height()
        painter.drawImage(QRectF(0, 0, logo_w, logo_h), logo)
        x = logo_w + 5 * px_mm
    pt_px = dpi_pt(px_mm)
    title_font = QFont(FONT_FAMILY)
    title_font.setPixelSize(round(16 * pt_px))
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(QColor(_BLUE))
    painter.drawText(QRectF(x, 0, page.width() - x, logo_h * 0.58),
                     Qt.AlignLeft | Qt.AlignBottom, report.title)
    sub_font = QFont(FONT_FAMILY)
    sub_font.setPixelSize(round(10 * pt_px))
    painter.setFont(sub_font)
    painter.setPen(QColor(_GREY))
    painter.drawText(QRectF(x, logo_h * 0.62, page.width() - x, logo_h * 0.38),
                     Qt.AlignLeft | Qt.AlignTop, report.subtitle)
    pen = QPen(QColor(_BLUE))
    pen.setWidthF(max(1.0, 0.5 * px_mm))
    painter.setPen(pen)
    painter.drawLine(0, round(logo_h + 2 * px_mm), round(page.width()), round(logo_h + 2 * px_mm))


def _paint_footer(painter, report: Report, page: QRectF, foot_h: float, n: int, total: int, px_mm: float):
    font = QFont(FONT_FAMILY)
    font.setPixelSize(round(8 * dpi_pt(px_mm)))
    painter.setFont(font)
    painter.setPen(QColor(_GREY))
    top = page.height() - foot_h + 2 * px_mm
    painter.drawText(QRectF(0, top, page.width() / 2, foot_h),
                     Qt.AlignLeft | Qt.AlignTop,
                     f"{SCHOOL_NAME} — édité le {report.generated:%d/%m/%Y à %H:%M}")
    painter.drawText(QRectF(page.width() / 2, top, page.width() / 2, foot_h),
                     Qt.AlignRight | Qt.AlignTop, f"Page {n} / {total}")


def dpi_pt(px_mm: float) -> float:
    """Pixels par point typographique (1 pt = 1/72 in) pour ce périphérique."""
    return px_mm * 25.4 / 72


def save_pdf(report: Report, path: str) -> bool:
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(path)
    printer.setDocName(report.title)
    configure_printer(printer)
    return paint_report(report, printer)
