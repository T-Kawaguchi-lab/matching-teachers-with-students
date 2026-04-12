from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .utils import normalize_text


@dataclass
class SimilarityArtifacts:
    total_score: np.ndarray
    field_score: np.ndarray
    content_score: np.ndarray
    teacher_teacher_similarity: np.ndarray


def _prefixed(texts: List[str], mode: str) -> List[str]:
    prefix = "query:" if mode == "query" else "passage:"
    return [f"{prefix} {normalize_text(text)}" for text in texts]


def compute_similarity(
    students: pd.DataFrame,
    teachers: pd.DataFrame,
    model,
    weights: Dict[str, float],
) -> SimilarityArtifacts:
    student_field_texts = students["field_text"].fillna("").astype(str).tolist()
    teacher_field_texts = teachers["field_text"].fillna("").astype(str).tolist()
    student_content_texts = students["content_text"].fillna("").astype(str).tolist()
    teacher_content_texts = teachers["content_text"].fillna("").astype(str).tolist()

    sf = model.encode(
        _prefixed(student_field_texts, "query"),
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    tf = model.encode(
        _prefixed(teacher_field_texts, "passage"),
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    sc = model.encode(
        _prefixed(student_content_texts, "query"),
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    tc = model.encode(
        _prefixed(teacher_content_texts, "passage"),
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    field_score = np.asarray(sf @ tf.T, dtype=float)
    content_score = np.asarray(sc @ tc.T, dtype=float)
    teacher_teacher_similarity = np.asarray(tc @ tc.T, dtype=float)
    total = (
        weights["field_similarity_weight"] * field_score
        + weights["content_similarity_weight"] * content_score
    )

    return SimilarityArtifacts(
        total_score=total,
        field_score=field_score,
        content_score=content_score,
        teacher_teacher_similarity=teacher_teacher_similarity,
    )


def top_matches_for_group(
    students: pd.DataFrame,
    teachers: pd.DataFrame,
    similarity: SimilarityArtifacts,
    top_k: Optional[int] = 10,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    top_k:
      - int: 上位N件だけ詳細結果に入れる
      - None: 全件を詳細結果に入れる
    推薦結果(rec_df)は常に上位3件を使う
    """
    score_rows = []
    recommendation_rows = []
    teacher_names = teachers["teacher_name"].tolist()

    for i, student in students.reset_index(drop=True).iterrows():
        order = similarity.total_score[i].argsort()[::-1]

        if top_k is None:
            selected = order
        else:
            selected = order[:top_k]

        for rank, j in enumerate(selected, start=1):
            score_rows.append(
                {
                    "group": student["group"],
                    "student_name": student["student_name"],
                    "title": student["title"],
                    "teacher_name": teacher_names[int(j)],
                    "rank": rank,
                    "total_score": float(similarity.total_score[i, j]),
                    "field_score": float(similarity.field_score[i, j]),
                    "content_score": float(similarity.content_score[i, j]),
                    "student_field_text": student.get("field_text", ""),
                    "teacher_field_text": teachers.iloc[int(j)].get("field_text", ""),
                    "student_content_text": student.get("content_text", ""),
                    "teacher_content_text": teachers.iloc[int(j)].get("content_text", ""),
                }
            )

        top3 = [teacher_names[int(j)] for j in order[:3]]
        while len(top3) < 3:
            top3.append("")

        recommendation_rows.append(
            {
                "group": student["group"],
                "student_name": student["student_name"],
                "title": student["title"],
                "teacher_1": top3[0],
                "teacher_2": top3[1],
                "teacher_3": top3[2],
                "score_1": float(similarity.total_score[i, order[0]]) if len(order) >= 1 else 0.0,
                "score_2": float(similarity.total_score[i, order[1]]) if len(order) >= 2 else 0.0,
                "score_3": float(similarity.total_score[i, order[2]]) if len(order) >= 3 else 0.0,
            }
        )

    return pd.DataFrame(score_rows), pd.DataFrame(recommendation_rows)