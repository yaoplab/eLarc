"""Panneau d'évaluations (Formatives F01-F12 / Sommatives S01-S12)
avec slots cliquables ouvrant une fenêtre de détail."""
from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QCheckBox,
    QSizePolicy,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from larccommon.design_system import ds
from larccommon.theme import theme_manager
from common.database import db
from common.logger import log
from larccommon.safe_slot import safe_slot
from larccommon.widgets.themed_widget import ThemedDialog

try:
    import enchant
    HAS_ENCHANT = True
except ImportError:
    from larccommon.error_reporting import get_reporter
    get_reporter().report_exception()
    HAS_ENCHANT = False


# ---------------------------------------------------------------------------
# Surligneur orthographique
# ---------------------------------------------------------------------------

class _SpellHighlighter(QSyntaxHighlighter):
    """Surligne les mots mal orthographiés en rouge (si enchant disponible)."""

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
        for m in re.finditer(r'\b\w+\b', text):
            word = m.group()
            if word.isdigit() or len(word) <= 1:
                continue
            if not self._dict.check(word):
                self.setFormat(m.start(), m.end() - m.start(), self._fmt)


# ---------------------------------------------------------------------------
# Widget formulaire réutilisable (détail d'une évaluation)
# ---------------------------------------------------------------------------

