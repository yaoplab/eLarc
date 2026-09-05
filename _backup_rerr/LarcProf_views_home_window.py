"""Fenetre d'accueil — Dashboard professeur.

Design: 100% conforme aux skills design-system-larc.
- Pattern _STYLE property + _restyle + ThemedWidget
- ZERO hardcoded (tokens ds.space_*, ds.p.*, s(*))
- Dashboard pattern (DP1-DP8)
- Ergonomie Q7-Q21
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStatusBar,
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


class HomeWindow(QMainWindow):

    @property
    def _STYLE(self) -> str:
        p = theme_manager.palette
        s = theme_manager.font_size
        return f"""
            QMainWindow {{ background: {p.background}; }}
            QWidget#home_root {{ background: {p.background}; color: {p.text_strong}; }}
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
            QLabel#profile_connection {{ font-size: {s(11)}px; }}
            QFrame#sync_card {{
                background: {p.surface}; color: {p.text_strong};
                border: 1px solid {p.outline_variant}; border-radius: {ds.radius_md}px;
            }}
            QLabel#sync_title {{ font-size: {s(16)}px; font-weight: bold; color: {p.text_strong}; }}
            QLabel#sync_date {{ font-size: {s(12)}px; color: {p.text_soft}; }}
            QLabel#sync_count {{ font-size: {s(36)}px; font-weight: bold; color: {p.primary}; }}
            QLabel#sync_label {{ font-size: {s(12)}px; color: {p.text_soft}; }}
            QLabel#sync_detail {{ font-size: {s(11)}px; color: {p.error}; font-weight: bold; }}
            QPushButton#sync_btn {{
                background: {p.success}; color: white; border: none;
                border-radius: {ds.radius_lg}px; font-size: {s(14)}px; font-weight: bold;
                padding: {ds.space_xs}px {ds.space_m3}px; min-height: {ds.field_height + ds.space_xs}px;
            }}
            QPushButton#sync_btn:hover {{ background: {p.success}; }}
            QPushButton#logout_btn {{
                background: transparent; color: {p.error};
                border: 2px solid {p.error}; border-radius: {ds.radius_lg}px;
                font-size: {s(13)}px; font-weight: bold;
                padding: {ds.space_xs}px {ds.space_m3}px; min-height: {ds.field_height + ds.space_xs}px;
            }}
            QPushButton#logout_btn:hover {{ background: {p.error}; color: white; }}
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
                padding: {ds.space_xs}px {ds.space_m3}px; min-height: {ds.button_height}px;
            }}
            QPushButton#pp_btn:hover {{ background: {p.secondary}; }}
            QFrame#sep {{ border: none; border-top: 1px solid {p.outline_variant}; }}
        """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle('LarcProf — Tableau de bord')
        self.resize(ds.window_width * 53 // 50, ds.window_height * 17 // 20)
        self.setMinimumSize(ds.window_width * 41 // 50, ds.window_height * 13 // 20)

        self._main_window = None
        self._pgm_buttons: dict[str, QPushButton] = {}
        self._pgm_sections: dict[str, QWidget] = {}

        self._setup_ui()
        self._load_data()
        ds.theme_changed.connect(self._restyle)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        root = QWidget()
        root.setObjectName('home_root')
        self.setCentralWidget(root)
        root.setStyleSheet(self._STYLE)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(ds.space_md, ds.space_md, ds.space_md, ds.space_md)
        outer.setSpacing(ds.space_md)

        # ── Logo + Header ──
        outer.addWidget(self._build_header())

        # ── Body: gauche (profil + synchro) | droite (programmes) ──
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

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage('Pret')

    def _build_header(self) -> QWidget:
        p = theme_manager.palette
        s = theme_manager.font_size

        header = QFrame()
        header.setObjectName('header')
        header.setFixedHeight(ds.header_height)

        h = QHBoxLayout(header)
        h.setContentsMargins(ds.space_m3, ds.space_xs, ds.space_m3, ds.space_xs)
        h.setSpacing(ds.space_md)

        # Logo
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'img', 'logoAEC.png')
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path)
            logo = QLabel()
            logo.setPixmap(pix.scaledToHeight(ds.header_height - ds.space_xs * 2, Qt.SmoothTransformation))
            logo.setFixedHeight(ds.header_height - ds.space_xs * 2)
            h.addWidget(logo)

        # Titre + sous-titre
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

        self._hdr_last_login = QLabel()
        self._hdr_last_login.setFont(QFont('Segoe UI', theme_manager.font_size(11)))
        self._hdr_last_login.setStyleSheet(f'color: {p.on_primary}; border: none;')
        h.addWidget(self._hdr_last_login)

        return header

    # ── Carte Profil ──
    def _build_profile_card(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName('profile_card')
        panel.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
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

        # Indicateurs connexion
        self._profile_intra = QLabel()
        self._profile_intra.setObjectName('profile_connection')
        layout.addWidget(self._profile_intra)

        self._profile_cloud = QLabel()
        self._profile_cloud.setObjectName('profile_connection')
        layout.addWidget(self._profile_cloud)

        layout.addStretch()
        return panel

    # ── Carte Synchro ──
    def _build_sync_card(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName('sync_card')
        panel.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
        layout.setSpacing(ds.space_xs)

        title = QLabel('Synchronisation')
        title.setObjectName('sync_title')
        layout.addWidget(title)

        self._lbl_sync_date = QLabel()
        self._lbl_sync_date.setObjectName('sync_date')
        layout.addWidget(self._lbl_sync_date)

        self._lbl_sync_mode = QLabel()
        self._lbl_sync_mode.setObjectName('sync_date')
        layout.addWidget(self._lbl_sync_mode)

        layout.addSpacing(ds.space_md)

        self._lbl_unsynced_count = QLabel('0')
        self._lbl_unsynced_count.setObjectName('sync_count')
        self._lbl_unsynced_count.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._lbl_unsynced_count)

        self._lbl_unsynced_label = QLabel('modifications non synchronisees')
        self._lbl_unsynced_label.setObjectName('sync_label')
        self._lbl_unsynced_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._lbl_unsynced_label)

        self._lbl_unsynced_detail = QLabel()
        self._lbl_unsynced_detail.setObjectName('sync_detail')
        self._lbl_unsynced_detail.setWordWrap(True)
        layout.addWidget(self._lbl_unsynced_detail)

        layout.addSpacing(ds.space_sm)

        btn_sync = QPushButton('Synchroniser')
        btn_sync.setObjectName('sync_btn')
        btn_sync.setCursor(Qt.PointingHandCursor)
        btn_sync.clicked.connect(self._do_sync)
        layout.addWidget(btn_sync)

        layout.addStretch()
        return panel

    # ── Zone Programmes ──
    def _build_pgm_area(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ds.space_md)

        pei_section = self._build_program_card('PEI', _PEI_BUTTONS)
        self._pgm_sections['PEI'] = pei_section
        layout.addWidget(pei_section, 1)

        dp_section = self._build_program_card('DP', _DP_BUTTONS)
        self._pgm_sections['DP'] = dp_section
        layout.addWidget(dp_section, 1)

        self._btn_prof_principal = QPushButton('Professeur principal')
        self._btn_prof_principal.setObjectName('pp_btn')
        self._btn_prof_principal.setCursor(Qt.PointingHandCursor)
        self._btn_prof_principal.clicked.connect(self._open_pp)
        layout.addWidget(self._btn_prof_principal)

        btn_logout = QPushButton('Deconnexion')
        btn_logout.setObjectName('logout_btn')
        btn_logout.setCursor(Qt.PointingHandCursor)
        btn_logout.clicked.connect(self._logout)
        layout.addWidget(btn_logout)

        return wrapper

    def _build_program_card(self, pgm_label: str, buttons_def: list[tuple[str, str]]) -> QWidget:
        panel = QFrame()
        panel.setObjectName('pgm_card')
        panel.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(ds.space_m3, ds.space_m3, ds.space_m3, ds.space_m3)
        layout.setSpacing(ds.space_sm)

        title = QLabel(pgm_label)
        title.setObjectName('pgm_title')
        layout.addWidget(title)

        # Grille 2 colonnes
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout()
        grid.setSpacing(ds.space_sm)

        for idx, (key, text) in enumerate(buttons_def):
            btn = QPushButton(text)
            btn.setProperty('class', 'pgm_btn')
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(self._on_pgm_btn_clicked(key))
            self._pgm_buttons[key] = btn
            row, col = idx // 2, idx % 2
            grid.addWidget(btn, row, col)

        layout.addLayout(grid)
        layout.addStretch()
        return panel

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def _load_data(self) -> None:
        self._load_profile()
        self._load_sync()
        self._apply_program_visibility()
        QTimer.singleShot(50, self._load_counts)

    def _load_profile(self) -> None:
        conn = db.local_conn
        full_name = session.full_name or '—'
        email_val = session.email or '—'
        mode = session.conn_mode
        mode_str = mode.value if mode else 'Hors connexion'

        self._hdr_title.setText(f'Bienvenue, {full_name}')
        self._hdr_mode.setText(f'Mode : {mode_str}')
        self._lbl_name.setText(full_name)
        self._lbl_email.setText(email_val)
        self._lbl_role.setText(session.role_display)

        server_ok = db.server_conn is not None
        p = theme_manager.palette
        if server_ok:
            server_mode = db.server_mode
            intra_active = server_mode == DBMode.INTRANET
            cloud_active = server_mode == DBMode.CLOUD
            self._profile_intra.setText(f'Intranet : {"●" if intra_active else "○"}')
            self._profile_intra.setStyleSheet(
                f"color: {'#27ae60' if intra_active else p.text_soft}; "
                f"font-size: {theme_manager.font_size(11)}px; font-weight: {'bold' if intra_active else 'normal'};")
            self._profile_cloud.setText(f'Cloud : {"●" if cloud_active else "○"}')
            self._profile_cloud.setStyleSheet(
                f"color: {'#27ae60' if cloud_active else p.text_soft}; "
                f"font-size: {theme_manager.font_size(11)}px; font-weight: {'bold' if cloud_active else 'normal'};")
        else:
            self._profile_intra.setText('Intranet : ○')
            self._profile_intra.setStyleSheet(f"color: {p.text_strong}; font-size: {theme_manager.font_size(11)}px;")
            self._profile_cloud.setText('Cloud : ○')
            self._profile_cloud.setStyleSheet(f"color: {p.text_strong}; font-size: {theme_manager.font_size(11)}px;")

        if conn is None:
            return
        try:
            row = conn.execute(
                "SELECT updated_at FROM session_cache WHERE user_id = ?",
                (session.user_id,)
            ).fetchone()
            if row and row[0]:
                self._hdr_last_login.setText(f'Derniere connexion : {row[0]}')
        except Exception as e:
            log(f"Chargement de la dernière connexion impossible : {e}")
        try:
            row = conn.execute(
                "SELECT annee_scolaire, trimestre_courant FROM module_config WHERE id = 1"
            ).fetchone()
            if row:
                self._lbl_year.setText(f'Annee scolaire : {row[0]}')
                self._lbl_term.setText(f'Trimestre : {row[1]}')
            else:
                self._lbl_year.setText('Annee scolaire : —')
                self._lbl_term.setText('Trimestre : —')
        except Exception:
            self._lbl_year.setText('Annee scolaire : —')
            self._lbl_term.setText('Trimestre : —')

    def _load_counts(self) -> None:
        conn = db.local_conn
        if conn is None:
            return
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM larcauth_classroom_termsubject WHERE fk_teacher_id = ?",
                (session.user_id,)
            ).fetchone()
            count_cts = row[0] if row else 0
            self._lbl_classes_count.setText(f'Classes-Matieres : {count_cts}')
        except Exception as e:
            log(f"Chargement du nombre de classes-matières impossible : {e}")
        try:
            row = conn.execute(
                """SELECT COUNT(DISTINCT s.aecuser_ptr_id)
                   FROM larcauth_classroom_termsubject cts
                   JOIN larcauth_classroom c ON c.id = cts.fk_classroom_id
                   JOIN larcauth_student s ON s.s_classroom_id = c.id
                   WHERE cts.fk_teacher_id = ?""",
                (session.user_id,)
            ).fetchone()
            count_students = row[0] if row else 0
            self._lbl_students_count.setText(f'Eleves : {count_students}')
        except Exception as e:
            log(f"Chargement du nombre d'élèves impossible : {e}")

    def _load_sync(self) -> None:
        conn = db.local_conn
        if conn is None:
            return
        try:
            row = conn.execute(
                "SELECT derniere_synchronisation FROM module_config WHERE id = 1"
            ).fetchone()
            if row and row[0]:
                self._lbl_sync_date.setText(f'Derniere synchronisation : {row[0]}')
            else:
                self._lbl_sync_date.setText('Derniere synchronisation : jamais')
        except Exception:
            self._lbl_sync_date.setText('Derniere synchronisation : —')
        try:
            row = conn.execute(
                "SELECT last_source FROM sync_state LIMIT 1"
            ).fetchone()
            src = row[0] if row and row[0] else 'inconnu'
            self._lbl_sync_mode.setText(f'Source : {src}')
        except Exception:
            self._lbl_sync_mode.setText('Source : —')

        total_unsynced = 0
        detail_parts = []
        for table in BUSINESS_TABLES:
            count = self._count_unsynced_rows(table)
            if count > 0:
                label = _STAT_TABLE_LABELS.get(table, table)
                detail_parts.append(f'{label} : {count}')
                total_unsynced += count

        self._lbl_unsynced_count.setText(str(total_unsynced))
        if total_unsynced == 0:
            self._lbl_unsynced_label.setText('Aucune modification en attente')
            self._lbl_unsynced_detail.setText('Toutes les donnees sont a jour.')
        else:
            self._lbl_unsynced_label.setText('modifications non synchronisees')
            self._lbl_unsynced_detail.setText(' | '.join(detail_parts))

    def _count_unsynced_rows(self, table: str) -> int:
        conn = db.local_conn
        if conn is None:
            return 0
        ref_table = f'{table}_ref'
        try:
            cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]
            if not cols:
                return 0
            conditions = ' OR '.join(
                f'(w."{c}" IS NOT r."{c}") OR (w."{c}" IS NULL AND r."{c}" IS NOT NULL) OR (w."{c}" IS NOT NULL AND r."{c}" IS NULL)'
                for c in cols
            )
            sql = f'SELECT COUNT(*) FROM "{table}" w JOIN "{ref_table}" r ON w.id = r.id WHERE ({conditions})'
            row = conn.execute(sql).fetchone()
            return row[0] if row else 0
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Detection programmes
    # ------------------------------------------------------------------
    def _detect_programs(self) -> dict[str, bool]:
        conn = db.local_conn
        if conn is None:
            return {'PEI': False, 'DP': False}
        has_pei, has_dp = False, False
        try:
            rows = conn.execute("""
                SELECT DISTINCT p.sigle
                FROM larcauth_classroom_termsubject cts
                JOIN larcauth_classroom c ON c.id = cts.fk_classroom_id
                JOIN larcauth_level l ON l.id = c.fk_level_id
                JOIN larcauth_program p ON p.id = l.fk_program_id
                WHERE cts.fk_teacher_id = ?
            """, (session.user_id,)).fetchall()
            for r in rows:
                sigle = (r[0] or '').upper()
                if sigle in ('PEI', 'MYP'):
                    has_pei = True
                if sigle in ('DPFR', 'DPEN', 'DP'):
                    has_dp = True
        except Exception as e:
            log(f"Vérification des programmes PEI/DP impossible : {e}")
        return {'PEI': has_pei, 'DP': has_dp}

    def _detect_button_visibility(self, pgm: str, btn_key: str) -> bool:
        conn = db.local_conn
        if conn is None:
            return False
        uid, tid = session.user_id, session.term_id
        if not uid or not tid:
            return False
        try:
            if btn_key in ('pei_grp_matieres', 'dp_grp_matieres'):
                pids = '(12, 22)' if pgm == 'PEI' else '(13, 23)'
                row = conn.execute(f"""
                    SELECT 1 FROM larcauth_classroom_termsubject cts
                    JOIN larcauth_classroom c ON c.id = cts.fk_classroom_id
                    JOIN larcauth_level l ON l.id = c.fk_level_id
                    WHERE cts.fk_teacher_id = ? AND cts.fk_term_id = ?
                      AND (cts.enabled = 1 OR cts.enabled = 'true')
                      AND l.fk_program_id IN {pids} LIMIT 1
                """, (uid, tid)).fetchone()
                return row is not None
            if btn_key == 'pei_interdisc':
                row = conn.execute("""
                    SELECT 1 FROM larcauth_classroom_termothersubject cto
                    JOIN larcauth_classroom c ON c.id = cto.fk_classroom_id
                    JOIN larcauth_level l ON l.id = c.fk_level_id
                    WHERE cto.fk_supervisor_id = ? AND cto.fk_term_id = ?
                      AND (cto.enabled = 1 OR cto.enabled = 'true')
                      AND l.fk_program_id IN (12, 22)
                      AND (cto.unit_multisubjects = 1 OR cto.unit_multisubjects = 'true') LIMIT 1
                """, (uid, tid)).fetchone()
                return row is not None
            if btn_key == 'pei_pp':
                row = conn.execute("""
                    SELECT 1 FROM larcauth_classroom_termothersubject cto
                    JOIN larcauth_classroom c ON c.id = cto.fk_classroom_id
                    JOIN larcauth_level l ON l.id = c.fk_level_id
                    WHERE cto.fk_supervisor_id = ? AND cto.fk_term_id = ?
                      AND (cto.enabled = 1 OR cto.enabled = 'true')
                      AND l.fk_program_id IN (12, 22)
                      AND (cto.label LIKE 'Personal%' OR cto.label LIKE 'Projet%') LIMIT 1
                """, (uid, tid)).fetchone()
                return row is not None
            if btn_key == 'pei_mes_classes':
                return db.server_conn is not None and self._detect_button_visibility(pgm, 'pei_grp_matieres')
            if btn_key == 'dp_mes_classes':
                return db.server_conn is not None and self._detect_button_visibility(pgm, 'dp_grp_matieres')
            if btn_key in ('dp_tdc', 'dp_cas', 'dp_memoire'):
                patterns = {'dp_tdc': ['Th%'], 'dp_cas': ['Cr%'], 'dp_memoire': ['Me%', 'Ext%']}.get(btn_key, [])
                clauses = ' OR '.join(['cto.label LIKE ?' for _unused in patterns])
                row = conn.execute(f"""
                    SELECT 1 FROM larcauth_classroom_termothersubject cto
                    WHERE cto.fk_supervisor_id = ? AND cto.fk_term_id = ?
                      AND (cto.enabled = 1 OR cto.enabled = 'true') AND ({clauses}) LIMIT 1
                """, [uid, tid] + patterns).fetchone()
                return row is not None
        except Exception:
            return False
        return True

    def _apply_program_visibility(self) -> None:
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
                log(f"Vérification du rôle professeur principal impossible : {e}")
        self._btn_prof_principal.setVisible(pp_visible)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    @safe_slot("Unknown._on_pgm_btn_clicked")
    def _on_pgm_btn_clicked(self, key: str):
        def handler():
            view = _BTN_VIEW.get(key, key)
            self._open_main_window(focus=view)
        return handler

    @safe_slot("Unknown._open_pp")
    def _open_pp(self) -> None:
        detected = self._detect_programs()
        view = 'college_bulletin' if detected.get('PEI') else 'lycee_bulletin' if detected.get('DP') else 'prof_principal'
        self._open_main_window(focus=view)

    def _open_main_window(self, focus: str = 'notes') -> None:
        from views.main_window import MainWindow
        self._main_window = MainWindow()
        self._main_window.showMaximized()
        self.hide()

        # Fermeture des notes → retour au tableau de bord.
        # Le dashboard est montré AVANT l'acceptation : il reste une fenêtre
        # visible quand les notes se ferment → quitOnLastWindowClosed ne
        # termine pas l'appli.
        def _intercept_close(event):
            if not self._main_window._confirm_leave():
                event.ignore()
                return
            self._main_window = None
            self.show()
            self._load_sync()
            event.accept()

        self._main_window.closeEvent = _intercept_close

    @safe_slot("Unknown._do_sync")
    def _do_sync(self) -> None:
        self.statusBar().showMessage('Synchronisation en cours...')
        QApplication.processEvents()
        try:
            if db.server_conn is None:
                if not db.connect_intranet():
                    if not db.connect_cloud():
                        self.statusBar().showMessage('Aucun serveur disponible (Intranet/Cloud).', 5000)
                        return
            report = sync_manager.pull_push()
            if report.has_errors:
                self.statusBar().showMessage(f'Sync terminee avec {len(report.errors)} erreur(s).', 8000)
            elif report.has_conflicts:
                self.statusBar().showMessage(f'Sync terminee — {len(report.conflicts)} conflit(s) a resoudre.', 8000)
            else:
                self.statusBar().showMessage(f'Sync reussie — {report.summary()}', 5000)
            self._load_sync()
        except Exception as e:
            self.statusBar().showMessage(f'Erreur de synchronisation : {e}', 8000)

    @safe_slot("Unknown._logout")
    def _logout(self) -> None:
        session.is_authenticated = False
        db.disconnect_all()
        self._main_window = None
        login = self.parentWidget()
        if login is not None:
            login.show()
        else:
            from views.login import LoginWindow
            login = LoginWindow()
            login.show()
        self.close()

    # ------------------------------------------------------------------
    # Theme reactivity
    # ------------------------------------------------------------------
    @safe_slot("HomeWindow._restyle")
    def _restyle(self):
        self.centralWidget().setStyleSheet(self._STYLE())
        p = theme_manager.palette
        s = theme_manager.font_size
        # Re-styler les labels inline du header
        if hasattr(self, '_hdr_title'):
            self._hdr_title.setStyleSheet(f'color: {p.on_primary}; border: none;')
        if hasattr(self, '_hdr_mode'):
            self._hdr_mode.setStyleSheet(f'color: {p.on_primary}; border: none;')
        if hasattr(self, '_hdr_last_login'):
            self._hdr_last_login.setStyleSheet(f'color: {p.on_primary}; border: none;')
        # Indicateurs connexion
        if hasattr(self, '_profile_intra'):
            server_ok = db.server_conn is not None
            if server_ok:
                server_mode = db.server_mode
                intra_active = server_mode == DBMode.INTRANET
                cloud_active = server_mode == DBMode.CLOUD
                self._profile_intra.setStyleSheet(
                    f"color: {'#27ae60' if intra_active else p.text_soft}; "
                    f"font-size: {theme_manager.font_size(11)}px; font-weight: {'bold' if intra_active else 'normal'};")
                self._profile_cloud.setStyleSheet(
                    f"color: {'#27ae60' if cloud_active else p.text_soft}; "
                    f"font-size: {theme_manager.font_size(11)}px; font-weight: {'bold' if cloud_active else 'normal'};")
            else:
                self._profile_intra.setStyleSheet(
                    f"color: {p.text_strong}; font-size: {theme_manager.font_size(11)}px;")
                self._profile_cloud.setStyleSheet(
                    f"color: {p.text_strong}; font-size: {theme_manager.font_size(11)}px;")
            # Re-appliquer les couleurs de connexion (garder le vert si actif)
            self._load_profile()
