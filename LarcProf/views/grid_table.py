"""Fenêtre principale — Espace de travail du professeur.

Top bar (toujours visible) : matière-classe, formatives, sommatives, jugements.
Workspace (après sélection) : grille élèves × notes + barre actions.
"""
from __future__ import annotations

from functools import partial

from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QFont, QColor, QAction, QKeySequence, QPalette, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStatusBar,
    QStyle,
    QStyleOptionButton,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from larccommon.design_system import ds



from common.database import db
from common.logger import log
from common.session import session
from common.theme import theme_manager
from common.grid_config import pei_config
from views.eval_manager import EvalManagerWindow
from larccommon.safe_slot import safe_slot






class ColorItem(QTableWidgetItem):
    """QTableWidgetItem qui stocke une couleur de fond accessible via UserRole+3."""
    def __init__(self, text: str, bg: QColor | None = None):
        super().__init__(text)
        self._bg = bg

    def set_bg(self, bg: QColor | None):
        self._bg = bg

    def data(self, role: int):
        if role == Qt.UserRole + 3 and self._bg is not None:
            return self._bg
        return super().data(role)


def _note_gradient(val: str, cycle: str, default_bg=QColor(255, 255, 255)) -> QColor | None:
    """Calcule la couleur de fond d'une cellule de note (rouge→vert)."""
    if not val:
        return default_bg
    try:
        note_val = float(val)
    except (ValueError, TypeError):
        return default_bg
    max_note = 8 if cycle == 'PEI' else 20
    half = max_note / 2
    clamped = max(0, min(note_val, max_note))
    if clamped <= half:
        t = clamped / half
        r, g, b = 255, int(100 + 155 * t), int(100 + 155 * t)
    else:
        t = (clamped - half) / half
        r, g, b = int(255 - 155 * t), 255, int(255 - 155 * t)
    return QColor(r, g, b)


class ColorDelegate(QStyledItemDelegate):
    """Delegate: fond depuis UserRole+3, texte centré par-dessus."""
    def paint(self, painter, option, index):
        self.initStyleOption(option, index)

        # Fond
        painter.save()
        custom_bg = index.data(Qt.UserRole + 3)
        if custom_bg:
            painter.fillRect(option.rect, custom_bg)
        else:
            painter.fillRect(option.rect, QColor(theme_manager.palette.background))
        painter.restore()

        # Sélection
        if option.state & QStyle.State_Selected:
            painter.save()
            c = option.palette.highlight().color()
            c.setAlpha(80)
            painter.fillRect(option.rect, c)
            painter.restore()

        # Texte centré avec padding design system.
        # Foreground de l'item prioritaire (texte blanc sur fonds de zone sombres).
        painter.save()
        painter.setFont(option.font)
        fg = index.data(Qt.ForegroundRole)
        if fg:
            painter.setPen(fg)
        else:
            painter.setPen(option.palette.color(QPalette.Text))
        trect = option.rect.adjusted(8, 4, -8, -4)
        painter.drawText(trect, Qt.AlignCenter, option.text)
        painter.restore()

        # Case à cocher (colonne « Valide ») : notre paint surchargé
        # remplace le paint natif qui dessine l'indicateur — on le
        # redessine via le style, centré dans la cellule (le rect natif
        # est décalé par le style ; le centrage manuel est partagé avec
        # editorEvent pour que le clic tombe exactement sur le dessin).
        if option.features & QStyleOptionViewItem.HasCheckIndicator:
            cb_opt = self._check_option(option, index)
            QApplication.style().drawPrimitive(
                QStyle.PE_IndicatorCheckBox, cb_opt, painter, option.widget)

    @staticmethod
    def _check_rect(option) -> QRect:
        """Rect de la case à cocher : 14px centré sur la cellule."""
        sz = QApplication.style().pixelMetric(
            QStyle.PM_IndicatorWidth, None, option.widget) or 14
        r = QRect(0, 0, sz, sz)
        r.moveCenter(option.rect.center())
        return r

    def _check_option(self, option, index) -> QStyleOptionButton:
        cb_opt = QStyleOptionButton()
        cb_opt.rect = self._check_rect(option)
        cb_opt.state = QStyle.State_Enabled
        if index.data(Qt.CheckStateRole) == Qt.Checked:
            cb_opt.state |= QStyle.State_On
        return cb_opt


