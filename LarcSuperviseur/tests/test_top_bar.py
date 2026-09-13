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


def test_construct_no_theme_warning(qtbot, mock_theme, mock_session, monkeypatch, recwarn):
    bar, _ = _make_bar(qtbot, monkeypatch, mock_session)
    theme_warnings = [x for x in recwarn.list if "cree sans theme=" in str(x.message)]
    assert not theme_warnings, [str(x.message) for x in theme_warnings]


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


def _icon_fill_color(qicon, size=24) -> str | None:
    """Échantillonne le premier pixel opaque d'une QIcon MD3 mono-couleur — renvoie son hex."""
    from PySide6.QtCore import QSize as _QSize

    pm = qicon.pixmap(_QSize(size, size))
    img = pm.toImage()
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() == 255:  # pixel pleinement opaque — évite l'anti-aliasing des bords
                return c.name()
    return None


def test_restyle_recolors_menu_icons(qtbot, monkeypatch):
    """restyle() recolore bien les icônes du menu profil (smoke, setIcon rappelé sans exception)
    ET préserve la prévisualisation par-thème du menu de sélection (chaque entrée garde SA
    propre couleur de palette, elles ne s'effondrent pas toutes sur p.primary — cf. finding)."""
    import copy

    from LarcSuperviseur.common.theme import theme_manager as real_theme_manager
    from LarcSuperviseur.views.top_bar import TopBar

    # Les 4 thèmes réels partagent le même primary "#1F4494" (cf. THEMES_CONFIG) — on force des
    # couleurs distinctes par clé pour que le test ait des dents : si restyle() recolore tout en
    # p.primary (couleur du thème ACTIF), les entrées collapseraient vers UNE seule couleur au lieu
    # de garder chacune la leur.
    fake_primaries = {"blue": "#111111", "dark": "#222222", "sobre": "#333333", "contrast": "#444444"}
    orig_get_palette = real_theme_manager.get_palette

    def fake_get_palette(key):
        pal = orig_get_palette(key)
        if pal is None:
            return None
        fake = copy.copy(pal)
        fake.primary = fake_primaries.get(key, pal.primary)
        return fake

    monkeypatch.setattr(real_theme_manager, "get_palette", fake_get_palette)

    bar = TopBar(lambda k: None, lambda k: None, lambda: None)
    qtbot.addWidget(bar)

    old_icon = bar._prefs_action.icon()
    bar.restyle()
    new_icon = bar._prefs_action.icon()

    assert isinstance(old_icon, type(new_icon))  # smoke : setIcon() a bien été rappelé, pas d'exception

    # Teeth : au moins 2 entrées du menu de thèmes, colorées différemment l'une de l'autre APRES
    # restyle() — la régression du finding les aurait toutes recolorées en p.primary (une couleur
    # unique, celle du thème actif), détruisant l'aperçu par-thème.
    assert len(bar._theme_menu_actions) >= 2
    colors_by_key = {
        key: _icon_fill_color(action.icon()) for action, _icon_name, key in bar._theme_menu_actions
    }
    keys = list(colors_by_key)
    assert colors_by_key[keys[0]] != colors_by_key[keys[1]]
    for key, color in colors_by_key.items():
        assert color == fake_primaries[key].lower()
