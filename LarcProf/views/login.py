import os
from typing import Optional

from larccommon.design_system import ds
from larccommon.icons import icon as md3_icon
from larccommon.l10n import Translator, _
from phibuilder.phi.scale import SpacingToken
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from common.network import NetworkMode, detect_network, network_mode_color
from common.session import AuthResult, ConnMode, UserRole
from common.sqlite_init import sqlite_init
from common.theme import theme_manager
from larccommon.safe_slot import safe_slot


# ---------------------------------------------------------------------------
# Login window


from views.login_auth import LoginAuthMixin, _Worker
from views.login_creation import LoginCreationMixin
from views.login_helpers import LoginHelpersMixin


class LoginWindow(LoginAuthMixin, LoginCreationMixin, LoginHelpersMixin, QMainWindow):
    @property
    def _STYLE(self) -> str:
        p = theme_manager.theme.palette
        fs = theme_manager.font_size
        return f"""
            QMainWindow {{ background: {p.background}; }}
            QWidget#root {{ background: {p.background}; }}
            QFrame.panel {{
                background: {p.surface};
                border: 1px solid {p.border};
                border-radius: {ds.radius_sm}px;
            }}
            QLabel.logo-title {{
                font-size: {fs(22)}px;
                font-weight: bold;
                color: {p.text_strong};
            }}
            QLabel.logo-sub {{
                font-size: {fs(11)}px;
                color: {p.text_soft};
            }}
            QLabel.section-title {{
                font-size: {fs(13)}px;
                font-weight: bold;
                color: {p.text_strong};
            }}
            QLabel.info-text {{
                font-size: {fs(11)}px;
                color: {p.text_soft};
            }}
            QLabel.error-text {{
                color: {p.error};
                font-size: {fs(11)}px;
                font-weight: bold;
            }}
            QLabel.indicator-on {{
                font-size: {fs(12)}px;
                font-weight: bold;
            }}
            QLabel.indicator-off {{
                font-size: {fs(12)}px;
            }}
            QLineEdit {{
                padding: {ds.space_xs + ds.space_xxs // 2}px {ds.space_sm + ds.space_xxs // 2}px;
                border: 1px solid {p.border};
                border-radius: {ds.radius_sm}px;
                font-size: {fs(13)}px;
                background: {p.surface};
                color: {p.text_strong};
                min-height: {ds.field_height}px;
            }}
            QLineEdit:focus {{ border-color: {p.primary}; }}
            QPushButton.btn-primary {{
                background: {p.primary};
                color: {p.on_primary};
                border: none;
                border-radius: {ds.radius_sm}px;
                padding: {ds.space_xs + ds.space_xxs // 2}px {ds.space_md}px;
                font-size: {fs(13)}px;
                font-weight: bold;
                text-align: center;
            }}
            QPushButton.btn-primary:hover {{ background: {p.primary}; }}
            QPushButton.btn-primary:disabled {{ background: {p.inactive}; }}
            QPushButton.btn-google {{
                background: {p.error};
                color: {p.on_primary};
                border: none;
                border-radius: {ds.radius_sm}px;
                padding: {ds.space_xs + ds.space_xxs // 2}px {ds.space_md}px;
                font-size: {fs(13)}px;
                font-weight: bold;
                text-align: center;
            }}
            QPushButton.btn-google:hover {{ background: {p.error}; }}
            QPushButton.btn-google:disabled {{ background: {p.inactive}; }}
            QPushButton.btn-pin {{
                background: {p.secondary};
                color: {p.on_secondary};
                border: none;
                border-radius: {ds.radius_sm}px;
                padding: {ds.space_xs + ds.space_xxs // 2}px {ds.space_md}px;
                font-size: {fs(13)}px;
                font-weight: bold;
                text-align: center;
            }}
            QPushButton.btn-pin:hover {{ background: {p.secondary}; }}
            QPushButton.btn-pin:disabled {{ background: {p.inactive}; }}
            QPushButton.btn-create {{
                background: {p.success};
                color: {p.on_primary};
                border: none;
                border-radius: {ds.radius_sm}px;
                padding: {ds.space_xs + ds.space_xxs // 2}px {ds.space_md}px;
                font-size: {fs(13)}px;
                font-weight: bold;
                text-align: center;
            }}
            QPushButton.btn-create:hover {{ background: {p.success}; }}
            QPushButton.btn-create:disabled {{ background: {p.inactive}; }}
            QPushButton.btn-secondary {{
                background: transparent;
                color: {p.text_soft};
                border: 1px solid {p.border};
                border-radius: {ds.radius_sm}px;
                padding: {ds.space_xs}px {ds.font_label_lg}px;
                font-size: {fs(11)}px;
            }}
            QPushButton.btn-secondary:hover {{ background: {p.primary_container}; color: {p.text_strong}; }}
            QPushButton.btn-browse {{
                background: {p.text_soft};
                color: {p.on_primary};
                border: none;
                border-radius: {ds.radius_sm}px;
                padding: {ds.space_xs}px {ds.font_label_lg}px;
                font-size: {fs(11)}px;
                font-weight: bold;
                min-width: {theme_manager.image.theme_btn}px;
                text-align: center;
            }}
            QPushButton.btn-browse:hover {{ background: {p.inactive}; }}
            QTabWidget::pane {{
                border: 1px solid {p.border};
                background: {p.surface};
                border-radius: {ds.radius_sm}px;
            }}
            QTabBar::tab {{
                padding: {ds.space_xs}px {ds.space_sm + ds.space_xxs}px;
                font-size: {fs(11)}px;
            }}
            QTabBar::tab:selected {{
                background: {p.surface};
                border-bottom: 2px solid {p.primary};
                color: {p.text_strong};
                font-weight: bold;
            }}
            QTabBar::tab:!selected {{
                background: {p.border_light};
                color: {p.text_soft};
            }}
            QFrame#sep {{
                border: none;
                border-top: 1px solid {p.border_light};
            }}
        """

    def __init__(self):
        super().__init__()
        import os

        lang = os.environ.get("LARC_LANG", "fr")
        trans = Translator.instance(lang)
        trans.load_dir(Translator.l10n_dir())

        # Charger les préférences
        from PySide6.QtCore import QSettings

        s = QSettings("Larc", "LarcProf")
        saved_theme = s.value("theme_pref", "")
        if saved_theme and saved_theme in (
            "default",
            "material_light",
            "material_dark",
            "nature",
            "blue",
            "dark",
            "sobre",
            "contrast",
        ):
            theme_manager.set_active(saved_theme)

        self._worker: Optional[_Worker] = None
        self._net_mode: Optional[NetworkMode] = None
        self._sp = theme_manager.phi_theme.spacing.spacing

        self._setup_ui()
        self._start_net_detection()

        self._network_timer = QTimer(self)
        self._network_timer.setInterval(30000)
        self._network_timer.timeout.connect(self._check_network)

        ds.theme_changed.connect(self._restyle)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        sp = self._sp
        self.setWindowTitle(_("prof_login.window_title"))
        self.setMinimumSize(ds.window_width * 7 // 20, ds.window_height * 17 // 20)  # 420×680
        self.resize(ds.window_width * 2 // 5, ds.window_height - 20)  # 480×780
        self.setStyleSheet(self._STYLE)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(
            sp(SpacingToken.SM), sp(SpacingToken.SM), sp(SpacingToken.SM), sp(SpacingToken.SM)
        )
        outer.setSpacing(sp(SpacingToken.SM))

        # Logo — largeur = 80% de la fenêtre (ratio conservé, recalculé au resize)
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "img", "logoAEC.png")
        if os.path.exists(logo_path):
            self._logo_src = QPixmap(logo_path)
            self._logo_label = QLabel()
            self._logo_label.setAlignment(Qt.AlignCenter)
            outer.addWidget(self._logo_label)
            self._resize_logo()

        # Titre + sous-titre — pile centrée, sans boîte (pattern LarcSuperviseur)
        title = QLabel(_("prof_login.title"))
        title.setProperty("class", "logo-title")
        title.setAlignment(Qt.AlignCenter)
        outer.addWidget(title)
        outer.addSpacing(sp(SpacingToken.XS))

        sub = QLabel(_("prof_login.subtitle"))
        sub.setProperty("class", "logo-sub")
        sub.setAlignment(Qt.AlignCenter)
        outer.addWidget(sub)
        outer.addSpacing(sp(SpacingToken.SM))

        # Indicateurs réseau (entre titre et onglets)
        self._net_row = QWidget()
        net_layout = QHBoxLayout(self._net_row)
        net_layout.setContentsMargins(sp(SpacingToken.SM), sp(SpacingToken.XXS), sp(SpacingToken.SM), sp(SpacingToken.XXS))
        net_layout.setSpacing(sp(SpacingToken.MD))
        net_layout.addStretch()
        self._intra_indicator = QLabel(_("login.status.intranet"))
        self._intra_indicator.setFont(theme_manager.font(11))
        net_layout.addWidget(self._intra_indicator)
        self._cloud_indicator = QLabel(_("login.status.cloud"))
        self._cloud_indicator.setFont(theme_manager.font(11))
        net_layout.addWidget(self._cloud_indicator)
        outer.addWidget(self._net_row)

        self._tabs = QTabWidget()
        self._build_intranet_tab()
        self._build_cloud_tab()
        self._build_pin_tab()
        self._build_new_tab()
        self._apply_icons()
        outer.addWidget(self._tabs, 1)

        self._err_lbl = QLabel()
        self._err_lbl.setProperty("class", "error-text")
        self._err_lbl.setWordWrap(True)
        self._err_lbl.hide()
        outer.addWidget(self._err_lbl)

        self._log_area = QPlainTextEdit()
        self._log_area.setReadOnly(True)
        self._log_area.setMaximumHeight(ds.window_height * 7 // 80)  # 70px
        self._log_area.setPlaceholderText("Messages de progression…")
        self._log_area.hide()
        outer.addWidget(self._log_area)

        self._bottom_indicator = QLabel()
        self._bottom_indicator.setAlignment(Qt.AlignCenter)
        self._bottom_indicator.setWordWrap(True)
        p = theme_manager.theme.palette
        self._bottom_indicator.setStyleSheet(
            f"color: {p.text_strong}; font-size: {theme_manager.font_size(13)}px; font-weight: bold;"
            f"padding: {sp(SpacingToken.SM)}px {sp(SpacingToken.MD)}px;"
        )
        outer.addWidget(self._bottom_indicator)

        sb = QStatusBar()
        self.setStatusBar(sb)
        self._net_lbl = QLabel("Détection du réseau")
        self._net_lbl.setStyleSheet(f"font-size: {theme_manager.font_size(11)}px; color: {p.text_strong};")
        self._net_lbl.setContentsMargins(sp(SpacingToken.SM), 0, 0, 0)
        self._dot_lbl = QLabel("●")
        self._dot_lbl.setStyleSheet(
            f"color: {p.inactive}; font-size: {theme_manager.font_size(14)}px;"
        )
        sb.addWidget(self._net_lbl)
        sb.addWidget(self._dot_lbl)

    def _resize_logo(self) -> None:
        """Logo à 60% de la largeur de la fenêtre — ratio conservé."""
        if not hasattr(self, "_logo_src"):
            return
        pm = self._logo_src.scaledToWidth(self.width() * 3 // 5, Qt.SmoothTransformation)
        pm.setDevicePixelRatio(1)
        self._logo_label.setPixmap(pm)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_logo()

    def _apply_icons(self) -> None:
        """Icônes MD3 des boutons — recréées au restyle (theme-reactivity)."""
        p = theme_manager.theme.palette
        self._btn_intra.setIcon(md3_icon("lock", color=p.on_primary, size=ds.icon_sm))
        self._btn_google.setIcon(md3_icon("cloud", color=p.on_primary, size=ds.icon_sm))
        self._btn_pin.setIcon(md3_icon("badge", color=p.on_secondary, size=ds.icon_sm))
        self._btn_create.setIcon(md3_icon("add", color=p.on_primary, size=ds.icon_sm))
        self._btn_browse.setIcon(md3_icon("upload_file", color=p.on_primary, size=ds.icon_sm))

    def _tab_widget(self) -> tuple:
        sp = self._sp
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(
            sp(SpacingToken.SM), sp(SpacingToken.SM), sp(SpacingToken.SM), sp(SpacingToken.SM)
        )
        outer.setSpacing(sp(SpacingToken.SM))

        panel = QFrame()
        panel.setProperty("class", "panel")
        inner = QVBoxLayout(panel)
        inner.setContentsMargins(
            sp(SpacingToken.MD), sp(SpacingToken.MD), sp(SpacingToken.MD), sp(SpacingToken.MD)
        )
        inner.setSpacing(sp(SpacingToken.SM))

        outer.addWidget(panel)
        return tab, inner, outer

    def _build_intranet_tab(self) -> None:
        sp = self._sp
        tab, layout, _outer = self._tab_widget()

        title = QLabel(_("login.tab_intranet"))
        title.setProperty("class", "section-title")
        layout.addWidget(title)

        self._edt_i_email = QLineEdit()
        self._edt_i_email.setPlaceholderText(_("login.email_placeholder"))
        layout.addWidget(self._edt_i_email)

        self._edt_i_pass = QLineEdit()
        self._edt_i_pass.setEchoMode(QLineEdit.Password)
        self._edt_i_pass.setPlaceholderText(_("login.password_placeholder"))
        layout.addWidget(self._edt_i_pass)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(sp(SpacingToken.SM))

        self._btn_intra = QPushButton(_("login.connect_intranet"))
        self._btn_intra.setProperty("class", "btn-primary")
        self._btn_intra.setToolTip(_("login.connect_intranet"))
        self._btn_intra.clicked.connect(self._on_intranet)
        self._edt_i_pass.returnPressed.connect(self._btn_intra.click)
        btn_row.addWidget(self._btn_intra, 1)

        self._btn_change_pwd_intra = QPushButton(_("prof_login.change_password"))
        self._btn_change_pwd_intra.setProperty("class", "btn-secondary")
        self._btn_change_pwd_intra.setToolTip(_("prof_login.change_password"))
        self._btn_change_pwd_intra.clicked.connect(self._on_change_password)
        btn_row.addWidget(self._btn_change_pwd_intra)

        layout.addLayout(btn_row)
        layout.addStretch()
        self._tabs.addTab(tab, _("login.tab_intranet"))

    def _build_cloud_tab(self) -> None:
        tab, layout, _outer = self._tab_widget()

        title = QLabel(_("login.tab_cloud"))
        title.setProperty("class", "section-title")
        layout.addWidget(title)

        info = QLabel(_("prof_login.info_cloud"))
        info.setProperty("class", "info-text")
        info.setAlignment(Qt.AlignCenter)
        info.setWordWrap(True)
        layout.addWidget(info)

        self._btn_google = QPushButton(_("login.connect_google"))
        self._btn_google.setProperty("class", "btn-google")
        self._btn_google.setToolTip(_("login.connect_google"))
        self._btn_google.clicked.connect(self._on_cloud)
        layout.addWidget(self._btn_google)

        layout.addStretch()
        self._tabs.addTab(tab, _("login.tab_cloud"))

    def _build_pin_tab(self) -> None:
        sp = self._sp
        tab, layout, _outer = self._tab_widget()

        title = QLabel(_("prof_login.pin_title"))
        title.setProperty("class", "section-title")
        layout.addWidget(title)

        self._edt_p_email = QLineEdit()
        self._edt_p_email.setPlaceholderText(_("login.email_placeholder"))
        layout.addWidget(self._edt_p_email)

        self._edt_p_pin = QLineEdit()
        self._edt_p_pin.setEchoMode(QLineEdit.Password)
        self._edt_p_pin.setPlaceholderText(_("prof_login.pin_placeholder"))
        self._edt_p_pin.setMaxLength(8)
        layout.addWidget(self._edt_p_pin)

        note = QLabel(_("prof_login.pin_note"))
        note.setProperty("class", "info-text")
        layout.addWidget(note)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(sp(SpacingToken.SM))

        self._btn_pin = QPushButton(_("prof_login.connect_pin"))
        self._btn_pin.setProperty("class", "btn-pin")
        self._btn_pin.setToolTip(_("prof_login.connect_pin"))
        self._btn_pin.clicked.connect(self._on_pin)
        self._edt_p_pin.returnPressed.connect(self._btn_pin.click)
        btn_row.addWidget(self._btn_pin, 1)

        self._btn_change_pin = QPushButton(_("prof_login.change_pin"))
        self._btn_change_pin.setProperty("class", "btn-secondary")
        self._btn_change_pin.setToolTip(_("prof_login.change_pin"))
        self._btn_change_pin.clicked.connect(self._on_change_pin)
        btn_row.addWidget(self._btn_change_pin)

        layout.addLayout(btn_row)
        layout.addStretch()
        self._tabs.addTab(tab, _("prof_login.tab_pin"))

    def _build_new_tab(self) -> None:
        sp = self._sp
        tab, layout, _outer = self._tab_widget()

        title = QLabel(_("prof_login.new_title"))
        title.setProperty("class", "section-title")
        layout.addWidget(title)

        info = QLabel(_("prof_login.new_info"))
        info.setProperty("class", "info-text")
        info.setWordWrap(True)
        layout.addWidget(info)

        self._edt_n_email = QLineEdit()
        self._edt_n_email.setPlaceholderText(_("login.email_placeholder"))
        layout.addWidget(self._edt_n_email)

        dest_row = QHBoxLayout()
        dest_row.setSpacing(sp(SpacingToken.XS))
        self._edt_n_dest = QLineEdit()
        self._edt_n_dest.setPlaceholderText(_("prof_login.new_dest"))
        self._edt_n_dest.setReadOnly(True)
        dest_row.addWidget(self._edt_n_dest)
        self._btn_browse = QPushButton("…")
        self._btn_browse.setProperty("class", "btn-browse")
        self._btn_browse.setToolTip(_("prof_login.new_dest"))
        self._btn_browse.clicked.connect(self._browse_dest)
        dest_row.addWidget(self._btn_browse)
        layout.addLayout(dest_row)

        self._btn_create = QPushButton(_("prof_login.create_instance"))
        self._btn_create.setProperty("class", "btn-create")
        self._btn_create.setToolTip(_("prof_login.create_instance"))
        self._btn_create.clicked.connect(self._on_create)
        layout.addWidget(self._btn_create)

        layout.addStretch()
        self._tabs.addTab(tab, _("prof_login.tab_new"))

    # ------------------------------------------------------------------
    # Network detection (inchangé)
    # ------------------------------------------------------------------
    def _start_net_detection(self) -> None:
        worker = _Worker(lambda: (True, *detect_network(), ""), parent=self)
        worker.done.connect(self._on_net_detected)
        worker.start()

    def showEvent(self, event):
        super().showEvent(event)
        self._network_timer.start()
        intra_ok, internet_ok = detect_network()
        self._on_net_detected((True, intra_ok, internet_ok, ""))
        self._check_network()
        self._update_indicators(intra_ok, internet_ok)
        try:
            sqlite_init.init()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self._log(f"Erreur d'initialisation de la base locale : {e}")
        try:
            self._update_status_bar_from_module_config()
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self._log(f"Erreur lors de la mise à jour de la barre d'état : {e}")

    def hideEvent(self, event):
        super().hideEvent(event)
        self._network_timer.stop()

    @safe_slot("Unknown._check_network")
    def _check_network(self) -> None:
        worker = _Worker(lambda: (True, *detect_network(), ""), parent=self)
        worker.done.connect(self._on_net_detected)
        worker.start()

    @safe_slot("Unknown._on_net_detected")
    def _on_net_detected(self, result) -> None:
        ok, intra_ok, internet_ok, _ignored = result
        if not ok:
            return
        self._intranet_ok = intra_ok
        self._internet_ok = internet_ok
        if intra_ok:
            mode = NetworkMode.INTRANET
        elif internet_ok:
            mode = NetworkMode.INTERNET
        else:
            mode = NetworkMode.OFFLINE
        self._net_mode = mode
        color = network_mode_color(mode)
        self._dot_lbl.setStyleSheet(f"color: {color}; font-size: {theme_manager.font_size(14)}px;")
        labels = {
            NetworkMode.INTRANET: _("login.status.intranet").replace(" ●", ""),
            NetworkMode.INTERNET: _("prof_login.status.internet"),
            NetworkMode.OFFLINE: _("prof_login.status.offline"),
        }
        self._net_lbl.setText(labels.get(mode, ""))
        self._update_indicators(intra_ok, internet_ok)
        from common.session import session

        if session.is_authenticated:
            self._update_status_bar(
                AuthResult(
                    user_id=session.user_id,
                    email=session.email,
                    full_name=session.full_name,
                    role=session.role,
                    term_id=session.term_id,
                    term_label=session.term_label,
                ),
                session.conn_mode,
            )
        else:
            self._update_status_bar(
                AuthResult(
                    user_id=0, email="", full_name="", role=UserRole.PROF, term_id=0, term_label=""
                ),
                ConnMode.OFFLINE,
            )

    def _update_indicators(self, intranet: bool, cloud: bool) -> None:
        p = theme_manager.theme.palette
        on_color, off_color = ds.p.success, p.text_soft
        self._intra_indicator.setStyleSheet(
            f"color: {on_color if intranet else off_color}; "
            f"font-size: {theme_manager.font_size(11)}px;"
            f"font-weight: {'bold' if intranet else 'normal'};"
        )
        self._cloud_indicator.setStyleSheet(
            f"color: {on_color if cloud else off_color}; "
            f"font-size: {theme_manager.font_size(11)}px;"
            f"font-weight: {'bold' if cloud else 'normal'};"
        )

    @safe_slot("LoginWindow._restyle")
    def _restyle(self):
        """Re-applique les styles palette-dependent au changement de theme."""
        p = theme_manager.theme.palette
        sp = self._sp
        self.setStyleSheet(self._STYLE)
        self._apply_icons()
        self._bottom_indicator.setStyleSheet(
            f"color: {p.text_strong}; font-size: {theme_manager.font_size(13)}px; font-weight: bold;"
            f"padding: {sp(SpacingToken.SM)}px {sp(SpacingToken.MD)}px;"
        )
        self._net_lbl.setStyleSheet(f"font-size: {theme_manager.font_size(11)}px; color: {p.text_strong};")
        self._dot_lbl.setStyleSheet(
            f"color: {network_mode_color(self._net_mode)}; font-size: {theme_manager.font_size(14)}px;")
        intra_ok = getattr(self, '_intranet_ok', False)
        cloud_ok = getattr(self, '_internet_ok', False)
        on_color, off_color = ds.p.success, p.text_soft
        self._intra_indicator.setStyleSheet(
            f"color: {on_color if intra_ok else off_color}; "
            f"font-size: {theme_manager.font_size(11)}px;"
            f"font-weight: {'bold' if intra_ok else 'normal'};"
        )
        self._cloud_indicator.setStyleSheet(
            f"color: {on_color if cloud_ok else off_color}; "
            f"font-size: {theme_manager.font_size(11)}px;"
            f"font-weight: {'bold' if cloud_ok else 'normal'};"
        )
        self._err_lbl.setStyleSheet(
            f"color: {p.text_strong}; font-size: {theme_manager.font_size(11)}px;"
        )
        if hasattr(self, '_spinner') and self._spinner:
            self._spinner.setStyleSheet(
                f"QProgressBar {{ border: 1px solid {p.border}; border-radius: {ds.radius_xs}px; "
                f"background: {p.surface}; text-align: center; }}"
                f"QProgressBar::chunk {{ background: {p.primary}; }}"
            )

    @safe_slot("Unknown._on_change_password")
    def _on_change_password(self) -> None:
        from views.password import ChangePasswordDialog

        dlg = ChangePasswordDialog(self)
        dlg.exec()

    @safe_slot("Unknown._on_change_pin")
    def _on_change_pin(self) -> None:
        from views.password import ChangePinDialog

        dlg = ChangePinDialog(self)
        dlg.exec()
