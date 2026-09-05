"""LetterManager — gestionnaire de courriers et modèles de lettres (Module 12).

Pattern: modèles entreprise (AEC-*) visibles et actionnables, catalogue standard
accessible via "Nouveau modèle" → sélection → duplication automatique.
"""
from __future__ import annotations

import os
from datetime import date

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTextEdit, QLineEdit, QFileDialog, QMessageBox,
    QListWidget, QListWidgetItem, QApplication, QDialog,
)

from larccommon.session import session
from larccommon.design_system import ds
from larccommon.theme import theme_manager
from larccommon.icons import icon as md3_icon
from larccommon.safe_slot import safe_slot
from larccommon.widgets.themed_widget import ThemedDialog
from phibuilder.phi.scale import SpacingToken

from LarcRH.common.hr_database import HRDatabase
from LarcRH.views.letter_templates import build as build_letter
from LarcRH.views.letter_templates import generate_docx, render_body, PLACEHOLDER_STAFF

FAMILIES = [
    ("A", "Contrat et emploi"),
    ("B", "Rémunération"),
    ("C", "Discipline"),
    ("D", "Congés (RH)"),
    ("E", "Fin de contrat"),
    ("F", "Vie professionnelle"),
    ("G", "Recrutement"),
    ("H", "Demandes employé"),
    ("I", "Spécifique IB"),
    ("J", "Syndical"),
]

COMPANY_PREFIX = "AEC-"


def _extract_body_from_full(full_text: str) -> str:
    """Extrait le corps seul d'un texte complet (en-tête + corps + pied)."""
    lines = full_text.split("\n")
    body_start = 0
    footer_start = len(lines)
    for i, line in enumerate(lines):
        if line.startswith("Objet :"):
            body_start = i
        if line == "─" * 60 and i > body_start + 1:
            footer_start = i
            break
    body_lines = lines[body_start + 2:]
    body_only = "\n".join(body_lines).split(f"\n{'─' * 60}\n")[0].strip()
    return body_only


# ════════════════════════════════════════════════════════════════════
# Dialogue de génération
# ════════════════════════════════════════════════════════════════════

