"""LarcDocs — Login (override _open_main_window)."""
from larccommon.login import LoginWindow as _Base
from larccommon.session import session
from LarcDocs.views.docs_window import DocsWindow


class LoginWindow(_Base):
    def _open_main_window(self):
        user = {
            'id': session.user_id,
            'email': session.email,
            'last_name': session.full_name.split()[-1] if session.full_name else '',
            'first_name': session.full_name.split()[0] if session.full_name else '',
        }
        DocsWindow(user).show()
        self.close()

