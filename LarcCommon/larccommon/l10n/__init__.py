import json
import os
from pathlib import Path

class Translator:
    _instance = None

    def __init__(self, lang: str = "fr"):
        self._lang = lang
        self._strings: dict[str, str] = {}

    @classmethod
    def instance(cls, lang: str | None = None) -> "Translator":
        if cls._instance is None:
            cls._instance = cls(lang or "fr")
        elif lang is not None:
            cls._instance._lang = lang
        return cls._instance

    def load(self, path: str | Path):
        p = Path(path)
        if p.exists():
            with open(p, encoding="utf-8") as f:
                self._strings.update(json.load(f))

    def load_dir(self, directory: str | Path, lang: str | None = None):
        lang = lang or self._lang
        p = Path(directory) / f"{lang}.json"
        if p.exists():
            self.load(p)

    @property
    def lang(self) -> str:
        return self._lang

    def set_language(self, lang: str):
        self._lang = lang

    @staticmethod
    def l10n_dir() -> str:
        return os.path.dirname(os.path.abspath(__file__))

    def t(self, key: str, default: str = "") -> str:
        return self._strings.get(key, default or key)

    def reload(self, directory: str | Path):
        self._strings.clear()
        self.load_dir(directory)

_ = Translator.instance().t
