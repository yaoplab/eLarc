"""Tests UI (qtbot) de LoginWindow — cf. docs/debug/CR-2026-08-14 §4.2.

Construction avec DB mockée et réseau neutralisé. Le flux d'authentification
réel (auth.py, OAuth2) reste couvert par lint_auth_checker / tests d'intégration.
"""
from __future__ import annotations

import larccommon  # noqa: F401 — initialiser larccommon AVANT phibuilder (import circulaire connu)


def test_login_constructs(qtbot, mock_db, mock_session, mock_theme, monkeypatch):
    # Import DANS la fonction + re-liaison explicite au mock du test courant.
    import LarcSuperviseur.views.login as lg

    lg.db = mock_db
    lg.session = mock_session
    monkeypatch.setattr(
        "LarcSuperviseur.views.login.detect_network",
        lambda: (True, False),
        raising=False,
    )
    w = lg.LoginWindow()
    qtbot.addWidget(w)
    assert w.windowTitle() != ""
    # DB mockée vide → pas de libellé de terme, pas de crash
    assert w._term_label == ""


def test_rate_limit_logic(monkeypatch):
    """_check_rate_limit/_record_failure : 5 échecs → blocage 30 s."""
    from LarcSuperviseur.views.login import LoginWindow

    LoginWindow._login_attempts.clear()
    for _ in range(5):
        LoginWindow._record_failure("test@x")
    try:
        LoginWindow._check_rate_limit("test@x")
        raised = False
    except RuntimeError:
        raised = True
    assert raised