class ZoneHeaderView(QHeaderView):
    """Entêtes à fond par zone (F = ciel, S = marine, neutre).

    Le BackgroundRole des header items est ignoré par le rendu du style et
    QHeaderView n'appelle jamais un delegate installé via setItemDelegate ;
    le paintEvent du widget, lui, est toujours appelé — on repeint donc les
    fonds des sections puis le texte (bold) par-dessus le rendu du style.
    """

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._zone_bgs: list = []
        self._zone_fgs: dict[int, QColor] = {}

    def set_zone_colors(self, bgs: list, fgs: dict):
        """bgs : couleur de fond par colonne (None = rendu du style conservé).
        fgs : couleur de texte par colonne (absente = couleur par défaut)."""
        self._zone_bgs = list(bgs)
        self._zone_fgs = dict(fgs)
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._zone_bgs:
            return
        vp = self.viewport()
        p = QPainter(vp)
        p.setClipRect(event.rect().translated(-vp.x(), -vp.y()))
        h = vp.height()
        # 1) Fonds de zone par-dessus les sections du style
        for col, bg in enumerate(self._zone_bgs):
            if col >= self.count() or bg is None:
                continue
            p.fillRect(self.sectionViewportPosition(col), 0,
                       self.sectionSize(col), h, bg)
        # 2) Texte bold par-dessus (le style l'a déjà dessiné, on le recouvre)
        f = self.font()
        f.setBold(True)
        p.setFont(f)
        for col in range(len(self._zone_bgs)):
            if col >= self.count():
                continue
            label = self.model().headerData(col, Qt.Horizontal, Qt.DisplayRole)
            if label is None:
                continue
            rect = QRect(self.sectionViewportPosition(col) + 4, 0,
                         self.sectionSize(col) - 8, h)
            fg = self._zone_fgs.get(col)
            if fg is None:
                fg = self.palette().color(QPalette.Text)
            p.setPen(fg)
            p.drawText(rect, Qt.AlignCenter, str(label))
        p.end()


