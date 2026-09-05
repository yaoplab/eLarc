from larccommon.design_system import ds
from larccommon.l10n import _
from phibuilder.widgets import M3Button, M3ComboBox, M3Dialog, M3TableWidget
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
)

from LarcSuperviseur.common.logger import log
from LarcSuperviseur.common.theme import theme_manager
from LarcSuperviseur.views.core.data_loader import DataLoader
from larccommon.safe_slot import safe_slot

# EventGenerator imported lazily in _open_event_dialog to avoid circular import




class TimetableEditor(M3Dialog):
    DAYS = [
        _("timetable.monday"),
        _("timetable.tuesday"),
        _("timetable.wednesday"),
        _("timetable.thursday"),
        _("timetable.friday"),
    ]

    def __init__(self, class_id: int, class_label: str, term_id: int, parent=None):
        super().__init__(parent)
        self._loader = DataLoader()
        self._class_id = class_id
        self._term_id = term_id
        self.setWindowTitle(_("timetable.title").format(label=class_label))
        self.setMinimumSize(ds.window_width * 2 // 3, ds.window_height * 5 // 8)  # 800×500
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QVBoxLayout(self)

        # Grille
        self._tt_grid = M3TableWidget()
        self._tt_grid.setAlternatingRowColors(False)
        self._tt_grid.horizontalHeader().setStretchLastSection(True)
        self._tt_grid.setEditTriggers(M3TableWidget.NoEditTriggers)
        layout.addWidget(self._tt_grid, 1)

        # Boutons
        btn_row = QHBoxLayout()
        save_btn = M3Button(_("timetable.save_button"))
        save_btn.setMinimumHeight(ds.space_lg + ds.space_xxs)  # 36px
        save_btn.setStyleSheet(
            f"QPushButton {{ background: {p.primary}; color: {p.on_primary}; "
            f"border: none; border-radius: {ds.radius_sm}px; font-weight: bold; "
            f"font-size: {s(12)}px; padding: {ds.space_xs}px {ds.space_md}px; }}"
            f"QPushButton:hover {{ background: {p.active}; }}"
        )
        save_btn.clicked.connect(self._save)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _load_data(self):
        try:
            from collections import defaultdict

            all_tps = self._loader.get_timeperiods()
            self._tp_by_day: dict[int, list[tuple]] = defaultdict(list)
            for tp_id, debut, fin, wd in all_tps:
                self._tp_by_day[wd].append((tp_id, debut, fin))

            tt = self._loader.get_classroom_timetable(self._class_id, self._term_id)
            self._cht_map = tt["cht_map"]
            self._cht_id_map = tt["cht_id_map"]

            self._subjects = self._loader.get_available_subjects(self._class_id)

            self._build_grid()

        except Exception as e:
            log(f"TimetableEditor._load_data: {e}")
            QMessageBox.critical(self, _("common.dialog.error"), str(e))

    def _build_grid(self):
        p = theme_manager.palette

        # Déterminer le nombre max de créneaux par jour
        max_slots = max(len(v) for v in self._tp_by_day.values()) if self._tp_by_day else 0

        self._tt_grid.setColumnCount(6)  # Heure + 5 jours
        self._tt_grid.setHorizontalHeaderLabels([_("timetable.hour")] + self.DAYS)
        self._tt_grid.setRowCount(max_slots)

        # Stocker les combos pour la sauvegarde
        self._cell_combos: dict[tuple[int, int], M3ComboBox] = {}

        for row in range(max_slots):
            for day_idx in range(1, 6):  # 1=Lundi ... 5=Vendredi
                tp_list = self._tp_by_day.get(day_idx, [])
                if row < len(tp_list):
                    tp_id, debut, fin = tp_list[row]
                    debut_str = debut.strftime("%H:%M") if debut else ""
                    fin_str = fin.strftime("%H:%M") if fin else ""
                    time_label = f"{debut_str}-{fin_str}"

                    # Colonne Heure (col 0)
                    if day_idx == 1:
                        time_item = QTableWidgetItem(time_label)
                        time_item.setFlags(time_item.flags() & ~Qt.ItemIsEditable)
                        self._tt_grid.setItem(row, 0, time_item)

                    # Combo matière
                    combo = M3ComboBox()
                    combo.addItems(self._subjects)
                    current_subj = self._cht_map.get((day_idx, tp_id), "")
                    idx = combo.findText(current_subj)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                    # Stocker tp_id et cht_id dans le combo
                    combo.setProperty("tp_id", tp_id)
                    combo.setProperty("cht_id", self._cht_id_map.get((day_idx, tp_id), ""))
                    combo.setProperty("day", day_idx)
                    self._cell_combos[(row, day_idx)] = combo
                    self._tt_grid.setCellWidget(row, day_idx, combo)

        self._tt_grid.resizeColumnsToContents()
        self._tt_grid.setColumnWidth(0, 80)
        for c in range(1, 6):
            self._tt_grid.setColumnWidth(c, 140)

    @safe_slot("TimetableEditor._save")
    def _save(self):
        updated = 0

        for (row, day), combo in self._cell_combos.items():
            tp_id = combo.property("tp_id")
            cht_id = combo.property("cht_id")
            subj = combo.currentText().strip()

            if not cht_id:
                continue

            subj_id = self._loader.get_subject_id_by_label(subj)
            if self._loader.update_timetable_slot(cht_id, subj_id):
                updated += 1

        QMessageBox.information(
            self, _("common.label.success"), _("timetable.save_success").format(count=updated)
        )
        self.accept()
