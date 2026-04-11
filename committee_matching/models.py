from __future__ import annotations

from typing import Iterable, List

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer

from .utils import normalize_text


class SimpleEmbeddingModel:
    def __init__(self, n_features: int = 2048):
        self.vectorizer = HashingVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 5),
            n_features=n_features,
            alternate_sign=False,
            norm="l2",
        )

    def encode(
        self,
        texts: Iterable[str],
        normalize_embeddings: bool = True,
        show_progress_bar: bool = False,
    ):
        normalized: List[str] = [normalize_text(t) for t in texts]
        matrix = self.vectorizer.transform(normalized).astype(np.float32)
        dense = matrix.toarray()

        if normalize_embeddings:
            norms = np.linalg.norm(dense, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)
            dense = dense / norms

        return dense


def load_embedding_model(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(model_name)
    except Exception:
        return SimpleEmbeddingModel()