"""Tests UI (qtbot) du wizard EventGenerator — cf. docs/debug/CR-2026-08-14 §4.2.

DB mockée vide : le fallback « Autres » (ajouté le 2026-08-14) garantit
un écran de mode non vide même sans données larcauth_type_event.
"""
from __future__ import annotations

import larccommon  # noqa: F401 — initialiser larccommon AVANT phibuilder (import circulaire connu)

from phibuilder.widgets import M3Button


def _make_dlg(qtbot, mock_db, mock_session, student_id=123):
    # Import DANS la fonction + re-liaison explicite au mock du test courant
    # (le module garde sinon le binding from-import du premier import).
    import LarcSuperviseur.views.dialogs.event_generator as eg

    eg.db = mock_db
    eg.session = mock_session
    dlg = eg.EventGenerator(student_id)
    qtbot.addWidget(dlg)
    return dlg


def test_construct_fallback_autres(qtbot, mock_db, mock_session, mock_theme):
    """Sans données, le wizard retombe sur le mode « Autres »."""
    dlg = _make_dlg(qtbot, mock_db, mock_session)
    assert dlg._modes == [("Autres", "autres")]
    labels = [b.text() or "" for b in dlg.findChildren(M3Button)]
    assert any("Autres" in t for t in labels)


def test_mode_click_advances_path(qtbot, mock_db, mock_session, mock_theme):
    """Clic sur un mode : _path avance et _mode est fixé."""
    dlg = _make_dlg(qtbot, mock_db, mock_session)
    btn = next(b for b in dlg.findChildren(M3Button) if "Autres" in (b.text() or ""))
    btn.click()
    assert dlg._path == ["Autres"]
    assert dlg._mode == "autres"


def test_breadcrumb_shown_after_step(qtbot, mock_db, mock_session, mock_theme):
    """Après un pas, le breadcrumb est visible (pas de crash, hiérarchie vide)."""
    dlg = _make_dlg(qtbot, mock_db, mock_session)
    btn = next(b for b in dlg.findChildren(M3Button) if "Autres" in (b.text() or ""))
    btn.click()
    assert not dlg._crumb_widget.isHidden()
