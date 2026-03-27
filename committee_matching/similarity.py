from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .utils import ensure_list, normalize_text


@dataclass
class SimilarityArtifacts:
    total_score: np.ndarray
    field_score: np.ndarray
    theme_score: np.ndarray
    exact_bonus: np.ndarray
    teacher_teacher_similarity: np.ndarray


def _prefixed(texts: List[str], mode: str) -> List[str]:
    prefix = 'query:' if mode == 'query' else 'passage:'
    return [f'{prefix} {normalize_text(text)}' for text in texts]


def build_teacher_text(row: pd.Series) -> str:
    parts = [
        row.get('teacher_name', ''),
        row.get('department', ''),
        row.get('position', ''),
        row.get('trios_topics_text', ''),
        row.get('trios_papers_text', ''),
        row.get('past_thesis_titles_text', ''),
        row.get('research_fields_text', ''),
    ]
    return '\n'.join([normalize_text(p) for p in parts if normalize_text(p)])


def build_student_text(row: pd.Series) -> str:
    parts = [
        row.get('student_name', ''),
        row.get('department', ''),
        row.get('thesis_title', ''),
        row.get('research_fields_text', ''),
    ]
    return '\n'.join([normalize_text(p) for p in parts if normalize_text(p)])


def compute_exact_bonus(student_fields: List[List[str]], teacher_fields: List[List[str]], per_match: float, max_bonus: float) -> np.ndarray:
    bonus = np.zeros((len(student_fields), len(teacher_fields)), dtype=float)
    for i, s_fields in enumerate(student_fields):
        s_norm = {normalize_text(v).lower() for v in s_fields if normalize_text(v)}
        for j, t_fields in enumerate(teacher_fields):
            t_norm = {normalize_text(v).lower() for v in t_fields if normalize_text(v)}
            overlap = len(s_norm & t_norm)
            bonus[i, j] = min(overlap * per_match, max_bonus)
    return bonus


def greedy_committee_selection(
    student_index: int,
    teacher_names: List[str],
    total_score: np.ndarray,
    teacher_teacher_similarity: np.ndarray,
    diversity_penalty_weight: float,
) -> Tuple[str, str, str, List[int]]:
    scores = total_score[student_index]
    if len(teacher_names) == 0:
        return ('', '', '', [])
    if len(teacher_names) == 1:
        return (teacher_names[0], '', '', [0])
    main_idx = int(np.argmax(scores))
    selected = [main_idx]

    target_size = min(3, len(teacher_names))
    while len(selected) < target_size:
        best_idx = None
        best_value = None
        for idx in range(len(teacher_names)):
            if idx in selected:
                continue
            penalty = 0.0
            if selected:
                penalty = float(np.mean([teacher_teacher_similarity[idx, s] for s in selected]))
            adjusted = float(scores[idx]) - diversity_penalty_weight * penalty
            if best_value is None or adjusted > best_value:
                best_value = adjusted
                best_idx = idx
        if best_idx is None:
            break
        selected.append(int(best_idx))

    names = [teacher_names[idx] for idx in selected]
    while len(names) < 3:
        names.append('')
    return (names[0], names[1], names[2], selected)


def compute_similarity(
    students: pd.DataFrame,
    teachers: pd.DataFrame,
    model,
    weights: Dict[str, float],
) -> SimilarityArtifacts:
    student_texts = [build_student_text(row) for _, row in students.iterrows()]
    teacher_texts = [build_teacher_text(row) for _, row in teachers.iterrows()]

    student_field_texts = [row.get('research_fields_text', '') for _, row in students.iterrows()]
    teacher_field_texts = [row.get('research_fields_text', '') for _, row in teachers.iterrows()]

    student_theme_embeddings = model.encode(_prefixed(student_texts, 'query'), normalize_embeddings=True, show_progress_bar=False)
    teacher_theme_embeddings = model.encode(_prefixed(teacher_texts, 'passage'), normalize_embeddings=True, show_progress_bar=False)
    student_field_embeddings = model.encode(_prefixed(student_field_texts, 'query'), normalize_embeddings=True, show_progress_bar=False)
    teacher_field_embeddings = model.encode(_prefixed(teacher_field_texts, 'passage'), normalize_embeddings=True, show_progress_bar=False)

    theme_score = np.asarray(student_theme_embeddings @ teacher_theme_embeddings.T, dtype=float)
    field_score = np.asarray(student_field_embeddings @ teacher_field_embeddings.T, dtype=float)
    teacher_teacher_similarity = np.asarray(teacher_theme_embeddings @ teacher_theme_embeddings.T, dtype=float)

    student_fields = [ensure_list(v) for v in students['research_fields']]
    teacher_fields = [ensure_list(v) for v in teachers['research_fields']]
    exact_bonus = compute_exact_bonus(
        student_fields,
        teacher_fields,
        per_match=weights['exact_field_bonus_per_match'],
        max_bonus=weights['max_exact_field_bonus'],
    )

    total = (
        weights['field_similarity_weight'] * field_score
        + weights['theme_similarity_weight'] * theme_score
        + exact_bonus
    )

    return SimilarityArtifacts(
        total_score=total,
        field_score=field_score,
        theme_score=theme_score,
        exact_bonus=exact_bonus,
        teacher_teacher_similarity=teacher_teacher_similarity,
    )
