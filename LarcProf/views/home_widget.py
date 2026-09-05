"""HomeWidget — Tableau de bord enseignant embarquable (QWidget).

Version allégée de HomeWindow pour intégration dans LarcHub.
Émet navigation_requested au lieu de créer une fenêtre séparée.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from common.database import db, DBMode
from common.session import session
from common.theme import theme_manager
from common.sync import sync as sync_manager
from common.sqlite_init import BUSINESS_TABLES
from common.logger import log
from larccommon.design_system import ds
from larccommon.safe_slot import safe_slot
from larccommon.l10n import _

_STAT_TABLE_LABELS = {
    'larcauth_evaluation': 'Evaluations',
    'larcauth_learnerpei_has_termsubjectpei': 'Notes PEI',
    'larcauth_learnerdp_has_termsubjectdp': 'Notes DP',
    'larcauth_classroom_termothersubject': 'Autres matieres',
    'larcauth_learner_has_termothersubject': 'Notes autres',
    'student_event': 'Evenements',
}

_PEI_BUTTONS = [
    ('pei_grp_matieres', "Unite de groupes\nde matieres"),
    ('pei_interdisc', "Unites\ninterdisciplinaires"),
    ('pei_pp', "Projet Personnel"),
]

_DP_BUTTONS = [
    ('dp_grp_matieres', "Unite de groupes\nde matieres"),
    ('dp_tdc', "TDC"),
    ('dp_cas', "CAS"),
    ('dp_memoire', "Memoire"),
]

_BTN_VIEW = {
    'pei_grp_matieres': 'college_notes_0',
    'pei_interdisc': 'college_notes_opt1',
    'pei_pp': 'college_notes_opt2',
    'pei_mes_classes': 'colleges_eleves',
    'dp_grp_matieres': 'lycee_notes_0',
    'dp_memoire': 'lycee_notes_opt1',
    'dp_tdc': 'lycee_notes_opt2',
    'dp_cas': 'lycee_notes_opt3',
    'dp_mes_classes': 'lycee_eleves',
    'pei_prof_principal': 'college_bulletin',
    'dp_prof_principal': 'lycee_bulletin',
}


class HomeWidget(QWidget):
    """Tableau de bord enseignant comme QWidget (intégrable dans LarcHub).

    Signaux :
        navigation_requested(str): émis quand le prof clique sur un bouton programme
        status_message(str): émis pour les messages de statut
    """

    navigation_requested = Signal(str)
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pgm_buttons: dict[str, QPushButton] = {}
        self._pgm_sections: dict[str, QWidget] = {}
        self._sync_labels: dict[str, QLabel] = {}

        self._setup_ui()
        self._load_data()
        ds.theme_changed.connect(self._restyle)

    # ------------------------------------------------------------------
    # Style
    # ------------------------------------------------------------------
    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        s = theme_manager.font_size
        return f"""
            QWidget#hw_root {{ background: {p.background}; color: {p.text_strong}; }}
            QFrame#header {{ background: {p.primary}; color: {p.on_primary}; border-radius: {ds.radius_sm}px; }}
            QFrame#header QLabel {{ color: {p.on_primary}; }}
            QFrame#profile_card {{
                background: {p.surface}; color: {p.text_strong};
                border: 1px solid {p.outline_variant}; border-radius: {ds.radius_md}px;
            }}
            QLabel#profile_name {{
                font-size: {s(16)}px; font-weight: bold; color: {p.text_strong};
            }}
            QLabel#profile_role {{ font-size: {s(13)}px; color: {p.primary}; font-weight: bold; }}
            QLabel#profile_meta {{ font-size: {s(12)}px; color: {p.text_soft}; }}
            QFrame#sync_card {{
                background: {p.surface}; color: {p.text_strong};
                border: 1px solid {p.outline_variant}; border-radius: {ds.radius_md}px;
            }}
            QPushButton#sync_btn {{
                background: {p.success}; color: white; border: none;
                border-radius: {ds.radius_lg}px; font-size: {s(14)}px; font-weight: bold;
                padding: {ds.space_xs}px {ds.space_md}px; min-height: {ds.field_height + ds.space_xs}px;
            }}
            QPushButton#sync_btn:hover {{ background: {p.success}; }}
            QFrame#pgm_card {{
                background: {p.surface}; color: {p.text_strong};
                border: 1px solid {p.outline_variant}; border-radius: {ds.radius_md}px;
            }}
            QLabel#pgm_title {{ font-size: {s(14)}px; font-weight: bold; color: {p.primary}; }}
            QPushButton.pgm_btn {{
                background: {p.primary_container}; color: {p.primary};
                border: 1px solid {p.primary}; border-radius: {ds.radius_lg}px;
                font-size: {s(12)}px; font-weight: bold; padding: {ds.space_xs}px {ds.space_sm}px;
                min-height: {ds.space_lg + ds.space_xs}px;
            }}
            QPushButton.pgm_btn:hover {{ background: {p.primary}; color: {p.on_primary}; }}
            QPushButton#pp_btn {{
                background: {p.secondary}; color: white; border: none;
                border-radius: {ds.radius_lg}px; font-size: {s(13)}px; font-weight: bold;
                padding: {ds.space_xs}px {ds.space_md}px; min-height: {ds.button_height}px;
            }}
            QPushButton#pp_btn:hover {{ background: {p.secondary}; }}
            QFrame#sep {{ border: none; border-top: 1px solid {p.outline_variant}; }}
        """

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        self.setObjectName('hw_root')
        self.setStyleSheet(self._STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        outer.setSpacing(ds.space_md)

        outer.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(ds.space_md)

        left = QVBoxLayout()
        left.setSpacing(ds.space_md)
        left.addWidget(self._build_profile_card(), 4)
        left.addWidget(self._build_sync_card(), 5)
        body.addLayout(left, 4)

        right = QVBoxLayout()
        right.setSpacing(ds.space_md)
        right.addWidget(self._build_pgm_area(), 1)
        body.addLayout(right, 6)

        outer.addLayout(body, 1)

        # Status label (remplace la statusbar)
        self._status_label = QLabel('Prêt')
        self._status_label.setStyleSheet(
            f"font-size: {theme_manager.font_size(11)}px; color: {theme_manager.palette.text_strong}; "
            f"padding: {ds.space_xs}px {ds.space_md}px;"
        )
        outer.addWidget(self._status_label)

    def _build_header(self) -> QWidget:
        p = theme_manager.palette
        s = theme_manager.font_size

        header = QFrame()
        header.setObjectName('header')
        header.setFixedHeight(ds.header_height)

        h = QHBoxLayout(header)
        h.setContentsMargins(ds.space_md, ds.space_xs, ds.space_md, ds.space_xs)
        h.setSpacing(ds.space_md)

        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'img', 'logoAEC.png')
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path)
            logo = QLabel()
            logo.setPixmap(pix.scaledToHeight(ds.header_height - ds.space_xs * 2, Qt.SmoothTransformation))
            logo.setFixedHeight(ds.header_height - ds.space_xs * 2)
            h.addWidget(logo)

        title_col = QVBoxLayout()
        title_col.setSpacing(ds.space_xxs)
        self._hdr_title = QLabel()
        self._hdr_title.setFont(QFont('Segoe UI', theme_manager.font_size(16), QFont.Bold))
        self._hdr_title.setStyleSheet(f'color: {p.on_primary}; border: none;')
        title_col.addWidget(self._hdr_title)

        self._hdr_mode = QLabel()
        self._hdr_mode.setFont(QFont('Segoe UI', theme_manager.font_size(12)))
        self._hdr_mode.setStyleSheet(f'color: {p.on_primary}; border: none;')
        title_col.addWidget(self._hdr_mode)

        h.addLayout(title_col)
        h.addStretch(1)
        return header

    def _build_profile_card(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName('profile_card')
        panel.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_xs)

        self._lbl_name = QLabel()
        self._lbl_name.setObjectName('profile_name')
        self._lbl_name.setWordWrap(True)
        layout.addWidget(self._lbl_name)

        self._lbl_role = QLabel()
        self._lbl_role.setObjectName('profile_role')
        layout.addWidget(self._lbl_role)

        self._lbl_email = QLabel()
        self._lbl_email.setObjectName('profile_meta')
        self._lbl_email.setWordWrap(True)
        layout.addWidget(self._lbl_email)

        sep = QFrame()
        sep.setObjectName('sep')
        sep.setFixedHeight(ds.border_width)
        layout.addWidget(sep)

        self._lbl_year = QLabel()
        self._lbl_year.setObjectName('profile_meta')
        layout.addWidget(self._lbl_year)

        self._lbl_term = QLabel()
        self._lbl_term.setObjectName('profile_meta')
        layout.addWidget(self._lbl_term)

        self._lbl_classes_count = QLabel()
        self._lbl_classes_count.setObjectName('profile_meta')
        layout.addWidget(self._lbl_classes_count)

        self._lbl_students_count = QLabel()
        self._lbl_students_count.setObjectName('profile_meta')
        layout.addWidget(self._lbl_students_count)

        layout.addSpacing(ds.space_xs)

        conn_layout = QHBoxLayout()
        conn_layout.setSpacing(ds.space_md)
        self._lbl_intranet = QLabel()
        self._lbl_intranet.setStyleSheet(f"font-size: {theme_manager.font_size(11)}px;")
        conn_layout.addWidget(self._lbl_intranet)
        self._lbl_cloud = QLabel()
        self._lbl_cloud.setStyleSheet(f"font-size: {theme_manager.font_size(11)}px;")
        conn_layout.addWidget(self._lbl_cloud)
        conn_layout.addStretch(1)
        layout.addLayout(conn_layout)

        return panel

    def _build_sync_card(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName('sync_card')
        panel.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        layout.setSpacing(ds.space_xs)

        title = QLabel("Synchronisation")
        title.setStyleSheet(
            f"font-size: {theme_manager.font_size(16)}px; font-weight: bold; "
            f"color: {theme_manager.palette.text_strong};"
        )
        layout.addWidget(title)

        self._lbl_sync_date = QLabel()
        self._lbl_sync_date.setStyleSheet(
            f"font-size: {theme_manager.font_size(12)}px; color: {theme_manager.palette.text_strong};"
        )
        layout.addWidget(self._lbl_sync_date)

        self._lbl_sync_count = QLabel()
        self._lbl_sync_count.setStyleSheet(
            f"font-size: {theme_manager.font_size(36)}px; font-weight: bold; color: {theme_manager.palette.primary};"
        )
        layout.addWidget(self._lbl_sync_count)

        self._lbl_sync_detail = QLabel()
        self._lbl_sync_detail.setStyleSheet(
            f"font-size: {theme_manager.font_size(11)}px; color: {theme_manager.palette.error}; font-weight: bold;"
        )
        layout.addWidget(self._lbl_sync_detail)

        btn = QPushButton("Synchroniser")
        btn.setObjectName("sync_btn")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self._do_sync)
        layout.addWidget(btn)

        layout.addStretch()
        return panel

    def _build_pgm_area(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName('pgm_card')

        outer = QVBoxLayout(panel)
        outer.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        outer.setSpacing(ds.space_md)

        title = QLabel("Programmes")
        title.setObjectName('pgm_title')
        outer.addWidget(title)

        self._pgm_grid = QHBoxLayout()
        outer.addLayout(self._pgm_grid)

        # PEI Section
        pei_card = self._build_pgm_section("PEI", _PEI_BUTTONS)
        self._pgm_sections['PEI'] = pei_card
        self._pgm_grid.addWidget(pei_card, 1)

        # DP Section
        dp_card = self._build_pgm_section("DP", _DP_BUTTONS)
        self._pgm_sections['DP'] = dp_card
        self._pgm_grid.addWidget(dp_card, 1)

        outer.addSpacing(ds.space_xs)

        # Bouton Professeur principal
        self._btn_prof_principal = QPushButton("Professeur principal")
        self._btn_prof_principal.setObjectName("pp_btn")
        self._btn_prof_principal.setCursor(Qt.PointingHandCursor)
        self._btn_prof_principal.clicked.connect(self._open_pp)
        self._btn_prof_principal.setVisible(False)
        outer.addWidget(self._btn_prof_principal)

        return panel

    def _build_pgm_section(self, name: str, buttons: list) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.space_xs)

        # Section title
        lbl = QLabel(name)
        lbl.setStyleSheet(
            f"font-size: {theme_manager.font_size(13)}px; font-weight: bold; "
            f"color: {theme_manager.palette.text_strong}; padding-bottom: {ds.space_xxs}px;"
        )
        layout.addWidget(lbl)

        # Program buttons
        for key, label_text in buttons:
            btn = QPushButton(label_text)
            btn.setProperty('class', 'pgm_btn')
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(self._on_pgm_btn_clicked(key))
            self._pgm_buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch()
        return panel

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def _load_data(self) -> None:
        self._load_profile()
        self._load_sync()
        self._detect_and_apply()

    def _load_profile(self) -> None:
        self._hdr_title.setText(session.full_name or session.email or "Enseignant")
        mode_labels = {
            DBMode.INTRANET: "Connecte (Intranet)",
            DBMode.CLOUD: "Connecte (Cloud)",
            DBMode.SQLITE: "Mode hors connexion",
            DBMode.NONE: "Non connecte",
        }
        self._hdr_mode.setText(mode_labels.get(db.mode, "Non connecte"))

        self._lbl_name.setText(session.full_name or "—")
        self._lbl_role.setText(session.role_display if hasattr(session, 'role_display') else session.role.value)
        self._lbl_email.setText(session.email or "")

        # Annee et trimestre depuis SQLite
        conn = db.local_conn
        if conn:
            try:
                row = conn.execute("SELECT annee_scolaire, trimestre_courant FROM module_config LIMIT 1").fetchone()
                if row:
                    self._lbl_year.setText(f"Annee : {row[0]}")
                    self._lbl_term.setText(f"Trimestre : {row[1]}")
            except Exception:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                self._lbl_year.setText(f"Annee : {session.term_id or '—'}")
                self._lbl_term.setText("")

        # Compteurs classes / eleves
        if conn:
            try:
                n_classes = conn.execute(
                    "SELECT COUNT(DISTINCT fk_classroom_id) FROM larcauth_classroom_termsubject "
                    "WHERE fk_supervisor_id = ? AND (enabled = 1 OR enabled = 'true')",
                    (session.user_id,)
                ).fetchone()[0]
                self._lbl_classes_count.setText(f"Classes : {n_classes}")
            except Exception:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                self._lbl_classes_count.setText("Classes : —")

            try:
                n_students = conn.execute(
                    "SELECT COUNT(DISTINCT lp.fk_student_id) "
                    "FROM larcauth_learnerpei_has_termsubjectpei lp "
                    "JOIN larcauth_classroom_termsubject cts ON lp.fk_classroom_termsubject_ptr_id = cts.id "
                    "WHERE cts.fk_supervisor_id = ?",
                    (session.user_id,)
                ).fetchone()[0]
                self._lbl_students_count.setText(f"Eleves : {n_students}")
            except Exception:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                self._lbl_students_count.setText("Eleves : —")

        # Indicateurs connexion
        intra_ok = db._intranet is not None
        cloud_ok = db._cloud is not None
        self._lbl_intranet.setText(f"Intranet : {'●' if intra_ok else '○'}")
        self._lbl_intranet.setStyleSheet(
            f"font-size: {theme_manager.font_size(11)}px; "
            f"color: {theme_manager.palette.success if intra_ok else theme_manager.palette.text_soft};"
        )
        self._lbl_cloud.setText(f"Cloud : {'●' if cloud_ok else '○'}")
        self._lbl_cloud.setStyleSheet(
            f"font-size: {theme_manager.font_size(11)}px; "
            f"color: {theme_manager.palette.success if cloud_ok else theme_manager.palette.text_soft};"
        )

    def _load_sync(self) -> None:
        conn = db.local_conn
        if conn is None:
            self._lbl_sync_date.setText("Base locale non disponible")
            self._lbl_sync_count.setText("—")
            return

        try:
            row = conn.execute(
                "SELECT table_name, last_sync, last_source FROM sync_state ORDER BY last_sync DESC LIMIT 1"
            ).fetchone()
            if row and row[1]:
                self._lbl_sync_date.setText(f"Derniere synchronisation : {row[1]} ({row[2] or 'inconnu'})")
            else:
                self._lbl_sync_date.setText("Jamais synchronise")
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self._lbl_sync_date.setText("—")

        # Compteur de modifications non synchronisees
        dirty = 0
        detail_parts = []
        for table in BUSINESS_TABLES:
            try:
                ref_table = f"{table}_ref"
                # Vérifier que les deux tables existent
                conn.execute(f"SELECT 1 FROM {table} LIMIT 0")
                conn.execute(f"SELECT 1 FROM {ref_table} LIMIT 0")
                cur = conn.execute(
                    f"SELECT COUNT(*) FROM {table} t "
                    f"INNER JOIN {ref_table} r ON t.id = r.id "
                    f"WHERE t.sync_version != r.sync_version"
                )
                c = cur.fetchone()[0]
                if c > 0:
                    dirty += c
                    label = _STAT_TABLE_LABELS.get(table, table)
                    detail_parts.append(f"{label}: {c}")
            except Exception as e:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                log(f"Statistiques de synchronisation incomplètes : {e}")

        self._lbl_sync_count.setText(str(dirty) if dirty > 0 else "0")
        self._lbl_sync_detail.setText(" | ".join(detail_parts[:3]) if detail_parts else "")

    def _detect_and_apply(self) -> None:
        detected = self._detect_programs()
        for pgm_key, section in self._pgm_sections.items():
            section.setVisible(detected.get(pgm_key, False))
        for btn_key, btn in self._pgm_buttons.items():
            pgm = 'PEI' if btn_key.startswith('pei_') else 'DP' if btn_key.startswith('dp_') else ''
            if not detected.get(pgm, False):
                btn.setVisible(False)
            else:
                btn.setVisible(self._detect_button_visibility(pgm, btn_key))

        pp_visible = False
        conn = db.local_conn
        if conn is not None:
            try:
                row = conn.execute(
                    "SELECT 1 FROM larcauth_classroom WHERE fk_headteacher_id = ? LIMIT 1",
                    (session.user_id,)
                ).fetchone()
                pp_visible = row is not None
            except Exception as e:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                log(f"Vérification du rôle professeur principal impossible : {e}")
        self._btn_prof_principal.setVisible(pp_visible)

    def _detect_programs(self) -> dict[str, bool]:
        conn = db.local_conn
        if conn is None:
            return {'PEI': False, 'DP': False}
        try:
            pei = conn.execute(
                "SELECT 1 FROM larcauth_classroom c "
                "JOIN larcauth_classroom_termsubject cts ON c.id = cts.fk_classroom_id "
                "JOIN larcauth_level l ON l.id = c.fk_level_id "
                "WHERE cts.fk_supervisor_id = ? AND (cts.enabled = 1 OR cts.enabled = 'true') "
                "AND l.fk_program_id IN (12, 22) LIMIT 1",
                (session.user_id,)
            ).fetchone()
            dp = conn.execute(
                "SELECT 1 FROM larcauth_classroom c "
                "JOIN larcauth_classroom_termsubject cts ON c.id = cts.fk_classroom_id "
                "JOIN larcauth_level l ON l.id = c.fk_level_id "
                "WHERE cts.fk_supervisor_id = ? AND (cts.enabled = 1 OR cts.enabled = 'true') "
                "AND l.fk_program_id IN (13, 23) LIMIT 1",
                (session.user_id,)
            ).fetchone()
            return {'PEI': pei is not None, 'DP': dp is not None}
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return {'PEI': False, 'DP': False}

    def _detect_button_visibility(self, pgm: str, btn_key: str) -> bool:
        conn = db.local_conn
        if conn is None:
            return False
        uid = session.user_id
        try:
            tid = conn.execute("SELECT trimestre_courant FROM module_config LIMIT 1").fetchone()[0]
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return False

        try:
            if btn_key in ('pei_grp_matieres', 'dp_grp_matieres'):
                row = conn.execute(
                    "SELECT 1 FROM larcauth_classroom_termsubject cts "
                    "JOIN larcauth_classroom c ON c.id = cts.fk_classroom_id "
                    "JOIN larcauth_level l ON l.id = c.fk_level_id "
                    "WHERE cts.fk_supervisor_id = ? AND cts.fk_term_id = ? "
                    "AND (cts.enabled = 1 OR cts.enabled = 'true') "
                    "AND l.fk_program_id IN (12, 22) LIMIT 1",
                    (uid, tid)
                ).fetchone()
                return row is not None
            if btn_key == 'pei_interdisc':
                row = conn.execute(
                    "SELECT 1 FROM larcauth_classroom_termothersubject cto "
                    "JOIN larcauth_classroom c ON c.id = cto.fk_classroom_id "
                    "JOIN larcauth_level l ON l.id = c.fk_level_id "
                    "WHERE cto.fk_supervisor_id = ? AND cto.fk_term_id = ? "
                    "AND (cto.enabled = 1 OR cto.enabled = 'true') "
                    "AND l.fk_program_id IN (12, 22) "
                    "AND (cto.unit_multisubjects = 1 OR cto.unit_multisubjects = 'true') LIMIT 1",
                    (uid, tid)
                ).fetchone()
                return row is not None
            if btn_key == 'pei_pp':
                row = conn.execute(
                    "SELECT 1 FROM larcauth_classroom_termothersubject cto "
                    "JOIN larcauth_classroom c ON c.id = cto.fk_classroom_id "
                    "JOIN larcauth_level l ON l.id = c.fk_level_id "
                    "WHERE cto.fk_supervisor_id = ? AND cto.fk_term_id = ? "
                    "AND (cto.enabled = 1 OR cto.enabled = 'true') "
                    "AND l.fk_program_id IN (12, 22) "
                    "AND (cto.label LIKE 'Personal%' OR cto.label LIKE 'Projet%') LIMIT 1",
                    (uid, tid)
                ).fetchone()
                return row is not None
            if btn_key == 'pei_mes_classes':
                return db.server_conn is not None and self._detect_button_visibility(pgm, 'pei_grp_matieres')
            if btn_key == 'dp_mes_classes':
                return db.server_conn is not None and self._detect_button_visibility(pgm, 'dp_grp_matieres')
            if btn_key in ('dp_tdc', 'dp_cas', 'dp_memoire'):
                patterns = {'dp_tdc': ['Th%'], 'dp_cas': ['Cr%'], 'dp_memoire': ['Me%', 'Ext%']}.get(btn_key, [])
                clauses = ' OR '.join(['cto.label LIKE ?' for _unused in patterns])
                row = conn.execute(
                    f"SELECT 1 FROM larcauth_classroom_termothersubject cto "
                    f"WHERE cto.fk_supervisor_id = ? AND cto.fk_term_id = ? "
                    f"AND (cto.enabled = 1 OR cto.enabled = 'true') AND ({clauses}) LIMIT 1",
                    [uid, tid] + patterns
                ).fetchone()
                return row is not None
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return False
        return True

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    @safe_slot("Unknown._on_pgm_btn_clicked")
    def _on_pgm_btn_clicked(self, key: str):
        def handler():
            view = _BTN_VIEW.get(key, key)
            self.navigation_requested.emit(view)
        return handler

    @safe_slot("Unknown._open_pp")
    def _open_pp(self) -> None:
        detected = self._detect_programs()
        view = 'college_bulletin' if detected.get('PEI') else 'lycee_bulletin' if detected.get('DP') else 'prof_principal'
        self.navigation_requested.emit(view)

    @safe_slot("HomeWidget._do_sync")
    def _do_sync(self) -> None:
        self._status_label.setText('Synchronisation en cours...')
        QApplication.processEvents()
        try:
            ok, msg = sync_manager.pull_push()
            self._status_label.setText(msg or ('Sync OK' if ok else 'Echec sync'))
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self._status_label.setText(f'Erreur : {e}')
        self._load_sync()
        QTimer.singleShot(3000, lambda: self._status_label.setText('Pret'))

    @safe_slot("HomeWidget._restyle")
    def _restyle(self) -> None:
        p = theme_manager.palette
        s = theme_manager.font_size
        self.setStyleSheet(self._STYLE)
        self._status_label.setStyleSheet(
            f"font-size: {s(11)}px; color: {p.text_strong}; "
            f"padding: {ds.space_xs}px {ds.space_md}px;")
        self._hdr_title.setStyleSheet(f'color: {p.on_primary}; border: none;')
        self._hdr_mode.setStyleSheet(f'color: {p.on_primary}; border: none;')
        intra_ok = db._intranet is not None
        cloud_ok = db._cloud is not None
        self._lbl_intranet.setStyleSheet(
            f"font-size: {s(11)}px; "
            f"color: {p.success if intra_ok else p.text_soft};")
        self._lbl_cloud.setStyleSheet(
            f"font-size: {s(11)}px; "
            f"color: {p.success if cloud_ok else p.text_soft};")
        self._lbl_sync_date.setStyleSheet(
            f"font-size: {s(12)}px; color: {p.text_strong};")
        self._lbl_sync_count.setStyleSheet(
            f"font-size: {s(36)}px; font-weight: bold; color: {p.primary};")
        self._lbl_sync_detail.setStyleSheet(
            f"font-size: {s(11)}px; color: {p.error}; font-weight: bold;")
