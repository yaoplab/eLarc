"""Tests du panneau Aide : sections intégrées, bouton guide, restyle."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from larcforge.ui.main_window import AppContext  # noqa: E402
from larcforge.ui.panels.help_panel import (  # noqa: E402
    _GUIDE_PATH, HelpPanel,
)
from larcforge.ui.profiles import ProfilesStore  # noqa: E402


@pytest.fixture
def panel(qtbot, tmp_path):
    store = ProfilesStore(path=tmp_path / "cfg.json")
    ctx = AppContext(root=str(tmp_path), timeout=30, store=store,
                     config=store.load())
    p = HelpPanel(ctx)
    p.show()
    qtbot.addWidget(p)
    return p


def test_guide_debutant_existe():
    assert _GUIDE_PATH.is_file()
    text = _GUIDE_PATH.read_text(encoding="utf-8")
    assert "LarcForge" in text
    assert "Vérifications" in text
    assert "Registre des issues" in text
    assert "Configuration" in text


def test_sections_integrees(panel):
    # 5 cartes de sections, chacune avec un titre et un corps
    assert len(panel._cards) == 5
    first_card = panel._cards[0]
    cl = first_card.content_layout()
    title = cl.itemAt(0).widget()
    assert "tableau de bord" in title.text().lower()


def test_bouton_ouvre_guide(panel, qtbot, monkeypatch):
    opened = []

    class _FakeUrl:
        pass

    def fake_open(url):
        opened.append(url.toLocalFile())
        return True

    monkeypatch.setattr("PySide6.QtGui.QDesktopServices.openUrl", fake_open)
    panel._open_guide()
    assert opened and Path(opened[0]) == _GUIDE_PATH


def test_reload_sans_effet(panel):
    panel.reload()  # ne doit pas crasher


def test_restyle_sans_crash(panel):
    panel._restyle()
