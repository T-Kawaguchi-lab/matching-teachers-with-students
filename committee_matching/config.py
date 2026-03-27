from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .utils import load_json


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / 'config' / 'app_config.json'
TAXONOMY_PATH = ROOT_DIR / 'config' / 'field_taxonomy_ja.json'


def get_config() -> Dict[str, Any]:
    cfg = load_json(CONFIG_PATH)
    cfg['root_dir'] = str(ROOT_DIR)
    return cfg
