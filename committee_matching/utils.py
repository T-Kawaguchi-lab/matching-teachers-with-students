from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List


_EMPTY_TEXT_MARKERS = {'', 'nan', 'none', 'null', 'nat', '<na>'}


def load_json(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save_json(path: str | Path, payload: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def normalize_text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, float) and math.isnan(value):
        return ''
    text = str(value).strip()
    if text.lower() in _EMPTY_TEXT_MARKERS:
        return ''
    text = text.replace('\u3000', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text


def normalize_name(value: Any) -> str:
    text = normalize_text(value).lower()
    text = re.sub(r'[\s\-‐‑‒–—―ー・･.,，、]+', '', text)
    return text


def ensure_list(value: Any, sep: str = ';') -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [normalize_text(v) for v in value if normalize_text(v)]
    text = normalize_text(value)
    if not text:
        return []
    if sep in text:
        return [normalize_text(v) for v in text.split(sep) if normalize_text(v)]
    return [text]


def unique_keep_order(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        key = normalize_text(value)
        if not key:
            continue
        if key.lower() in seen:
            continue
        seen.add(key.lower())
        result.append(key)
    return result


def slugify(value: str) -> str:
    text = normalize_text(value).lower()
    text = re.sub(r'[^0-9a-zA-Z\-ぁ-んァ-ヶ一-龠]+', '_', text)
    text = re.sub(r'_+', '_', text).strip('_')
    return text or 'unknown'