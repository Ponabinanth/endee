from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable


def _stable_hash(token: str) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


def _hash_embedding(text: str, dimensions: int = 384) -> list[float]:
    vector = [0.0] * dimensions
    tokens = re.findall(r"[A-Za-z0-9]+", text.lower())
    if not tokens:
        return vector

    for token in tokens:
        index = _stable_hash(token) % dimensions
        weight = 1.0 + min(len(token), 12) / 12.0
        vector[index] += weight

    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [value / norm for value in vector]
    return vector


class Embedder:
    def __init__(self, model_name: str, backend: str = "hash") -> None:
        self.model_name = model_name
        self.preferred_backend = (backend or "hash").strip().lower()
        self._model = None
        self.backend = "sentence-transformers" if self.preferred_backend == "sentence-transformers" else "hash"
        self.load_error: str | None = None

    def _load_model(self) -> None:
        if self._model is not None or self.preferred_backend != "sentence-transformers":
            return

        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            self.backend = "sentence-transformers"
        except Exception as exc:  # pragma: no cover - depends on runtime availability
            self._model = None
            self.backend = "hash"
            self.load_error = str(exc)
            self.preferred_backend = "hash"

    def embed(self, text: str) -> list[float]:
        self._load_model()
        if self._model is None:
            return _hash_embedding(text)

        try:
            vector = self._model.encode([text], normalize_embeddings=True)[0]
            return vector.tolist() if hasattr(vector, "tolist") else list(vector)
        except Exception as exc:  # pragma: no cover - depends on runtime availability
            self.backend = "hash"
            self.load_error = str(exc)
            self._model = None
            return _hash_embedding(text)

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]
