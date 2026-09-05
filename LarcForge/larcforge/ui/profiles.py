"""Profils de personnalisation « école » : vérification, connexions DB, marque.

Module PUR (aucune dépendance Qt) — importable depuis la CLI sans PySide6.
Persistance JSON local : les profils doivent fonctionner quand la base est
indisponible (c'est depuis le panneau Configuration qu'on répare l'accès DB).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .. import config as cfg

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "ui_config.json"
# surchargeable par variable d'environnement (utilisé par les tests tmp_path)
ENV_OVERRIDE = "LARCFORGE_UI_CONFIG"


@dataclass
class RunProfile:
    """Un profil de vérification (une école = ses contrôles activés)."""

    name: str
    projects: list[str] = field(default_factory=lambda: list(cfg.PROJETS))
    linters: list[str] = field(default_factory=lambda: list(cfg.LINTER_KEYS))
    test_projects: list[str] = field(default_factory=lambda: list(cfg.TEST_PROJECTS))
    include_integration: bool = False
    since_h: int = 24
    level: str = "ERROR,WARNING"


@dataclass
class DbProfile:
    """Un profil de connexion PostgreSQL (une école = sa base)."""

    name: str
    section: str = "IntranetDatabase"
    host: str | None = None  # si host renseigné → paramètres explicites
    port: str | None = None
    dbname: str | None = None
    user: str | None = None
    password: str | None = None


@dataclass
class Branding:
    """Marque affichée par l'IHM (nom de l'école + thème)."""

    school_name: str = "Larc"
    theme: str = "blue"


@dataclass
class UiConfig:
    """Configuration complète de l'IHM, sérialisée dans ui_config.json."""

    root_override: str | None = None
    active_run_profile: str | None = None
    active_db_profile: str | None = None
    run_profiles: list[RunProfile] = field(default_factory=list)
    db_profiles: list[DbProfile] = field(default_factory=list)
    branding: Branding = field(default_factory=Branding)


def _config_path() -> Path:
    override = os.environ.get(ENV_OVERRIDE)
    return Path(override) if override else DEFAULT_CONFIG_PATH


class ProfilesStore:
    """Chargement / sauvegarde de la configuration JSON de l'IHM."""

    def __init__(self, path: Path | None = None):
        self.path = path or _config_path()

    def load(self) -> UiConfig:
        if not self.path.is_file():
            return self.default_config()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # fichier corrompu → on repart des défauts (sans détruire le fichier)
            return self.default_config()
        cfg_ = self.default_config()
        # clés inconnues ignorées (forward-compat) ; chaque champ remplacé
        # uniquement si présent et bien typé
        if data.get("root_override") is not None:
            cfg_.root_override = data["root_override"]
        if data.get("active_run_profile"):
            cfg_.active_run_profile = data["active_run_profile"]
        if data.get("active_db_profile"):
            cfg_.active_db_profile = data["active_db_profile"]
        cfg_.run_profiles = [_run_profile(d) for d in data.get("run_profiles", [])]
        cfg_.db_profiles = [_db_profile(d) for d in data.get("db_profiles", [])]
        b = data.get("branding") or {}
        if b.get("school_name"):
            cfg_.branding.school_name = b["school_name"]
        if b.get("theme"):
            cfg_.branding.theme = b["theme"]
        return cfg_

    def save(self, cfg_: UiConfig) -> None:
        data = asdict(cfg_)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def default_config() -> UiConfig:
        return UiConfig()


def _run_profile(d: dict) -> RunProfile:
    base = RunProfile(name=str(d.get("name") or "Profil"))
    if isinstance(d.get("projects"), list):
        base.projects = [str(p) for p in d["projects"]]
    if isinstance(d.get("linters"), list):
        base.linters = [str(l) for l in d["linters"]]
    if isinstance(d.get("test_projects"), list):
        base.test_projects = [str(t) for t in d["test_projects"]]
    if isinstance(d.get("include_integration"), bool):
        base.include_integration = d["include_integration"]
    if isinstance(d.get("since_h"), int):
        base.since_h = d["since_h"]
    if isinstance(d.get("level"), str):
        base.level = d["level"]
    return base


def _db_profile(d: dict) -> DbProfile:
    base = DbProfile(name=str(d.get("name") or "Connexion"))
    for key in ("section", "host", "port", "dbname", "user", "password"):
        if isinstance(d.get(key), str):
            setattr(base, key, d[key])
    return base