class _GenerateLetterDialog(ThemedDialog):

    def __init__(self, template: dict, staff_data: dict | None = None,
                 campus: dict | None = None, parent=None):
        super().__init__(parent)
        self._template = template
        self._staff = staff_data
        self._campus = campus
        self._output_path = ""
        self.setWindowTitle(f"Générer — {template.get('title', '')}")
        _w = ds.golden_width(ds.kpi_card_height * 7)
        self.setMinimumSize(_w, ds.sp(SpacingToken.XXXL) * 3)
        self._setup_ui()

    @property
    def _STYLE(self) -> str:
        return f"GenerateLetterDialog {{ background: {theme_manager.palette.surface}; }}"

    @safe_slot("GenerateLetterDialog._restyle")
    def _restyle(self):
        try:
            self.setStyleSheet(self._STYLE)
        except RuntimeError:
            pass

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_sm)

        titre = QLabel(self._template.get("title", ""))
        titre.setStyleSheet(f"font-size: {s(16)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        layout.addWidget(titre)

        desc = QLabel(self._template.get("description", ""))
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: {s(12)}px; color: {p.text_soft}; border: none;")
        layout.addWidget(desc)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {p.outline_variant}; border: none;")
        layout.addWidget(sep)

        # Destinataire
        layout.addWidget(QLabel("Destinataire"))
        if self._staff:
            info = f"{self._staff.get('full_name', '—')}  |  ID {self._staff.get('id', '—')}"
        else:
            info = "Aucun employé sélectionné"
        lbl = QLabel(info)
        lbl.setStyleSheet(f"font-size: {s(13)}px; color: {p.text_strong}; border: none;")
        layout.addWidget(lbl)

        # Objet
        layout.addWidget(QLabel("Objet"))
        dflt = self._template.get("title", "")
        if self._staff:
            dflt = f"{dflt} — {self._staff.get('full_name', '')}"
        self._objet_field = QLineEdit(dflt)
        self._objet_field.setFixedHeight(ds.field_height)
        self._objet_field.setStyleSheet(ds.flat_input_qss())
        layout.addWidget(self._objet_field)

        # Réf
        layout.addWidget(QLabel("Numéro de référence"))
        ref = f"RH/{date.today().year}/{self._template.get('code', '')}/{date.today().strftime('%m')}"
        self._ref_field = QLineEdit(ref)
        self._ref_field.setFixedHeight(ds.field_height)
        self._ref_field.setStyleSheet(ds.flat_input_qss())
        layout.addWidget(self._ref_field)

        # Corps
        layout.addWidget(QLabel("Corps du courrier"))
        self._body_edit = QTextEdit()
        self._body_edit.setMinimumHeight(ds.kpi_card_height * 3)
        self._body_edit.setStyleSheet(f"""
            QTextEdit {{ background: {p.background}; border: 1px solid {p.outline};
            border-radius: {ds.radius_xs}px; padding: {ds.space_sm}px;
            color: {p.text_strong}; font-size: {s(12)}px; }}
            QTextEdit:focus {{ border-color: {p.primary}; }}
        """)
        layout.addWidget(self._body_edit)
        self._fill_body()
        layout.addStretch()

        # Boutons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Annuler")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setFixedHeight(ds.field_height + ds.space_xs)
        cancel.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {p.text_strong};
            border: 1px solid {p.outline}; border-radius: {ds.radius_sm}px;
            padding: {ds.space_xs}px {ds.space_md}px; font-size: {s(13)}px; }}
            QPushButton:hover {{ background: {p.surface_variant}; }}
        """)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        save = QPushButton("Générer et sauvegarder")
        save.setCursor(Qt.PointingHandCursor)
        save.setFixedHeight(ds.field_height + ds.space_xs)
        save.setStyleSheet(f"""
            QPushButton {{ background: {p.primary}; color: white; border: none;
            border-radius: {ds.radius_sm}px; padding: {ds.space_xs}px {ds.space_md}px;
            font-size: {s(13)}px; font-weight: bold; }}
            QPushButton:hover {{ background: {p.primary}; }}
        """)
        save.clicked.connect(self._on_generate)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)
        self.setStyleSheet(self._STYLE)

    def _fill_body(self):
        staff = self._staff or {}
        code = self._template.get("code", "")
        body = build_letter(staff, code, self._objet_field.text(),
                           self._ref_field.text(), campus=self._campus,
                           template=self._template)
        self._body_edit.setPlainText(body)
        self._body_initial = body  # pour détecter les modifications utilisateur

    @safe_slot("GenerateLetterDialog._on_generate")
    def _on_generate(self):
        default_name = f"courrier_{self._template.get('code', '')}.docx"
        fpath, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le courrier", default_name,
            "Word (*.docx);;PDF (*.pdf);;Texte (*.txt)")
        if not fpath:
            return
        edited = self._body_edit.toPlainText()
        if fpath.lower().endswith(".txt"):
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(edited)
        else:
            try:
                # Si l'utilisateur a modifié le texte, extraire le corps seul
                # pour éviter de dupliquer en-tête/pied dans le DOCX formaté
                body_override = None
                if edited != getattr(self, "_body_initial", ""):
                    body_override = render_body(
                        self._staff, self._template.get("code", ""),
                        template=self._template)
                    # Si le corps extrait du build est différent du corps
                    # extrait du texte édité, on utilise le texte édité
                    body_override = _extract_body_from_full(edited)
                generate_docx(staff=self._staff,
                    code=self._template.get("code", ""),
                    objet=self._objet_field.text(), ref=self._ref_field.text(),
                    campus=self._campus, output_path=fpath,
                    template=self._template, body_override=body_override)
            except Exception as exc:
                import traceback; traceback.print_exc()
                QMessageBox.warning(self, "Erreur", f"Erreur :\n{exc}")
                return
        if self._staff:
            HRDatabase.save_generated_letter(
                self._staff["id"], self._template["id"], fpath,
                reference=self._ref_field.text(), generated_by=session.user_id)
        QMessageBox.information(self, "Courrier généré", f"Courrier enregistré :\n{fpath}")
        self.accept()


# ════════════════════════════════════════════════════════════════════
# Dialogue sélection modèle standard (catalogue)
# ════════════════════════════════════════════════════════════════════

class _CatalogDialog(ThemedDialog):
    """Catalogue des modèles standards — sélection → duplication automatique,
    avec aperçu du corps du courrier."""

    template_chosen = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Catalogue des modèles")
        self.setMinimumSize(ds.golden_width(700), ds.golden_height(500))
        self._current_family: str | None = None
        self._selected_template: dict | None = None
        self._setup_ui()
        self._select_first()

    @property
    def _STYLE(self) -> str:
        return f"QDialog {{ background: {theme_manager.palette.background}; }}"

    @safe_slot("_CatalogDialog._restyle")
    def _restyle(self):
        try:
            self.setStyleSheet(self._STYLE)
        except RuntimeError:
            pass

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar familles ──
        sidebar = QWidget()
        sidebar.setAttribute(Qt.WA_StyledBackground, True)
        sidebar.setFixedWidth(ds.sp(SpacingToken.HUGE) - ds.sp(SpacingToken.XL))
        sidebar.setStyleSheet(f"background: {p.surface_variant}; border-right: 1px solid {p.outline_variant};")
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(ds.space_xs, ds.space_sm, ds.space_xs, ds.space_sm)
        sl.setSpacing(ds.space_xxs)

        sl.addWidget(QLabel("Familles"))
        self._cat_btns: dict[str, QPushButton] = {}
        for fam_key, fam_label in FAMILIES:
            btn = QPushButton(fam_label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(ds.field_height)
            btn.setStyleSheet(f"""
                QPushButton {{ text-align: left; padding: {ds.space_xxs}px {ds.space_xs}px;
                border: none; border-radius: {ds.radius_xs}px; color: {p.text_strong};
                font-size: {s(12)}px; background: transparent; }}
                QPushButton:checked {{ background: {p.primary_container}; color: {p.primary}; font-weight: bold; }}
                QPushButton:hover {{ background: {p.surface}; }}
            """)
            btn.clicked.connect(lambda checked, k=fam_key: self._switch(k))
            sl.addWidget(btn)
            self._cat_btns[fam_key] = btn
        sl.addStretch()
        layout.addWidget(sidebar)

        # ── Colonne gauche : liste + titre ──
        left_col = QVBoxLayout()
        left_col.setContentsMargins(ds.space_md, ds.space_sm, ds.space_xs, ds.space_sm)
        left_col.setSpacing(ds.space_sm)

        self._fam_title = QLabel("")
        self._fam_title.setStyleSheet(f"font-weight: bold; font-size: {s(14)}px; color: {p.text_strong}; border: none;")
        left_col.addWidget(self._fam_title)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._cards_w = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_w)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(ds.space_xxs)
        self._scroll.setWidget(self._cards_w)
        left_col.addWidget(self._scroll, 1)

        cancel_btn = QPushButton("Fermer")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFixedHeight(ds.field_height)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {p.text_strong};
            border: 1px solid {p.outline}; border-radius: {ds.radius_sm}px; }}
            QPushButton:hover {{ background: {p.surface_variant}; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        left_col.addWidget(cancel_btn, 0, Qt.AlignRight)

        layout.addLayout(left_col, 1)

        # ── Panneau d'aperçu à droite ──
        preview = QWidget()
        preview.setAttribute(Qt.WA_StyledBackground, True)
        preview.setFixedWidth(ds.sp(SpacingToken.XXXL) * 2)
        preview.setStyleSheet(f"background: {p.surface}; border-left: 1px solid {p.outline_variant};")
        pv = QVBoxLayout(preview)
        pv.setContentsMargins(ds.space_md, ds.space_sm, ds.space_md, ds.space_sm)
        pv.setSpacing(ds.space_sm)

        pv_label = QLabel("Aperçu")
        pv_label.setStyleSheet(f"font-weight: bold; font-size: {s(13)}px; color: {p.text_strong}; border: none;")
        pv.addWidget(pv_label)

        # Header aperçu
        self._pv_code = QLabel("")
        self._pv_code.setFixedWidth(ds.sp(SpacingToken.XL) - ds.sp(SpacingToken.XXS))
        self._pv_code.setAlignment(Qt.AlignCenter)
        self._pv_code.setStyleSheet(f"font-size: {s(10)}px; font-weight: bold; color: {p.primary}; "
                                     f"background: {p.primary_container}; border-radius: {ds.radius_xs}px; "
                                     f"padding: {ds.space_xxs}px {ds.space_xs}px; border: none;")
        pv_hdr = QHBoxLayout()
        pv_hdr.addWidget(self._pv_code)
        self._pv_title = QLabel("")
        self._pv_title.setWordWrap(True)
        self._pv_title.setStyleSheet(f"font-size: {s(12)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        pv_hdr.addWidget(self._pv_title, 1)
        pv.addLayout(pv_hdr)

        # Corps aperçu
        self._pv_body = QTextEdit()
        self._pv_body.setReadOnly(True)
        self._pv_body.setStyleSheet(f"""
            QTextEdit {{ background: {p.surface}; border: 1px solid {p.outline_variant};
            border-radius: {ds.radius_xs}px; padding: {ds.space_xs}px;
            color: {p.text_strong}; font-size: {s(11)}px; }}
        """)
        pv.addWidget(self._pv_body, 1)

        # Note tokens
        note = QLabel("Les mentions [Nom], [Poste], [Matricule] seront "
                       "remplacées automatiquement à la génération.")
        note.setWordWrap(True)
        note.setStyleSheet(f"font-size: {s(9)}px; color: {p.text_soft}; border: none;")
        pv.addWidget(note)

        # Bouton confirmer
        self._confirm_btn = QPushButton("  Sélectionner ce modèle")
        self._confirm_btn.setCursor(Qt.PointingHandCursor)
        self._confirm_btn.setFixedHeight(ds.field_height)
        self._confirm_btn.setStyleSheet(f"""
            QPushButton {{ background: {p.primary}; color: white; border: none;
            border-radius: {ds.radius_sm}px; padding: {ds.space_xs}px {ds.space_md}px;
            font-size: {s(13)}px; font-weight: bold; }}
            QPushButton:hover {{ background: {p.primary}; }}
            QPushButton:disabled {{ background: {p.outline_variant}; color: {p.text_disabled}; }}
        """)
        self._confirm_btn.clicked.connect(self._on_confirm)
        self._confirm_btn.setEnabled(False)
        pv.addWidget(self._confirm_btn)

        layout.addWidget(preview)
        self.setStyleSheet(self._STYLE)

    # ── Navigation ──

    def _select_first(self):
        if FAMILIES:
            self._switch(FAMILIES[0][0])

    def _switch(self, fam_key: str):
        self._current_family = fam_key
        for k, btn in self._cat_btns.items():
            btn.setChecked(k == fam_key)
        fam_label = next((lbl for k, lbl in FAMILIES if k == fam_key), fam_key)
        self._fam_title.setText(fam_label)
        self._selected_template = None
        self._confirm_btn.setEnabled(False)
        self._populate()

    # ── Cartes + aperçu ──

    def _populate(self):
        while self._cards_layout.count():
            w = self._cards_layout.takeAt(0).widget()
            if w: w.deleteLater()

        p = theme_manager.palette
        s = theme_manager.font_size
        templates = HRDatabase.get_letter_templates(family=self._current_family, active_only=True)
        builtins = [t for t in templates if t.get("is_builtin")]

        if not builtins:
            self._cards_layout.addWidget(QLabel("Aucun modèle standard dans cette famille."))
            self._cards_layout.addStretch()
            return

        for tpl in builtins:
            card = QFrame()
            card.setCursor(Qt.PointingHandCursor)
            card.setAttribute(Qt.WA_StyledBackground, True)
            card.setStyleSheet(f"""
                QFrame {{ background: {p.surface}; border: 1px solid {p.outline_variant};
                border-radius: {ds.radius_sm}px; }}
                QFrame:hover {{ background: {p.surface_variant}; border-color: {p.primary}; }}
            """)
            crd = QVBoxLayout(card)
            crd.setContentsMargins(ds.space_sm, ds.space_xs, ds.space_sm, ds.space_xs)
            crd.setSpacing(ds.space_xxs)

            r1 = QHBoxLayout()
            code_lbl = QLabel(tpl.get("code", ""))
            code_lbl.setFixedWidth(ds.field_height + ds.space_xs)
            code_lbl.setAlignment(Qt.AlignCenter)
            code_lbl.setStyleSheet(f"font-size: {s(11)}px; font-weight: bold; color: {p.primary}; "
                                    f"background: {p.primary_container}; border-radius: {ds.radius_xs}px; "
                                    f"padding: {ds.space_xxs}px {ds.space_xs}px; border: none;")
            r1.addWidget(code_lbl)
            title_lbl = QLabel(tpl.get("title", ""))
            title_lbl.setStyleSheet(f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong}; border: none;")
            r1.addWidget(title_lbl, 1)
            crd.addLayout(r1)

            desc = tpl.get("description", "")
            if desc:
                d = QLabel(desc)
                d.setWordWrap(True)
                d.setStyleSheet(f"font-size: {s(11)}px; color: {p.text_soft}; border: none; padding-left: 52px;")
                crd.addWidget(d)

            # Clic sur la carte → aperçu
            card.mousePressEvent = lambda e, t=tpl, c=card: self._on_card_click(t, c)
            self._cards_layout.addWidget(card)

        self._cards_layout.addStretch()

    @safe_slot("_CatalogDialog._on_card_click")
    def _on_card_click(self, template: dict, card_widget):
        """Affiche l'aperçu du modèle cliqué."""
        p = theme_manager.palette
        s = theme_manager.font_size
        self._selected_template = template

        # Surbrillance
        for i in range(self._cards_layout.count()):
            w = self._cards_layout.itemAt(i).widget()
            if w and isinstance(w, QFrame):
                w.setStyleSheet(f"""
                    QFrame {{ background: {p.surface}; border: 1px solid {p.outline_variant};
                    border-radius: {ds.radius_sm}px; }}
                    QFrame:hover {{ background: {p.surface_variant}; border-color: {p.primary}; }}
                """)
        card_widget.setStyleSheet(f"""
            QFrame {{ background: {p.surface_variant}; border: 2px solid {p.primary};
            border-radius: {ds.radius_sm}px; }}
        """)

        # Remplir l'aperçu
        code = template.get("code", "")
        self._pv_code.setText(code)
        self._pv_title.setText(template.get("title", ""))
        try:
            body = render_body(PLACEHOLDER_STAFF, code)
            self._pv_body.setPlainText(body)
        except Exception:
            self._pv_body.setPlainText(f"[Erreur lors du rendu du modèle {code}]")

        self._confirm_btn.setEnabled(True)

    @safe_slot("_CatalogDialog._on_confirm")
    def _on_confirm(self):
        if self._selected_template:
            self.template_chosen.emit(self._selected_template)
            self.accept()

    @safe_slot("_CatalogDialog._on_select")
    def _on_select(self, template: dict):
        """Méthode conservée pour rétrocompatibilité — le bouton confirmer est privilégié."""
        self.template_chosen.emit(template)
        self.accept()