class EvaluationDetailWidget(QWidget):
    """Formulaire d'édition d'un slot d'évaluation (label, nature, source, critères)."""

    def __init__(self, slot_index: int, eval_type: str, eval_data: dict | None = None,
                 termsubject_id: int | None = None, subject_label: str = '',
                 parent=None):
        super().__init__(parent)
        self.slot_index = slot_index
        self.eval_type = eval_type
        self._data = eval_data
        self._termsubject_id = termsubject_id
        self._subject_label = subject_label

        self._build_ui()
        self._load_data()
        self._load_criteria_labels()

    def _build_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QVBoxLayout(self)
        layout.setSpacing(ds.space_xs)
        layout.setContentsMargins(0, 0, 0, 0)

        # Titre (Q8: label au-dessus, pas QFormLayout)
        self._title_lbl = QLabel(f'{self.eval_type}{self.slot_index:02d}')
        self._title_lbl.setStyleSheet(
            f"font-size: {s(16)}px; font-weight: bold; color: {p.text_strong};")
        layout.addWidget(self._title_lbl)

        if self._subject_label:
            sl = QLabel(self._subject_label)
            sl.setStyleSheet(
                f"font-size: {s(12)}px; color: {p.text_strong}; margin-top: -{ds.space_xxs}px;")
            sl.setWordWrap(True)
            layout.addWidget(sl)

        # Label (affichage)
        self._label_lbl = QLabel('Label :')
        self._label_lbl.setStyleSheet(
            f"font-size: {s(11)}px; font-weight: bold; color: {p.text_strong};")
        layout.addWidget(self._label_lbl)

        self._label_display = QLabel('')
        self._label_display.setStyleSheet(
            f"font-size: {s(12)}px; color: {p.text_strong}; padding: {ds.space_xxs}px 0;")
        self._label_display.setWordWrap(True)
        layout.addWidget(self._label_display)

        # Nature
        self._nature_lbl = QLabel('Nature :')
        self._nature_lbl.setStyleSheet(
            f"font-size: {s(11)}px; font-weight: bold; color: {p.text_strong};")
        layout.addWidget(self._nature_lbl)

        self._nature_edit = QLineEdit()
        self._nature_edit.setPlaceholderText('Nature (ex: Devoir, Interrogation, Projet...)')
        self._nature_edit.setMinimumHeight(ds.field_height)
        self._nature_edit.setStyleSheet(ds.flat_input_qss())
        layout.addWidget(self._nature_edit)

        src_label = QLabel('Source / Texte de l\'évaluation :')
        src_label.setStyleSheet(f"font-size: {theme_manager.font_size(10)}px; font-weight: bold; color: {theme_manager.palette.text_strong};")
        layout.addWidget(src_label)

        # Barre d'outils formatage
        tb = QHBoxLayout()
        tb.setSpacing(ds.space_xs)   # distance entre boutons = 8
        tb.setContentsMargins(0, 0, 0, 0)
        for icon, tip, md_insert in [
            ('B', 'Gras', '**texte**'),
            ('I', 'Italique', '*texte*'),
            ('H', 'Titre', '## '),
            ('•', 'Liste', '- '),
            ('🔗', 'Lien', '[texte](url)'),
        ]:
            p = theme_manager.palette
            btn = QPushButton(icon)
            btn.setFixedSize(ds.icon_btn_size, ds.icon_btn_size)  # Fibonacci LG = 32
            btn.setToolTip(tip)
            btn.setStyleSheet(f"""
                QPushButton {{ font-weight: bold; font-size: {theme_manager.font_size(11)}px;
                              background: {p.surface_variant}; border: 1px solid {p.outline_variant};
                              border-radius: {ds.radius_xs}px; padding: 0; }}
                QPushButton:hover {{ background: {p.outline_variant}; }}
            """)
            btn.clicked.connect(lambda checked, s=md_insert: self._insert_md(s))
            tb.addWidget(btn)
        tb.addStretch()
        layout.addLayout(tb)

        self._source_edit = QTextEdit()
        self._source_edit.setPlaceholderText('Saisir le texte (Markdown supporté)')
        self._source_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._source_edit.setMinimumHeight(ds.button_height)  # 52
        self._source_edit.setAcceptRichText(False)
        self._spell = _SpellHighlighter(self._source_edit.document(), 'fr_FR')
        layout.addWidget(self._source_edit)

        crit_label = QLabel('Critères :')
        crit_label.setStyleSheet(f"font-size: {theme_manager.font_size(11)}px; font-weight: bold; color: {theme_manager.palette.text_strong}; margin-top: 4px;")
        layout.addWidget(crit_label)

        self._crit_grid = QFrame()
        self._crit_grid.setFrameShape(QFrame.StyledPanel)
        p = theme_manager.palette
        d = theme_manager.design
        self._crit_grid.setAttribute(Qt.WA_StyledBackground, True)
        self._crit_grid.setStyleSheet(f"""
            QFrame {{ background: {p.surface_variant}; border: 1px solid {p.outline_variant};
                     border-radius: {d.radius}px; padding: {ds.space_xxs}px; }}
        """)
        grid = QGridLayout(self._crit_grid)
        grid.setContentsMargins(ds.space_xxs, ds.space_xxs, ds.space_xxs, ds.space_xxs)
        grid.setSpacing(ds.space_xxs)

        self._crit_widgets = {}
        for i, letter in enumerate(['a', 'b', 'c', 'd']):
            cb = QCheckBox(letter.upper())
            cb.setStyleSheet(f"font-weight: bold; font-size: {theme_manager.font_size(13)}px;")
            grid.addWidget(cb, 0, i, Qt.AlignCenter)

            cl = QLabel('')
            cl.setStyleSheet(f"color: {theme_manager.palette.text_strong}; font-size: {theme_manager.font_size(10)}px;")
            cl.setWordWrap(True)
            cl.setAlignment(Qt.AlignCenter)
            grid.addWidget(cl, 1, i)

            self._crit_widgets[letter] = {'check': cb, 'label': cl, 'aspects_widget': None}
        layout.addWidget(self._crit_grid)

        ds.theme_changed.connect(self._restyle)

    @safe_slot("EvaluationDetailWidget._restyle")
    def _restyle(self):
        p = theme_manager.palette
        d = theme_manager.design
        qss = (
            f"QFrame {{ background: {p.surface_variant}; border: 1px solid {p.outline_variant}; "
            f"border-radius: {d.radius}px; padding: {ds.space_xxs}px; }}"
        )
        try:
            self._crit_grid.setStyleSheet(qss)
            if hasattr(self, '_label_display') and self._label_display:
                self._label_display.setStyleSheet(
                    f"font-size: {theme_manager.font_size(11)}px; color: {p.text_strong}; "
                    f"padding: {ds.space_xxs}px 0;"
                )
            if hasattr(self, '_title_lbl') and self._title_lbl:
                self._title_lbl.setStyleSheet(
                    f"font-size: {theme_manager.font_size(16)}px; font-weight: bold; color: {p.text_strong};")
            if hasattr(self, '_label_lbl') and self._label_lbl:
                self._label_lbl.setStyleSheet(
                    f"font-size: {theme_manager.font_size(11)}px; font-weight: bold; color: {p.text_strong};")
            if hasattr(self, '_nature_lbl') and self._nature_lbl:
                self._nature_lbl.setStyleSheet(
                    f"font-size: {theme_manager.font_size(11)}px; font-weight: bold; color: {p.text_strong};")
        except RuntimeError:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass

    def _load_data(self):
        if self._data is None:
            return
        self._label_display.setText(self._data.get('label', ''))
        self._nature_edit.setText(self._data.get('nature', '') or '')
        md = (self._data.get('source', '') or '').strip()
        if md:
            self._source_edit.setMarkdown(md)
        else:
            self._source_edit.clear()
        for letter, w in self._crit_widgets.items():
            val = self._data.get(f'crit_{letter}', '0')
            w['check'].setChecked(val in ('1', 1, True))

    def _load_criteria_labels(self):
        if self._termsubject_id is None:
            return
        conn = db.local_conn
        if conn is None:
            return
        try:
            row = conn.execute("""
                SELECT fk_levelsubject_id FROM larcauth_classroom_termsubject
                WHERE id = ?
            """, (str(self._termsubject_id),)).fetchone()
            if row is None:
                return
            ls_id = row[0]
            rows = conn.execute("""
                SELECT criteria_letter, criteria_label
                FROM larcauth_criteria_of_levelsubject
                WHERE fk_levelsubject_id = ?
                  AND criteria_letter IN ('A','B','C','D')
                ORDER BY criteria_letter
            """, (ls_id,)).fetchall()
            for r in rows:
                letter = r[0].lower()
                w = self._crit_widgets.get(letter)
                if w is None:
                    continue
                label_txt = (r[1] or '').replace('\n', ' ').replace('\r', '')
                w['label'].setText(label_txt)
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"Erreur chargement critères: {e}")

    def get_form_data(self) -> dict:
        crits = {letter: w['check'].isChecked() for letter, w in self._crit_widgets.items()}
        return {
            'nature': self._nature_edit.text().strip(),
            'source': self._source_edit.toMarkdown().strip(),
            'crit_a': '1' if crits['a'] else '0',
            'crit_b': '1' if crits['b'] else '0',
            'crit_c': '1' if crits['c'] else '0',
            'crit_d': '1' if crits['d'] else '0',
        }

    def set_data(self, data: dict | None):
        self._data = data
        if data is None:
            self._label_display.clear()
            self._nature_edit.clear()
            self._source_edit.clear()
            for w in self._crit_widgets.values():
                w['check'].setChecked(False)
        else:
            self._load_data()

    def set_slot_info(self, slot_index: int, eval_type: str):
        self.slot_index = slot_index
        self.eval_type = eval_type
        layout = self.layout()
        if layout and layout.count() > 0:
            item = layout.itemAt(0)
            if item and item.widget():
                item.widget().setText(f'{eval_type}{slot_index:02d}')

    def _insert_md(self, snippet: str):
        cursor = self._source_edit.textCursor()
        cursor.insertText(snippet)
        self._source_edit.setTextCursor(cursor)
        self._source_edit.setFocus()


