"""Fenêtre principale — Espace de travail du professeur.

Sidebar verticale (toujours visible) : matière-classe, formatives, sommatives, jugements.
Workspace (après sélection) : grille élèves × notes + barre actions.
"""
from __future__ import annotations

from functools import partial

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QFont, QColor, QAction, QIcon, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStatusBar,
    QStyle,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon



from common.database import db
from common.logger import log
from common.session import session
from common.theme import (
    theme_manager,
    ZONE_F_COLOR,
    ZONE_S_COLOR,
    ZONE_NEUTRAL,
    ZONE_TEXT_LIGHT,
    ZONE_BORDER,
    ZONE_BTN_BG,
)
from common.grid_config import pei_config
from views.eval_manager import EvalManagerWindow
from views.grid_table import ClipboardTable, ColorDelegate, ZoneHeaderView
from larccommon.safe_slot import safe_slot






from views.main_data import DataMixin
from views.main_notes import NotesGridMixin
from views.main_actions import SyncActionsMixin


class MainWindow(DataMixin, NotesGridMixin, SyncActionsMixin, QMainWindow):
    """Espace de travail du professeur."""

    @property
    def _STYLE(self) -> str:
        p = theme_manager.theme.palette
        return f"""
            QFrame#header {{
                background: {ZONE_S_COLOR};
                color: {p.on_primary};
                border-radius: {ds.radius_sm}px;
            }}
            QFrame#header QLabel {{ color: {p.on_primary}; }}
            QFrame.panel {{
                background: {p.surface};
                border: 1px solid {p.border};
                border-radius: {ds.radius_sm}px;
            }}
            QLabel.placeholder {{
                color: {p.inactive};
                font-style: italic;
            }}
        """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        QApplication.setStyle('Fusion')
        self.setWindowTitle('LarcProf — College Notes')
        self.resize(ds.window_width, ds.window_height)
        self.setStyleSheet(self._STYLE)

        # Data cache
        self._items: list[dict] = []
        self._eleves_par_classe: dict[int, list[dict]] = {}
        self._cycle_par_classe: dict[int, str] = {}
        self._items_other: list[dict] = []
        self._manager_f: EvalManagerWindow | None = None
        self._manager_s: EvalManagerWindow | None = None
        self._grille: QTableWidget | None = None
        self._current_item: dict | None = None

        # État courant
        self._current_ts_id: int | None = None
        self._current_cycle: str = 'PEI'
        self._evals_f: list[dict] = []  # index_eval, label, nature, crit_a..d, is_active
        self._evals_s: list[dict] = []
        self._visible_f: set[int] = set()  # slots indices actuellement affichés dans la grille
        self._visible_s: set[int] = set()
        self._show_f_comment: bool = False
        self._show_s_comment: bool = False
        self._last_clicked_f: int | None = None  # dernier slot cliqué pour détail
        self._last_clicked_s: int | None = None
        self._show_jgt_comment: bool = False
        self._visible_crits: dict[str, bool] = {'a': True, 'b': True, 'c': True, 'd': True}
        self._name_format_prenom_first: bool = False  # True = "Prenom Nom"
        self._row_ids: dict[int, int] = {}  # student_id → learner table row id
        self._dirty_cells: dict[tuple[int, str], str] = {}  # (student_id, col_db_name) → new value
        self._last_item_idx = -1  # index matière-classe affiché (garde de sortie)
        self._current_table: str = ''
        self._current_col_names: list[str] = ['Élève']
        self._current_student_ids: list[int] = []

        # Widgets sidebar (références pour mise à jour)
        self._sidebar: QWidget | None = None
        self._workspace_widget: QWidget | None = None
        self._fwidgets: dict = {}  # widgets section formatives
        self._swidgets: dict = {}  # widgets section sommatives
        self._jwidgets: dict = {}  # widgets section jugements

        self._setup_ui()
        self._load_combined_data()
        ds.theme_changed.connect(self._restyle)

    @safe_slot("MainWindow._restyle")
    def _restyle(self):
        """Re-applique les styles palette-dependent au changement de theme."""
        p = theme_manager.theme.palette
        self.setStyleSheet(self._STYLE)
        self._lbl_other.setStyleSheet(f'color: {p.text_strong};')
        self._items_other_combo.setStyleSheet(f"background: {p.primary_container};")
        self._weight_btn.setStyleSheet(self._btn_zone_style())
        self._roles_lbl.setStyleSheet(f"color: {p.on_primary}; border: none;")
        if hasattr(self, "_theme_btn"):
            self._theme_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: 1px solid {p.on_primary}; "
                f"border-radius: {ds.icon_btn_size // 2}px; }}"
                f"QPushButton:hover {{ background: rgba(255,255,255,0.2); }}"
            )
        # Les 4 panneaux du sidebar (matiere / F / S / jugements)
        for section, frame in self._side_frames.items():
            frame.setStyleSheet(self._panel_qss(section))
        # Titres des panneaux F/S : blanc fixe sur fonds colorés
        if self._fwidgets.get('title_lbl'):
            self._fwidgets['title_lbl'].setStyleSheet(f'color: {ZONE_TEXT_LIGHT};')
        if self._swidgets.get('title_lbl'):
            self._swidgets['title_lbl'].setStyleSheet(f'color: {ZONE_TEXT_LIGHT};')
        # Entêtes de grille recolorées (sauvegarde avant rechargement)
        self._save_grid_edits()
        if self._current_item is not None:
            item = self._current_item
            eleves = self._eleves_par_classe.get(item['class_id'], [])
            self._fill_grille(item, item['cycle'], eleves)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(ds.space_xxs, ds.space_xxs, ds.space_xxs, ds.space_xxs)
        layout.setSpacing(ds.space_xxs)

        layout.addWidget(self._build_header())

        # Sidebar verticale (toujours visible) : 4 sections empilées, scroll si besoin
        side_area = QScrollArea()
        side_area.setWidgetResizable(True)
        side_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        side_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        side_area.setFrameShape(QFrame.NoFrame)
        side_area.setFixedWidth(ds.workspace_sidebar_width)
        side_area.setWidget(self._build_sidebar())
        side_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        # Workspace (grille + actions) — toujours en layout, vide si pas de sélection
        self._workspace_widget = QWidget()
        self._workspace_widget.setMinimumHeight(ds.workspace_min_height)
        ws_layout = QVBoxLayout(self._workspace_widget)
        ws_layout.setContentsMargins(0, 0, 0, 0)
        ws_layout.setSpacing(ds.space_xxs)
        ws_layout.addWidget(self._build_students_grid(), 1)
        ws_layout.addWidget(self._build_actions_bar())

        # Corps : sidebar à gauche (260 px), workspace à droite
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(ds.space_xxs)
        body.addWidget(side_area, 0)
        body.addWidget(self._workspace_widget, 1)
        layout.addLayout(body, 1)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage('Prêt')

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName('header')
        header.setMinimumHeight(ds.header_height)
        h = QHBoxLayout(header)
        h.setContentsMargins(ds.space_sm, ds.space_xs, ds.space_sm, ds.space_xs)

        prof_name = session.full_name or '—'
        annee = self._read_annee_scolaire()
        trim = session.term_label or '—'

        title_font = QFont('Segoe UI', theme_manager.font_size(14), QFont.Bold)
        meta_font = QFont('Segoe UI', theme_manager.font_size(11))
        small_font = QFont('Segoe UI', theme_manager.font_size(10))

        # Nom + roles sur deux lignes
        prof_col = QVBoxLayout()
        prof_col.setSpacing(ds.space_xxs)
        prof_lbl = QLabel(prof_name)
        prof_lbl.setFont(title_font)
        prof_col.addWidget(prof_lbl)

        self._roles_lbl = QLabel()
        self._roles_lbl.setFont(small_font)
        self._update_roles_label()
        prof_col.addWidget(self._roles_lbl)
        h.addLayout(prof_col)
        h.addStretch(1)

        annee_lbl = QLabel(f'Annee  {annee}')
        annee_lbl.setFont(meta_font)
        h.addWidget(annee_lbl)
        h.addSpacing(ds.space_md)
        trim_lbl = QLabel(f'Trimestre  {trim}')
        trim_lbl.setFont(meta_font)
        h.addWidget(trim_lbl)

        h.addSpacing(ds.space_sm)

        # Bouton thème — icône MD3 réactive au thème actif (comme LarcSuperviseur)
        self._theme_btn = QPushButton()
        self._theme_btn.setFixedSize(ds.icon_btn_size, ds.icon_btn_size)
        self._theme_btn.setToolTip('Changer le thème')
        self._theme_btn.setIcon(self._theme_icon())
        self._theme_btn.setIconSize(QSize(20, 20))
        self._theme_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {theme_manager.theme.palette.on_primary}; "
            f"border-radius: {ds.icon_btn_size // 2}px; }}"
            f"QPushButton:hover {{ background: rgba(255,255,255,0.2); }}"
        )
        theme_menu = QMenu(self)
        for key, label in theme_manager.names():
            act = QAction(label, self)
            act.setData(key)
            pal = theme_manager.get_palette(key)
            act.setIcon(md3_icon(
                self._THEME_ICONS.get(key, 'light_mode'),
                color=pal.primary if pal is not None else '#1565C0',
                size=18))
            act.triggered.connect(lambda checked=False, k=key: self._set_theme(k))
            theme_menu.addAction(act)
        self._theme_btn.setMenu(theme_menu)
        h.addWidget(self._theme_btn)

        # Bouton profil — initiales + menu compte (comme LarcSuperviseur/LarcSecretaire)
        initials = "".join(w[0].upper() for w in (session.full_name or '').split() if w)[:2] or '?'
        profile_btn = QPushButton(initials)
        profile_btn.setFixedSize(ds.icon_btn_size, ds.icon_btn_size)
        profile_btn.setToolTip('Compte — préférences, mot de passe')
        profile_btn.setStyleSheet(
            f"QPushButton {{ background: {theme_manager.theme.palette.on_primary}; "
            f"color: {theme_manager.theme.palette.primary}; border: none; "
            f"border-radius: {ds.icon_btn_size // 2}px; font-weight: bold; "
            f"font-size: {theme_manager.font_size(12)}px; }}"
            f"QPushButton:hover {{ background: rgba(255,255,255,0.85); }}"
        )
        profile_menu = QMenu(self)
        profile_menu.addAction('Préférences…', self._on_preferences)
        profile_menu.addAction('Changer le mot de passe…', self._on_change_password)
        profile_menu.addSeparator()
        profile_menu.addAction('Déconnexion', self.close)
        profile_btn.setMenu(profile_menu)
        h.addWidget(profile_btn)

        return header

    _THEME_ICONS = {"blue": "light_mode", "dark": "dark_mode",
                    "sobre": "tonality", "contrast": "bolt"}

    def _theme_icon(self) -> QIcon:
        """Icône MD3 du thème actif, dans la couleur du header (comme LarcSuperviseur)."""
        name = self._THEME_ICONS.get(theme_manager.active_name, 'light_mode')
        return md3_icon(name, color=theme_manager.theme.palette.on_primary, size=20)

    def _set_theme(self, name: str):
        theme_manager.set_active(name)
        self.setStyleSheet(self._STYLE)
        if hasattr(self, '_theme_btn'):
            self._theme_btn.setIcon(self._theme_icon())
        self.statusBar().showMessage(f'Thème : {theme_manager.theme.label}')

    @safe_slot("MainWindow._on_preferences")
    def _on_preferences(self) -> None:
        """Préférences (langue, thème, vignettes) — comme LarcSuperviseur."""
        from larccommon.preferences_dialog import PreferencesDialog
        old_theme = theme_manager.active_name
        dlg = PreferencesDialog(self)
        if dlg.exec():
            if theme_manager.active_name != old_theme:
                self._set_theme(theme_manager.active_name)

    @safe_slot("MainWindow._on_change_password")
    def _on_change_password(self) -> None:
        """Dialogue de changement de mot de passe — comme LarcSuperviseur."""
        from larccommon.password_dialog import ChangePasswordDialog
        dlg = ChangePasswordDialog(self)
        dlg.exec()

    def _build_sidebar(self) -> QWidget:
        """Sidebar verticale 260 px : matière-classe | formatives | sommatives | jugements."""
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(ds.space_xs)

        # Les 4 frames du sidebar, pour re-style au changement de thème
        self._side_frames: dict[str, QFrame] = {}

        # Section 1 : Matière-Classe
        self._side_frames['matiere'] = self._build_matiere_section()
        v.addWidget(self._side_frames['matiere'], 0)

        # Section 2 : Formatives
        f_panel = self._build_eval_section('F')
        self._fwidgets = f_panel['widgets']
        self._side_frames['F'] = f_panel['frame']
        v.addWidget(f_panel['frame'], 1)

        # Section 3 : Sommatives
        s_panel = self._build_eval_section('S')
        self._swidgets = s_panel['widgets']
        self._side_frames['S'] = s_panel['frame']
        v.addWidget(s_panel['frame'], 1)

        # Section 4 : Jugements
        j_panel = self._build_jugements_section()
        self._jwidgets = j_panel['widgets']
        self._side_frames['jugements'] = j_panel['frame']
        v.addWidget(j_panel['frame'], 0)

        return container

    @staticmethod
    def _panel_qss(section: str) -> str:
        """QSS d'un panneau sidebar : fond gris clair neutre + cadre gris épais,
        la couleur de zone (bleu ciel / bleu marine) ne porte que sur la
        ligne de titre (voir title_frame dans _build_eval_section)."""
        return (f"QFrame#panel_{section} {{ background: {ZONE_NEUTRAL}; "
                f"border: 2px solid {ZONE_BORDER}; "
                f"border-radius: {ds.radius_sm}px; }}")

    @staticmethod
    def _btn_zone_style() -> str:
        """Boutons d'action du sidebar (Pondération, Gérer) :
        gris foncé, texte blanc bold."""
        return (
            f"QPushButton {{ background: {ZONE_BTN_BG}; color: {ZONE_TEXT_LIGHT}; "
            f"border: none; border-radius: {ds.radius_xs}px; font-weight: bold; "
            f"padding: {ds.space_xxs // 2}px {ds.space_xs}px; }}"
            f"QPushButton:hover {{ background: {ZONE_BTN_BG}; }}"
        )

    def _build_matiere_section(self) -> QFrame:
        """Section 1 : combo matière-classe + bouton Pondération."""
        f = QFrame()
        f.setProperty('class', 'panel')
        f.setFrameShape(QFrame.StyledPanel)
        # Zone 1 « Matière-Classe » : fond bleu clair + bordure primary
        f.setObjectName('panel_matiere')
        f.setStyleSheet(self._panel_qss('matiere'))
        v = QVBoxLayout(f)
        v.setContentsMargins(ds.space_xs, ds.space_xxs, ds.space_xs, ds.space_xxs)
        v.setSpacing(ds.space_xs)   # distance entre boutons = 8

        lbl = QLabel('Matière - Classe')
        lbl.setFont(theme_manager.font(theme_manager.theme.fonts.small, QFont.Bold))
        lbl.setStyleSheet(f'color: {theme_manager.theme.palette.text_strong};')
        v.addWidget(lbl)

        self._items_combo = QComboBox()
        self._items_combo.setPlaceholderText('Choisir matière - classe')
        self._items_combo.setFont(theme_manager.font(theme_manager.theme.fonts.small))
        self._items_combo.currentIndexChanged.connect(self._on_item_selected)
        v.addWidget(self._items_combo)

        # "Autre Matière-Classe" (Projet Personnel, TDC, CAS, Mémoire…)
        # TODO: implémenter l'édition des notes pour larcauth_learner_has_termothersubject
        self._lbl_other = QLabel('Autre Matière - Classe')
        self._lbl_other.setFont(theme_manager.font(theme_manager.theme.fonts.small, QFont.Bold))
        self._lbl_other.setStyleSheet(f'color: {theme_manager.theme.palette.text_strong};')
        self._lbl_other.setVisible(False)  # masqué tant que non implémenté
        v.addWidget(self._lbl_other)

        self._items_other_combo = QComboBox()
        self._items_other_combo.setPlaceholderText('Choisir autre matière - classe')
        self._items_other_combo.setFont(theme_manager.font(theme_manager.theme.fonts.small))
        self._items_other_combo.setStyleSheet(
            f"background: {theme_manager.theme.palette.primary_container};"
        )
        self._items_other_combo.currentIndexChanged.connect(self._on_other_item_selected)
        self._items_other_combo.setVisible(False)  # masqué tant que non implémenté
        v.addWidget(self._items_other_combo)

        v.addSpacing(ds.space_xxs)

        # Bouton Mode de calcul — gris foncé, texte blanc bold (cohérence sidebar)
        self._weight_btn = QPushButton('Mode de calcul')
        self._weight_btn.setFixedHeight(ds.field_height)   # Fibonacci LG = 32 (was 29)
        self._weight_btn.setFont(theme_manager.font(theme_manager.theme.fonts.small, QFont.Bold))
        self._weight_btn.setStyleSheet(self._btn_zone_style())
        self._weight_btn.clicked.connect(self._on_weight)
        v.addWidget(self._weight_btn)

        v.addStretch()
        return f

    @staticmethod
    def _btn_crit_style(checked: bool) -> str:
        return theme_manager.btn_crit_style(checked)

    def _build_eval_section(self, eval_type: str) -> dict:
        """Construit une section formatives (F) ou sommatives (S) du top bar."""
        is_f = eval_type == 'F'
        f = QFrame()
        f.setProperty('class', 'panel')
        f.setFrameShape(QFrame.StyledPanel)
        f.setObjectName(f'panel_{eval_type}')
        # Formatives : panneau blanc — Sommatives : panneau gris foncé
        f.setStyleSheet(self._panel_qss(eval_type))
        v = QVBoxLayout(f)
        v.setContentsMargins(ds.space_xs, ds.space_xxs, ds.space_xs, ds.space_xxs)
        v.setSpacing(ds.space_xs)   # distance entre boutons = 8

        # Ligne de titre dans la couleur de la zone (F → bleu ciel, S → bleu marine) ;
        # le reste du panneau reste neutre (gris très clair)
        title_frame = QFrame()
        title_frame.setObjectName(f'title_{eval_type}')
        title_frame.setAttribute(Qt.WA_StyledBackground, True)
        title_color = ZONE_F_COLOR if is_f else ZONE_S_COLOR
        title_frame.setStyleSheet(
            f"QFrame#title_{eval_type} {{ background: {title_color}; "
            f"border-radius: {ds.radius_xs}px; }}"
        )
        title_row = QHBoxLayout(title_frame)
        title_row.setContentsMargins(ds.space_xs, ds.space_xxs, ds.space_xs, ds.space_xxs)
        lbl = QLabel('Formatives' if is_f else 'Sommatives')
        lbl.setFont(theme_manager.font(theme_manager.theme.fonts.small, QFont.Bold))
        # Texte blanc sur ligne de titre colorée
        lbl.setStyleSheet(f'color: {ZONE_TEXT_LIGHT};')
        title_row.addWidget(lbl)
        title_row.addStretch()
        gerer_btn = QPushButton('Gérer')
        gerer_btn.setFixedHeight(ds.field_height)   # Fibonacci LG = 32 (was table_row_min 21)
        gerer_btn.setFont(theme_manager.font(theme_manager.theme.fonts.small, QFont.Bold))
        gerer_btn.setStyleSheet(self._btn_zone_style())
        if is_f:
            gerer_btn.clicked.connect(self._open_manager_f)
        else:
            gerer_btn.clicked.connect(self._open_manager_s)
        title_row.addWidget(gerer_btn)
        v.addWidget(title_frame)

        # Zone scrollable des slots actifs
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }}")

        scroll_content = QWidget()
        scroll_content.setAttribute(Qt.WA_StyledBackground, True)
        scroll_content.setStyleSheet("background: transparent;")

        slot_layout = QVBoxLayout(scroll_content)
        slot_layout.setContentsMargins(0, 0, 0, 0)
        slot_layout.setSpacing(ds.space_xs)   # distance entre boutons = 8

        scroll.setWidget(scroll_content)
        v.addWidget(scroll, 1)

        # Boutons Toute / Aucune / Commentaire
        btn_row = QHBoxLayout()
        btn_row.setSpacing(ds.space_xs)   # distance entre boutons = 8
        tout_btn = QPushButton('Toute')
        tout_btn.setCheckable(True)
        tout_btn.setFixedHeight(ds.field_height)   # Fibonacci LG = 32 (was table_row_min 21)
        tout_btn.setFont(theme_manager.font(theme_manager.theme.fonts.small))
        tout_btn.setStyleSheet(self._btn_toggle_style(False))
        tout_btn.clicked.connect(partial(self._on_toggle_all, eval_type))
        btn_row.addWidget(tout_btn)

        aucune_btn = QPushButton('Aucune')
        aucune_btn.setCheckable(True)
        aucune_btn.setFixedHeight(ds.field_height)   # Fibonacci LG = 32 (was table_row_min 21)
        aucune_btn.setFont(theme_manager.font(theme_manager.theme.fonts.small))
        aucune_btn.setStyleSheet(self._btn_toggle_style(False))
        aucune_btn.clicked.connect(partial(self._on_toggle_none, eval_type))
        btn_row.addWidget(aucune_btn)

        comm_btn = QPushButton('Commentaire')
        comm_btn.setCheckable(True)
        comm_btn.setFixedHeight(ds.field_height)   # Fibonacci LG = 32 (was table_row_min 21)
        comm_btn.setFont(theme_manager.font(theme_manager.theme.fonts.small))
        comm_btn.setStyleSheet(self._btn_toggle_style(False))
        comm_btn.clicked.connect(partial(self._on_toggle_comment, eval_type))
        btn_row.addWidget(comm_btn)

        v.addLayout(btn_row)

        return {
            'frame': f,
            'widgets': {
                'title_lbl': lbl,
                'scroll_content': scroll_content,
                'tout_btn': tout_btn,
                'aucune_btn': aucune_btn,
                'comm_btn': comm_btn,
                'slot_rows': {},  # index -> QFrame
            }
        }

    def _build_jugements_section(self) -> dict:
        """Section 4 : 3 boutons + légende critères."""
        f = QFrame()
        f.setProperty('class', 'panel')
        f.setFrameShape(QFrame.StyledPanel)
        # Zone 4 « Jugements » : fond rose pâle + bordure tertiary
        f.setObjectName('panel_jugements')
        f.setStyleSheet(self._panel_qss('jugements'))
        v = QVBoxLayout(f)
        v.setContentsMargins(ds.space_xs, ds.space_xxs, ds.space_xs, ds.space_xxs)
        v.setSpacing(ds.space_xs)   # distance entre boutons = 8

        lbl = QLabel('Affichage colonnes')
        lbl.setFont(theme_manager.font(theme_manager.theme.fonts.small, QFont.Bold))
        lbl.setStyleSheet(f'color: {theme_manager.theme.palette.text_strong};')
        v.addWidget(lbl)

        # Deux colonnes pour gagner de la place :
        # gauche = boutons d'affichage (Jugement, Note sur 7, Commentaire),
        # droite = critères A-D
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(ds.space_xs)   # distance entre boutons = 8
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        jgt_btn = QPushButton('Jugement')
        jgt_btn.setCheckable(True)
        jgt_btn.setChecked(False)
        jgt_btn.setFixedHeight(ds.field_height)   # Fibonacci LG = 32 (was table_row_min 21)
        jgt_btn.setFont(theme_manager.font(theme_manager.theme.fonts.small))
        jgt_btn.setStyleSheet(self._btn_toggle_style(False))
        jgt_btn.clicked.connect(self._on_jgt_toggle)
        grid.addWidget(jgt_btn, 0, 0)

        note_btn = QPushButton('Note sur 7')
        note_btn.setCheckable(True)
        note_btn.setChecked(False)
        note_btn.setFixedHeight(ds.field_height)   # Fibonacci LG = 32 (was table_row_min 21)
        note_btn.setFont(theme_manager.font(theme_manager.theme.fonts.small))
        note_btn.setStyleSheet(self._btn_toggle_style(False))
        note_btn.clicked.connect(self._on_jgt_note_toggle)
        grid.addWidget(note_btn, 1, 0)

        comm_btn = QPushButton('Commentaire')
        comm_btn.setCheckable(True)
        comm_btn.setFixedHeight(ds.field_height)   # Fibonacci LG = 32 (was table_row_min 21)
        comm_btn.setFont(theme_manager.font(theme_manager.theme.fonts.small))
        comm_btn.setStyleSheet(self._btn_toggle_style(False))
        comm_btn.clicked.connect(self._on_jgt_comment_toggle)
        grid.addWidget(comm_btn, 2, 0)

        self._crit_btns = {}
        for i, letter in enumerate(('a', 'b', 'c', 'd')):
            btn = QPushButton(f'Critère {letter.upper()}')
            btn.setCheckable(True)
            btn.setChecked(self._visible_crits[letter])
            btn.setFixedHeight(ds.field_height)   # Fibonacci LG = 32 (was table_row_min 21)
            btn.setFont(theme_manager.font(theme_manager.theme.fonts.small))
            btn.setStyleSheet(self._btn_crit_style(True))
            btn.clicked.connect(partial(self._on_toggle_crit, letter))
            grid.addWidget(btn, i, 1)
            self._crit_btns[letter] = btn

        v.addLayout(grid)

        v.addStretch()
        return {
            'frame': f,
            'widgets': {
                'jgt_btn': jgt_btn,
                'note_btn': note_btn,
                'comm_btn': comm_btn,
            }
        }

    def _btn_toggle_style(self, checked: bool, dark: bool = False) -> str:
        if dark:
            return theme_manager.btn_toggle_style_dark(checked, height=22)
        return theme_manager.btn_toggle_style(checked, height=22)

    def _build_students_grid(self) -> QWidget:
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Grille unique — colonne 0 = élève, colonnes 1..N = notes
        self._grille = ClipboardTable()
        self._grille.setSelectionBehavior(QTableWidget.SelectItems)
        self._grille.setSelectionMode(QTableWidget.ContiguousSelection)
        self._grille.setEditTriggers(
            QTableWidget.SelectedClicked | QTableWidget.EditKeyPressed | QTableWidget.AnyKeyPressed
        )
        self._grille.setSortingEnabled(True)
        self._grille.verticalHeader().setVisible(False)
        # Entêtes à fond par zone : ZoneHeaderView repeint les sections dans
        # son paintEvent (le BackgroundRole des items et un delegate sont
        # ignorés par QHeaderView — seul le paintEvent du widget est fiable).
        # La hauteur fixe remplace le padding du QSS retiré.
        zone_hdr = ZoneHeaderView(Qt.Horizontal, self._grille)
        zone_hdr.setFixedHeight(ds.field_height)
        self._grille.setHorizontalHeader(zone_hdr)
        zone_hdr.sectionClicked.connect(self._on_header_section_clicked)
        # Tri par clic header : Qt deplace les items mais laisse les
        # QCheckBox « Valide » en place — recaler les cases sur les lignes.
        zone_hdr.sortIndicatorChanged.connect(self._resync_validated_widgets)
        self._grille.setItemDelegate(ColorDelegate())

        self._grille.cellChanged.connect(self._on_cell_changed)
        self._grille.cellDoubleClicked.connect(self._on_cell_double_clicked)

        h.addWidget(self._grille, 1)

        return container

    def _build_actions_bar(self) -> QWidget:
        bar = QFrame()
        h = QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 0, 0)
        h.addStretch(1)
        # Enregistrer : sauvegarde SQLite locale uniquement — jamais de sync.
        # La synchronisation reste un geste explicite du dashboard.
        self._save_btn = QPushButton('Enregistrer')
        self._save_btn.setToolTip('Enregistre les modifications en local (SQLite)')
        self._save_btn.clicked.connect(self._on_save_only)
        self._cancel_btn = QPushButton('Annuler')
        self._cancel_btn.setToolTip('Abandonne les modifications non enregistrees et revient au dashboard')
        self._cancel_btn.clicked.connect(self._on_cancel)
        h.addWidget(self._save_btn)
        h.addWidget(self._cancel_btn)
        return bar

    def _confirm_leave(self) -> bool:
        """Interdit de sortir tant qu'il reste des modifications non enregistrees."""
        if not self._dirty_cells:
            return True
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(
            self, 'Modifications non enregistrees',
            'Il reste des modifications non enregistrees.\n'
            'Cliquez « Enregistrer » pour les sauvegarder,\n'
            'ou « Annuler » pour les abandonner.')
        return False

    def closeEvent(self, event):
        """Garde : pas de sortie sans avoir enregistré ou annulé."""
        if not self._confirm_leave():
            event.ignore()
            return
        super().closeEvent(event)