# ════════════════════════════════════════════════════════════════════
# Dialogue édition modèle
# ════════════════════════════════════════════════════════════════════

class _EditTemplateDialog(ThemedDialog):
    """Dialogue d'édition d'un modèle entreprise : titre, description, corps."""

    def __init__(self, template: dict, parent=None):
        super().__init__(parent)
        self._template = template
        self._restore_requested = False
        self.setWindowTitle(f"Modifier — {template.get('title', '')}")
        self.setMinimumSize(ds.golden_width(600), ds.golden_height(500))
        self._setup_ui()

    @property
    def _STYLE(self) -> str:
        return f"QDialog {{ background: {theme_manager.palette.surface}; }}"

    @safe_slot("_EditTemplateDialog._restyle")
    def _restyle(self):
        try:
            self.setStyleSheet(self._STYLE)
        except RuntimeError:
            pass

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_sm)

        layout.addWidget(QLabel(f"Code : {self._template.get('code', '')}"))

        layout.addWidget(QLabel("Titre :"))
        self._title_edit = QLineEdit(self._template.get("title", ""))
        self._title_edit.setFixedHeight(ds.field_height)
        self._title_edit.setStyleSheet(ds.flat_input_qss())
        layout.addWidget(self._title_edit)

        layout.addWidget(QLabel("Description :"))
        self._desc_edit = QTextEdit()
        self._desc_edit.setPlainText(self._template.get("description", ""))
        self._desc_edit.setFixedHeight(ds.kpi_card_height)
        self._desc_edit.setStyleSheet(f"""
            QTextEdit {{ background: {p.background}; border: 1px solid {p.outline};
            border-radius: {ds.radius_xs}px; padding: {ds.space_xs}px;
            color: {p.text_strong}; font-size: {s(12)}px; }}
        """)
        layout.addWidget(self._desc_edit)

        # ── Corps du courrier ──
        layout.addWidget(QLabel("Corps du courrier :"))
        # Note sur les tokens auto-remplacés
        note = QLabel("Les mentions [Nom], [Poste], [Matricule] seront "
                       "remplacées automatiquement à la génération.")
        note.setWordWrap(True)
        note.setStyleSheet(f"font-size: {s(10)}px; color: {p.text_soft}; border: none;")
        layout.addWidget(note)

        self._body_initial = render_body(
            PLACEHOLDER_STAFF, self._template.get("code", ""),
            template=self._template)

        self._body_edit = QTextEdit()
        self._body_edit.setPlainText(self._body_initial)
        self._body_edit.setMinimumHeight(ds.kpi_card_height * 2)
        self._body_edit.setStyleSheet(f"""
            QTextEdit {{ background: {p.background}; border: 1px solid {p.outline};
            border-radius: {ds.radius_xs}px; padding: {ds.space_sm}px;
            color: {p.text_strong}; font-size: {s(12)}px; }}
            QTextEdit:focus {{ border-color: {p.primary}; }}
        """)
        layout.addWidget(self._body_edit, 1)

        # Bouton restaurer
        restore_btn = QPushButton("  Restaurer le contenu d'origine")
        restore_btn.setCursor(Qt.PointingHandCursor)
        restore_btn.setFixedHeight(ds.icon_btn_size + ds.space_xxs)
        restore_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {p.text_soft};
            border: 1px solid {p.outline}; border-radius: {ds.radius_xs}px;
            padding: {ds.space_xxs}px {ds.space_xs}px; font-size: {s(11)}px; }}
            QPushButton:hover {{ background: {p.surface_variant}; color: {p.primary}; }}
        """)
        restore_btn.clicked.connect(self._on_restore)
        layout.addWidget(restore_btn)

        # ── Boutons ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Annuler")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setFixedHeight(ds.field_height)
        cancel.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {p.text_strong};
            border: 1px solid {p.outline}; border-radius: {ds.radius_sm}px;
            padding: {ds.space_xs}px {ds.space_md}px; }}
            QPushButton:hover {{ background: {p.surface_variant}; }}
        """)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        save = QPushButton("Enregistrer")
        save.setCursor(Qt.PointingHandCursor)
        save.setFixedHeight(ds.field_height)
        save.setStyleSheet(f"""
            QPushButton {{ background: {p.primary}; color: white; border: none;
            border-radius: {ds.radius_sm}px; padding: {ds.space_xs}px {ds.space_md}px;
            font-weight: bold; }}
            QPushButton:hover {{ background: {p.primary}; }}
        """)
        save.clicked.connect(self.accept)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)
        self.setStyleSheet(self._STYLE)

    @safe_slot("_EditTemplateDialog._on_restore")
    def _on_restore(self):
        """Remet le corps au texte fonction d'origine (body_text = NULL)."""
        original = render_body(
            PLACEHOLDER_STAFF, self._template.get("code", ""),
            template={k: v for k, v in self._template.items() if k != "body_text"})
        self._body_edit.setPlainText(original)
        self._restore_requested = True

    def result(self):
        """Retourne (titre, description, payload) où payload est None,
        {"body_text": ...} ou {"clear_body": True}."""
        payload = None
        if self._restore_requested:
            payload = {"clear_body": True}
        else:
            current = self._body_edit.toPlainText()
            if current != self._body_initial:
                payload = {"body_text": current}
        return self._title_edit.text().strip(), self._desc_edit.toPlainText().strip(), payload


