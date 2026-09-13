"""Tests UI (qtbot) de StudentDetail — cf. docs/debug/CR-2026-08-14 §4.2.

DataLoader remplacé par un stub : comportement de load() vérifié sans DB.
"""
from __future__ import annotations

from datetime import datetime

import larccommon  # noqa: F401 — initialiser larccommon AVANT phibuilder (import circulaire connu)

from PySide6.QtCore import QDate


class _StubLoader:
    """DataLoader de substitution : élève connu + 1 événement (creator NULL)."""

    def get_student_info(self, student_id):
        return {"first_name": "Jean", "last_name": "Dupont", "class_label": "PEI-1"}

    def get_student_kpis(self, student_id, date_from, date_to):
        return {"abs_count": 2, "exit_count": 1, "total": 5}

    def get_student_events(self, student_id, limit=20, date_from=None, date_to=None):
        return [
            {
                "event_id": 51,
                "event_type": "Absence cours",
                "lieu_label": "Salle de cours",
                "subject_label": "Maths",
                "event_at": datetime(2026, 7, 8, 8, 30),
                "note": "",
                "creator": None,  # LEFT JOIN → NULL : ne doit pas crasher (fix 2026-08-14)
                "validated_by": None,
            }
        ]


class _EmptyLoader(_StubLoader):
    def get_student_info(self, student_id):
        return {}


def _make_detail(qtbot, monkeypatch, mock_db, mock_session, loader=_StubLoader):
    monkeypatch.setattr(
        "LarcSuperviseur.views.panels.student_detail.DataLoader", loader
    )
    import LarcSuperviseur.views.panels.student_detail as sd

    sd.db = mock_db
    sd.session = mock_session
    d = sd.StudentDetail()
    qtbot.addWidget(d)
    return d


def test_construct_no_theme_warning(qtbot, mock_db, mock_session, mock_theme, monkeypatch, recwarn):
    _make_detail(qtbot, monkeypatch, mock_db, mock_session)
    theme_warnings = [x for x in recwarn.list if "cree sans theme=" in str(x.message)]
    assert not theme_warnings, [str(x.message) for x in theme_warnings]


def test_construct_empty_state(qtbot, mock_db, mock_session, mock_theme, monkeypatch):
    d = _make_detail(qtbot, monkeypatch, mock_db, mock_session)
    assert d._student_id == 0


def test_period_dates_three_months(qtbot, mock_db, mock_session, mock_theme, monkeypatch):
    d = _make_detail(qtbot, monkeypatch, mock_db, mock_session)
    date_from, date_to = d._period_dates()
    assert date_from < date_to
    assert date_to == QDate.currentDate().toString("yyyy-MM-dd")


def test_restyle_all_updates_identity_labels(qtbot, mock_db, mock_session, mock_theme, monkeypatch):
    # mock_theme est INOPERANT ici : il patch l'attribut module
    # "LarcSuperviseur.common.theme.theme_manager", mais student_detail.py fait
    # `from LarcSuperviseur.common.theme import theme_manager` (ligne 42) — ce
    # nom reste lie au VRAI singleton ThemeManager pour tout le process. On
    # mute donc directement les attributs de la VRAIE Palette active et on
    # emet le VRAI signal ds.theme_changed (meme pattern que
    # test_event_dialog.py::test_restyle_all_updates_colors_on_theme_changed).
    #
    # NB : QWidget.styleSheet() ne renvoie QUE le style local pose via
    # setStyleSheet() sur ce widget precis -- jamais le QSS hérité par cascade
    # ancestor (ex. QLabel#sd_name_lbl {{...}} dans le _STYLE du panel parent).
    # Interroger detail._sd_name_lbl.styleSheet() serait donc toujours "" une
    # fois le fix applique (labels sans setStyleSheet local) : on verifie donc
    # a la fois (a) que les labels n'ont plus de style LOCAL et (b) que la
    # regle #objectName correspondante existe bel et bien dans le _STYLE du
    # panel et qu'elle est mise a jour par _restyle_all().
    from larccommon.design_system import ds
    from LarcSuperviseur.views.panels import student_detail as sd_mod

    d = _make_detail(qtbot, monkeypatch, mock_db, mock_session)

    real_palette = sd_mod.theme_manager.palette
    old_text_strong = real_palette.text_strong

    # Pas de style local sur les labels : ils dependent de la cascade ancestor.
    assert d._sd_name_lbl.styleSheet() == ""
    assert d._sd_class_lbl.styleSheet() == ""
    assert d._sd_id_lbl.styleSheet() == ""

    old_style = d.styleSheet()
    assert "QLabel#sd_name_lbl" in old_style
    assert "QLabel#sd_class_lbl" in old_style
    assert "QLabel#sd_id_lbl" in old_style
    assert old_text_strong in old_style

    monkeypatch.setattr(real_palette, "text_strong", "#123456")

    ds.theme_changed.emit()  # signal reel : prouve que _restyle_all() est bien connecte

    new_style = d.styleSheet()
    assert new_style != old_style
    assert "QLabel#sd_name_lbl" in new_style
    assert "QLabel#sd_class_lbl" in new_style
    assert "QLabel#sd_id_lbl" in new_style
    assert "#123456" in new_style
    assert old_text_strong not in new_style


def test_load_populates_ui(qtbot, mock_db, mock_session, mock_theme, monkeypatch):
    d = _make_detail(qtbot, monkeypatch, mock_db, mock_session)
    d.load(123)
    assert d._sd_name_lbl.text() == "Jean Dupont"
    assert d._sd_class_lbl.text() == "PEI-1"
    assert d._sd_id_lbl.text() == "ID : 123"
    assert d._sd_kpis["abs"].text() == "2"
    assert d._sd_kpis["exit"].text() == "1"
    assert d._sd_kpis["total"].text() == "5"
    assert d._sd_events.rowCount() == 1
    assert "Absence cours" in d._sd_events.item(0, 1).text()
    assert d._sd_placeholder.isHidden()


def test_load_unknown_student_keeps_empty(
    qtbot, mock_db, mock_session, mock_theme, monkeypatch
):
    d = _make_detail(qtbot, monkeypatch, mock_db, mock_session, loader=_EmptyLoader)
    d.load(999)
    assert d._student_id == 999
    assert d._sd_events.rowCount() == 0
