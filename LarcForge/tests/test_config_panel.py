"""Tests du panneau Configuration : racine, marque, profils DB et vérification.

La persistance (ui_config.json) passe par ProfilesStore(path=tmp_path) —
aucun fichier réel n'est touché. pg.connect est mocké pour « Tester la
connexion ».
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("PySide6")

from larcforge import database as pg  # noqa: E402
from larcforge.ui.main_window import AppContext  # noqa: E402
from larcforge.ui.panels.config_panel import ConfigPanel  # noqa: E402
from larcforge.ui.profiles import ProfilesStore  # noqa: E402


class _FakeConn:
    def close(self):
        pass


@pytest.fixture
def panel(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(pg, "connect", lambda **kw: _FakeConn())
    store = ProfilesStore(path=tmp_path / "cfg.json")
    ctx = AppContext(root=str(tmp_path), timeout=30, store=store,
                     config=store.load())
    p = ConfigPanel(ctx)
    p.show()
    qtbot.addWidget(p)
    p.reload()
    return p


def test_champs_initialises_depuis_config(panel):
    assert panel._root_field.text() == ""
    assert panel._school_field.text() == "Larc"
    assert panel._theme_combo.currentText() == "Bleu"  # blue par défaut


def test_enregistrer_racine_ecrit_json(panel, tmp_path):
    panel._root_field.setText("F:\\projets")
    panel._save_root()
    data = json.loads((tmp_path / "cfg.json").read_text(encoding="utf-8"))
    assert data["root_override"] == "F:\\projets"
    assert panel._ctx.config.root_override == "F:\\projets"
    assert "✓" in panel._msg_labels["root"].text()


def test_enregistrer_marque_met_a_jour_config_et_emett_signal(panel,
                                                              tmp_path, qtbot):
    fired = []
    panel.branding_changed.connect(lambda: fired.append(1))
    panel._school_field.setText("École Saint-Joseph")
    panel._theme_combo.setCurrentIndex(2)  # Sobre
    panel._save_branding()
    data = json.loads((tmp_path / "cfg.json").read_text(encoding="utf-8"))
    assert data["branding"]["school_name"] == "École Saint-Joseph"
    assert data["branding"]["theme"] == "sobre"
    assert panel._ctx.config.branding.school_name == "École Saint-Joseph"
    assert fired == [1]


def test_profil_db_sauvegarde_et_combo(panel):
    panel._db_new()
    panel._db_form["nom"].setText("École de Lomé")
    panel._db_form["host"].setText("192.168.1.50")
    panel._db_form["port"].setText("5432")
    panel._db_form["dbname"].setText("SchoolDB")
    panel._db_save()
    profiles = panel._ctx.config.db_profiles
    assert len(profiles) == 1
    assert profiles[0].name == "École de Lomé"
    assert profiles[0].host == "192.168.1.50"
    assert profiles[0].dbname == "SchoolDB"
    assert panel._db_combo.currentText() == "École de Lomé"


def test_profil_db_champs_vides_retombent_sur_config_ini(panel):
    panel._db_new()
    panel._db_form["nom"].setText("Sans params")
    panel._db_save()
    profile = panel._ctx.config.db_profiles[0]
    assert profile.host is None
    assert profile.port is None
    assert profile.section == "IntranetDatabase"


def test_profil_db_activation_active_connexion(panel, monkeypatch):
    panel._db_new()
    panel._db_form["nom"].setText("École B")
    panel._db_save()
    panel._db_combo.setCurrentIndex(0)
    panel._db_activate_sel()
    assert panel._ctx.config.active_db_profile == "École B"
    # open_db sans profil → AppContext résout le profil actif
    called = {}

    def fake_db_open(root, profile):
        called["profile"] = profile
        return _FakeConn()

    from larcforge.ui import main_window as mw_mod

    monkeypatch.setattr(mw_mod.db_mod, "open_db", fake_db_open)
    conn = panel._ctx.open_db()
    assert called["profile"].name == "École B"
    assert conn is not None


def test_profil_db_supprime(panel):
    panel._db_new()
    panel._db_form["nom"].setText("À supprimer")
    panel._db_save()
    panel._db_combo.setCurrentIndex(0)
    panel._db_delete_sel()
    assert panel._ctx.config.db_profiles == []
    assert "supprimée" in panel._msg_labels["db"].text()


def test_profil_db_test_connexion_ok(panel):
    panel._db_new()
    panel._db_form["nom"].setText("Test")
    panel._db_form["host"].setText("127.0.0.1")
    panel._db_test_conn()
    assert "réussie" in panel._msg_labels["db"].text()


def test_profil_db_test_connexion_ko(panel, monkeypatch):
    def down(**kw):
        raise pg.DBUnavailable("refusée (mock)")

    monkeypatch.setattr(pg, "connect", down)
    panel._db_new()
    panel._db_form["nom"].setText("Test")
    panel._db_test_conn()
    assert "Échec de connexion" in panel._msg_labels["db"].text()


def test_profil_run_sauvegarde_cases_et_combos(panel):
    panel._rp_new()
    panel._rp_name.setText("École Saint-Joseph")
    # décoche un linter et un projet
    panel._rp_checks["linters"]["R"].setChecked(False)
    panel._rp_checks["projects"]["LarcSuperviseur"].setChecked(False)
    panel._rp_since.setCurrentIndex(2)   # 48 h
    panel._rp_level.setCurrentIndex(1)   # ERROR seulement
    panel._rp_include.setChecked(True)
    panel._rp_save()
    profiles = panel._ctx.config.run_profiles
    assert len(profiles) == 1
    p = profiles[0]
    assert p.name == "École Saint-Joseph"
    assert "R" not in p.linters
    assert "LarcSuperviseur" not in p.projects
    assert p.include_integration is True
    assert p.since_h == 48
    assert p.level == "ERROR"
    assert panel._rp_combo.currentText() == "École Saint-Joseph"


def test_profil_run_actif_et_rechargement_form(panel):
    panel._rp_new()
    panel._rp_name.setText("École A")
    panel._rp_save()
    panel._rp_combo.setCurrentIndex(0)
    panel._rp_activate_sel()
    assert panel._ctx.config.active_run_profile == "École A"
    # sélection du profil dans le combo → le formulaire se re-synchronise
    panel._rp_checks["tests"]["LarcPhibuilder"].setChecked(False)
    panel._rp_combo.setCurrentIndex(-1)  # désélection
    panel._rp_combo.setCurrentIndex(0)   # re-sélection → rechargé depuis config
    assert panel._rp_checks["tests"]["LarcPhibuilder"].isChecked() is True


def test_profil_run_supprime_et_active_nettoye(panel):
    panel._rp_new()
    panel._rp_name.setText("École X")
    panel._rp_save()
    panel._rp_combo.setCurrentIndex(0)
    panel._rp_activate_sel()
    panel._rp_delete_sel()
    assert panel._ctx.config.run_profiles == []
    assert panel._ctx.config.active_run_profile is None


def test_nom_manquant_refuse_sauvegarde(panel):
    panel._rp_new()
    panel._rp_save()
    assert "Donnez un nom" in panel._msg_labels["run"].text()
    assert panel._ctx.config.run_profiles == []


def test_restyle_sans_crash(panel):
    panel._restyle()