# ---------------------------------------------------------------------------
# Dialogue modal (quick-edit depuis l'écran principal)
# ---------------------------------------------------------------------------

class EvaluationDetailDialog(ThemedDialog):
    """Fenêtre modale d'édition rapide d'un slot d'évaluation."""

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        return f"""
            QDialog {{ background: {p.background}; }}
            QPushButton#save_btn {{
                background: {p.success}; color: white; font-weight: bold;
                padding: {ds.space_xs}px {ds.table_row_min}px;
                border-radius: {ds.radius_xs}px; font-size: {theme_manager.font_size(12)}px; }}
            QPushButton#save_btn:hover {{ background: {p.success}; }}
            QPushButton#cancel_btn {{
                background: {p.outline_variant}; color: {p.text_strong};
                padding: {ds.space_xs}px {ds.table_row_min}px;
                border-radius: {ds.radius_xs}px; font-size: {theme_manager.font_size(12)}px; }}
            QPushButton#cancel_btn:hover {{ background: {p.outline_variant}; }}
        """

    def __init__(self, slot_index: int, eval_type: str, eval_data: dict | None,
                 termsubject_id: int | None = None, subject_label: str = '',
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'{eval_type}{slot_index:02d} — Détails')
        self.setMinimumWidth(ds.sidebar_width + ds.golden_width(ds.sidebar_width))  # 610px
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._form = EvaluationDetailWidget(slot_index, eval_type, eval_data,
                                             termsubject_id, subject_label, self)
        layout.addWidget(self._form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._save_btn = QPushButton("Enregistrer")
        self._save_btn.setObjectName('save_btn')
        self._cancel_btn = QPushButton("Annuler")
        self._cancel_btn.setObjectName('cancel_btn')
        self._save_btn.clicked.connect(self.accept)
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._save_btn)
        btn_layout.addWidget(self._cancel_btn)
        layout.addLayout(btn_layout)

        self.setStyleSheet(self._STYLE)
        ds.theme_changed.connect(self._restyle)

    @safe_slot("EvaluationDetailDialog._restyle")
    def _restyle(self):
        self.setStyleSheet(self._STYLE)

    def get_form_data(self) -> dict:
        return self._form.get_form_data()