# ════════════════════════════════════════════════════════════════════
# Staff search popup
# ════════════════════════════════════════════════════════════════════

class _StaffSearchPopup(QFrame):
    staff_chosen = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        p = theme_manager.palette
        self.setObjectName("letter_template_dialog")
        # IE9 : sélecteur scopé (voir contract_form)
        self.setStyleSheet(f"QDialog#letter_template_dialog {{ background: {p.surface}; "
                           f"border: 1px solid {p.outline}; border-radius: {ds.radius_sm}px; }}")
        self.setMinimumWidth(ds.sp(SpacingToken.GIANT) - ds.sp(SpacingToken.XXS))
        self.setMaximumHeight(ds.sp(SpacingToken.HUGE) + ds.sp(SpacingToken.XXL))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ds.space_xxs, ds.space_xxs, ds.space_xxs, ds.space_xxs)
        self._list = QListWidget()
        self._list.setFrameShape(QListWidget.NoFrame)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)
        self._items_data: list[dict] = []

    def set_results(self, results: list[dict]):
        self._items_data = results
        self._list.clear()
        for d in results:
            text = f"{d.get('full_name', '—')}  |  ID {d.get('id', '—')}  |  {d.get('professional_category', '')}"
            self._list.addItem(QListWidgetItem(text))

    @safe_slot("_StaffSearchPopup._on_item_clicked")
    def _on_item_clicked(self, item):
        idx = self._list.row(item)
        if 0 <= idx < len(self._items_data):
            self.staff_chosen.emit(self._items_data[idx])
            self.hide()


