"""Tests des profils de personnalisation (module pur, sans Qt ni DB)."""

from __future__ import annotations

from larcforge.ui.profiles import (
    Branding,
    DbProfile,
    ProfilesStore,
    RunProfile,
    UiConfig,
)


def _store(tmp_path):
    return ProfilesStore(path=tmp_path / "cfg.json")


def test_load_sans_fichier_donne_defauts(tmp_path):
    cfg_ = _store(tmp_path).load()
    assert cfg_.root_override is None
    assert cfg_.branding.school_name == "Larc"
    assert cfg_.run_profiles == []
    assert cfg_.db_profiles == []


def test_round_trip_complet(tmp_path):
    store = _store(tmp_path)
    cfg_ = UiConfig(
        root_override="F:\\projets",
        active_run_profile="Collège A",
        active_db_profile="École B",
        run_profiles=[
            RunProfile(name="Collège A", linters=["R", "D"], since_h=12),
        ],
        db_profiles=[
            DbProfile(name="École B", host="10.0.0.5", port="55515",
                      dbname="EcoleB", user="postgres", password="secret"),
        ],
        branding=Branding(school_name="Collège A", theme="forêt"),
    )
    store.save(cfg_)
    loaded = store.load()
    assert loaded.root_override == "F:\\projets"
    assert loaded.active_run_profile == "Collège A"
    assert loaded.active_db_profile == "École B"
    assert len(loaded.run_profiles) == 1
    rp = loaded.run_profiles[0]
    assert rp.name == "Collège A"
    assert rp.linters == ["R", "D"]
    assert rp.since_h == 12
    # défauts des champs non fournis
    assert rp.projects
    assert rp.test_projects
    assert rp.include_integration is False
    dbp = loaded.db_profiles[0]
    assert dbp.name == "École B"
    assert dbp.host == "10.0.0.5"
    assert dbp.password == "secret"
    assert loaded.branding.school_name == "Collège A"
    assert loaded.branding.theme == "forêt"


def test_cles_inconnues_ignorees(tmp_path):
    store = _store(tmp_path)
    store.path.write_text(
        '{"run_profiles": [{"name": "X", "bogus": 1}], "future_key": 42}',
        encoding="utf-8",
    )
    cfg_ = store.load()
    assert len(cfg_.run_profiles) == 1
    assert cfg_.run_profiles[0].name == "X"
    # la clé inconnue n'a pas planté le chargement
    assert cfg_.branding.school_name == "Larc"


def test_fichier_corrompu_retombe_sur_defauts(tmp_path):
    store = _store(tmp_path)
    store.path.write_text("{pas du json", encoding="utf-8")
    cfg_ = store.load()
    assert cfg_.run_profiles == []
    assert store.path.exists()  # le fichier n'est pas détruit


def test_env_override_du_chemin(tmp_path, monkeypatch):
    monkeypatch.setenv("LARCFORGE_UI_CONFIG", str(tmp_path / "autre.json"))
    store = ProfilesStore()
    assert store.path == tmp_path / "autre.json"
    store.save(UiConfig(branding=Branding(school_name="École C")))
    loaded = store.load()
    assert loaded.branding.school_name == "École C"