# ---------------------------------------------------------------------------
# Slot cliquable
# ---------------------------------------------------------------------------

class _SlotButton(QFrame):
    """Bouton représentant un slot d'évaluation cliquable compact.

    Affiche le titre, le label, et les 4 critères sous forme compacte (☑A ☐B ☐C ☑D).
    """

    clicked = Signal(int)  # slot_index

    @property
    def _STYLE_INACTIF(self):
        p = theme_manager.palette
        return f"""
            background: {p.surface_variant}; border: 1px solid {p.outline_variant};
            border-radius: {ds.space_xxs}px; padding: {ds.space_xxs}px;
        """

    @property
    def _STYLE_ACTIF(self):
        p = theme_manager.palette
        return f"""
            background: {p.surface}; border: 1px solid {p.success};
            border-radius: {ds.space_xxs}px; padding: {ds.space_xxs}px;
        """

    def __init__(self, slot_index: int, eval_type: str, parent=None):
        super().__init__(parent)
        self.slot_index = slot_index
        self.eval_type = eval_type
        self.eval_id = None
        self._active = False
        self._data: dict | None = None

        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(self._STYLE_INACTIF)

        self._build_ui()
        ds.theme_changed.connect(self._restyle)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_xxs, ds.space_xxs, ds.space_xxs, ds.space_xxs)
        layout.setSpacing(ds.space_xxs)

        p = theme_manager.palette
        # Titre
        self._title = QLabel(f"{self.eval_type}{self.slot_index:02d}")
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setStyleSheet(f"font-weight: bold; font-size: {theme_manager.font_size(11)}px; font-family: Roboto; color: {p.text_strong}; border: none; padding: 0;")
        layout.addWidget(self._title)

        # Label (titre descriptif) — toujours visible
        self._label_info = QLabel('')
        self._label_info.setAlignment(Qt.AlignCenter)
        self._label_info.setStyleSheet(f"font-size: {theme_manager.font_size(9)}px; font-family: Roboto; color: {p.text_strong}; border: none; padding: 0;")
        self._label_info.setWordWrap(True)
        self._label_info.setMaximumHeight(ds.font_label_lg)  # 13px
        layout.addWidget(self._label_info)

        # Critères : une ligne compacte "☑A  ☐B  ☑C  ☐D"
        self._crit_label = QLabel('')
        self._crit_label.setAlignment(Qt.AlignCenter)
        self._crit_label.setStyleSheet(f"font-size: {theme_manager.font_size(12)}px; font-family: Roboto; border: none; padding: 0; letter-spacing: 3px; color: {theme_manager.palette.text_disabled};")
        layout.addWidget(self._crit_label)

    def mousePressEvent(self, event):
        self.clicked.emit(self.slot_index)

    def restyle(self):
        """Ré-applique le style actif/inactif avec la palette courante (changement de thème)."""
        p = theme_manager.palette
        if self._active and self.eval_id is not None:
            self._crit_label.setStyleSheet(f"font-size: {theme_manager.font_size(12)}px; font-family: Roboto; color: {p.success}; border: none; padding: 0; letter-spacing: 3px;")
            self._title.setStyleSheet(f"font-weight: bold; font-size: {theme_manager.font_size(11)}px; font-family: Roboto; color: {p.text_strong}; border: none; padding: 0;")
            self._label_info.setStyleSheet(f"font-size: {theme_manager.font_size(9)}px; font-family: Roboto; color: {p.text_strong}; border: none; padding: 0;")
            self.setStyleSheet(self._STYLE_ACTIF)
        else:
            self._crit_label.setStyleSheet(f"font-size: {theme_manager.font_size(12)}px; font-family: Roboto; color: {p.outline_variant}; border: none; padding: 0; letter-spacing: 3px;")
            self._title.setStyleSheet(f"font-weight: bold; font-size: {theme_manager.font_size(11)}px; font-family: Roboto; color: {p.text_disabled}; border: none; padding: 0;")
            self._label_info.setStyleSheet(f"font-size: {theme_manager.font_size(9)}px; font-family: Roboto; color: {p.text_strong}; border: none; padding: 0;")
            self.setStyleSheet(self._STYLE_INACTIF)

    @safe_slot("_SlotButton._restyle")
    def _restyle(self):
        """Hook theme_changed — même rendu que restyle()."""
        self.restyle()

    def set_data(self, eval_id: str, data: dict, subject_label: str = ''):
        self.eval_id = eval_id
        self._data = data
        self._subject_label = subject_label

        # Label — toujours affiché entre le titre et les critères
        lbl = data.get('label', '')
        if lbl:
            self._label_info.setText(lbl)
            self._label_info.show()
        else:
            self._label_info.setText('')
            self._label_info.hide()

        # Critères : construire "☑A ☐B ☑C ☐D"
        parts = []
        crits = []
        for letter in ['a', 'b', 'c', 'd']:
            val = data.get(f'crit_{letter}', '0')
            checked = val in ('1', 1, True)
            if checked:
                parts.append(f'☑{letter.upper()}')
                crits.append(letter.upper())
            else:
                parts.append(f'☐{letter.upper()}')
        self._crit_label.setText(' '.join(parts))
        self._active = len(crits) > 0

        p = theme_manager.palette
        if self._active:
            self._crit_label.setStyleSheet(f"font-size: {theme_manager.font_size(12)}px; font-family: Roboto; color: {p.success}; border: none; padding: 0; letter-spacing: 3px;")
            self._title.setStyleSheet(f"font-weight: bold; font-size: {theme_manager.font_size(11)}px; font-family: Roboto; color: {p.text_strong}; border: none; padding: 0;")
            self.setStyleSheet(self._STYLE_ACTIF)
        else:
            self._crit_label.setStyleSheet(f"font-size: {theme_manager.font_size(12)}px; font-family: Roboto; color: {p.outline_variant}; border: none; padding: 0; letter-spacing: 3px;")
            self._title.setStyleSheet(f"font-weight: bold; font-size: {theme_manager.font_size(11)}px; font-family: Roboto; color: {p.text_disabled}; border: none; padding: 0;")
            self.setStyleSheet(self._STYLE_INACTIF)

    def clear(self):
        p = theme_manager.palette
        self.eval_id = None
        self._data = None
        self._active = False
        self._label_info.hide()
        self._crit_label.setText('☐A  ☐B  ☐C  ☐D')
        self._crit_label.setStyleSheet(f"font-size: {theme_manager.font_size(12)}px; font-family: Roboto; color: {p.outline_variant}; border: none; padding: 0; letter-spacing: 3px;")
        self._title.setStyleSheet(f"font-weight: bold; font-size: {theme_manager.font_size(11)}px; font-family: Roboto; color: {p.text_disabled}; border: none; padding: 0;")
        self.setStyleSheet(self._STYLE_INACTIF)


