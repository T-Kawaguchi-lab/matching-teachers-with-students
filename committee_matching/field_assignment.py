from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import numpy as np

from .config import TAXONOMY_PATH
from .utils import ensure_list, load_json, normalize_text, unique_keep_order


class FieldTaxonomyMatcher:
    def __init__(self, model, taxonomy_path: str | Path = TAXONOMY_PATH):
        self.model = model
        self.taxonomy: List[str] = load_json(taxonomy_path)
        self.taxonomy_embeddings = model.encode(
            [f'passage: {item}' for item in self.taxonomy],
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    def suggest_fields(
        self,
        texts: Iterable[str],
        top_k: int = 5,
        min_score: float = 0.18,
        additional_min_score: float | None = None,
        relative_score_floor: float | None = None,
    ) -> List[str]:
        merged_text = '\n'.join([normalize_text(t) for t in texts if normalize_text(t)])
        if not merged_text:
            return []
        vec = self.model.encode(
            [f'query: {merged_text}'],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
        scores = np.asarray(self.taxonomy_embeddings @ vec, dtype=float)
        order = np.argsort(-scores)
        selected: List[str] = []
        best_score: float | None = None
        follow_score = additional_min_score if additional_min_score is not None else min_score

        for idx in order:
            field_name = self.taxonomy[idx]
            score = float(scores[idx])

            if best_score is None:
                if score < min_score:
                    break
                best_score = score
                selected.append(field_name)
                if len(selected) >= top_k:
                    break
                continue

            if score < follow_score:
                continue
            if relative_score_floor is not None and best_score > 0 and score < best_score * relative_score_floor:
                continue
            selected.append(field_name)
            if len(selected) >= top_k:
                break
        return unique_keep_order(selected)


def merge_manual_and_generated(manual: str | List[str], generated: List[str], top_k: int = 5) -> List[str]:
    values = ensure_list(manual) + list(generated)
    return unique_keep_order(values)[:top_k]
