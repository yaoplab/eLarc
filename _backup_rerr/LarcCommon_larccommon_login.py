import os
import hashlib
from typing import Optional
import time
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QMessageBox,
    QApplication,
    QTabWidget,
    QCheckBox,
    QProgressDialog,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QEvent
from PySide6.QtGui import QPixmap
from larccommon.database import db
from larccommon.design_system import ds
from larccommon.session import session, UserRole, ConnMode
from larccommon.logger import log
from larccommon.network import detect_network
from larccommon.theme import theme_manager, QssHelper
from larccommon.auth import OAuth2Manager
from larccommon.app_config import app_config
from larccommon.l10n import Translator, _
from larccommon.safe_slot import safe_slot

try:
    from LarcSuperviseur.common.trace import trace
except ImportError:

    from larccommon.error_reporting import get_reporter
    get_reporter().report_exception()
    def trace(msg):
        pass


class _Worker(QThread):
    done = Signal(object)

    def __init__(self, fn, *args, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._args = args
        self.finished.connect(self.deleteLater)

    def run(self):
        try:
            self.done.emit(self._fn(*self._args))
        except Exception as exc:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self.done.emit((False, None, str(exc)))


class LoginWindow(QWidget):
    """Fenêtre de connexion partagée — utilisée par LarcSuperviseur, LarcSecretaire, LarcHub.

    Usage:
        window = LoginWindow(on_success=lambda: open_main_window())
        window.show()
    """

    _login_attempts: dict[str, dict] = {}

    @classmethod
    def _check_rate_limit(cls, key: str) -> bool:
        now = time.time()
        entry = cls._login_attempts.get(key)
        if entry and entry["until"] > now:
            remaining = int(entry["until"] - now)
            raise RuntimeError(f"Trop de tentatives. R\u00e9essayez dans {remaining}s.")
        if entry and entry["until"] <= now:
            cls._login_attempts.pop(key, None)
        return True

    @classmethod
    def _record_failure(cls, key: str):
        entry = cls._login_attempts.setdefault(key, {"count": 0, "until": 0})
        entry["count"] += 1
        if entry["count"] >= 5:
            entry["until"] = time.time() + 30

    def __init__(
        self,
        on_success=None,
        title_prefix=None,
        subtitle=None,
        on_intranet_login=None,
        on_cloud_login=None,
    ):
        if not db.is_server_connected:
            return
        super().__init__()
        self._on_success = on_success or self._open_main_window
        self._title_prefix = title_prefix or _("app.title.superviseur")
        self._subtitle = subtitle or _("login.subtitle.superviseur")
        self._on_intranet_login = on_intranet_login
        self._on_cloud_login = on_cloud_login
        self._worker: Optional[_Worker] = None
        self._tabs_forced = False
        import os

        lang = os.environ.get("LARC_LANG", "fr")
        trans = Translator.instance(lang)
        trans.load_dir(Translator.l10n_dir())
        title = self._title_prefix + " - " + _("login.title")
        self.setWindowTitle(title)

        ok_intra = db.connect_intranet()
        trace(f" LoginWindow.__init__: connect_intranet={ok_intra}")
        if not db.server_conn:
            ok_cloud = db.connect_cloud()
            trace(f" LoginWindow.__init__: connect_cloud={ok_cloud}")
        app_config.load()
        trace(f" LoginWindow.__init__: server_conn={db.server_conn is not None}")

        self._term_label = self._get_current_term_label()
        self._init_ui()

    def _get_current_term_label(self) -> str:
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return ""
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT t.label
                FROM larcauth_term t, larcauth_academicyear ay
                WHERE ay.s_id = 1 AND t.trim = ay.current_term_number
                LIMIT 1
            """)
            r = cur.fetchone()
            return r[0] if r else ""
        except Exception:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            return ""

    def _style(self) -> str:
        p = theme_manager.palette
        s = theme_manager.font_size
        rd = ds.radius_sm
        return f"""
            QWidget#root {{ background: {p.background}; }}
            QLabel {{ font-size: {s(13)}px; color: {p.text_strong}; }}
            QTabWidget::pane {{
                border: 1px solid {p.outline_variant}; background: {p.surface};
                border-radius: {rd}px;
            }}
            QTabBar::tab          {{ padding: {ds.space_xxs + ds.space_xxs // 2}px {ds.space_m3}px; font-size: {s(13)}px; }}
            QTabBar::tab:selected {{
                background: {p.surface}; border-bottom: 2px solid {p.primary};
                color: {p.text_strong}; font-weight: bold;
            }}
            QTabBar::tab:!selected {{ background: {p.surface_variant}; color: {p.text_strong}; }}
            QLineEdit {{
                padding: {ds.space_xs - ds.space_xxs // 4}px {ds.space_xs + ds.space_xxs // 2}px; border: 1px solid {p.outline_variant};
                border-radius: {rd}px; font-size: {s(13)}px; background: {p.surface};
                color: {p.text_strong};
            }}
            QLineEdit:focus {{ border-color: {p.primary}; }}
            QPushButton {{
                padding: {ds.space_xs + ds.space_xxs // 4}px {ds.space_md}px; border: none; border-radius: {rd}px;
                font-size: {s(13)}px; font-weight: bold; color: white;
            }}
            QPushButton#btnIntra  {{ background: {p.primary}; }}
            QPushButton#btnIntra:hover  {{ background: {p.active}; }}
            QPushButton#btnIntra:disabled  {{ background: {p.inactive}; }}
            QPushButton#btnGoogle {{ background: #DB4437; }}
            QPushButton#btnGoogle:hover {{ background: #C53929; }}
            QPushButton#btnGoogle:disabled {{ background: {p.inactive}; }}
            QPushButton#btnCloud {{ background: {p.primary}; }}
            QPushButton#btnCloud:hover {{ background: {p.active}; }}
            QLabel#errLabel {{ color: {p.error}; font-size: {s(13)}px; }}
            QLabel#hdrTitle {{ color: {p.text_strong}; font-size: {s(21)}px; font-weight: bold; }}
            QLabel#hdrSub   {{ color: {p.text_soft}; font-size: {s(13)}px; }}
            QLabel#infoLbl  {{ color: {p.text_soft}; font-size: {s(13)}px; }}
            QLabel#formLbl {{ color: {p.text_strong}; font-size: {s(13)}px; }}
        """

    def _init_ui(self):
        self.setStyleSheet(self._style())
        W = 420
        H = int(W * 1.618033988749895)
        self.setFixedSize(W, H)

        outer = QVBoxLayout()
        outer.setContentsMargins(theme_manager.image.theme_btn, ds.table_row_min, theme_manager.image.theme_btn, ds.table_row_min)
        outer.setSpacing(0)

        logo_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "LarcSuperviseur",
            "img",
            "logoAEC.png",
        )
        self._logo_label = QLabel()
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path)
            self._logo_pixmap = pix.scaledToHeight(89, Qt.SmoothTransformation)
            self._logo_label.setPixmap(self._logo_pixmap)
        else:
            self._logo_pixmap = None
            self._logo_label.setText("[Logo]")
        self._logo_label.setAlignment(Qt.AlignCenter)
        self._logo_label.setCursor(Qt.PointingHandCursor)
        self._logo_label.installEventFilter(self)
        outer.addWidget(self._logo_label)
        outer.addSpacing(21)

        title = QLabel(self._title_prefix)
        title.setObjectName("hdrTitle")
        title.setAlignment(Qt.AlignCenter)
        outer.addWidget(title)
        outer.addSpacing(8)

        sub = QLabel(self._subtitle)
        sub.setObjectName("hdrSub")
        sub.setAlignment(Qt.AlignCenter)
        outer.addWidget(sub)
        outer.addSpacing(21)

        self._net_label = QLabel()
        self._net_label.setAlignment(Qt.AlignCenter)
        self._net_label.setObjectName("infoLbl")
        outer.addWidget(self._net_label)
        outer.addSpacing(21)

        self._force_check = QCheckBox("Choisir connexion")
        self._force_check.setVisible(False)
        self._force_check.toggled.connect(self._on_force_toggle)
        outer.addWidget(self._force_check, 0, Qt.AlignCenter)
        outer.addSpacing(21)

        self._tabs = QTabWidget()
        self._tab_intra_widget = self._tab_intranet()
        self._tab_cloud_widget = self._tab_cloud()
        self._tabs.addTab(self._tab_intra_widget, "Intranet")
        self._tabs.addTab(self._tab_cloud_widget, "Cloud")
        outer.addWidget(self._tabs, 1)

        self._err_label = QLabel()
        self._err_label.setObjectName("errLabel")
        self._err_label.setAlignment(Qt.AlignCenter)
        self._err_label.setWordWrap(True)
        outer.addWidget(self._err_label)
        outer.addSpacing(8)

        self._status_label = QLabel()
        self._status_label.setObjectName("infoLbl")
        outer.addWidget(self._status_label)

        self.setLayout(outer)
        self._update_network_status()

        self._net_timer = QTimer(self)
        self._net_timer.setInterval(30000)
        self._net_timer.timeout.connect(self._update_network_status)
        self._net_timer.start()

    def eventFilter(self, obj, event):
        if obj is self._logo_label and event.type() == QEvent.MouseButtonDblClick:
            self._force_check.setVisible(True)
            if self._force_check.isChecked():
                self._tabs_forced = True
                self._apply_tab_visibility()
        return super().eventFilter(obj, event)

    @safe_slot("LoginWindow._on_force_toggle")
    def _on_force_toggle(self, checked: bool):
        self._tabs_forced = checked
        self._apply_tab_visibility()

    def clear_fields(self):
        """Vide les champs de connexion (retour à l'écran de login)."""
        if hasattr(self, "_edt_i_email"):
            self._edt_i_email.clear()
        if hasattr(self, "_edt_i_pwd"):
            self._edt_i_pwd.clear()

    def _tab_intranet(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)

        email_lbl = QLabel("Email :")
        email_lbl.setObjectName("formLbl")
        layout.addWidget(email_lbl)
        email = QLineEdit()
        email.setPlaceholderText(_("login.email_placeholder"))
        email.setFixedHeight(ds.logo_small)
        self._edt_i_email = email
        layout.addWidget(email)

        layout.addSpacing(21)

        pwd_lbl = QLabel("Mot de passe :")
        pwd_lbl.setObjectName("formLbl")
        layout.addWidget(pwd_lbl)
        pwd = QLineEdit()
        pwd.setEchoMode(QLineEdit.Password)
        pwd.setPlaceholderText(_("login.password_placeholder"))
        pwd.setFixedHeight(ds.logo_small)
        pwd.returnPressed.connect(self._on_intranet)
        self._edt_i_pwd = pwd
        layout.addWidget(pwd)

        layout.addSpacing(34)

        if self._term_label:
            term_lbl = QLabel(f"Trimestre : {self._term_label}")
            term_lbl.setObjectName("infoLbl")
            term_lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(term_lbl)
            layout.addSpacing(16)

        btn = QPushButton("Connexion Intranet")
        btn.setObjectName("btnIntra")
        btn.setFixedSize(ds.window_width * 7 // 40, ds.logo_small)
        btn.clicked.connect(self._on_intranet)
        layout.addWidget(btn, 0, Qt.AlignCenter)

        layout.addSpacing(21)
        info = QLabel("Authentification via le serveur interne.")
        info.setObjectName("infoLbl")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        return w

    def _tab_cloud(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)

        info = QLabel("Connectez-vous avec votre compte\nGoogle @arc-en-ciel.org")
        info.setObjectName("infoLbl")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        layout.addSpacing(24)

        if self._term_label:
            term_lbl = QLabel(f"Trimestre : {self._term_label}")
            term_lbl.setObjectName("infoLbl")
            term_lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(term_lbl)
            layout.addSpacing(16)

        btn = QPushButton("Connexion Google")
        btn.setObjectName("btnGoogle")
        btn.setFixedSize(ds.window_width * 7 // 40, ds.logo_small)
        btn.clicked.connect(self._on_cloud)
        layout.addWidget(btn, 0, Qt.AlignCenter)

        layout.addSpacing(16)
        info2 = QLabel("Authentification OAuth2 via Supabase.")
        info2.setObjectName("infoLbl")
        info2.setAlignment(Qt.AlignCenter)
        layout.addWidget(info2)
        return w

    @safe_slot("LoginWindow._on_intranet")
    def _on_intranet(self):
        trace(f"_on_intranet: START")
        email = self._edt_i_email.text().strip()
        password = self._edt_i_pwd.text()
        if not email or not password:
            trace(f"_on_intranet: email or password empty")
            self._show_error(_("login.error.required"))
            return
        try:
            self._check_rate_limit(email.lower())
        except RuntimeError as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self._show_error(str(e))
            return
        self._hide_error()
        self._set_busy(True)

        if self._on_intranet_login:
            self._worker = _Worker(self._on_intranet_login, email, password, parent=self)
            self._worker.done.connect(lambda r, ek=email.lower(): self._on_cloud_done(r, ek))
            self._worker.start()
            return

    @safe_slot("LoginWindow._on_cloud")
    def _on_cloud(self):
        try:
            self._check_rate_limit("cloud")
        except RuntimeError as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            self._show_error(str(e))
            return
        self._hide_error()
        self._set_busy(True)
        if self._on_cloud_login:
            self._worker = _Worker(self._on_cloud_login, parent=self)
        else:
            self._worker = _Worker(OAuth2Manager.authenticate, parent=self)
        self._worker.done.connect(self._on_cloud_done)
        self._worker.start()

    @safe_slot("LoginWindow._on_cloud_done")
    def _on_cloud_done(self, result, mode=None, rate_key="cloud"):
        self._set_busy(False)
        ok, res, err = result
        if not ok:
            self._record_failure(rate_key)
            self._show_error(err or "Authentification echouee.")
            return
        log(f"Connexion : {getattr(res, 'full_name', '?')}")
        self._on_success()
        self.close()

    def _open_main_window(self):
        from LarcSuperviseur.common.photos import get_uncached_ids, PhotoPreloader
        from LarcSuperviseur.views.main_window import MainWindow

        student_ids = get_uncached_ids()
        if student_ids:
            progress = QProgressDialog(
                "Pr\u00e9paration des photos...", "Annuler", 0, len(student_ids), self
            )
            progress.setWindowTitle("LarcSuperviseur")
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)

            preloader = PhotoPreloader(student_ids, self)
            preloader.progress.connect(lambda cur, total, sid: progress.setValue(cur))
            preloader.done.connect(lambda loaded, failed: progress.close())
            progress.canceled.connect(preloader.cancel)
            preloader.finished.connect(self._on_preloader_finished)
            preloader.finished.connect(preloader.deleteLater)
            preloader.start()
            self._preloader = preloader
        else:
            self._do_open_main_window(MainWindow)

    @safe_slot("LoginWindow._on_preloader_finished")
    def _on_preloader_finished(self):
        self._do_open_main_window(MainWindow)

    def _do_open_main_window(self, MainWindow):
        self.main = MainWindow()
        self.main.resize(1200, 750)
        self.main.showMaximized()
        self.close()

    def _apply_tab_visibility(self):
        intra_ok, internet_ok = self._net_status
        p = theme_manager.palette

        if self._tabs_forced:
            self._tabs.setTabVisible(0, True)
            self._tabs.setTabVisible(1, True)
            self._err_label.setText("")
            intra_color = p.success if intra_ok else p.text_soft
            cloud_color = p.primary if internet_ok else p.text_soft
            self._net_label.setText(
                f"<span style='color:{intra_color}'>Intranet \u25cf</span>"
                f"   "
                f"<span style='color:{cloud_color}'>Cloud \u25cf</span>"
            )
            self._net_label.setTextFormat(Qt.RichText)
            self._net_label.setStyleSheet(f"font-weight: bold; font-size: {theme_manager.font_size(13)}px;")
            return

        if intra_ok and internet_ok:
            self._tabs.setTabVisible(0, True)
            self._tabs.setTabVisible(1, False)
            self._tabs.setCurrentIndex(0)
            self._err_label.setText("")
            self._net_label.setText("Intranet \u25cf")
            self._net_label.setStyleSheet(
                f"color: {p.success}; font-weight: bold; font-size: {theme_manager.font_size(13)}px;"
            )

        elif internet_ok and not intra_ok:
            self._tabs.setTabVisible(0, False)
            self._tabs.setTabVisible(1, True)
            self._tabs.setCurrentIndex(1)
            self._err_label.setText("")
            self._net_label.setText("Cloud \u25cf")
            self._net_label.setStyleSheet(
                f"color: {p.primary}; font-weight: bold; font-size: {theme_manager.font_size(13)}px;"
            )

        elif intra_ok and not internet_ok:
            self._tabs.setTabVisible(0, True)
            self._tabs.setTabVisible(1, False)
            self._tabs.setCurrentIndex(0)
            self._err_label.setText("")
            self._net_label.setText("Intranet \u25cf")
            self._net_label.setStyleSheet(
                f"color: {p.success}; font-weight: bold; font-size: {theme_manager.font_size(13)}px;"
            )

        else:
            self._tabs.setTabVisible(0, False)
            self._tabs.setTabVisible(1, False)
            self._err_label.setText("Acc\u00e8s \u00e0 LarcSuperviseur Impossible")
            self._net_label.setText("Hors ligne")
            self._net_label.setStyleSheet(
                f"color: {p.text_disabled}; font-weight: bold; font-size: {theme_manager.font_size(13)}px;"
            )

    @safe_slot("LoginWindow._update_network_status")
    def _update_network_status(self):
        self._net_status = detect_network()
        self._apply_tab_visibility()

    def _show_error(self, msg: str):
        self._err_label.setText(msg)

    def _hide_error(self):
        self._err_label.setText("")

    def _set_busy(self, busy: bool):
        for btn in self.findChildren(QPushButton):
            btn.setEnabled(not busy)
        if busy:
            self._status_label.setText("Connexion en cours...")
        else:
            self._status_label.setText("")
