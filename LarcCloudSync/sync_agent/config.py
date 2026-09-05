logger.py = logger.py is okay but config.json path

Actually let me create all files at once:<｜end▁of▁thinking｜>

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="write">
<｜｜DSML｜｜parameter name="content" string="true">"""Configuration du daemon de synchronisation."""
import json
import os

_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')


def load() -> dict:
    with open(_PATH, encoding='utf-8') as f:
        return json.load(f)


def table_frequency(table: str, cfg: dict) -> int:
    lvl = cfg['tables'].get(table)
    if lvl is None:
        return 0  # non gérée
    return cfg['levels'][str(lvl)]
