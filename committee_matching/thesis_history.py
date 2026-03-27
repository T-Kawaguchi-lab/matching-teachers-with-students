from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd

from .utils import normalize_name, normalize_text, unique_keep_order


POSSIBLE_NAME_COLUMNS = ['指導教員', '教員名', 'teacher_name', 'name']
POSSIBLE_TITLE_COLUMNS = ['修士論文主題', '修論テーマ', 'thesis_title', 'title']


def _find_first_existing(columns: List[str], candidates: List[str]) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return ''


def load_teacher_history_map(history_path: str | Path) -> Dict[str, List[str]]:
    history_path = Path(history_path)
    if not history_path.exists():
        return {}

    if history_path.suffix.lower() == '.csv':
        df = pd.read_csv(history_path)
    else:
        df = pd.read_excel(history_path)

    name_col = _find_first_existing(df.columns.tolist(), POSSIBLE_NAME_COLUMNS)
    title_col = _find_first_existing(df.columns.tolist(), POSSIBLE_TITLE_COLUMNS)
    if not name_col or not title_col:
        return {}

    result: Dict[str, List[str]] = {}
    for _, row in df.iterrows():
        name = normalize_text(row.get(name_col))
        title = normalize_text(row.get(title_col))
        if not name or not title:
            continue
        key = normalize_name(name)
        result.setdefault(key, [])
        result[key].append(title)

    return {key: unique_keep_order(values) for key, values in result.items()}
