from __future__ import annotations

import hashlib
import math
import re


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


class HashEmbedder:
    """Small deterministic embedding backend for local demos and tests."""

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in TOKEN_PATTERN.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]
