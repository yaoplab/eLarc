import hashlib
import os
import time
from typing import Optional

from larccommon.design_system import ds
from larccommon.l10n import Translator, _
from larccommon.safe_slot import safe_slot
from phibuilder.widgets import M3Button, M3Card, M3Label, M3TabWidget, M3TextField
from phibuilder.widgets.card import CardVariant
from PySide6.QtCore import QEvent, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QProgressDialog,
    QVBoxLayout,
    QWidget,
)

from LarcSuperviseur.common.app_config import app_config
from LarcSuperviseur.common.auth import OAuth2Manager
from LarcSuperviseur.common.database import db
from LarcSuperviseur.common.logger import log
from LarcSuperviseur.common.network import detect_network
from LarcSuperviseur.common.session import ConnMode, UserRole, session
from LarcSuperviseur.common.theme import QssHelper, theme_manager
from LarcSuperviseur.common.trace import trace


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
            raise RuntimeError(_("login.too_many_attempts").format(seconds=remaining))
        if entry and entry["until"] <= now:
            cls._login_attempts.pop(key, None)
        return True

    @classmethod
    def _record_failure(cls, key: str):
        entry = cls._login_attempts.setdefault(key, {"count": 0, "until": 0})
        entry["count"] += 1
        if entry["count"] >= 5:
            entry["until"] = time.time() + 30

    def __init__(self):
        super().__init__()
        self._worker: Optional[_Worker] = None
        self._tabs_forced = False
        import os

        lang = os.environ.get("LARC_LANG", "fr")
        trans = Translator.instance(lang)
        trans.load_dir(Translator.l10n_dir())
        trace(f" LoginWindow.__init__: langue={lang}")
        self.setWindowTitle(_("app.title.superviseur") + " - " + _("login.title"))
        trace(" LoginWindow.__init__: démarre")

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
                WHERE ay.s_id = (SELECT MAX(s_id) FROM larcauth_academicyear)
                  AND t.trim = ay.current_term_number
                  AND t.fk_language_id = %s
                ORDER BY t.id DESC
                LIMIT 1
            """, (getattr(session, "fk_language", 2),))
            r = cur.fetchone()
            return r[0] if r else ""
        except Exception as e:
            from larccommon.error_reporting import get_reporter
            get_reporter().report_exception()
            log(f"_get_current_term_label: {e}")
            return ""

    @staticmethod
    def _label(text: str = "", style: str = "body_medium", color: str = "") -> M3Label:
        """M3Label avec style typo M3 + couleur explicite (évite que le style M3
        par défaut n'écrase silencieusement les couleurs sémantiques du QSS)."""
        lbl = M3Label(text, theme=theme_manager.phi_theme, style=style)
        if color:
            lbl.set_color(color)
        return lbl

    def _init_ui(self):
        self.setObjectName("root")
        self.setStyleSheet(QssHelper.login_qss(theme_manager.palette))
        W = 420
        H = int(W * 1.618033988749895)
        self.setFixedSize(W, H)

        phi = theme_manager.phi_theme
        p = theme_manager.palette

        outer = QVBoxLayout()
        outer.setContentsMargins(
            theme_manager.image.theme_btn,  # 34px
            ds.table_row_min,  # 21px
            theme_manager.image.theme_btn,
            ds.table_row_min,
        )
        outer.setSpacing(0)

        card = M3Card(theme=phi, variant=CardVariant.ELEVATED)
        cl = card.content_layout()
        cl.setSpacing(0)

        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "img", "logoAEC.png")
        self._logo_label = self._label()
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path)
            self._logo_pixmap = pix.scaledToHeight(
                theme_manager.image.logo, Qt.SmoothTransformation
            )
            self._logo_label.setPixmap(self._logo_pixmap)
        else:
            self._logo_pixmap = None
            self._logo_label.setText("[Logo]")
        self._logo_label.setAlignment(Qt.AlignCenter)
        self._logo_label.setCursor(Qt.PointingHandCursor)
        self._logo_label.installEventFilter(self)
        cl.addWidget(self._logo_label)
        cl.addSpacing(21)

        title = self._label(_("login.superviseur_title"), "title_large", p.text_strong)
        title.setAlignment(Qt.AlignCenter)
        cl.addWidget(title)
        cl.addSpacing(8)

        sub = self._label(_("login.superviseur_subtitle"), "body_medium", p.text_soft)
        sub.setAlignment(Qt.AlignCenter)
        cl.addWidget(sub)
        cl.addSpacing(21)

        self._net_label = self._label(style="body_medium", color=p.text_soft)
        self._net_label.setAlignment(Qt.AlignCenter)
        cl.addWidget(self._net_label)
        cl.addSpacing(21)

        self._force_check = QCheckBox(_("login.choose_connection"))
        self._force_check.setVisible(False)
        self._force_check.toggled.connect(self._on_force_toggle)
        cl.addWidget(self._force_check, 0, Qt.AlignCenter)
        cl.addSpacing(21)

        self._tabs = M3TabWidget(theme=phi)
        self._tab_intra_widget = self._tab_intranet()
        self._tab_cloud_widget = self._tab_cloud()
        self._tabs.addTab(self._tab_intra_widget, _("login.tab_intranet"))
        self._tabs.addTab(self._tab_cloud_widget, _("login.tab_cloud"))
        cl.addWidget(self._tabs, 1)

        self._err_label = self._label(style="body_medium", color=p.error)
        self._err_label.setAlignment(Qt.AlignCenter)
        self._err_label.setWordWrap(True)
        cl.addWidget(self._err_label)
        cl.addSpacing(8)

        self._status_label = self._label(style="body_medium", color=p.text_soft)
        cl.addWidget(self._status_label)

        outer.addWidget(card, 1)
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

    @safe_slot("LoginWindow.on_force_toggle")
    def _on_force_toggle(self, checked: bool):
        self._tabs_forced = checked
        self._apply_tab_visibility()

    def _tab_intranet(self) -> QWidget:
        phi = theme_manager.phi_theme
        p = theme_manager.palette
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)

        email_lbl = self._label(_("login.email_label"), "body_medium", p.text_strong)
        layout.addWidget(email_lbl)
        email = M3TextField(theme=phi)
        email.setPlaceholderText(_("login.email_placeholder"))
        email.setFixedHeight(ds.field_height)
        self._edt_i_email = email
        layout.addWidget(email)

        layout.addSpacing(21)

        pwd_lbl = self._label(_("login.password_label"), "body_medium", p.text_strong)
        layout.addWidget(pwd_lbl)
        pwd = M3TextField(theme=phi)
        pwd.setEchoMode(M3TextField.Password)
        pwd.setPlaceholderText(_("login.password_placeholder"))
        pwd.setFixedHeight(ds.field_height)
        pwd.returnPressed.connect(self._on_intranet)
        self._edt_i_pwd = pwd
        layout.addWidget(pwd)

        layout.addSpacing(34)

        if self._term_label:
            term_lbl = self._label(
                _("login.term_label").format(label=self._term_label), "body_medium", p.text_soft
            )
            term_lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(term_lbl)
            layout.addSpacing(16)

        btn = M3Button(_("login.connect_intranet"), theme=phi)
        btn.setFixedSize(ds.window_width * 7 // 40, ds.logo_small)  # 210×55
        btn.clicked.connect(self._on_intranet)
        layout.addWidget(btn, 0, Qt.AlignCenter)

        layout.addSpacing(21)
        info = self._label(_("login.info_intranet"), "body_medium", p.text_soft)
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        return w

    def _tab_cloud(self) -> QWidget:
        phi = theme_manager.phi_theme
        p = theme_manager.palette
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)

        info = self._label(_("login.info_cloud"), "body_medium", p.text_soft)
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        layout.addSpacing(24)

        if self._term_label:
            term_lbl = self._label(
                _("login.term_label").format(label=self._term_label), "body_medium", p.text_soft
            )
            term_lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(term_lbl)
            layout.addSpacing(16)

        # accent_color préserve le rouge de marque Google (identique au QSS d'origine)
        btn = M3Button(_("login.connect_google"), theme=phi, accent_color="#DB4437")  # clé manquante dans fr.json
        btn.setFixedSize(ds.window_width * 7 // 40, ds.logo_small)  # 210×55
        btn.clicked.connect(self._on_cloud)
        layout.addWidget(btn, 0, Qt.AlignCenter)

        layout.addSpacing(16)
        info2 = M3Label(_("login.info_oauth"), theme=phi)
        info2.setObjectName("infoLbl")
        info2.setAlignment(Qt.AlignCenter)
        layout.addWidget(info2)
        return w

    @safe_slot("LoginWindow.on_intranet")
    def _on_intranet(self):
        trace("_on_intranet: START")
        email = self._edt_i_email.text().strip()
        password = self._edt_i_pwd.text()
        if not email or not password:
            trace("_on_intranet: email or password empty")
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

        ok = db.connect_intranet()
        trace(f" _on_intranet: connect_intranet={ok}")
        if not ok:
            self._set_busy(False)
            self._show_error(_("login.error.intranet"))
            return

        conn = db.server_conn
        trace(f" _on_intranet: server_conn={conn is not None}")
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, first_name, last_name, email, password, "
                "type_director, type_coordonator, type_supervisor "
                "FROM public.larcauth_aecuser WHERE email = %s",
                (email,),
            )
            row = cur.fetchone()
            if row is None:
                self._set_busy(False)
                self._show_error(_("login.error.user_not_found"))
                db.disconnect_all()
                return

            user_id, first_name, last_name, email, pwd_hash, is_dir, is_coord, is_sup = row

            pass_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
            if pwd_hash and pwd_hash != pass_hash:
                self._set_busy(False)
                self._show_error(_("login.error.wrong_password"))
                db.disconnect_all()
                return

            if not (is_dir or is_coord or is_sup):
                self._set_busy(False)
                self._show_error(_("login.error.restricted"))
                db.disconnect_all()
                return

            if is_dir:
                role = UserRole.ADMIN
            elif is_coord:
                role = UserRole.COORD
            else:
                role = UserRole.SUPERVISEUR

            import os

            # Lire la langue preferee de l'utilisateur
            user_lang_id = 2
            try:
                cur.execute("SELECT fk_language FROM larcauth_aecuser WHERE id = %s", (user_id,))
                r = cur.fetchone()
                if r:
                    user_lang_id = int(r[0])
            except Exception as e:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                pass  # fk_language non critique, defaut fr
            user_lang = "en" if user_lang_id == 1 else "fr"
            lang = os.environ.get("LARC_LANG", user_lang)
            trans = Translator.instance(lang)
            trans.reload(Translator.l10n_dir())

            session.user_id = user_id
            session.email = email
            session.full_name = f"{first_name} {last_name}"
            session.role = role
            session.conn_mode = ConnMode.INTRANET
            session.is_authenticated = True
            session.fk_language = user_lang_id

            try:
                cur.execute("""
                    SELECT t.id, t.label FROM larcauth_term t, larcauth_academicyear ay
                    WHERE ay.s_id = (SELECT MAX(s_id) FROM larcauth_academicyear)
                      AND t.trim = ay.current_term_number
                      AND t.fk_language_id = %s
                    ORDER BY t.id DESC
                    LIMIT 1
                """, (getattr(session, "fk_language", 2),))
                r = cur.fetchone()
                if r:
                    session.term_id = int(r[0])
                    session.term_label = r[1]
            except Exception as e:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                log(f"set_term non critique: {e}")
            log(f"Connexion Intranet : {session.full_name} ({role.value})")
            trace(" _on_intranet: session OK, appel _open_main_window")
            self._open_main_window()
            trace(" _open_main_window terminé")

        except Exception as e:
            self._set_busy(False)
            log(f"_on_intranet: {e}")
            try:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception(e, context={"zone": "login_intranet"})
            except Exception:
                from larccommon.error_reporting import get_reporter
                get_reporter().report_exception()
                pass  # reporting non bloquant
            self._show_error(str(e))
            db.disconnect_all()

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
        self._worker = _Worker(OAuth2Manager.authenticate, parent=self)
        self._worker.done.connect(self._on_cloud_done)
        self._worker.start()

    @safe_slot("LoginWindow.on_cloud_done")
    def _on_cloud_done(self, result):
        self._set_busy(False)
        ok, res, err = result
        if not ok:
            self._record_failure("cloud")
            self._show_error(err or _("login.error.auth_failed"))
            return

        if res.role not in (UserRole.SUPERVISEUR, UserRole.COORD, UserRole.ADMIN):
            self._show_error(_("login.error.unauthorized"))
            return

        session.user_id = res.user_id
        session.email = res.email
        session.full_name = res.full_name
        session.role = res.role
        session.conn_mode = ConnMode.CLOUD
        session.is_authenticated = True
        session.term_id = res.term_id
        session.term_label = res.term_label
        session.fk_language = res.fk_language

        log(f"Connexion Cloud : {session.full_name} ({res.role.value})")
        self._open_main_window()

    def _open_main_window(self):
        from LarcSuperviseur.common.photos import PhotoPreloader, get_uncached_ids
        from LarcSuperviseur.views.main_window import MainWindow

        student_ids = get_uncached_ids()
        if student_ids:
            progress = QProgressDialog(
                _("login.photo_preparation"), _("common.button.cancel"), 0, len(student_ids), self
            )
            progress.setWindowTitle(_("login.progress_photos"))
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)

            preloader = PhotoPreloader(student_ids, self)
            preloader.progress.connect(lambda cur, total, sid: progress.setValue(cur))
            preloader.done.connect(lambda loaded, failed: progress.close())
            progress.canceled.connect(preloader.cancel)
            self._target_mw = MainWindow
            preloader.finished.connect(self._on_preloader_done)
            preloader.finished.connect(preloader.deleteLater)
            preloader.start()
            self._preloader = preloader
        else:
            self._do_open_main_window(MainWindow)

    @safe_slot("LoginWindow.on_preloader_done")
    def _on_preloader_done(self):
        self._do_open_main_window(self._target_mw)

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
                f"<span style='color:{intra_color}'>{_('login.status.intranet')}</span>"
                f"   "
                f"<span style='color:{cloud_color}'>{_('login.status.cloud')}</span>"
            )
            self._net_label.setTextFormat(Qt.RichText)
            self._net_label.setStyleSheet(
                f"font-weight: bold; font-size: {theme_manager.font_size(13)}px;"
            )
            return

        if intra_ok and internet_ok:
            self._tabs.setTabVisible(0, True)
            self._tabs.setTabVisible(1, False)
            self._tabs.setCurrentIndex(0)
            self._err_label.setText("")
            self._net_label.setText(_("login.status.intranet"))
            self._net_label.setStyleSheet(
                f"color: {p.success}; font-weight: bold; font-size: {theme_manager.font_size(13)}px;"
            )

        elif internet_ok and not intra_ok:
            self._tabs.setTabVisible(0, False)
            self._tabs.setTabVisible(1, True)
            self._tabs.setCurrentIndex(1)
            self._err_label.setText("")
            self._net_label.setText(_("login.status.cloud"))
            self._net_label.setStyleSheet(
                f"color: {p.primary}; font-weight: bold; font-size: {theme_manager.font_size(13)}px;"
            )

        elif intra_ok and not internet_ok:
            self._tabs.setTabVisible(0, True)
            self._tabs.setTabVisible(1, False)
            self._tabs.setCurrentIndex(0)
            self._err_label.setText("")
            self._net_label.setText(_("login.status.intranet"))
            self._net_label.setStyleSheet(
                f"color: {p.success}; font-weight: bold; font-size: {theme_manager.font_size(13)}px;"
            )

        else:
            self._tabs.setTabVisible(0, False)
            self._tabs.setTabVisible(1, False)
            self._err_label.setText(_("login.status.error"))
            self._net_label.setText(_("login.status.offline"))
            self._net_label.setStyleSheet(
                f"color: {p.text_disabled}; font-weight: bold; font-size: {theme_manager.font_size(13)}px;"
            )

    @safe_slot("LoginWindow.update_network_status")
    def _update_network_status(self):
        self._net_status = detect_network()
        self._apply_tab_visibility()

    def _show_error(self, msg: str):
        self._err_label.setText(msg)

    def _hide_error(self):
        self._err_label.setText("")

    def _set_busy(self, busy: bool):
        for btn in self.findChildren(M3Button):
            btn.setEnabled(not busy)
        if busy:
            self._status_label.setText(_("login.connecting"))
        else:
            self._status_label.setText("")
