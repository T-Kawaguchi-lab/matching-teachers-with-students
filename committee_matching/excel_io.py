from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

from .utils import normalize_text


TEACHER_COLUMN_ALIASES = {
    'teacher_name': ['teacher_name', '教員名', '氏名', 'name'],
    'department': ['department', '所属', '専攻'],
    'position': ['position', '職名'],
    'trios_url': ['trios_url', 'TRIOS_URL', 'trios'],
    'manual_research_fields': ['manual_research_fields', '研究分野候補', 'manual_fields'],
}

STUDENT_COLUMN_ALIASES = {
    'student_name': ['student_name', '学生名', '氏名', 'name'],
    'department': ['department', '所属', '専攻'],
    'thesis_title': ['thesis_title', '修論テーマ', '修士論文テーマ', 'title'],
    'manual_research_fields': ['manual_research_fields', '研究分野候補', 'manual_fields'],
}


def _rename_columns(df: pd.DataFrame, aliases: Dict[str, list]) -> pd.DataFrame:
    mapping: Dict[str, str] = {}
    for standard, candidates in aliases.items():
        for candidate in candidates:
            if candidate in df.columns:
                mapping[candidate] = standard
                break
    return df.rename(columns=mapping)


def load_teacher_excel(path: str | Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    df = _rename_columns(df, TEACHER_COLUMN_ALIASES)
    required = ['teacher_name']
    for col in required:
        if col not in df.columns:
            raise ValueError(f'教員Excelに必須列がありません: {col}')
    for column in ['department', 'position', 'trios_url', 'manual_research_fields']:
        if column not in df.columns:
            df[column] = ''
    df['teacher_name'] = df['teacher_name'].map(normalize_text)
    df = df[df['teacher_name'] != ''].copy()
    return df.reset_index(drop=True)


def load_student_excel(path: str | Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    df = _rename_columns(df, STUDENT_COLUMN_ALIASES)
    required = ['student_name', 'thesis_title']
    for col in required:
        if col not in df.columns:
            raise ValueError(f'学生Excelに必須列がありません: {col}')
    for column in ['department', 'manual_research_fields']:
        if column not in df.columns:
            df[column] = ''
    df['student_name'] = df['student_name'].map(normalize_text)
    df['thesis_title'] = df['thesis_title'].map(normalize_text)
    df = df[(df['student_name'] != '') & (df['thesis_title'] != '')].copy()
    return df.reset_index(drop=True)


def ensure_input_files(teacher_path: str | Path, student_path: str | Path) -> Tuple[Path, Path]:
    teacher = Path(teacher_path)
    student = Path(student_path)
    if not teacher.exists():
        raise FileNotFoundError(f'教員Excelが見つかりません: {teacher}')
    if not student.exists():
        raise FileNotFoundError(f'学生Excelが見つかりません: {student}')
    return teacher, student
