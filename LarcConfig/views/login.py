"""LarcConfig — Login (override _open_main_window)."""
from larccommon.login import LoginWindow as _Base
from larccommon.session import session
from LarcConfig.views.config_window import ConfigWindow


class LoginWindow(_Base):
    def _open_main_window(self):
        user = {
            'id': session.user_id,
            'email': session.email,
            'last_name': session.full_name.split()[-1] if session.full_name else '',
            'first_name': session.full_name.split()[0] if session.full_name else '',
        }
        ConfigWindow(user).showMaximized()  # fenêtre au maximum (1024×720 min)
        self.close()
