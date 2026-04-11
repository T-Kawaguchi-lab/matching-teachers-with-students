from __future__ import annotations

from pathlib import Path
from typing import Tuple

import pandas as pd


def ensure_input_files(teacher_path: str | Path, student_path: str | Path, history_path: str | Path | None = None) -> Tuple[Path, Path, Path | None]:
    teacher = Path(teacher_path)
    student = Path(student_path)
    history = Path(history_path) if history_path else None
    if not teacher.exists():
        raise FileNotFoundError(f'教員Excelが見つかりません: {teacher}')
    if not student.exists():
        raise FileNotFoundError(f'学生Excelが見つかりません: {student}')
    if history is not None and not history.exists():
        history = None
    return teacher, student, history


def load_teacher_excel(path: str | Path) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=0)


def load_student_excel(path: str | Path) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=0)


def load_generic_table(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() == '.csv':
        return pd.read_csv(p)
    return pd.read_excel(p, sheet_name=0)
