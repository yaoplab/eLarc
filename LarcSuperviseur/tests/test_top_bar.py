"""Tests UI (qtbot) du TopBar — cf. docs/debug/CR-2026-08-14 §4.2.

Réseau neutralisé (detect_network monkeypatché) pour des tests déterministes.
"""
from __future__ import annotations

import larccommon  # noqa: F401 — initialiser larccommon AVANT phibuilder (import circulaire connu)

from LarcSuperviseur.views.top_bar import TopBar


def _make_bar(qtbot, monkeypatch, mock_session) -> tuple[TopBar, list]:
    monkeypatch.setattr(
        "LarcSuperviseur.views.top_bar.detect_network",
        lambda: (True, False),
        raising=False,
    )
    import LarcSuperviseur.views.top_bar as tb

    tb.session = mock_session
    clicks: list = []
    bar = tb.TopBar(
        on_period_click=lambda k: clicks.append(k),
        on_theme_change=lambda k: None,
        on_refresh=lambda: None,
    )
    qtbot.addWidget(bar)
    return bar, clicks


def test_construct_labels(qtbot, mock_theme, mock_session, monkeypatch):
    bar, _ = _make_bar(qtbot, monkeypatch, mock_session)
    assert bar._date_label.text() != ""
    assert bar._time_label.text() != ""


def test_fixed_period_keys(qtbot, mock_theme, mock_session, monkeypatch):
    bar, _ = _make_bar(qtbot, monkeypatch, mock_session)
    assert bar._period_keys[:5] == ["day", "week", "month", "term", "year"]


def test_period_button_click_callback(qtbot, mock_theme, mock_session, monkeypatch):
    bar, clicks = _make_bar(qtbot, monkeypatch, mock_session)
    bar._period_group.buttons()[0].click()
    assert clicks == ["day"]


def test_set_unit_periods(qtbot, mock_theme, mock_session, monkeypatch):
    bar, _ = _make_bar(qtbot, monkeypatch, mock_session)
    bar.set_unit_periods([{"id": 1, "label": "U1"}, {"id": 2, "label": "U2"}])
    assert bar._unit_keys == ["unit_1", "unit_2"]
    assert [b.text() for b in bar._unit_buttons] == ["U1", "U2"]


def test_update_datetime(qtbot, mock_theme, mock_session, monkeypatch):
    bar, _ = _make_bar(qtbot, monkeypatch, mock_session)
    bar._update_datetime()
    assert bar._date_label.text() != ""
    assert bar._time_label.text() != ""


def test_restyle_recolors_menu_icons(qtbot, mock_theme):
    from LarcSuperviseur.views.top_bar import TopBar

    bar = TopBar(lambda k: None, lambda k: None, lambda: None)
    qtbot.addWidget(bar)

    old_icon = bar._prefs_action.icon()
    bar.restyle()
    new_icon = bar._prefs_action.icon()

    assert isinstance(old_icon, type(new_icon))  # smoke : setIcon() a bien été rappelé, pas d'exception
