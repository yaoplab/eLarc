import os
import time
from functools import partial
from typing import Optional, Tuple

from larccommon.design_system import ds
from larccommon.l10n import _
from larccommon.safe_slot import safe_slot
from LarcSecretaire.common.app_config import app_config
from LarcSecretaire.common.audit import audit
from LarcSecretaire.common.auth import AuthManager
from LarcSecretaire.common.database import db
from LarcSecretaire.common.logger import log
from LarcSecretaire.common.network import detect_network
from LarcSecretaire.common.session import AuthResult, ConnMode, UserRole, session
from LarcSecretaire.common.sqlite_init import sqlite_init
from LarcSecretaire.common.theme import theme_manager
from PySide6.QtCore import QEvent, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


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
    _login_attempts: dict[str, dict] = {}

    @classmethod
    def _check_rate_limit(cls, key: str) -> bool:
        now = time.time()
        entry = cls._login_attempts.get(key)
        if entry and entry["until"] > now:
            remaining = int(entry["until"] - now)
            raise RuntimeError(_("sec_login.too_many_attempts").format(seconds=remaining))
        if entry and entry["until"] <= now:
            cls._login_attempts.pop(key, None)
        return True

    @classmethod
    def _record_failure(cls, key: str):
        entry = cls._login_attempts.setdefault(key, {"count": 0, "until": 0})
        entry["count"] += 1
        if entry["count"] >= 5:
            entry["until"] = time.time() + 30

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
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_get_current_term_label: {e}")
            return ""

    def __init__(self):
        if not db.is_server_connected:
            return
        super().__init__()
        self._worker: Optional[_Worker] = None
        self._tabs_forced = False

        db.connect_intranet()
        print(f"[DEBUG] Intranet OK: {db.server_conn is not None}")
        if not db.server_conn:
            db.connect_cloud()
            print(f"[DEBUG] Cloud OK: {db.server_conn is not None}")
        print(f"[DEBUG] Final conn: {db.server_conn is not None}, mode: {db.mode}")
        sqlite_init.init()
        app_config.load()

        self._term_label = self._get_current_term_label()
        self._init_ui()

        self._net_timer = QTimer(self)
        self._net_timer.setInterval(30000)
        self._net_timer.timeout.connect(self._update_network_status)
        self._net_timer.start()

        self.setWindowTitle(_("sec_login.title"))

        self.setWindowTitle(_("sec_login.title"))

    def _style(self) -> str:
        p = theme_manager.palette
        d = theme_manager.design
        s = theme_manager.font_size
        return f"""
            QWidget#root {{ background: {p.background}; }}
            QLabel {{ font-size: {s(13)}px; color: {p.text_strong}; }}
            QTabWidget::pane {{
                border: 1px solid {p.outline_variant}; background: {p.surface};
                border-radius: {d.radius}px;
            }}
            QTabBar::tab {{ padding: {d.btn_sm_pad_v}px {d.btn_sm_pad_h}px; font-size: {s(13)}px; }}
            QTabBar::tab:selected {{
                background: {p.surface}; border-bottom: 2px solid {p.primary};
                color: {p.text_strong}; font-weight: bold;
            }}
            QTabBar::tab:!selected {{ background: {p.surface_variant}; color: {p.text_strong}; }}
            QLineEdit {{
                padding: {d.field_pad_v}px {d.field_pad_h}px; border: 1px solid {p.outline_variant};
                border-radius: {d.radius}px; font-size: {s(13)}px; background: {p.surface};
                color: {p.text_strong};
            }}
            QLineEdit:focus {{ border-color: {p.primary}; }}
            QPushButton {{
                padding: {d.btn_pad_v}px {d.btn_pad_h}px; border: none; border-radius: {d.radius}px;
                font-size: {s(13)}px; font-weight: bold; color: white;
            }}
            QPushButton#btnIntra {{ background: {p.primary}; }}
            QPushButton#btnIntra:hover {{ background: {p.active}; }}
            QPushButton#btnIntra:disabled {{ background: {p.inactive}; }}
            QPushButton#btnGoogle {{ background: {p.error}; }}
            QPushButton#btnGoogle:hover {{ background: {p.error}; }}
            QPushButton#btnGoogle:disabled {{ background: {p.inactive}; }}
            QLabel#errLabel {{ color: {p.error}; font-size: {s(13)}px; }}
            QLabel#hdrTitle {{ color: {p.text_strong}; font-size: {s(22)}px; font-weight: bold; }}
            QLabel#hdrSub {{ color: {p.text_soft}; font-size: {s(13)}px; }}
            QLabel#infoLbl {{ color: {p.text_soft}; font-size: {s(13)}px; }}
            QLabel#formLbl {{ color: {p.text_strong}; font-size: {s(13)}px; }}
        """

    def _init_ui(self):
        self.setStyleSheet(self._style())
        p = theme_manager.palette
        W = ds.window_width // 3 + ds.space_md  # 420
        H = int(W * ds.GOLDEN)  # 679
        self.setFixedSize(W, H)

        outer = QVBoxLayout()
        outer.setContentsMargins(ds.space_lg, ds.space_md, ds.space_lg, ds.space_md)
        outer.setSpacing(0)

        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "img", "logoAEC.png")
        self._logo_label = QLabel()
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path)
            self._logo_pixmap = pix.scaledToHeight(ds.space_xxl + ds.space_xxs, Qt.SmoothTransformation)  # 88px
            self._logo_label.setPixmap(self._logo_pixmap)
        else:
            self._logo_pixmap = None
            self._logo_label.setText(_("sec_login.logo_fallback"))
        self._logo_label.setAlignment(Qt.AlignCenter)
        self._logo_label.setCursor(Qt.PointingHandCursor)
        self._logo_label.installEventFilter(self)
        outer.addWidget(self._logo_label)
        outer.addSpacing(ds.space_md)

        title = QLabel(
            _("sec_login.app_title"),
        )
        title.setAlignment(Qt.AlignCenter)
        outer.addWidget(title)
        outer.addSpacing(ds.space_xs)

        sub = QLabel(
            _("sec_login.subtitle"),
        )
        sub.setAlignment(Qt.AlignCenter)
        outer.addWidget(sub)
        outer.addSpacing(ds.space_md)

        self._net_label = QLabel()
        self._net_label.setAlignment(Qt.AlignCenter)
        self._net_label.setStyleSheet(f"font-size: {theme_manager.font_size(13)}px; font-weight: bold; color: {p.text_strong};")
        outer.addWidget(self._net_label)
        outer.addSpacing(ds.space_md)

        self._force_check = QCheckBox(_("sec_login.choose_connection"))
        self._force_check.setVisible(False)
        self._force_check.toggled.connect(self._on_force_toggle)
        outer.addWidget(self._force_check, 0, Qt.AlignCenter)
        outer.addSpacing(ds.space_md)

        self._tabs = QTabWidget()
        self._tab_intra_widget = self._tab_intranet()
        self._tab_cloud_widget = self._tab_cloud()
        self._tabs.addTab(self._tab_intra_widget, _("sec_login.tab_intranet"))
        self._tabs.addTab(self._tab_cloud_widget, _("sec_login.tab_cloud"))
        d = theme_manager.design
        s = theme_manager.font_size
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {p.outline_variant}; background: {p.surface};
                border-radius: {d.radius}px;
            }}
            QTabBar::tab {{ padding: {d.btn_sm_pad_v}px {d.btn_sm_pad_h}px; font-size: {s(13)}px; }}
            QTabBar::tab:selected {{
                background: {p.surface}; border-bottom: 2px solid {p.primary};
                color: {p.text_strong}; font-weight: bold;
            }}
            QTabBar::tab:!selected {{ background: {p.surface_variant}; color: {p.text_strong}; }}
        """)
        outer.addWidget(self._tabs, 1)

        self._err_label = QLabel()
        self._err_label.setStyleSheet(f"color: {p.error}; font-size: {theme_manager.font_size(13)}px;")
        self._err_label.setAlignment(Qt.AlignCenter)
        self._err_label.setWordWrap(True)
        outer.addWidget(self._err_label)
        outer.addSpacing(ds.space_xs)

        self._status_label = QLabel()
        self._status_label.setStyleSheet(f"font-size: {theme_manager.font_size(13)}px; color: {p.text_strong};")
        outer.addWidget(self._status_label)

        self.setLayout(outer)
        self._update_network_status()

    def eventFilter(self, obj, event):
        if obj is self._logo_label and event.type() == QEvent.MouseButtonDblClick:
            self._force_check.setVisible(True)
            if self._force_check.isChecked():
                self._tabs_forced = True
                self._apply_tab_visibility()
        return super().eventFilter(obj, event)

    @safe_slot("LoginWindow.on_force_toggle")
    def _on_force_toggle(self, checked: bool):
        self._tabs_forced = checked
        self._apply_tab_visibility()

    # ---- Intranet ----
    def _tab_intranet(self) -> QWidget:
        p = theme_manager.palette
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)

        email_lbl = QLabel(_("sec_login.email_label"))
        layout.addWidget(email_lbl)
        email = QLineEdit()
        email.setPlaceholderText(_("sec_login.email_placeholder"))
        email.setFixedHeight(ds.button_height)  # 52
        self._edt_i_email = email
        layout.addWidget(email)

        layout.addSpacing(ds.space_md)

        pwd_lbl = QLabel(_("sec_login.password_label"))
        layout.addWidget(pwd_lbl)
        pwd = QLineEdit()
        pwd.setPlaceholderText(_("sec_login.password_placeholder"))
        pwd.setEchoMode(QLineEdit().EchoMode.Password)
        pwd.setFixedHeight(ds.button_height)  # 52
        pwd.returnPressed.connect(self._on_intranet)
        self._edt_i_pwd = pwd
        layout.addWidget(pwd)

        layout.addSpacing(ds.space_lg)  # 32

        if self._term_label:
            term_lbl = QLabel(
                _("sec_login.term_label").format(label=self._term_label),
            )
            term_lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(term_lbl)
            layout.addSpacing(ds.space_sm + ds.space_xxs)  # 16

        btn = QPushButton(_("sec_login.connect_intranet"))
        btn.setObjectName("btnIntra")
        btn.setFixedSize(ds.sidebar_width - ds.space_md, ds.button_height)  # 213×52
        btn.clicked.connect(self._on_intranet)
        layout.addWidget(btn, 0, Qt.AlignCenter)

        layout.addSpacing(ds.space_md)
        info = QLabel(
            _("sec_login.info_intranet"),
        )
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        return w

    # ---- Cloud ----
    def _tab_cloud(self) -> QWidget:
        p = theme_manager.palette
        p = theme_manager.palette
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)

        info = QLabel(
            _("sec_login.info_cloud"),
        )
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        layout.addSpacing(ds.space_md + ds.space_xxs)  # 24

        if self._term_label:
            term_lbl = QLabel(
                _("sec_login.term_label").format(label=self._term_label),
            )
            term_lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(term_lbl)
            layout.addSpacing(ds.space_sm + ds.space_xxs)  # 16

        btn = QPushButton(_("sec_login.connect_google"))
        btn.setObjectName("btnGoogle")
        btn.setFixedSize(ds.sidebar_width - ds.space_md, ds.button_height)  # 213×52
        btn.clicked.connect(self._on_cloud)
        layout.addWidget(btn, 0, Qt.AlignCenter)

        layout.addSpacing(ds.space_sm + ds.space_xxs)  # 16
        info2 = QLabel(
            _("sec_login.info_oauth"),
        )
        info2.setAlignment(Qt.AlignCenter)
        layout.addWidget(info2)
        return w

    # ---- Auth ----
    @safe_slot("LoginWindow.on_intranet")
    def _on_intranet(self):
        email = self._edt_i_email.text().strip()
        pwd = self._edt_i_pwd.text()
        if not email or not pwd:
            self._show_error(_("sec_login.error.required"))
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
        email_key = email.lower()
        self._worker = _Worker(AuthManager.auth_intranet, email, pwd, parent=self)
        self._worker.done.connect(partial(self._on_auth_done, mode=ConnMode.INTRANET, rate_key=email_key))
        self._worker.start()

    @safe_slot("LoginWindow.on_cloud")
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
        self._worker = _Worker(AuthManager.auth_cloud, parent=self)
        self._worker.done.connect(partial(self._on_auth_done, mode=ConnMode.CLOUD, rate_key="cloud"))
        self._worker.start()

    def _check_secretary_exists(self, email: str) -> Tuple[bool, dict]:
        if not db.is_server_connected:
            return
        conn = db.server_conn
        if not conn:
            return False, {}
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT aec.id, aec.last_name, aec.first_name, aec.email
                FROM larcauth_aecuser aec
                WHERE LOWER(aec.email) = %s AND aec.type_secretary = TRUE AND aec.is_active = TRUE
                LIMIT 1
            """,
                (email.lower().strip(),),
            )
            row = cur.fetchone()
            if not row:
                return False, {}
            return True, {
                "user_id": row[0],
                "last_name": row[1],
                "first_name": row[2],
                "email": row[3],
            }
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_check_secretary_exists: {e}")
            return False, {}

    @safe_slot("LoginWindow.on_auth_done")
    def _on_auth_done(self, result, mode: ConnMode, rate_key: str):
        self._set_busy(False)
        ok, res, err = result
        if not ok:
            self._record_failure(rate_key)
            self._show_error(err or _("sec_login.error.auth_failed"))
            return

        if mode in (ConnMode.INTRANET, ConnMode.CLOUD):
            exists, infos = self._check_secretary_exists(res.email)
            if not exists:
                self._show_error(_("sec_login.error.not_secretary"))
                return
            res.user_id = infos["user_id"]
            res.full_name = f"{infos['first_name']} {infos['last_name']}"

            if not sqlite_init.init():
                self._show_error(_("sec_login.error.local_init"))
                return

            sqlite_init.set_module_config("secretary_name", res.full_name)
            sqlite_init.set_module_config("secretary_email", res.email)
            sqlite_init.set_module_config("secretary_id", str(res.user_id))

            self._apply_session(res, mode)

    def _apply_session(self, res: AuthResult, mode: ConnMode):
        session.user_id = res.user_id
        session.email = res.email
        session.full_name = res.full_name
        session.role = UserRole.SECR
        session.conn_mode = mode

        audit.login(session.user_id, session.full_name, mode.value)

        from LarcSecretaire.views.main_window import MainWindow

        self._main_window = MainWindow()
        self._main_window.showMaximized()
        self.close()

    # ---- Network ----
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
                f"<span style='color:{intra_color}'>{_('sec_login.status.intranet')}</span>"
                f"   <span style='color:{cloud_color}'>{_('sec_login.status.cloud')}</span>"
            )
            self._net_label.setTextFormat(Qt.RichText)
            self._net_label.setStyleSheet(f"font-weight: bold; font-size: {theme_manager.font_size(13)}px;")
            return

        if intra_ok:
            self._tabs.setTabVisible(0, True)
            self._tabs.setTabVisible(1, False)
            self._tabs.setCurrentIndex(0)
            self._err_label.setText("")
            self._net_label.setText(_("sec_login.status.intranet"))
            self._net_label.setStyleSheet(f"color: {p.success}; font-weight: bold; font-size: {theme_manager.font_size(13)}px;")

        elif internet_ok:
            self._tabs.setTabVisible(0, False)
            self._tabs.setTabVisible(1, True)
            self._tabs.setCurrentIndex(1)
            self._err_label.setText("")
            self._net_label.setText(_("sec_login.status.cloud"))
            self._net_label.setStyleSheet(f"color: {p.primary}; font-weight: bold; font-size: {theme_manager.font_size(13)}px;")

        else:
            self._tabs.setTabVisible(0, False)
            self._tabs.setTabVisible(1, False)
            self._err_label.setText(_("sec_login.status.error_title"))
            self._net_label.setText(_("sec_login.status.offline"))
            self._net_label.setStyleSheet(f"color: {p.text_disabled}; font-weight: bold; font-size: {theme_manager.font_size(13)}px;")

    @safe_slot("LoginWindow.update_network_status")
    def _update_network_status(self):
        self._net_status = detect_network()
        self._apply_tab_visibility()

    # ---- UI helpers ----
    def _show_error(self, msg: str):
        self._err_label.setText(msg)

    def _hide_error(self):
        self._err_label.setText("")

    def _set_busy(self, busy: bool):
        for btn in self.findChildren(QPushButton):
            btn.setEnabled(not busy)
        if busy:
            self._status_label.setText(_("sec_login.connecting"))
        else:
            self._status_label.setText("")