# ════════════════════════════════════════════════════════════════════
# LetterManager — page principale
# ════════════════════════════════════════════════════════════════════

class LetterManager(QWidget):
    staff_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_family: str | None = None
        self._selected_staff: dict | None = None
        self._search_text = ""
        self._search_timer: QTimer | None = None
        self._staff_popup: _StaffSearchPopup | None = None
        self._setup_ui()
        self._select_first_family()

    def set_staff(self, staff_data: dict):
        self._selected_staff = staff_data
        if staff_data:
            self._staff_search.setText(f"{staff_data.get('full_name', '')} (ID {staff_data.get('id', '')})")
        self._refresh_cards()

    def _setup_ui(self):
        p = theme_manager.palette
        s = theme_manager.font_size
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sidebar ──
        sidebar = QWidget()
        sidebar.setFixedWidth(ds.sp(SpacingToken.XXXL) + ds.space_sm * 2)
        sidebar.setAttribute(Qt.WA_StyledBackground, True)
        sidebar.setStyleSheet(f"background: {p.surface_variant}; border-right: 1px solid {p.outline_variant};")
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(ds.space_xs, ds.space_sm, ds.space_xs, ds.space_sm)
        sl.setSpacing(ds.space_xxs)

        sl.addWidget(QLabel("Familles"))
        self._cat_buttons: dict[str, QPushButton] = {}
        for fam_key, fam_label in FAMILIES:
            btn = QPushButton(fam_label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(ds.field_height)
            btn.setStyleSheet(f"""
                QPushButton {{ text-align: left; padding: {ds.space_xxs}px {ds.space_xs}px;
                border: none; border-radius: {ds.radius_xs}px; color: {p.text_strong};
                font-size: {s(12)}px; background: transparent; }}
                QPushButton:checked {{ background: {p.primary_container}; color: {p.primary}; font-weight: bold; }}
                QPushButton:hover {{ background: {p.surface}; }}
            """)
            btn.clicked.connect(lambda checked, k=fam_key: self._switch_family(k))
            sl.addWidget(btn)
            self._cat_buttons[fam_key] = btn
        sl.addStretch()
        layout.addWidget(sidebar)

        # ── Content ──
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(ds.space_md, ds.space_sm, ds.space_md, ds.space_sm)
        cl.setSpacing(ds.space_sm)

        # Staff selector
        staff_row = QHBoxLayout()
        staff_row.setSpacing(ds.space_sm)
        from phibuilder.widgets import M3TextField
        self._staff_search = M3TextField()
        self._staff_search.setPlaceholderText("Rechercher un employé...")
        self._staff_search.setFixedHeight(ds.field_height)
        self._staff_search.setStyleSheet(ds.flat_input_qss())
        self._staff_search.textChanged.connect(self._on_staff_search_typed)
        staff_row.addWidget(QLabel("Destinataire :"))
        staff_row.addWidget(self._staff_search, 1)
        clear_btn = QPushButton()
        clear_btn.setIcon(md3_icon("close", color=p.text_soft, size=14))
        clear_btn.setFixedSize(ds.icon_btn_size + ds.space_xxs, ds.icon_btn_size + ds.space_xxs)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setToolTip("Effacer")
        clear_btn.setStyleSheet("QPushButton { border: none; background: transparent; }")
        clear_btn.clicked.connect(self._clear_staff)
        staff_row.addWidget(clear_btn)
        cl.addLayout(staff_row)

        # Header: titre + bouton Nouveau modèle
        hdr = QHBoxLayout()
        hdr.setSpacing(ds.space_sm)
        self._fam_title = QLabel("")
        self._fam_title.setStyleSheet(f"font-weight: bold; font-size: {s(14)}px; color: {p.text_strong}; border: none;")
        hdr.addWidget(self._fam_title)
        hdr.addStretch()

        new_btn = QPushButton("+ Nouveau modèle")
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.setFixedHeight(ds.field_height)
        new_btn.setStyleSheet(f"""
            QPushButton {{ background: {p.primary}; color: white; border: none;
            border-radius: {ds.radius_sm}px; padding: {ds.space_xxs}px {ds.space_md}px;
            font-size: {s(13)}px; font-weight: bold; }}
            QPushButton:hover {{ background: {p.primary}; }}
        """)
        new_btn.clicked.connect(self._on_new_model)
        hdr.addWidget(new_btn)
        cl.addLayout(hdr)

        # Compteur
        self._counter_lbl = QLabel("")
        self._counter_lbl.setStyleSheet(f"font-size: {s(11)}px; color: {p.text_soft}; border: none;")
        cl.addWidget(self._counter_lbl)

        # Scroll
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._cards_w = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_w)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(ds.space_xs)
        self._scroll.setWidget(self._cards_w)
        cl.addWidget(self._scroll, 1)
        layout.addWidget(content, 1)

    # ── Staff search ──

    @safe_slot("LetterManager._on_staff_search_typed")
    def _on_staff_search_typed(self, text: str):
        if len(text.strip()) < 2:
            if self._staff_popup: self._staff_popup.hide()
            return
        if self._search_timer is None:
            self._search_timer = QTimer(self); self._search_timer.setSingleShot(True)
            self._search_timer.timeout.connect(self._do_staff_search)
        self._search_timer.stop(); self._search_timer.start(300)

    @safe_slot("LetterManager._do_staff_search")
    def _do_staff_search(self):
        q = self._staff_search.text().strip()
        if len(q) < 2: return
        results = HRDatabase.search_staff(1001, 5000, is_staff=False, search_text=q)
        results += HRDatabase.search_staff(4001, 5000, is_staff=True, search_text=q)
        seen = set(); unique = []
        for r in results:
            if r["id"] not in seen: seen.add(r["id"]); unique.append(r)
        if unique: self._show_staff_popup(unique[:20])

    def _show_staff_popup(self, results):
        if self._staff_popup is None:
            self._staff_popup = _StaffSearchPopup(self)
            self._staff_popup.staff_chosen.connect(self._on_staff_chosen)
        self._staff_popup.set_results(results)
        self._staff_popup.setFixedWidth(self._staff_search.width())
        pos = self._staff_search.mapToGlobal(self._staff_search.rect().bottomLeft())
        self._staff_popup.move(pos); self._staff_popup.show()

    @safe_slot("LetterManager._on_staff_chosen")
    def _on_staff_chosen(self, staff_data):
        self._selected_staff = staff_data
        self._staff_search.setText(f"{staff_data.get('full_name', '')} (ID {staff_data.get('id', '')})")
        if self._staff_popup: self._staff_popup.hide()
        self._refresh_cards()

    @safe_slot("LetterManager._clear_staff")
    def _clear_staff(self):
        self._selected_staff = None; self._staff_search.clear()
        if self._staff_popup: self._staff_popup.hide()
        self._refresh_cards()

    # ── Navigation ──

    def _select_first_family(self):
        if FAMILIES: self._switch_family(FAMILIES[0][0])

    def _switch_family(self, fam_key: str):
        self._current_family = fam_key
        for k, btn in self._cat_buttons.items(): btn.setChecked(k == fam_key)
        fam_label = next((lbl for k, lbl in FAMILIES if k == fam_key), fam_key)
        self._fam_title.setText(fam_label)
        self._refresh_cards()

    # ── Cards ──

    def _refresh_cards(self):
        while self._cards_layout.count():
            w = self._cards_layout.takeAt(0).widget()
            if w: w.deleteLater()

        p = theme_manager.palette
        s = theme_manager.font_size

        # Affiche UNIQUEMENT les modèles personnalisés (is_builtin=false)
        templates = HRDatabase.get_letter_templates(family=self._current_family, search=self._search_text)
        customs = [t for t in templates if not t.get("is_builtin")]

        self._counter_lbl.setText(f"{len(customs)} modèle(s) entreprise dans cette famille")

        if not customs:
            empty = QLabel("Aucun modèle entreprise.\nCliquez « + Nouveau modèle » pour ajouter un modèle depuis le catalogue.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {p.text_soft}; font-size: {s(13)}px; border: none; padding: {ds.field_height + ds.space_xs}px;")
            self._cards_layout.addWidget(empty)
            self._cards_layout.addStretch()
            return

        for tpl in customs:
            card = self._make_card(tpl, p, s)
            self._cards_layout.addWidget(card)
        self._cards_layout.addStretch()

    def _make_card(self, tpl, p, s):
        code = tpl.get("code", "")
        title = tpl.get("title", "")
        desc = tpl.get("description", "")
        family = tpl.get("family", "F")

        card = QFrame()
        card.setAttribute(Qt.WA_StyledBackground, True)
        card.setStyleSheet(f"""
            QFrame {{ background: {p.surface}; border: 2px solid {p.outline_variant};
            border-radius: {ds.radius_sm}px; }}
            QFrame:hover {{ border-color: {p.primary}; }}
        """)
        crd = QVBoxLayout(card)
        crd.setContentsMargins(ds.space_sm, ds.space_xs, ds.space_sm, ds.space_xs)
        crd.setSpacing(ds.space_xxs)

        # Row 1: code + title + badge AEC
        r1 = QHBoxLayout()
        r1.setSpacing(ds.space_sm)
        code_lbl = QLabel(code)
        code_lbl.setFixedWidth(ds.sp(SpacingToken.XL) + ds.sp(SpacingToken.MD))
        code_lbl.setAlignment(Qt.AlignCenter)
        code_lbl.setStyleSheet(f"font-size: {s(10)}px; font-weight: bold; color: {p.on_primary}; background: {p.primary}; border-radius: {ds.radius_xs}px; padding: {ds.space_xxs}px {ds.space_xs}px; border: none;")
        r1.addWidget(code_lbl)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: {s(13)}px; font-weight: bold; color: {p.text_strong}; border: none;")
        r1.addWidget(title_lbl, 1)

        badge = QLabel("  AEC  ")
        badge.setStyleSheet(f"font-size: {s(8)}px; color: {p.primary}; border: {ds.border_width}px solid {p.primary}; border-radius: {ds.radius_xs}px; padding: {ds.space_xxs}px; background: {p.primary_container};")
        r1.addWidget(badge)
        crd.addLayout(r1)

        if desc:
            d = QLabel(desc)
            d.setWordWrap(True)
            d.setStyleSheet(f"font-size: {s(11)}px; color: {p.text_soft}; border: none; padding-left: 82px;")
            crd.addWidget(d)

        # Famille
        fam_names = {"A": "Contrat", "B": "Rémunération", "C": "Discipline", "D": "Congé",
                     "E": "Départ", "F": "Vie pro", "G": "Recrutement", "H": "Demande employé",
                     "I": "IB", "J": "Syndical"}
        fam_lbl = QLabel(fam_names.get(family, ""))
        fam_lbl.setStyleSheet(f"font-size: {s(10)}px; color: {p.text_soft}; border: none; padding-left: 82px;")
        crd.addWidget(fam_lbl)

        # Staff chip
        actions = QHBoxLayout()
        actions.setSpacing(ds.space_xxs)
        if self._selected_staff:
            chip = QLabel(f"  {self._selected_staff.get('full_name', '')[:25]}  ")
            chip.setStyleSheet(f"font-size: {s(10)}px; color: {p.primary}; background: {p.primary_container}; border-radius: {ds.radius_sm}px; padding: {ds.space_xxs}px {ds.space_xs}px; border: none;")
            chip.setFixedHeight(ds.icon_sm)
            actions.addWidget(chip)
        else:
            actions.addWidget(QLabel("  Pas de destinataire  "))
        actions.addStretch()

        # Modifier
        edit_btn = QPushButton("  Modifier")
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.setFixedHeight(ds.icon_btn_size + ds.space_xxs)
        edit_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {p.text_soft};
            border: 1px solid {p.outline}; border-radius: {ds.radius_xs}px;
            padding: {ds.space_xxs}px {ds.space_xs}px; font-size: {s(11)}px; }}
            QPushButton:hover {{ background: {p.surface_variant}; color: {p.primary}; }}
        """)
        edit_btn.clicked.connect(lambda checked, t=tpl: self._on_edit(t))
        actions.addWidget(edit_btn)

        # Supprimer
        del_btn = QPushButton("  Supprimer")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setFixedHeight(ds.icon_btn_size + ds.space_xxs)
        del_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {p.error};
            border: 1px solid {p.error}; border-radius: {ds.radius_xs}px;
            padding: {ds.space_xxs}px {ds.space_xs}px; font-size: {s(11)}px; }}
            QPushButton:hover {{ background: {p.error}; color: white; }}
        """)
        del_btn.clicked.connect(lambda checked, t=tpl: self._on_delete(t))
        actions.addWidget(del_btn)

        # Générer
        gen_btn = QPushButton("  Générer")
        gen_btn.setCursor(Qt.PointingHandCursor)
        gen_btn.setFixedHeight(ds.icon_btn_size + ds.space_xxs)
        gen_btn.setStyleSheet(f"""
            QPushButton {{ background: {p.primary}; color: white; border: none;
            border-radius: {ds.radius_xs}px; padding: {ds.space_xxs}px {ds.space_xs}px;
            font-size: {s(12)}px; font-weight: bold; }}
            QPushButton:hover {{ background: {p.primary}; }}
        """)
        gen_btn.clicked.connect(lambda checked, t=tpl: self._on_generate(t))
        actions.addWidget(gen_btn)
        crd.addLayout(actions)

        return card

    # ── Actions ──

    @safe_slot("LetterManager._on_new_model")
    def _on_new_model(self):
        dlg = _CatalogDialog(self)
        dlg.template_chosen.connect(self._on_template_chosen)
        dlg.exec()

    @safe_slot("LetterManager._on_template_chosen")
    def _on_template_chosen(self, template: dict):
        """Duplique un standard en modèle entreprise."""
        new_code = f"{COMPANY_PREFIX}{template.get('code', '')}"
        existing = HRDatabase.get_letter_templates(search=new_code)
        if existing:
            QMessageBox.information(self, "Déjà existant",
                f"Un modèle {new_code} existe déjà. Modifiez-le directement.")
            return
        new_id = HRDatabase.save_letter_template({
            "family": template.get("family", "F"),
            "code": new_code,
            "title": f"{COMPANY_PREFIX}{template.get('title', '')}",
            "description": f"[De {template.get('code', '')}] {template.get('description', '')}",
            "source_code": template.get("code", ""),
            "created_by": session.user_id,
        })
        if new_id:
            # Aller sur la famille correspondante
            fam = template.get("family", "F")
            if fam in self._cat_buttons:
                self._switch_family(fam)
            QMessageBox.information(self, "Modèle ajouté",
                f"Le modèle {new_code} est maintenant dans vos modèles entreprise.\n"
                f"Vous pouvez le modifier avant de générer un courrier.")
        else:
            QMessageBox.warning(self, "Erreur", "Impossible de créer le modèle.")

    @safe_slot("LetterManager._on_edit")
    def _on_edit(self, template: dict):
        dlg = _EditTemplateDialog(template, parent=self)
        if dlg.exec():
            new_title, new_desc, payload = dlg.result()
            if new_title:
                data = {"id": template["id"], "title": new_title, "description": new_desc}
                if payload:
                    data.update(payload)
                HRDatabase.save_letter_template(data)
                self._refresh_cards()

    @safe_slot("LetterManager._on_delete")
    def _on_delete(self, template: dict):
        code = template.get("code", "")
        r = QMessageBox.question(self, "Supprimer",
            f"Supprimer définitivement le modèle {code} ?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r == QMessageBox.Yes:
            HRDatabase.toggle_letter_template(template["id"], False)
            self._refresh_cards()

    @safe_slot("LetterManager._on_generate")
    def _on_generate(self, template: dict):
        campus = None
        if self._selected_staff:
            cid = self._selected_staff.get("fk_campus_id")
            if cid: campus = HRDatabase.get_campus_full(cid)
        dlg = _GenerateLetterDialog(template, self._selected_staff, campus=campus, parent=self)
        dlg.exec()

    def refresh(self):
        self._refresh_cards()
