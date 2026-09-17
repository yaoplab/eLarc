"""Vue detaillee par eleve — toutes les evaluations en tableaux-lignes, photo,
commentaire general avec correcteur orthographique, validation de la note.

Gauche : liste des eleves. Droite : sections Formatives | Sommatives en
parallele (une ligne par evaluation : Label | Nature | A B C D, lecture
seule), en bas la photo grande + nom + matiere a gauche, jugements
auto-calcules, note/7 predite, checkbox validation et commentaire a droite.
"""
from __future__ import annotations

import os
import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot
from larccommon.photos import get_photo_path
from larccommon.widgets.themed_widget import ThemedDialog
from common.database import db
from common.session import session
from common.logger import log

try:
    import enchant
    HAS_ENCHANT = True
except ImportError:
    from larccommon.error_reporting import get_reporter
    get_reporter().report_exception()
    HAS_ENCHANT = False


class _SpellHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, lang='fr_FR'):
        super().__init__(parent)
        self._fmt = QTextCharFormat()
        self._fmt.setUnderlineColor(Qt.red)
        self._fmt.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        self._dict = None
        if HAS_ENCHANT:
            try:
                self._dict = enchant.Dict(lang)
            except Exception as e:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                log(f"Correcteur orthographique indisponible : {e}")

    def highlightBlock(self, text: str):
        if self._dict is None:
            return
        for m in re.finditer(r'\b\w{2,}\b', text):
            word = m.group()
            if not self._dict.check(word):
                self.setFormat(m.start(), m.end() - m.start(), self._fmt)