class ClipboardTable(QTableWidget):
    """QTableWidget avec support Ctrl+C / Ctrl+V (formats Excel) + menu contextuel."""

    def mouseReleaseEvent(self, event):
        """Clic sur une case à cocher (colonne « Valide ») : le view ne
        transmet le release à l'éditeur que si le clic tombe dans le rect
        natif du style (décalé) — on bascule donc nous-mêmes, indépendamment
        du style. item.setCheckState → itemChanged → _on_cell_changed."""
        if event.button() == Qt.LeftButton:
            idx = self.indexAt(event.pos())
            if idx.isValid():
                item = self.itemFromIndex(idx)
                # ATTENTION : ItemIsUserCheckable est dans les flags PAR DÉFAUT
                # des QTableWidgetItem (Qt 6.7+) — il ne suffit pas à identifier
                # une vraie case à cocher (toute cellule de note en serait une).
                # Une checkbox réelle a un CheckStateRole défini ; les autres
                # cellules n'en ont pas et ne doivent pas être basculées.
                if item is not None and item.data(Qt.CheckStateRole) is not None:
                    item.setCheckState(
                        Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)
                    return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            self._copy_selection()
            return
        if event.matches(QKeySequence.Paste):
            self._paste_clipboard()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        """Clic droit sur un eleve → actions evenement."""
        item = self.itemAt(event.pos())
        if item is None:
            return
        row = item.row()
        # Colonne 0 = nom eleve
        name_item = self.item(row, 0)
        if name_item is None:
            return
        student_id = name_item.data(Qt.UserRole)
        student_name = name_item.text()
        if student_id is None or not student_name:
            return

        menu = QMenu(self)
        menu.addAction('Fiche detaillee...', lambda: self._open_student_card(student_id))
        menu.addSeparator()
        menu.addAction('Absence', lambda: self._add_event(student_id, student_name, 'absence'))
        menu.addAction('Retard', lambda: self._add_event(student_id, student_name, 'late'))
        menu.addAction('Sortie anticipee', lambda: self._add_event(student_id, student_name, 'exit'))
        menu.addSeparator()
        menu.addAction('Autre evenement...', lambda: self._add_event(student_id, student_name, None))
        menu.exec(event.globalPos())

    def _add_event(self, student_id: int, student_name: str, event_type: str | None):
        from views.event_dialog import EventDialog
        from common.event_service import EventService

        if event_type is not None:
            # Creation directe sans dialogue
            try:
                from common.session import session
                EventService.insert_event(
                    student_id=student_id,
                    event_type=event_type,
                    created_by=session.user_id,
                )
                self.window().statusBar().showMessage(
                    f'Evenement enregistre pour {student_name}', 3000
                )
            except Exception as e:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                self.window().statusBar().showMessage(f'Erreur : {e}', 5000)
        else:
            # Dialogue pour evenement personnalise
            dlg = EventDialog(student_name, student_id, self)
            if dlg.exec() == QDialog.Accepted:
                self.window().statusBar().showMessage(
                    f'Evenement enregistre pour {student_name}', 3000
                )

    def _open_student_card(self, student_id: int) -> None:
        """Ouvre la fiche detaillee de l'eleve via le parent (MainWindow)."""
        parent = self.window()
        if parent is not None and hasattr(parent, '_open_student_card'):
            parent._open_student_card(student_id)

    def _copy_selection(self) -> None:
        rows = sorted(set(item.row() for item in self.selectedItems()))
        cols = sorted(set(item.column() for item in self.selectedItems()))
        if not rows or not cols:
            return
        col_range = range(cols[0], cols[-1] + 1)
        lines = []
        for r in rows:
            cells = []
            for c in col_range:
                it = self.item(r, c)
                cells.append(it.text() if it else '')
            lines.append('\t'.join(cells))
        QApplication.clipboard().setText('\n'.join(lines))

    def _paste_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        if not text.strip():
            return
        lines = text.split('\n')
        rows_data = [line.split('\t') for line in lines if line.strip()]
        if not rows_data:
            return
        cur_row = self.currentRow()
        cur_col = self.currentColumn()
        parent = self.window()

        has_dp = getattr(parent, '_current_table', '').endswith('dp')
        max_val = 20 if has_dp else 8

        self.blockSignals(True)
        errors = []
        paste_count = 0
        for ri, row_cells in enumerate(rows_data):
            for ci, val in enumerate(row_cells):
                r = cur_row + ri
                c = cur_col + ci
                if r >= self.rowCount() or c >= self.columnCount():
                    continue
                if c == 0:
                    continue  # colonne 0 = élève, pas de collage
                val = val.strip()
                item = self.item(r, c)
                if item is None:
                    item = QTableWidgetItem()
                    self.setItem(r, c, item)
                item.setText(val)
                paste_count += 1

                if val:
                    try:
                        f = float(val)
                        if f < 0 or f > max_val:
                            errors.append(f"L{ri+1}C{ci+1} ({f}) hors {0}-{max_val}")
                    except ValueError:
                        from larccommon.error_reporting import get_reporter
                        get_reporter().report_exception()
                        pass

        self.blockSignals(False)

        for ri, row_cells in enumerate(rows_data):
            for ci in range(len(row_cells)):
                r = cur_row + ri
                c = cur_col + ci
                if r >= self.rowCount() or c >= self.columnCount():
                    continue
                QTimer.singleShot(0, partial(self._mark_dirty, r, c))

        if errors:
            QApplication.beep()
            parent.statusBar().showMessage(
                f"Collé — {paste_count} cellules, {len(errors)} hors plage: "
                f"{', '.join(errors[:5])}", 10000
            )
        else:
            parent.statusBar().showMessage(
                f"Collé — {paste_count} cellule(s)"
            )

    def _mark_dirty(self, row: int, col: int) -> None:
        parent = self.window()
        if not hasattr(parent, '_on_cell_changed'):
            return
        parent._on_cell_changed(row, col)

