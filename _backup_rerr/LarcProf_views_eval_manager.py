"""Fenetre de gestion des evaluations (Formatives ou Sommatives).

Design: conforme form-pattern (FP1-FP14), ergonomics (Q7-Q21).
Gauche : tabs F01-F12 + liste verticale de barres slots
Droite : formulaire de detail responsive
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from larccommon.design_system import ds
from larccommon.theme import theme_manager
from common.database import db
from common.eval_helpers import save_evaluation_criteria
from common.logger import log
from views.evaluation_panel import EvaluationDetailWidget
from larccommon.safe_slot import safe_slot
from larccommon.widgets.themed_widget import ThemedDialog


# ── Barre slot cliquable (horizontale) ──
class _SlotBar(QFrame):
    clicked = Signal(int)

    def __init__(self, slot_index: int, eval_type: str, parent=None):
        super().__init__(parent)
        self.slot_index = slot_index
        self.eval_type = eval_type
        self.eval_id = None
        self._active = False
        self._data: dict | None = None

        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._build_ui()
        self.clear()
        ds.theme_changed.connect(self._restyle)

    def _build_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QHBoxLayout(self)
        layout.setContentsMargins(ds.space_xxs, ds.space_xxs, ds.space_xxs, ds.space_xxs)
        layout.setSpacing(ds.space_xxs)

        self._code = QLabel(f"{self.eval_type}{self.slot_index:02d}")
        self._code.setFixedWidth(ds.idx_label_width)
        self._code.setAlignment(Qt.AlignCenter)
        self._code.setStyleSheet(
            f"font-weight: bold; font-size: {s(10)}px; border: none; padding: 0;")
        layout.addWidget(self._code)

        self._label = QLabel('')
        self._label.setStyleSheet(
            f"font-size: {s(10)}px; color: {p.text_strong}; border: none; padding: 0;")
        self._label.setWordWrap(True)
        layout.addWidget(self._label, 1)

        self._crits: dict[str, QCheckBox] = {}
        for letter in ('A', 'B', 'C', 'D'):
            cb = QCheckBox(letter)
            cb.setEnabled(False)
            cb.setStyleSheet(f"font-size: {s(9)}px; border: none; padding: 0;")
            self._crits[letter] = cb
            layout.addWidget(cb)

    def mousePressEvent(self, event):
        self.clicked.emit(self.slot_index)

    def set_data(self, eval_id, data: dict):
        self.eval_id = eval_id
        self._data = data
        nature = (data.get('nature') or '').strip()
        self._label.setText(nature[:72] if nature else '')
        active = False
        for letter in ('A', 'B', 'C', 'D'):
            val = data.get(f'crit_{letter.lower()}', '0')
            checked = val in ('1', 1, True)
            self._crits[letter].setChecked(checked)
            if checked:
                active = True
        self._active = active

    def clear(self):
        self.eval_id = None
        self._active = False
        self._data = None
        self._label.setText('')
        for cb in self._crits.values():
            cb.setChecked(False)

    def restyle(self):
        """Ré-applique le style (actif ou suivant) avec la palette courante."""
        p = theme_manager.palette
        if self._active and self.eval_id is not None:
            self.setStyleSheet(
                f"_SlotBar {{ background: {p.surface}; border: 1px solid {p.success}; "
                f"border-radius: {ds.radius_xs}px; padding: {ds.space_xxs}px; }}")
            code_color, label_color = p.text_strong, p.text_strong
        else:
            self.setStyleSheet(
                f"_SlotBar {{ background: {p.surface_variant}; border: 1px dashed {p.outline_variant}; "
                f"border-radius: {ds.radius_xs}px; padding: {ds.space_xxs}px; }}")
            code_color, label_color = p.text_disabled, p.text_disabled
        self._code.setStyleSheet(
            f"font-weight: bold; font-size: {theme_manager.font_size(10)}px; "
            f"color: {code_color}; border: none; padding: 0;")
        self._label.setStyleSheet(
            f"font-size: {theme_manager.font_size(10)}px; color: {label_color}; border: none; padding: 0;")

    def _restyle(self):
        """Hook theme_changed — même rendu que restyle()."""
        self.restyle()


# ── Fenetre de gestion ──
class EvalManagerWindow(ThemedDialog):

    def __init__(self, eval_type: str, termsubject_id: int,
                 subject_label: str = '', parent=None):
        super().__init__(parent)
        self.eval_type = eval_type
        self._termsubject_id = termsubject_id
        self._subject_label = subject_label
        self._current_slot_index = 1

        type_label = "Formatives" if eval_type == 'F' else "Sommatives"
        self.setWindowTitle(f"Gestion des Evaluations {type_label} — {subject_label}")
        self.setMinimumSize(ds.window_width * 3 // 4, ds.window_height * 3 // 4)
        self.setModal(False)

        self._build_ui()
        self._load_data()
        self._on_slot_selected(1)
        ds.theme_changed.connect(self._restyle)

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        s = theme_manager.font_size
        return f"""
            QDialog {{ background: {p.background}; }}
            QFrame#left_panel {{
                background: {p.surface}; color: {p.text_strong};
                border: 1px solid {p.outline_variant}; border-radius: {ds.radius_md}px;
            }}
            QFrame#right_panel {{
                background: {p.surface}; color: {p.text_strong};
                border: 1px solid {p.outline_variant}; border-radius: {ds.radius_md}px;
            }}
            QScrollArea {{ border: none; background: transparent; }}
            QPushButton#save_btn {{
                background: {p.success}; color: white; font-weight: bold;
                font-size: {s(13)}px; padding: {ds.space_xs}px {ds.space_m3}px;
                border: none; border-radius: {ds.radius_lg}px;
                min-height: {ds.field_height + ds.space_xs}px;
            }}
            QPushButton#save_btn:hover {{ background: {p.success}; }}
        """

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.setStyleSheet(self._STYLE)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        self._left_panel = self._build_left_panel()
        self._right_panel = self._build_right_panel()
        splitter.addWidget(self._left_panel)
        splitter.addWidget(self._right_panel)
        splitter.setSizes([ds.jugements_width + ds.sidebar_width + ds.space_md,
                           ds.kpi_card_height * 6 + ds.space_md])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_xxs, ds.space_xxs, ds.space_xxs, ds.space_xxs)
        layout.setSpacing(0)
        layout.addWidget(splitter)

        self._status_lbl = QLabel('')
        self._status_lbl.setStyleSheet(
            f"font-size: {theme_manager.font_size(10)}px; color: {theme_manager.palette.text_strong}; "
            f"padding: {ds.space_xxs}px 0;")
        layout.addWidget(self._status_lbl)

    def _build_left_panel(self) -> QWidget:
        container = QFrame()
        container.setObjectName('left_panel')
        container.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(ds.space_xs, ds.space_xs, ds.space_xs, ds.space_xs)
        layout.setSpacing(ds.space_xs)

        self._build_tabs(layout)

        self._legend = QLabel('')
        self._legend.setStyleSheet(
            f"font-size: {theme_manager.font_size(8)}px; color: {theme_manager.palette.text_strong}; "
            f"border: none; padding: 0;")
        self._legend.setWordWrap(True)
        self._legend.hide()
        layout.addWidget(self._legend)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.viewport().setStyleSheet("background: transparent;")

        self._list_container = QWidget()
        self._list_container.setAttribute(Qt.WA_StyledBackground, True)
        self._list_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._list_container.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(ds.space_xs)

        self._bars: list[_SlotBar] = []
        for i in range(12):
            bar = _SlotBar(i + 1, self.eval_type)
            bar.clicked.connect(self._on_slot_selected)
            self._bars.append(bar)
            self._list_layout.addWidget(bar)

        self._list_layout.addStretch()
        scroll.setWidget(self._list_container)
        layout.addWidget(scroll, 1)

        return container

    def _build_tabs(self, layout: QVBoxLayout):
        p = theme_manager.palette
        tabs = QWidget()
        tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        th = QHBoxLayout(tabs)
        th.setContentsMargins(0, 0, 0, 0)
        th.setSpacing(ds.space_xs)   # distance entre boutons = 8

        self._tab_btns: list[QPushButton] = []
        for i in range(12):
            btn = QPushButton(f"{self.eval_type}{i + 1:02d}")
            btn.setFixedHeight(ds.field_height)   # Fibonacci LG = 32
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{ font-size: {theme_manager.font_size(10)}px; font-weight: bold;
                    padding: {ds.space_xxs // 2}px {ds.space_xs}px;
                    background: {p.outline_variant}; color: {p.text_disabled};
                    border: none; border-radius: {ds.radius_xs}px; }}
                QPushButton:checked {{ background: {p.success}; color: white; }}
                QPushButton:hover {{ background: {p.outline_variant}; }}
            """)
            btn.clicked.connect(lambda checked, idx=i + 1: self._on_tab_clicked(idx))
            self._tab_btns.append(btn)
            th.addWidget(btn)

        layout.addWidget(tabs)

    def _build_right_panel(self) -> QWidget:
        p = theme_manager.palette
        container = QFrame()
        container.setObjectName('right_panel')
        container.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(ds.space_sm, ds.space_sm, ds.space_sm, ds.space_sm)
        layout.setSpacing(ds.space_xs)

        self._detail = EvaluationDetailWidget(
            1, self.eval_type, None, self._termsubject_id, self._subject_label)
        layout.addWidget(self._detail, 1)

        self._save_btn = QPushButton("Enregistrer cette evaluation")
        self._save_btn.setObjectName('save_btn')
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.clicked.connect(self._on_save_slot)
        layout.addWidget(self._save_btn)

        return container

    # ------------------------------------------------------------------
    # Logique
    # ------------------------------------------------------------------
    def _load_data(self):
        conn = db.local_conn
        if conn is None:
            return
        try:
            row = conn.execute(
                "SELECT fk_levelsubject_id FROM larcauth_classroom_termsubject WHERE id = ?",
                (str(self._termsubject_id),)).fetchone()
            if row:
                ls_id = row[0]
                rows = conn.execute(
                    "SELECT criteria_letter, criteria_label FROM larcauth_criteria_of_levelsubject "
                    "WHERE fk_levelsubject_id = ? AND criteria_letter IN ('A','B','C','D') "
                    "ORDER BY criteria_letter", (ls_id,)).fetchall()
                if rows:
                    parts = []
                    for r in rows:
                        lbl = (r[1] or '').replace('\n', ' ')
                        parts.append(f'{r[0]}: {lbl}')
                    self._legend.setText(' | '.join(parts))
                    self._legend.show()
        except Exception as e:
            log(f"Erreur légende évaluations : {e}")

        rows = conn.execute(
            "SELECT id, index_eval, crit_a, crit_b, crit_c, crit_d, label, nature, source "
            "FROM larcauth_evaluation "
            "WHERE fk_classroom_termsubject_id = ? AND type_evaluation = ? "
            "AND CAST(index_eval AS INTEGER) BETWEEN 1 AND 12 "
            "ORDER BY CAST(index_eval AS INTEGER)",
            (str(self._termsubject_id), self.eval_type)).fetchall()

        loaded = {int(r[1]): r for r in rows}
        for bar in self._bars:
            r = loaded.get(bar.slot_index)
            if r:
                bar.set_data(r[0], {
                    'crit_a': r[2], 'crit_b': r[3], 'crit_c': r[4], 'crit_d': r[5],
                    'label': r[6] or '', 'nature': r[7] or '', 'source': r[8] or ''})
            else:
                bar.clear()

        self._update_visibility()
        self._update_tabs()

    def _update_visibility(self):
        found_next = False
        for bar in self._bars:
            if bar._active and bar.eval_id is not None:
                bar.restyle()
                bar.setVisible(True)
            elif not found_next:
                bar.restyle()
                bar.setVisible(True)
                found_next = True
            else:
                bar.setVisible(False)

    def _update_tabs(self):
        p = theme_manager.palette
        for i, bar in enumerate(self._bars):
            active = bar._active and bar.eval_id is not None
            btn = self._tab_btns[i]
            if active:
                btn.setStyleSheet(f"""
                    QPushButton {{ font-size: {theme_manager.font_size(10)}px; font-weight: bold;
                        padding: {ds.space_xxs // 2}px {ds.space_xs}px;
                        background: {p.success}; color: white; border: none;
                        border-radius: {ds.radius_xs}px; }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{ font-size: {theme_manager.font_size(10)}px; font-weight: bold;
                        padding: {ds.space_xxs // 2}px {ds.space_xs}px;
                        background: {p.outline_variant}; color: {p.text_disabled};
                        border: none; border-radius: {ds.radius_xs}px; }}
                """)
            btn.setChecked(i + 1 == self._current_slot_index)

    @safe_slot("EvalManagerWindow._on_tab_clicked")
    def _on_tab_clicked(self, slot_index: int):
        self._on_slot_selected(slot_index)

    @safe_slot("Unknown._on_slot_selected")
    def _on_slot_selected(self, slot_index: int):
        self._current_slot_index = slot_index
        bar = self._bars[slot_index - 1]
        self._detail.set_slot_info(slot_index, self.eval_type)
        self._detail.set_data(bar._data or {})
        self._detail._load_criteria_labels()
        self._update_tabs()

    @safe_slot("Unknown._on_save_slot")
    def _on_save_slot(self):
        bar = self._bars[self._current_slot_index - 1]
        form_data = self._detail.get_form_data()
        slot_id = bar.eval_id
        if slot_id is None:
            self._status_msg('Impossible d\'enregistrer: evaluation non identifiee')
            return

        label_val = (bar._data or {}).get('label', '')
        if not save_evaluation_criteria(slot_id, label_val,
                form_data.get('nature', ''), form_data.get('source', ''),
                {k: form_data.get(k, '0') for k in ('crit_a', 'crit_b', 'crit_c', 'crit_d')}):
            self._status_msg('Erreur: base locale non disponible')
            return

        if bar._data:
            bar._data['nature'] = form_data.get('nature', '')
            bar._data['source'] = form_data.get('source', '')
            for k in ('crit_a', 'crit_b', 'crit_c', 'crit_d'):
                bar._data[k] = form_data.get(k, '0')
        bar.set_data(slot_id, bar._data or {})
        self._update_visibility()
        self._update_tabs()
        self._status_msg(f'Evaluation {self.eval_type}{self._current_slot_index:02d} enregistree')

    def _status_msg(self, msg: str):
        self._status_lbl.setText(msg)

    # ── Theme reactivity ──
    @safe_slot("EvalManagerWindow._restyle")
    def _restyle(self):
        self.setStyleSheet(self._STYLE)
        p = theme_manager.palette
        for bar in self._bars:
            bar.restyle()
        self._update_tabs()
        self._status_lbl.setStyleSheet(
            f"font-size: {theme_manager.font_size(10)}px; color: {p.text_strong}; "
            f"padding: {ds.space_xxs}px 0;")
        if hasattr(self, '_legend') and self._legend:
            self._legend.setStyleSheet(
                f"font-size: {theme_manager.font_size(8)}px; color: {p.text_strong}; "
                f"border: none; padding: 0;")