class StudentCardView(ThemedDialog):
    """Fenetre de consultation des notes d'un eleve (lecture seule)."""

    def __init__(self, termsubject_id: int, subject_label: str,
                 class_id: int, cycle: str, parent=None):
        super().__init__(parent)
        self._ts_id = termsubject_id
        self._subject_label = subject_label
        self._class_id = class_id
        self._cycle = cycle
        self._term_obs_dirty = False
        # Aucun élève sélectionné tant que l'utilisateur n'a pas cliqué dans
        # la liste : _load_data → _refresh_student_data doit pouvoir lire cet
        # attribut (None → pas de données, panneau droit vide).
        self._current_student_id = None

        self.setWindowTitle(f"Eleves — {subject_label}")
        self.resize(ds.window_width + ds.sidebar_width, ds.window_height)
        self.setModal(False)

        self._load_data()
        self._setup_ui()
        ds.theme_changed.connect(self._restyle)

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        s = theme_manager.font_size
        return f"""
            QDialog {{ background: {p.background}; }}
            QWidget#root {{ background: {p.background}; color: {p.text_strong}; }}
            QListWidget {{
                background: {p.surface}; color: {p.text_strong};
                border: 1px solid {p.outline_variant};
                font-size: {s(13)}px;
            }}
            QListWidget::item {{
                padding: {ds.space_xs}px {ds.space_sm}px; border-bottom: 1px solid {p.outline_variant};
            }}
            QListWidget::item:selected {{
                background: {p.primary}; color: {p.on_primary};
            }}
            QListWidget::item:hover:!selected {{
                background: {p.surface_variant};
            }}
            QFrame#judgment_panel {{
                background: {p.surface}; color: {p.text_strong};
                border: 1px solid {p.outline_variant};
            }}
            QTableWidget {{
                background: {p.surface}; color: {p.text_strong};
                border: 1px solid {p.outline_variant};
                gridline-color: {p.outline_variant};
            }}
            QTableWidget::item {{
                color: {p.text_strong}; padding: {ds.space_xxs}px;
            }}
            QHeaderView::section {{
                background: {p.surface_variant}; color: {p.text_strong};
                font-weight: bold; padding: {ds.space_xxs}px;
                border: none; border-bottom: 2px solid {p.primary};
                font-size: {s(11)}px;
            }}
            QLabel#jlbl {{
                font-size: {s(14)}px; font-weight: bold; color: {p.text_strong};
            }}
            QLabel#jval {{
                font-size: {s(22)}px; font-weight: bold; color: {p.text_strong};
            }}
            QLabel#note_lbl {{
                font-size: {s(16)}px; font-weight: bold; color: {p.text_strong};
            }}
            QLabel#section_title {{
                font-size: {s(13)}px; font-weight: bold; color: {p.primary};
            }}
            QLabel#photo_lbl {{
                background: {p.surface_variant}; color: {p.text_strong};
                border: 2px solid {p.primary}; border-radius: {ds.radius_lg}px;
                font-size: {s(18)}px; font-weight: bold;
            }}
            QLabel#student_name {{
                font-size: {s(18)}px; font-weight: bold; color: {p.text_strong};
            }}
            QLabel#student_sub {{
                font-size: {s(12)}px; color: {p.text_strong};
            }}
            QTextEdit {{
                background: {p.surface}; color: {p.text_strong};
                border: 1px solid {p.outline_variant};
                padding: {ds.space_xs}px; font-size: {s(13)}px;
            }}
            QPushButton#save_btn {{
                background: {p.success}; color: white; border: none;
                font-size: {s(13)}px; font-weight: bold;
                padding: {ds.space_xs}px {ds.space_m3}px;
                min-height: {ds.field_height + ds.space_xs}px;
            }}
            QPushButton#save_btn:hover {{ background: {p.success}; }}
            QPushButton#save_btn:disabled {{ background: {p.outline_variant}; }}
        """

    # ── Data ──────────────────────────────────────────────────

    def _load_data(self):
        conn = db.local_conn
        if conn is None:
            return
        # Eleves de la classe
        rows = conn.execute("""
            SELECT s.aecuser_ptr_id, aec.last_name, aec.first_name
            FROM larcauth_student s
            JOIN larcauth_aecuser aec ON aec.id = s.aecuser_ptr_id
            WHERE s.s_classroom_id = ? AND s.enabled = 1
            ORDER BY aec.last_name, aec.first_name
        """, (self._class_id,)).fetchall()
        self._students = [{'id': r[0], 'nom': r[1], 'prenom': r[2]} for r in rows]

        # Evaluations
        evals = conn.execute("""
            SELECT type_evaluation, index_eval, crit_a, crit_b, crit_c, crit_d,
                   label, nature, source
            FROM larcauth_evaluation
            WHERE fk_classroom_termsubject_id = ? AND CAST(index_eval AS INTEGER) BETWEEN 1 AND 12
            ORDER BY type_evaluation, CAST(index_eval AS INTEGER)
        """, (str(self._ts_id),)).fetchall()

        self._evals_f, self._evals_s = [], []
        for r in evals:
            etype = str(r[0]).strip().upper()
            item = {
                'type': etype, 'index': int(r[1]),
                'crits': {'a': str(r[2]) == '1', 'b': str(r[3]) == '1',
                          'c': str(r[4]) == '1', 'd': str(r[5]) == '1'},
                'label': r[6] or '', 'nature': r[7] or '', 'source': r[8] or '',
            }
            if etype in ('F', 'FORMATIVES'):
                self._evals_f.append(item)
            else:
                self._evals_s.append(item)

        self._refresh_student_data()

    def _refresh_student_data(self):
        """Recharge les donnees de l'eleve selectionne depuis la DB."""
        sid = self._current_student_id
        conn = db.local_conn
        self._notes: dict[str, str] = {}
        self._learner_id = None
        self._judgments: dict[str, int] = {}
        self._note_on_7 = None
        self._note_checked = False
        self._term_obs = ''

        if conn is None or sid is None:
            return

        table = ('larcauth_learnerpei_has_termsubjectpei' if self._cycle == 'PEI'
                 else 'larcauth_learnerdp_has_termsubjectdp')

        row = conn.execute(f"""
            SELECT * FROM "{table}"
            WHERE fk_student_id = ? LIMIT 1
        """, (sid,)).fetchone()

        if row is None:
            return
        cols = [c[1] for c in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]
        self._notes = {cols[i]: str(row[i]) if row[i] is not None else '' for i in range(len(cols))}
        self._learner_id = row[0]

        # Jugements
        for c in ('a', 'b', 'c', 'd'):
            key = f'jgt_{c}'
            val = self._notes.get(key, '') if key in self._notes else ''
            self._judgments[c] = int(val) if val and val not in ('0', 'None') else 0

        # Note/7
        note_key = 'note_on_7' if self._cycle == 'PEI' else 'moy_on_20'
        note_val = self._notes.get(note_key, '')
        self._note_on_7 = float(note_val) if note_val and note_val != 'None' else None

        # Validation
        checked_val = self._notes.get('note_on_7_checked', '')
        self._note_checked = checked_val in ('1', 'True', 'true', True)

        # Commentaire general
        self._term_obs = self._notes.get('term_observation', '') or ''

    # ── UI ────────────────────────────────────────────────────

    def _setup_ui(self):
        self.setStyleSheet(self._STYLE)

        root = QWidget()
        root.setObjectName('root')
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
        self.layout().setSpacing(ds.space_md)
        self.layout().addWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.space_md)

        # Splitter gauche/droite
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_student_list())
        splitter.addWidget(self._build_detail_panel())
        splitter.setSizes([ds.sidebar_width, ds.window_width])
        layout.addWidget(splitter, 1)

        if self._students:
            self._student_list.setCurrentRow(0)

    def _build_student_list(self) -> QWidget:
        p = theme_manager.palette
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.space_xs)

        lbl = QLabel(f"{len(self._students)} eleves")
        lbl.setStyleSheet(f"font-size: {theme_manager.font_size(12)}px; font-weight: bold; color: {p.text_strong};")
        layout.addWidget(lbl)

        self._student_list = QListWidget()
        self._student_list.setCursor(Qt.PointingHandCursor)
        for s in self._students:
            item = QListWidgetItem(f"{s['nom']} {s['prenom']}")
            item.setData(Qt.UserRole, s['id'])
            self._student_list.addItem(item)
        self._student_list.currentRowChanged.connect(self._on_student_changed)

        layout.addWidget(self._student_list, 1)
        return container

    def _build_detail_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.space_md)

        # Sections Formatives | Sommatives en parallele (tableaux-lignes)
        sections = QSplitter(Qt.Horizontal)
        sections.addWidget(self._build_section_table('Formatives', self._evals_f, 'F'))
        sections.addWidget(self._build_section_table('Sommatives', self._evals_s, 'S'))
        sections.setSizes([ds.window_width // 2, ds.window_width // 2])
        layout.addWidget(sections, 3)

        # Bas : photo + nom/matiere a gauche, jugements/note/commentaire a droite
        bottom = QHBoxLayout()
        bottom.setSpacing(ds.space_md)
        bottom.addWidget(self._build_photo_header(), 1)

        right = QVBoxLayout()
        right.setSpacing(ds.space_md)
        right.addWidget(self._build_judgments_panel())
        right.addWidget(self._build_note_panel())
        right.addWidget(self._build_comment_section())

        # Bouton Enregistrer
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._save_btn = QPushButton('Enregistrer le commentaire')
        self._save_btn.setObjectName('save_btn')
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)
        right.addLayout(btn_row)
        bottom.addLayout(right, 2)

        layout.addLayout(bottom, 2)
        return container

    def _build_photo_header(self) -> QWidget:
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(ds.space_sm)

        self._photo_lbl = QLabel()
        self._photo_lbl.setObjectName('photo_lbl')
        self._photo_lbl.setFixedSize(ds.header_height * 4, ds.header_height * 4)
        self._photo_lbl.setAlignment(Qt.AlignCenter)
        lay.addStretch()
        lay.addWidget(self._photo_lbl, 0, Qt.AlignHCenter)
        lay.addStretch()

        self._student_name_lbl = QLabel('')
        self._student_name_lbl.setObjectName('student_name')
        self._student_name_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._student_name_lbl)

        self._student_sub_lbl = QLabel(self._subject_label)
        self._student_sub_lbl.setObjectName('student_sub')
        self._student_sub_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._student_sub_lbl)
        return container

    def _update_photo(self) -> None:
        """Photo de l'eleve courant (placeholder initiales si absente)."""
        sid = self._current_student_id
        pix = None
        if sid is not None:
            path = get_photo_path(sid)
            if path and os.path.isfile(path):
                pm = QPixmap(path)
                if not pm.isNull():
                    pix = pm.scaled(ds.header_height * 4 - 8, ds.header_height * 4 - 8,
                                    Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if pix is not None:
            self._photo_lbl.setPixmap(pix)
            self._photo_lbl.setText('')
        else:
            self._photo_lbl.setPixmap(QPixmap())
            initials = ''
            if sid is not None:
                cur = next((s for s in self._students if s['id'] == sid), None)
                if cur is not None:
                    initials = f"{cur['nom'][:1]}{cur['prenom'][:1]}"
            self._photo_lbl.setText(initials or '—')

    def _build_section_table(self, titre: str, evals: list, etype: str) -> QWidget:
        """Tableau-lignes d'une section : Label | Nature | A B C D, une ligne par eval."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.space_xs)

        title = QLabel(titre)
        title.setObjectName('section_title')
        layout.addWidget(title)

        tbl = QTableWidget(0, 6)
        tbl.setObjectName(f'{etype.lower()}_table')
        tbl.setHorizontalHeaderLabels(['Label', 'Nature', 'A', 'B', 'C', 'D'])
        tbl.verticalHeader().setVisible(False)
        tbl.setSelectionMode(QTableWidget.NoSelection)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setFocusPolicy(Qt.NoFocus)
        tbl.verticalHeader().setDefaultSectionSize(ds.table_row_min)
        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        tbl.setColumnWidth(1, ds.table_row_min * 3)
        for col in range(2, 6):
            hdr.setSectionResizeMode(col, QHeaderView.Fixed)
            tbl.setColumnWidth(col, ds.table_row_min + ds.space_xs)
        layout.addWidget(tbl, 1)

        if etype == 'F':
            self._f_table = tbl
        else:
            self._s_table = tbl
        self._fill_section_table(tbl, evals, etype)
        return container

    def _fill_section_table(self, tbl: QTableWidget, evals: list, etype: str) -> None:
        """Une ligne par evaluation : label (tooltip observation), nature, notes ABCD."""
        p = theme_manager.palette
        tbl.setRowCount(len(evals))
        for i, ev in enumerate(evals):
            idx = ev['index']

            lbl_it = QTableWidgetItem(ev['label'] or f"{etype}{idx:02d}")
            obs = self._notes.get(f"{etype.lower()}{idx:02d}_observation", '') or ''
            if obs:
                lbl_it.setToolTip(obs)
            tbl.setItem(i, 0, lbl_it)

            tbl.setItem(i, 1, QTableWidgetItem(ev['nature']))

            for ci, crit in enumerate(('a', 'b', 'c', 'd')):
                col_name = f"{etype.lower()}{idx:02d}_note_{crit}"
                val = self._notes.get(col_name, '')
                it = QTableWidgetItem()
                if not ev['crits'][crit] or not val or val in ('0', 'None'):
                    it.setText('—')
                    color = p.text_disabled
                else:
                    fval = float(val)
                    it.setText(str(int(fval)) if fval.is_integer() else str(fval))
                    color = p.success if fval >= 4 else p.error
                it.setForeground(QColor(color))
                it.setTextAlignment(Qt.AlignCenter)
                tbl.setItem(i, 2 + ci, it)

    def _build_judgments_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName('judgment_panel')
        panel.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(ds.space_m3, ds.space_sm, ds.space_m3, ds.space_sm)
        layout.setSpacing(ds.space_md)

        lbl = QLabel('Jugements :')
        lbl.setObjectName('jlbl')
        layout.addWidget(lbl)

        self._jgt_labels: dict[str, QLabel] = {}
        for crit in ('a', 'b', 'c', 'd'):
            cl = QVBoxLayout()
            cl.setSpacing(0)
            cl.setAlignment(Qt.AlignCenter)
            c_title = QLabel(f'Crit. {crit.upper()}')
            c_title.setStyleSheet(f"font-size: {theme_manager.font_size(10)}px; color: {theme_manager.palette.text_strong};")
            c_title.setAlignment(Qt.AlignCenter)
            cl.addWidget(c_title)
            c_val = QLabel('—')
            c_val.setObjectName('jval')
            c_val.setAlignment(Qt.AlignCenter)
            cl.addWidget(c_val)
            self._jgt_labels[crit] = c_val
            layout.addLayout(cl)

        layout.addStretch()
        return panel

    def _build_note_panel(self) -> QWidget:
        p = theme_manager.palette
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.space_md)

        note_title = 'Note prevue :' if self._cycle == 'PEI' else 'Moyenne prevue :'
        suffix = '/7' if self._cycle == 'PEI' else '/20'

        self._note_display = QLabel(f'{note_title} —{suffix}')
        self._note_display.setObjectName('note_lbl')
        layout.addWidget(self._note_display)

        self._valid_cb = QCheckBox('Validee')
        self._valid_cb.setStyleSheet(
            f"QCheckBox {{ font-size: {theme_manager.font_size(13)}px; color: {p.text_strong}; "
            f"spacing: {ds.space_xs}px; font-weight: bold; }}"
            f"QCheckBox::indicator {{ width: 18px; height: 18px; "
            f"border: 2px solid {p.outline}; border-radius: {ds.radius_xs}px; }}")
        self._valid_cb.toggled.connect(self._on_validation_toggled)
        layout.addWidget(self._valid_cb)
        layout.addStretch()
        return container

    def _build_comment_section(self) -> QWidget:
        p = theme_manager.palette
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.space_xs)

        lbl = QLabel('Commentaire general du trimestre :')
        lbl.setStyleSheet(f"font-size: {theme_manager.font_size(13)}px; font-weight: bold; color: {p.text_strong};")
        layout.addWidget(lbl)

        self._comment_edit = QTextEdit()
        self._comment_edit.setPlaceholderText('Saisir le commentaire general...')
        self._comment_edit.setMinimumHeight(ds.kpi_card_height)
        self._comment_edit.setMaximumHeight(ds.kpi_card_height * 2)
        self._comment_edit.textChanged.connect(self._on_comment_changed)
        self._spell = _SpellHighlighter(self._comment_edit.document(), 'fr_FR')
        layout.addWidget(self._comment_edit)

        return container

    # ── Events ────────────────────────────────────────────────

    @safe_slot("StudentCardView._on_student_changed")
    def _on_student_changed(self, idx: int):
        if idx < 0:
            return
        item = self._student_list.item(idx)
        self._current_student_id = item.data(Qt.UserRole)
        self._refresh_student_data()
        cur = next((s for s in self._students if s['id'] == self._current_student_id), None)
        self._student_name_lbl.setText(f"{cur['nom']} {cur['prenom']}" if cur else '')
        self._update_photo()
        self._fill_section_table(self._f_table, self._evals_f, 'F')
        self._fill_section_table(self._s_table, self._evals_s, 'S')
        self._update_judgments()
        self._update_note()
        self._comment_edit.blockSignals(True)
        self._comment_edit.setPlainText(self._term_obs)
        self._comment_edit.blockSignals(False)
        self._term_obs_dirty = False
        self._save_btn.setEnabled(False)

    def _update_judgments(self):
        p = theme_manager.palette
        for crit in ('a', 'b', 'c', 'd'):
            val = self._judgments.get(crit, 0)
            self._jgt_labels[crit].setText(str(val) if val else '—')
            color = p.success if val and val >= 4 else p.error if val else p.text_disabled
            self._jgt_labels[crit].setStyleSheet(
                f"font-size: {theme_manager.font_size(22)}px; font-weight: bold; color: {color};")

    def _update_note(self):
        p = theme_manager.palette
        suffix = '/7' if self._cycle == 'PEI' else '/20'
        note_title = 'Note prevue :' if self._cycle == 'PEI' else 'Moyenne prevue :'
        if self._note_on_7 is not None:
            self._note_display.setText(f'{note_title} {self._note_on_7}{suffix}')
            self._note_display.setStyleSheet(
                f"font-size: {theme_manager.font_size(16)}px; font-weight: bold; color: {p.text_strong};")
        else:
            self._note_display.setText(f'{note_title} —{suffix}')
            self._note_display.setStyleSheet(
                f"font-size: {theme_manager.font_size(16)}px; font-weight: bold; color: {p.text_disabled};")

        self._valid_cb.blockSignals(True)
        self._valid_cb.setChecked(self._note_checked)
        self._valid_cb.blockSignals(False)
        self._valid_cb.setStyleSheet(
            f"QCheckBox {{ font-size: {theme_manager.font_size(13)}px; "
            f"color: {'#2E7D32' if self._note_checked else p.text_soft}; "
            f"spacing: {ds.space_xs}px; font-weight: bold; }}"
            f"QCheckBox::indicator {{ width: 18px; height: 18px; "
            f"border: 2px solid {'#2E7D32' if self._note_checked else '#E65100'}; "
            f"border-radius: {ds.radius_xs}px; "
            f"background: {'#2E7D32' if self._note_checked else p.surface}; }}")

    @safe_slot("StudentCardView._on_comment_changed")
    def _on_comment_changed(self):
        self._term_obs_dirty = True
        self._save_btn.setEnabled(True)

    @safe_slot("StudentCardView._on_validation_toggled")
    def _on_validation_toggled(self, checked: bool):
        conn = db.local_conn
        if conn is None or self._learner_id is None:
            return
        self._note_checked = checked
        table = ('larcauth_learnerpei_has_termsubjectpei' if self._cycle == 'PEI'
                 else 'larcauth_learnerdp_has_termsubjectdp')
        conn.execute(
            f'UPDATE "{table}" SET note_on_7_checked = ? WHERE id = ?',
            (checked, self._learner_id)
        )
        conn.commit()
        self._update_note()

    @safe_slot("Unknown._on_save")
    def _on_save(self):
        conn = db.local_conn
        if conn is None or self._learner_id is None:
            QMessageBox.warning(self, "Erreur", "Connexion locale ou élève indisponible.")
            return
        table = ('larcauth_learnerpei_has_termsubjectpei' if self._cycle == 'PEI'
                 else 'larcauth_learnerdp_has_termsubjectdp')
        text = self._comment_edit.toPlainText()
        conn.execute(
            f'UPDATE "{table}" SET term_observation = ? WHERE id = ?',
            (text, self._learner_id)
        )
        conn.commit()
        self._term_obs_dirty = False
        self._save_btn.setEnabled(False)

    # ── Theme ─────────────────────────────────────────────────

    @safe_slot("StudentCardView._restyle")
    def _restyle(self):
        self.setStyleSheet(self._STYLE)
        self._fill_section_table(self._f_table, self._evals_f, 'F')
        self._fill_section_table(self._s_table, self._evals_s, 'S')
        self._update_judgments()
        self._update_note()
