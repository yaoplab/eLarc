"""Tests UI (qtbot) de MainWindow — cf. docs/debug/CR-2026-08-14 §4.2.

Smoke tests : construction complète sur DB mockée + chemins thème/période/
validation. La donnée est vide (cursors mockés) — on vérifie l'absence de crash
et la présence des sous-composants.
"""
from __future__ import annotations

import larccommon  # noqa: F401 — initialiser larccommon AVANT phibuilder (import circulaire connu)


def _make_window(qtbot, mock_db, mock_session):
    # Import DANS la fonction + re-liaison explicite : le module garde le
    # binding from-import du PREMIER import (ou est re-lié au vrai db par le
    # teardown du conftest) — on fixe ici le mock du test courant.
    import LarcSuperviseur.views.main_window as mw

    mw.db = mock_db
    mw.session = mock_session
    w = mw.MainWindow()
    qtbot.addWidget(w)
    return w


def test_main_window_constructs(qtbot, mock_db, mock_session, mock_theme):
    w = _make_window(qtbot, mock_db, mock_session)
    assert w.windowTitle() != ""
    assert hasattr(w, "_top_bar")
    assert hasattr(w, "_sidebar")
    assert hasattr(w, "_student_detail")
    assert hasattr(w, "_actions")  # fix 2026-08-14 : initialisé dans __init__


def test_theme_change_no_crash(qtbot, mock_db, mock_session, mock_theme):
    w = _make_window(qtbot, mock_db, mock_session)
    w._restyle()


def test_period_click_no_crash(qtbot, mock_db, mock_session, mock_theme):
    w = _make_window(qtbot, mock_db, mock_session)
    w._on_period_clicked("day")


def test_toggle_validation_mock_db(qtbot, mock_db, mock_session, mock_theme):
    w = _make_window(qtbot, mock_db, mock_session)
    w._toggle_validation(42)  # méthode void — vérifie UPDATE + commit
    mc = mock_db.server_conn.cursor.return_value
    updates = [
        c.args for c in mc.execute.call_args_list if "UPDATE student_event" in c.args[0]
    ]
    assert updates, "aucun UPDATE student_event émis"
    assert updates[0][1] == (1, 42)  # session.user_id + event_id
    assert mock_db.server_conn.commit.called


def test_edit_event_dialog_no_theme_warning(qtbot, mock_db, mock_session, mock_theme, recwarn, monkeypatch):
    from datetime import datetime
    import warnings

    from PySide6.QtWidgets import QDialog

    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.Rejected)

    w = _make_window(qtbot, mock_db, mock_session)
    fake = mock_db.server_conn.cursor.return_value
    fake.fetchone.return_value = (
        "Absence cours", None, datetime(2026, 7, 8, 8, 30),
        "Salle de cours", "Maths", "", "Dupont Jean",
    )
    fake.fetchall.return_value = [("Absence cours",), ("Sortie",)]
    recwarn.clear()

    # pytest's recwarn fixture uses the "default" warning filter, which dedups
    # by (message, category, module, lineno) — NOT reset by recwarn.clear()
    # (only pytest's own captured list is cleared). _make_window() above builds
    # SidebarWidget (LarcCommon, out-of-scope), whose M3Button already fired the
    # "cree sans theme=" warning from button.py's _update_style() BEFORE
    # recwarn.clear(). Without "always", a later M3Button warning from this
    # exact same call site — e.g. a regression on main_events.py's own
    # save_btn/cancel_btn — would be silently deduped against that earlier
    # warning and never reach recwarn.list. See commit 7be90be for the
    # identical mechanism found in test_event_dialog.py.
    warnings.simplefilter("always")

    w._edit_event(42)

    # _edit_event constructs EventTypeSelectorWidget (LarcCommon/larccommon/
    # dialogs/event_type_selector.py). That widget used to have 3 of its own
    # unfixed theme= sites (M3TextField/M3Label/M3Button), which required
    # tolerating exactly those 3 out-of-scope warnings here. It was fixed on
    # 2026-09-11 (commit 166f370) — EventTypeSelectorWidget now contributes 0
    # warnings, so this test asserts a plain empty list like the other tasks'
    # tests. See test_event_dialog.py::test_no_theme_warning's git history for
    # the class-count workaround pattern if this regresses upstream again.
    theme_warnings = [str(x.message) for x in recwarn.list if "cree sans theme=" in str(x.message)]
    assert not theme_warnings, theme_warnings


def test_show_event_context_menu_no_theme_warning(qtbot, mock_db, mock_session, mock_theme, recwarn, monkeypatch):
    import warnings
    from unittest.mock import MagicMock

    from PySide6.QtCore import QPoint
    from phibuilder.widgets import M3Menu

    # M3Menu extends QMenu, not QDialog — patch M3Menu.exec (not QDialog.exec,
    # which the other tests in this file patch) to avoid a blocking modal.
    monkeypatch.setattr(M3Menu, "exec", lambda self, *a, **kw: None)

    w = _make_window(qtbot, mock_db, mock_session)

    # A MagicMock table (same pattern as
    # TestEventActionsGetEventIdFromTable.test_returns_id_from_selected_row in
    # test_event_actions.py) — a real M3TableWidget's setCurrentCell() does not
    # reliably update currentRow() off-screen/headless in this environment, so
    # a real widget makes _get_event_id_from_table short-circuit on
    # `if not eid: return` before ever reaching the M3Menu construction this
    # test targets. table.viewport().mapToGlobal(pos) on a MagicMock resolves
    # harmlessly since menu.exec is patched above and never inspects it.
    table = MagicMock()
    table.currentRow.return_value = 0
    item = MagicMock()
    item.text.return_value = "42"
    table.item.return_value = item

    # Avoid depending on DB cursor/description plumbing: EventActions.get_event_by_id
    # is a thin DB read whose exact shape is exercised elsewhere (test_event_actions.py);
    # here we only need _show_event_context_menu to not short-circuit before
    # `menu = M3Menu(theme=theme_manager.phi_theme, parent=self)`.
    monkeypatch.setattr(w._actions, "get_event_by_id", lambda eid: None)

    recwarn.clear()

    # Same dedup pitfall as test_edit_event_dialog_no_theme_warning above, but
    # for a different call site: TopBar (built during _make_window, as part of
    # MainWindow.__init__) constructs self._theme_menu = M3Menu() with NO
    # theme= (views/top_bar.py) — an out-of-scope, pre-existing defect not
    # part of this branch's fix list. That M3Menu() firing during window
    # construction, before recwarn.clear(), would silently dedup-suppress a
    # genuine regression on main_events.py's own
    # `menu = M3Menu(theme=theme_manager.phi_theme, parent=self)` site without
    # "always" (identical mechanism to commit 7be90be).
    warnings.simplefilter("always")

    w._show_event_context_menu(table, QPoint(0, 0))

    theme_warnings = [x for x in recwarn.list if "cree sans theme=" in str(x.message)]
    assert not theme_warnings, [str(x.message) for x in theme_warnings]
