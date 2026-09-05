"""Dialogue Mode de calcul — Configuration du calcul des notes.

Deux aspects seulement :
1. Ponderation de la matiere entiere : coefficient multiplicateur 1/2/3.
2. Comment calculer la moyenne avec les criteres : poids F/S + conversion
   (bandes IB, declinees par nombre de criteres). Les criteres ne se
   configurent plus ici — la formule conserve les siens tels quels.
L'utilisateur ne voit JAMAIS le JSON. Tout est visuel.
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from common.calc_engine import CalcEngine, _recalc_boundaries
from common.database import db
from common.session import session
from common.theme import ZONE_F_COLOR, ZONE_S_COLOR
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.safe_slot import safe_slot
from larccommon.widgets.themed_widget import ThemedDialog


class WeightDialog(ThemedDialog):
    """Dialogue de configuration du calcul des notes."""

    _BOUNDARY_LABELS = {1: "1 (tres faible)", 2: "2 (faible)", 3: "3 (satisfaisant)",
                        4: "4 (bon)", 5: "5 (tres bon)", 6: "6 (excellent)", 7: "7 (exceptionnel)"}

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        return f"QDialog {{ background: {p.background}; }}"

    def _gb_qss(self) -> str:
        """Style commun des cadres de section : bordure toujours visible, titre sur le bord."""
        p = theme_manager.palette
        s = theme_manager.font_size
        return (
            f"QGroupBox {{ border: 1px solid {p.outline_variant}; "
            f"border-radius: {ds.radius_sm}px; "
            f"margin-top: {ds.space_md}px; padding-top: {ds.space_sm}px; "
            f"font-weight: bold; color: {p.text_strong}; font-size: {s(13)}px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; "
            f"left: {ds.space_md}px; padding: 0 {ds.space_xs}px; }}"
        )

    def __init__(self, termsubject_id: int, subject_label: str = '', parent=None):
        super().__init__(parent)
        self._termsubject_id = termsubject_id
        self._subject_label = subject_label or f"Matiere #{termsubject_id}"

        self.setWindowTitle(f"Mode de calcul — {self._subject_label}")
        # Fenetre elargie (4 colonnes de sidebar + un espace fibonacci) :
        # tout est visible en meme temps, pas de scroll.
        self.setMinimumWidth(ds.sidebar_width * 4 + ds.space_lg)
        self.setModal(True)

        self._formula = CalcEngine.get_formula(termsubject_id)
        self._is_pei = self._formula.get("type") == "PEI"
        self._built = False
        self._current_criteria = 4  # déclinaison de bandes affichée par défaut

        # Droits : seul directeur / coordonnateur peut modifier cette fenêtre.
        flags = getattr(session, 'role_flags', None)
        if not flags:
            session.load_role_flags()
            flags = getattr(session, 'role_flags', {})
        self._is_editor = bool(flags.get('Directeur')) or bool(flags.get('Coordinateur'))

        # Charger le poids et les infos depuis la DB locale
        self._subject_weight = 1.0
        self._term_label = ''
        conn = db.local_conn
        if conn is not None:
            row = conn.execute(
                "SELECT cts.subject_weight, t.label FROM larcauth_classroom_termsubject cts "
                "JOIN larcauth_term t ON t.id = cts.fk_term_id WHERE cts.id = ?",
                (str(termsubject_id),)
            ).fetchone()
            if row:
                self._subject_weight = float(row[0]) if row[0] is not None else 1.0
                self._term_label = str(row[1]) if row[1] else ''

        self._setup_ui()
        self.setStyleSheet(self._STYLE)
        ds.theme_changed.connect(self._restyle)
        self._load_current()
        if not self._is_editor:
            self._apply_read_only()
        self._built = True

    # ── UI ─────────────────────────────────────────────────────

    @safe_slot("WeightDialog._restyle")
    def _restyle(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        self.setStyleSheet(self._STYLE)
        self._weight_combo.setStyleSheet(
            f"QComboBox {{ font-size: {s(14)}px; color: {p.text_strong}; font-weight: bold; "
            f"border: 1px solid {p.primary}; border-radius: {ds.radius_xs}px; "
            f"padding: {ds.space_xxs}px; }}")
        slider_qss = (
            f"QSlider::groove:horizontal {{ height: 6px; background: {p.outline_variant}; "
            f"border-radius: {ds.radius_xs}px; }} "
            f"QSlider::handle:horizontal {{ background: {p.primary}; width: 14px; height: 14px; "
            f"margin: -{ds.space_xxs}px 0; border-radius: {ds.radius_sm}px; }}")
        if hasattr(self, '_f_slider'):
            self._f_slider.setStyleSheet(slider_qss)
            f_pct_qss = f"color: {ZONE_F_COLOR}; font-weight: bold; font-size: {s(13)}px;"
            s_pct_qss = f"color: {ZONE_S_COLOR}; font-weight: bold; font-size: {s(13)}px;"
            self._f_pct.setStyleSheet(f_pct_qss)
            self._s_pct.setStyleSheet(s_pct_qss)
            self._formula_label.setStyleSheet(
                f"color: {p.text_strong}; font-size: {s(13)}px; "
                f"background: {p.surface}; border: 1px solid {p.outline_variant}; "
                f"border-radius: {ds.radius_sm}px; padding: {ds.space_sm}px;")
            self._rule_label.setStyleSheet(
                f"color: {p.text_strong}; font-size: {s(12)}px; font-style: italic;")
        self._boundaries_table.setStyleSheet(
            f"QTableWidget {{ gridline-color: {p.outline_variant}; font-size: {s(12)}px; }}"
            f"QTableWidget::item {{ color: {p.text_strong}; padding: {ds.space_xxs}px; }}")
        gb_qss = self._gb_qss()
        for gb in self.findChildren(QGroupBox):
            gb.setStyleSheet(gb_qss)
        for rb in getattr(self, '_crit_radios', {}).values():
            rb.setStyleSheet(f"color: {p.text_strong}; font-size: {s(12)}px;")

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        root = QVBoxLayout(self)
        root.setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
        root.setSpacing(ds.space_md)

        # ── Header: Matiere, Trimestre, Coefficient ──
        # Aucun cadre : le header reste propre (fond + bordure supprimes)
        info_panel = QFrame()
        info_layout = QHBoxLayout(info_panel)
        info_layout.setContentsMargins(ds.space_m3, ds.space_sm, ds.space_m3, ds.space_sm)
        info_layout.setSpacing(ds.space_md)

        # Nom matiere
        mat_col = QVBoxLayout()
        mat_col.setSpacing(ds.space_xxs)
        mat_lbl = QLabel('Matiere')
        mat_lbl.setStyleSheet(f"font-size: {s(11)}px; color: {p.text_strong}; font-weight: bold;")
        mat_col.addWidget(mat_lbl)
        mat_val = QLabel(self._subject_label)
        mat_val.setStyleSheet(f"font-size: {s(14)}px; color: {p.text_strong}; font-weight: bold;")
        mat_col.addWidget(mat_val)
        info_layout.addLayout(mat_col)

        # Trimestre
        term_col = QVBoxLayout()
        term_col.setSpacing(ds.space_xxs)
        term_lbl = QLabel('Trimestre')
        term_lbl.setStyleSheet(f"font-size: {s(11)}px; color: {p.text_strong}; font-weight: bold;")
        term_col.addWidget(term_lbl)
        term_val = QLabel(self._term_label or '—')
        term_val.setStyleSheet(f"font-size: {s(14)}px; color: {p.text_strong};")
        term_col.addWidget(term_val)
        info_layout.addLayout(term_col)

        info_layout.addStretch()

        # Ponderation de la matiere entiere : coefficient multiplicateur 1/2/3
        coef_col = QVBoxLayout()
        coef_col.setSpacing(ds.space_xxs)
        coef_lbl = QLabel('Ponderation de la matiere')
        coef_lbl.setStyleSheet(f"font-size: {s(11)}px; color: {p.text_strong}; font-weight: bold;")
        coef_col.addWidget(coef_lbl)
        coef_row = QHBoxLayout()
        coef_row.setSpacing(ds.space_xxs)
        self._weight_combo = QComboBox()
        self._weight_combo.addItem("1", 1)
        self._weight_combo.addItem("2", 2)
        self._weight_combo.addItem("3", 3)
        # Valeur actuelle arrondie dans {1, 2, 3} (les anciennes valeurs
        # type 0.5 ou 4.0 retombent sur l'entier le plus proche).
        cur = max(1, min(3, int(round(self._subject_weight))))
        self._weight_combo.setCurrentIndex(cur - 1)
        self._weight_combo.setFixedWidth(ds.sidebar_width // 3)
        self._weight_combo.setStyleSheet(
            f"QComboBox {{ font-size: {s(14)}px; color: {p.text_strong}; font-weight: bold; "
            f"border: 1px solid {p.primary}; border-radius: {ds.radius_xs}px; "
            f"padding: {ds.space_xxs}px; }}")
        coef_row.addWidget(self._weight_combo)
        coef_hint = QLabel('(coefficient multiplicateur)')
        coef_hint.setStyleSheet(f"font-size: {s(11)}px; color: {p.text_strong};")
        coef_row.addWidget(coef_hint)
        coef_col.addLayout(coef_row)
        info_layout.addLayout(coef_col)

        root.addWidget(info_panel)

        # Template selector — PEI : aucun (les criteres ne se configurent
        # plus ici, seuls le coefficient et le calcul de la moyenne comptent).
        # DP : choix de la methode (standard / moyenne simple).
        if not self._is_pei:
            tmpl_row = QHBoxLayout()
            tmpl_lbl = QLabel("Template :")
            tmpl_lbl.setStyleSheet(f"font-weight: bold; color: {p.text_strong}; font-size: {s(13)}px;")
            tmpl_row.addWidget(tmpl_lbl)

            self._template_combo = QComboBox()
            self._template_combo.currentIndexChanged.connect(self._on_template_changed)
            self._template_combo.addItem("DP Standard IB", "standard")
            self._template_combo.addItem("DP Moyenne simple", "simple")
            self._template_combo.addItem("Personnalise", "custom")
            tmpl_row.addWidget(self._template_combo, 1)
            root.addLayout(tmpl_row)

        # ── Deux colonnes cote a cote : tout visible, pas de scroll ──
        if self._is_pei:
            cols = QHBoxLayout()
            cols.setSpacing(ds.space_xl)
            # Colonne gauche : calcul de la moyenne avec les criteres
            # (barre unique F/S + formule)
            left = QVBoxLayout()
            left.setSpacing(ds.space_md)
            left.addWidget(self._build_weights_section())
            # Colonne droite : conversion somme → note/7 (bandes IB)
            right = QVBoxLayout()
            right.setSpacing(ds.space_md)
            right.addWidget(self._build_conversion_section())
            right.addStretch(1)
            cols.addLayout(left, 1)
            cols.addLayout(right, 1)
            root.addLayout(cols, 1)
        else:
            root.addWidget(self._build_dp_section())

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._apply_all_btn = QPushButton("Appliquer par defaut a toutes")
        self._apply_all_btn.setStyleSheet(
            f"QPushButton {{ color: {p.primary}; font-size: {theme_manager.font_size(12)}px; "
            f"border: 1px solid {p.outline_variant}; border-radius: {ds.radius_lg}px; "
            f"padding: {ds.space_xs}px {ds.space_m3}px; }}")
        self._apply_all_btn.clicked.connect(self._on_apply_all)
        btn_row.addWidget(self._apply_all_btn)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self._on_save)
        box.rejected.connect(self.reject)
        btn_row.addWidget(box)
        root.addLayout(btn_row)

    # ── PEI: Poids F/S — comment calculer la moyenne avec les critères ──

    def _build_weights_section(self) -> QGroupBox:
        p = theme_manager.palette
        gb = QGroupBox("Calcul de la moyenne avec les criteres")
        gb.setStyleSheet(self._gb_qss())

        layout = QVBoxLayout(gb)
        layout.setSpacing(ds.space_sm)

        # Noms des zones (couleurs cohérentes avec les entêtes de la grille)
        names_row = QHBoxLayout()
        f_lbl = QLabel("Formatives")
        f_lbl.setStyleSheet(f"color: {ZONE_F_COLOR}; font-weight: bold; "
                            f"font-size: {theme_manager.font_size(13)}px;")
        names_row.addWidget(f_lbl)
        names_row.addStretch(1)
        s_lbl = QLabel("Sommatives")
        s_lbl.setStyleSheet(f"color: {ZONE_S_COLOR}; font-weight: bold; "
                            f"font-size: {theme_manager.font_size(13)}px;")
        names_row.addWidget(s_lbl)
        layout.addLayout(names_row)

        # Une seule barre : F% = x, S% = 100 - x (la somme vaut toujours 100 %)
        self._f_slider = QSlider(Qt.Horizontal)
        self._f_slider.setRange(0, 100)
        self._f_slider.setValue(40)
        self._f_slider.setStyleSheet(
            f"QSlider::groove:horizontal {{ height: 6px; background: {p.outline_variant}; "
            f"border-radius: {ds.radius_xs}px; }} "
            f"QSlider::handle:horizontal {{ background: {p.primary}; width: 14px; height: 14px; "
            f"margin: -{ds.space_xxs}px 0; border-radius: {ds.radius_sm}px; }}")
        self._f_slider.valueChanged.connect(self._on_weight_changed)
        layout.addWidget(self._f_slider)

        # Pourcentages aux deux extremites : on voit la complementarite
        pct_row = QHBoxLayout()
        self._f_pct = QLabel("40%")
        self._f_pct.setStyleSheet(f"color: {ZONE_F_COLOR}; font-weight: bold; "
                                  f"font-size: {theme_manager.font_size(13)}px;")
        pct_row.addWidget(self._f_pct)
        pct_row.addStretch(1)
        self._s_pct = QLabel("60%")
        self._s_pct.setStyleSheet(f"color: {ZONE_S_COLOR}; font-weight: bold; "
                                  f"font-size: {theme_manager.font_size(13)}px;")
        pct_row.addWidget(self._s_pct)
        layout.addLayout(pct_row)

        # Formule de calcul des jugements, generee en direct par la barre
        self._formula_label = QLabel('')
        self._formula_label.setWordWrap(True)
        self._formula_label.setTextFormat(Qt.RichText)
        self._formula_label.setStyleSheet(
            f"color: {p.text_strong}; font-size: {theme_manager.font_size(13)}px; "
            f"background: {p.surface}; border: 1px solid {p.outline_variant}; "
            f"border-radius: {ds.radius_sm}px; padding: {ds.space_sm}px;")
        layout.addWidget(self._formula_label)

        # Regles par defaut (solo) : si un seul type a des notes, il compte seul
        self._rule_label = QLabel(
            "Regle par defaut (stockee dans calc_formula.solo_rule) :\n"
            "- aucune formative  -> 100 % sommatives\n"
            "- aucune sommative  -> 100 % formatives")
        self._rule_label.setStyleSheet(
            f"color: {p.text_strong}; font-size: {theme_manager.font_size(12)}px; "
            f"font-style: italic;")
        layout.addWidget(self._rule_label)

        return gb

    # ── PEI: Conversion ────────────────────────────────────────

    def _build_conversion_section(self) -> QGroupBox:
        p = theme_manager.palette
        gb = QGroupBox("Conversion somme → Note/7")
        gb.setStyleSheet(self._gb_qss())

        layout = QVBoxLayout(gb)
        layout.setSpacing(ds.space_xs)

        # Déclinaison : nombre de critères présents (radio au-dessus du tableau)
        radio_row = QHBoxLayout()
        radio_row.setSpacing(ds.space_md)
        self._crit_group = QButtonGroup(self)
        self._crit_radios: dict[int, QRadioButton] = {}
        for n in (4, 3, 2, 1):
            rb = QRadioButton(f"{n} critere{'s' if n > 1 else ''} present{'s' if n > 1 else ''}")
            rb.setStyleSheet(f"color: {p.text_strong}; font-size: {theme_manager.font_size(12)}px;")
            self._crit_group.addButton(rb, n)
            self._crit_radios[n] = rb
            radio_row.addWidget(rb)
        radio_row.addStretch(1)
        self._crit_radios[4].setChecked(True)
        layout.addLayout(radio_row)

        # Tableau des bandes : lignes de 32px (ds.space_xl) — grand et lisible, sans scroll
        self._boundaries_table = QTableWidget(7, 2)
        self._boundaries_table.setHorizontalHeaderLabels(["Note", "Seuil min → max"])
        self._boundaries_table.horizontalHeader().setStretchLastSection(True)
        self._boundaries_table.verticalHeader().setVisible(False)
        self._boundaries_table.verticalHeader().setDefaultSectionSize(ds.space_xl)
        self._boundaries_table.setColumnWidth(0, ds.sidebar_width // 3)
        self._boundaries_table.setFixedHeight(ds.space_xl * 8 + ds.space_md)
        self._boundaries_table.setStyleSheet(
            f"QTableWidget {{ gridline-color: {p.outline_variant}; font-size: {theme_manager.font_size(12)}px; }}"
            f"QTableWidget::item {{ color: {p.text_strong}; padding: {ds.space_xxs}px; }}")
        layout.addWidget(self._boundaries_table)

        self._crit_group.idClicked.connect(self._on_criteria_count_changed)

        return gb

    # ── DP Section ─────────────────────────────────────────────

    def _build_dp_section(self) -> QGroupBox:
        p = theme_manager.palette
        gb = QGroupBox("Coefficients de calcul")
        gb.setStyleSheet(self._gb_qss())

        form = QFormLayout(gb)
        form.setSpacing(ds.space_sm)

        info = QLabel("Moy = EI x coeff + moy(F/20) x coeff + moy(S/20) x coeff")
        info.setStyleSheet(f"color: {p.text_strong}; font-size: {theme_manager.font_size(11)}px; font-style: italic;")
        form.addRow(info)

        self._dp_ei = QDoubleSpinBox()
        self._dp_ei.setRange(-5.0, 5.0)
        self._dp_ei.setDecimals(3)
        self._dp_ei.setSingleStep(0.1)
        self._dp_ei.setStyleSheet(ds.flat_input_qss())
        form.addRow("Coefficient Evaluation Interne :", self._dp_ei)

        self._dp_f = QDoubleSpinBox()
        self._dp_f.setRange(-5.0, 5.0)
        self._dp_f.setDecimals(3)
        self._dp_f.setSingleStep(0.1)
        self._dp_f.setStyleSheet(ds.flat_input_qss())
        form.addRow("Coefficient Formatives :", self._dp_f)

        self._dp_s = QDoubleSpinBox()
        self._dp_s.setRange(-5.0, 5.0)
        self._dp_s.setDecimals(3)
        self._dp_s.setSingleStep(0.1)
        self._dp_s.setStyleSheet(ds.flat_input_qss())
        form.addRow("Coefficient Sommatives :", self._dp_s)

        return gb

    # ── Load / Save ────────────────────────────────────────────

    def _load_current(self):
        if self._is_pei:
            self._load_pei()
        else:
            self._load_dp()
        self._update_preview()

    def _load_pei(self):
        # Une seule barre : x% formatives, (100 - x)% sommatives
        x = self._f_weight_pct()
        self._f_slider.blockSignals(True)
        self._f_slider.setValue(x)
        self._f_slider.blockSignals(False)
        self._f_pct.setText(f"{x}%")
        self._s_pct.setText(f"{100 - x}%")
        self._update_formula_label()

        # Conversion : toujours en bandes IB, déclinée par nombre de critères.
        self._formula.setdefault("conversion", {})["method"] = "boundaries"
        self._show_boundaries(4)

    def _f_weight_pct(self) -> int:
        """% formatives depuis la formule, normalise pour que F + S = 100."""
        wf = self._formula.get("formative_weight", 0.4)
        ws = self._formula.get("summative_weight", 0.6)
        total = wf + ws
        if total <= 0:
            return 40
        return round(wf * 100 / total)

    def _update_formula_label(self) -> None:
        """Affiche la formule de calcul des jugements, generee par la barre."""
        x = self._f_slider.value()
        self._formula_label.setText(
            f'<b style="color:{theme_manager.palette.text_strong};">Jugement</b> = '
            f'<span style="color:{ZONE_F_COLOR}; font-weight:bold;">'
            f'moy(Formatives) &times; {x}%</span> + '
            f'<span style="color:{ZONE_S_COLOR}; font-weight:bold;">'
            f'moy(Sommatives) &times; {100 - x}%</span><br>'
            f'resultat <b>arrondi a l&#39;entier</b> — le jugement n&#39;a jamais de virgule.'
        )

    def _load_dp(self):
        conv = self._formula.get("conversion", {})
        method = conv.get("method", "simple_avg")
        if method == "simple_avg":
            self._template_combo.setCurrentIndex(1)  # simple
        else:
            self._template_combo.setCurrentIndex(0)  # standard

    def _fill_boundaries(self, boundaries: list[dict]):
        self._boundaries_table.setRowCount(len(boundaries) if boundaries else 7)
        for i in range(7):
            if i < len(boundaries):
                b = boundaries[i]
                self._boundaries_table.setItem(i, 0, QTableWidgetItem(str(b["note"])))
                self._boundaries_table.setItem(i, 1, QTableWidgetItem(f"{b['min']} → {b['max']}"))
            else:
                self._boundaries_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
                self._boundaries_table.setItem(i, 1, QTableWidgetItem("0 → 0"))

    # ── Handlers ───────────────────────────────────────────────

    @safe_slot("WeightDialog._on_template_changed")
    def _on_template_changed(self, idx: int):
        """DP uniquement — le PEI n'a plus de templates (criteres figes)."""
        if not self._built or idx < 0:
            return
        key = self._template_combo.currentData()
        if key == "custom":
            return

        templates = CalcEngine.get_templates_dp()
        tmpl = templates.get(key)
        if tmpl:
            self._formula = tmpl
            self._formula["type"] = "DP"

        conv = self._formula.get("conversion", {})
        method = conv.get("method", "simple_avg")
        if method != "simple_avg":
            self._dp_ei.setValue(conv.get("ei_coefficient", 0.125))
            self._dp_f.setValue(conv.get("formative_coefficient", 1.125))
            self._dp_s.setValue(conv.get("summative_coefficient", 0.75))

    @safe_slot("WeightDialog._on_weight_changed")
    def _on_weight_changed(self, _value: int = 0):
        if not self._built:
            return
        x = self._f_slider.value()
        self._f_pct.setText(f"{x}%")
        self._s_pct.setText(f"{100 - x}%")
        self._formula["formative_weight"] = x / 100
        self._formula["summative_weight"] = (100 - x) / 100
        self._update_formula_label()

    @safe_slot("WeightDialog._on_criteria_count_changed")
    def _on_criteria_count_changed(self, n: int):
        """Changement de déclinaison (4/3/2/1 critères) : on bascule le tableau."""
        if not self._built:
            return
        # Commit des éventuelles modifications du tableau « 4 critères »
        if self._current_criteria == 4 and self._is_editor:
            self._read_boundaries_from_table()
        self._current_criteria = n
        self._show_boundaries(n)

    def _show_boundaries(self, n: int):
        """Affiche les bandes de la déclinaison demandée.

        « 4 critères » : bandes enregistrées (modifiables par directeur/coordo).
        « 3/2/1 critères » : recalculées automatiquement (lecture seule),
        cohérentes avec le moteur de calcul.
        """
        if n == 4:
            boundaries = self._formula.get("conversion", {}).get("boundaries", [])
            if not boundaries:
                boundaries = _recalc_boundaries(4)  # fallback (ancienne formule « linéaire »)
            self._fill_boundaries(boundaries)
            editable = self._is_editor
        else:
            self._fill_boundaries(_recalc_boundaries(n))
            editable = False
        self._boundaries_table.setEditTriggers(
            QAbstractItemView.AllEditTriggers if editable else QAbstractItemView.NoEditTriggers)

    def _read_boundaries_from_table(self):
        """Relit le tableau et enregistre les bandes dans la formule (déclinaison 4)."""
        boundaries = []
        for i in range(self._boundaries_table.rowCount()):
            note_item = self._boundaries_table.item(i, 0)
            range_item = self._boundaries_table.item(i, 1)
            if note_item and range_item:
                parts = range_item.text().replace(" ", "").split("→")
                if len(parts) == 2:
                    try:
                        boundaries.append({
                            "min": int(parts[0]), "max": int(parts[1]),
                            "note": int(note_item.text()),
                        })
                    except ValueError:
                        pass
        if boundaries:
            self._formula.setdefault("conversion", {})["boundaries"] = boundaries

    def _apply_read_only(self):
        """Professeur : lecture seule (indicatif). Seul directeur/coordonnateur modifie."""
        self._weight_combo.setEnabled(False)
        if hasattr(self, '_f_slider'):
            self._f_slider.setEnabled(False)
        if hasattr(self, '_template_combo'):
            self._template_combo.setEnabled(False)
        for attr in ('_dp_ei', '_dp_f', '_dp_s'):
            if hasattr(self, attr):
                getattr(self, attr).setEnabled(False)
        if hasattr(self, '_boundaries_table'):
            self._boundaries_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._apply_all_btn.setEnabled(False)

    @safe_slot("Unknown._on_save")
    def _on_save(self):
        # Professeur : lecture seule, on ferme sans rien enregistrer.
        if not self._is_editor:
            self.accept()
            return
        # Lire les donnees du formulaire
        if self._is_pei:
            # Criteres de la formule conserves tels quels : ils ne se
            # configurent plus dans ce dialogue (seuls le coefficient et
            # le calcul de la moyenne comptent).
            x = self._f_slider.value()
            self._formula["formative_weight"] = x / 100
            self._formula["summative_weight"] = (100 - x) / 100
            # Regle explicite pour tout logiciel tiers : si un seul type
            # a des notes, il compte seul (100 %).
            self._formula["solo_rule"] = "if_only_one_type"
            # Enregistrer les bandes « 4 critères » (les autres sont recalculées)
            conv = self._formula.setdefault("conversion", {})
            conv["method"] = "boundaries"
            if self._current_criteria == 4:
                self._read_boundaries_from_table()
        else:
            conv = self._formula.setdefault("conversion", {})
            method = self._template_combo.currentData()
            if method == "simple":
                self._formula["conversion"] = {"method": "simple_avg"}
            else:
                conv["method"] = "formula"
                conv["ei_coefficient"] = self._dp_ei.value()
                conv["formative_coefficient"] = self._dp_f.value()
                conv["summative_coefficient"] = self._dp_s.value()

        CalcEngine.save_formula(self._termsubject_id, self._formula)
        # Sauvegarder le coefficient
        conn = db.local_conn
        if conn is not None:
            conn.execute(
                "UPDATE larcauth_classroom_termsubject SET subject_weight = ? WHERE id = ?",
                (self._weight_combo.currentData(), str(self._termsubject_id)))
            conn.commit()
        self.accept()

    @safe_slot("Unknown._on_apply_all")
    def _on_apply_all(self):
        """Applique la formule courante et le coefficient a toutes les matieres du prof."""
        if not self._is_editor:
            return
        conn = db.local_conn
        if conn is None or not session.user_id:
            return
        CalcEngine.save_formula(self._termsubject_id, self._formula)
        json_str = json.dumps(self._formula, ensure_ascii=False)
        conn.execute("""
            UPDATE larcauth_classroom_termsubject
            SET calc_formula = ?, subject_weight = ?
            WHERE fk_teacher_id = ? AND fk_term_id = ?
        """, (json_str, self._weight_combo.currentData(), session.user_id, session.term_id))
        conn.commit()

    def _update_preview(self):
        pass
