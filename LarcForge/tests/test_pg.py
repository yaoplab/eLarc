"""Tests de pg.py : résolution du config.ini (str ou Path acceptés)."""

from __future__ import annotations

from larcforge import database as pg


def test_find_config_accepte_str_et_path(tmp_path):
    (tmp_path / "LarcCommon").mkdir()
    ini = tmp_path / "LarcCommon" / "config.ini"
    ini.write_text("[IntranetDatabase]\nPort=55517\n", encoding="utf-8")
    assert pg.find_config(str(tmp_path)) == ini
    assert pg.find_config(tmp_path) == ini


def test_find_config_priorite_master_puis_local(tmp_path):
    master_dir = tmp_path / "LarcCommon"
    master_dir.mkdir()
    master = master_dir / "config.ini"
    master.write_text("", encoding="utf-8")
    local = tmp_path / "config.ini"
    local.write_text("", encoding="utf-8")
    assert pg.find_config(tmp_path) == master
    (master_dir / "config.ini").unlink()
    assert pg.find_config(tmp_path) == local


def test_find_config_sans_fichier_retourne_master(tmp_path):
    # inexistant → pg_params retombera sur les defaults
    assert pg.find_config(tmp_path) == tmp_path / "LarcCommon" / "config.ini"


def test_pg_params_ignore_section_absente(tmp_path):
    params = pg.pg_params("IntranetDatabase", tmp_path / "absent.ini")
    assert params["port"] == "5432"  # defaults