# ---------------------------------------------------------------------------
# Panneau d'évaluations
# ---------------------------------------------------------------------------

class EvaluationPanel(QFrame):
    """Panneau d'évaluations avec grille de slots.

    Modes :
    - compact=True (défaut) : seuls les slots actifs sont visibles + bouton Gérer
    - compact=False : les 12 slots sont affichés (pour le manager)
    """

    def __init__(self, eval_type: str, title: str, compact: bool = True, parent=None):
        super().__init__(parent)
        self.eval_type = eval_type
        self.compact = compact
        self._termsubject_id = None

        p = theme_manager.palette
        d = theme_manager.design
        self.setFrameShape(QFrame.StyledPanel)
        self._panel_qss = f"""
            QFrame {{ background: {p.surface}; border: 1px solid {p.outline_variant};
                     border-radius: {d.radius}px; }}
        """
        self.setStyleSheet(self._panel_qss)

        self._build_ui(title)

        ds.theme_changed.connect(self._restyle)

    @safe_slot("EvaluationPanel._restyle")
    def _restyle(self):
        p = theme_manager.palette
        d = theme_manager.design
        self._panel_qss = f"""
            QFrame {{ background: {p.surface}; border: 1px solid {p.outline_variant};
                     border-radius: {d.radius}px; }}
        """
        try:
            self.setStyleSheet(self._panel_qss)
        except RuntimeError:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            pass

        # Restyler les slots existants (pas de recréation — perte de données)
        for slot in getattr(self, '_slots', []):
            slot.restyle()
        self._update_indicators()

        # Bouton Gérer (mode compact)
        if getattr(self, '_manage_btn', None) is not None:
            self._manage_btn.setStyleSheet(f"""
                QPushButton {{ background: {p.primary}; color: {p.on_primary}; font-weight: bold;
                              font-size: {theme_manager.font_size(9)}px;
                              padding: {ds.space_xxs // 2}px {ds.font_label_lg}px;
                              border-radius: {ds.radius_xs}px; }}
                QPushButton:hover {{ background: {p.primary}; }}
            """)
        # Légende
        if getattr(self, '_legend', None) is not None:
            self._legend.setStyleSheet(
                f"font-size: {theme_manager.font_size(7)}px; font-family: Roboto; color: {p.text_strong}; "
                f"border: none; padding: 0;"
            )
        # Placeholder vide
        if getattr(self, '_empty_placeholder', None) is not None:
            self._empty_placeholder.setStyleSheet(
                f"color: {p.text_disabled}; font-size: {theme_manager.font_size(10)}px; font-family: Roboto; "
                f"border: none; padding: 0;"
            )

    def _build_ui(self, title: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_xs, ds.space_xxs, ds.space_xs, ds.space_xxs)
        layout.setSpacing(ds.space_xxs)

        # Header row: title + indicators + Gérer button
        header_row = QHBoxLayout()
        header_row.setSpacing(ds.space_xxs)

        hdr = QLabel(title)
        hdr.setStyleSheet(
            f"font-weight: bold; font-size: {theme_manager.font_size(10)}px; font-family: Roboto; "
            f"color: {theme_manager.palette.text_strong}; border: none; padding: 0;"
        )
        header_row.addWidget(hdr)
        header_row.addStretch()

        self._indicators: list[QLabel] = []
        for i in range(12):
            p = theme_manager.palette
            lbl = QLabel(f'{self.eval_type}{i+1:02d}')
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedSize(ds.table_row_min, ds.space_sm)  # 21×12
            lbl.setStyleSheet(
                f"background: {p.outline_variant}; color: {p.text_disabled}; font-size: {theme_manager.font_size(8)}px; "
                f"font-family: Roboto; font-weight: bold; border-radius: {ds.radius_xs // 2}px;"
            )
            self._indicators.append(lbl)
            header_row.addWidget(lbl)
        header_row.addStretch()

        if self.compact:
            p = theme_manager.palette
            self._manage_btn = QPushButton("Gérer")
            self._manage_btn.setFixedHeight(ds.field_height)   # Fibonacci LG = 32
            self._manage_btn.setStyleSheet(f"""
                QPushButton {{ background: {p.primary}; color: {p.on_primary}; font-weight: bold;
                              font-size: {theme_manager.font_size(9)}px;
                              padding: {ds.space_xxs // 2}px {ds.font_label_lg}px;
                              border-radius: {ds.radius_xs}px; }}
                QPushButton:hover {{ background: {p.primary}; }}
            """)
            self._manage_btn.clicked.connect(self.manage_requested.emit)
            header_row.addWidget(self._manage_btn)

        layout.addLayout(header_row)

        # Légende des critères
        self._legend = QLabel('')
        self._legend.setStyleSheet(
            f"font-size: {theme_manager.font_size(7)}px; font-family: Roboto; color: {theme_manager.palette.text_strong}; "
            f"border: none; padding: 0;"
        )
        self._legend.hide()
        layout.addWidget(self._legend)

        # Zone des slots
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setStyleSheet("QScrollArea { border: none; }")

        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(ds.space_xxs)

        # Placeholder visible uniquement quand aucun slot actif en mode compact
        self._empty_placeholder = QLabel("Aucune évaluation active — cliquer sur Gérer")
        self._empty_placeholder.setAlignment(Qt.AlignCenter)
        self._empty_placeholder.setStyleSheet(
            f"color: {theme_manager.palette.text_disabled}; font-size: {theme_manager.font_size(10)}px; font-family: Roboto; "
            f"border: none; padding: 0;"
        )
        self._empty_placeholder.hide()
        self._grid.addWidget(self._empty_placeholder, 0, 0)

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)

        # Création des slots (une seule fois — restylés par _restyle au changement de thème)
        self._slots: list[_SlotButton] = []
        for i in range(12):
            slot = _SlotButton(i + 1, self.eval_type)
            slot.clicked.connect(self._on_slot_clicked)
            self._slots.append(slot)
        self._connect_manager_mode()
        self._cols = 3
        self._update_layout()

    def _connect_manager_mode(self):
        """En mode non-compact, connexion au clic pour le manager."""
        if not self.compact:
            for slot in self._slots:
                slot.clicked.disconnect()
                slot.clicked.connect(self._on_slot_clicked_manager)

    @safe_slot("EvaluationPanel._on_slot_clicked")
    def _on_slot_clicked(self, slot_index: int):
        """Ouvre la boîte de dialogue modale pour ce slot (mode compact)."""
        if self._termsubject_id is None:
            return
        slot = self._slots[slot_index - 1]
        dlg = EvaluationDetailDialog(slot_index, self.eval_type, slot._data,
                                     self._termsubject_id, slot._subject_label,
                                     self)
        if dlg.exec() == QDialog.Accepted:
            form_data = dlg.get_form_data()
            self._save_criteria(slot, form_data)

    @safe_slot("EvaluationPanel._on_slot_clicked_manager")
    def _on_slot_clicked_manager(self, slot_index: int):
        """Signal émis quand le manager veut afficher ce slot dans le détail."""
        self.slot_selected.emit(slot_index)

    def _calc_cols(self) -> int:
        w = self.width() - 16  # margins 8+8
        if w <= 0:
            w = 400
        return max(1, w // 100)

    def showEvent(self, event):
        super().showEvent(event)
        self._cols = self._calc_cols()
        self._update_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_cols = self._calc_cols()
        if new_cols != self._cols:
            self._cols = new_cols
            self._update_layout()

    def _update_layout(self):
        """Reconstruit la grille avec un nombre de colonnes adaptatif."""
        cols = self._cols
        # Vider la grille
        for i in reversed(range(self._grid.count())):
            item = self._grid.itemAt(i)
            if item and item.widget():
                w = item.widget()
                self._grid.removeWidget(w)
                w.setParent(None)

        if self.compact:
            active_slots = [s for s in self._slots if s._active and s.eval_id is not None]
            n = len(active_slots)
            if n > 0:
                for idx, slot in enumerate(active_slots):
                    row, col = divmod(idx, cols)
                    self._grid.addWidget(slot, row, col)
                rows_used = (n + cols - 1) // cols
                self._empty_placeholder.hide()
            else:
                self._grid.addWidget(self._empty_placeholder, 0, 0)
                self._empty_placeholder.show()
                rows_used = 1
        else:
            n = 12
            for i, slot in enumerate(self._slots):
                row, col = divmod(i, cols)
                self._grid.addWidget(slot, row, col)
            rows_used = (n + cols - 1) // cols

        slot_h = 50
        if self._slots and self._slots[0].minimumSizeHint().height() > 0:
            slot_h = self._slots[0].minimumSizeHint().height()
        scroll_h = slot_h * rows_used + self._grid.spacing() * (rows_used - 1) + 4
        self._scroll.setMinimumHeight(scroll_h)
        self._scroll.setMaximumHeight(scroll_h)

    # -- Signaux --
    slot_selected = Signal(int)  # émis en mode !compact (pour le manager)
    manage_requested = Signal()  # émis en mode compact (clic Gérer)

    def _load_criteria_legend(self, termsubject_id: int):
        """Charge les labels des critères et remplit la légende."""
        conn = db.local_conn
        if conn is None:
            return
        try:
            row = conn.execute("""
                SELECT fk_levelsubject_id FROM larcauth_classroom_termsubject
                WHERE id = ?
            """, (str(termsubject_id),)).fetchone()
            if row is None:
                return
            ls_id = row[0]
            rows = conn.execute("""
                SELECT criteria_letter, criteria_label
                FROM larcauth_criteria_of_levelsubject
                WHERE fk_levelsubject_id = ?
                  AND criteria_letter IN ('A','B','C','D')
                ORDER BY criteria_letter
            """, (ls_id,)).fetchall()
            if not rows:
                return
            parts = []
            for r in rows:
                label = (r[1] or '').replace('\n', ' ')
                parts.append(f'{r[0]}: {label}')
            self._legend.setText(' | '.join(parts))
            self._legend.show()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"Erreur légende évaluations : {e}")

    def _update_indicators(self):
        """Met à jour la barre d'indicateurs selon l'état actif de chaque slot."""
        p = theme_manager.palette
        for i, slot in enumerate(self._slots):
            active = slot._active and slot.eval_id is not None
            if active:
                self._indicators[i].setStyleSheet(
                    f"background: {p.success}; color: white; font-size: {theme_manager.font_size(8)}px; "
                    f"font-family: Roboto; font-weight: bold; border-radius: {ds.radius_xs // 2}px;"
                )
            else:
                self._indicators[i].setStyleSheet(
                    f"background: {p.outline_variant}; color: {p.text_disabled}; font-size: {theme_manager.font_size(8)}px; "
                    f"font-family: Roboto; font-weight: bold; border-radius: {ds.radius_xs // 2}px;"
                )

    def _save_criteria(self, slot: _SlotButton, data: dict):
        """Sauvegarde nature, source et critères dans la base."""
        if slot.eval_id is None:
            return
        try:
            from common.eval_helpers import save_evaluation_criteria
            label_val = (slot._data or {}).get('label', '')
            if not save_evaluation_criteria(slot.eval_id, label_val,
                    data.get('nature', ''), data.get('source', ''),
                    {k: data.get(k, '0') for k in ('crit_a', 'crit_b', 'crit_c', 'crit_d')}):
                return
            if slot._data:
                slot._data['nature'] = data.get('nature', '')
                slot._data['source'] = data.get('source', '')
                for k in ('crit_a', 'crit_b', 'crit_c', 'crit_d'):
                    slot._data[k] = data.get(k, '0')
            slot.set_data(slot.eval_id, slot._data or {})
            self._update_indicators()
            self._update_layout()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"Erreur sauvegarde evaluation {slot.eval_id}: {e}")

    def load_evaluations(self, termsubject_id: int):
        """Charge les évaluations depuis SQLite pour ce termsubject_id."""
        self._termsubject_id = termsubject_id
        conn = db.local_conn
        if conn is None:
            self.clear_panel()
            return
        try:
            row = conn.execute("""
                SELECT label FROM larcauth_classroom_termsubject WHERE id = ?
            """, (str(termsubject_id),)).fetchone()
            subject_label = row[0] if row else ''

            self._load_criteria_legend(termsubject_id)

            rows = conn.execute("""
                SELECT id, index_eval,
                       crit_a, crit_b, crit_c, crit_d,
                       label, nature, source
                FROM larcauth_evaluation
                WHERE fk_classroom_termsubject_id = ?
                  AND type_evaluation = ?
                  AND CAST(index_eval AS INTEGER) BETWEEN 1 AND 12
                ORDER BY CAST(index_eval AS INTEGER)
            """, (str(termsubject_id), self.eval_type)).fetchall()

            loaded = {int(r[1]): r for r in rows}
            for slot in self._slots:
                r = loaded.get(slot.slot_index)
                if r:
                    data = {
                        'crit_a': r[2], 'crit_b': r[3], 'crit_c': r[4], 'crit_d': r[5],
                        'label': r[6] or '', 'nature': r[7] or '', 'source': r[8] or '',
                    }
                    slot.set_data(r[0], data, subject_label)
                else:
                    slot.clear()
            self._update_indicators()
            self._update_layout()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"Erreur chargement évaluations : {e}")
            self.clear_panel()

    def clear_panel(self):
        """Vide tous les slots et réinitialise le panneau."""
        self._termsubject_id = None
        self._legend.hide()
        for slot in self._slots:
            slot.clear()
        self._update_indicators()
        self._update_layout()



