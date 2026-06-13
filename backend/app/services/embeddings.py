"""Embedding provider with real OpenAI + deterministic fake fallback."""
from __future__ import annotations

import hashlib
import math
from typing import List, Protocol

from app.core.config import get_settings
from app.services.retry import retry_async

EMBEDDING_DIM = 1536  # text-embedding-3-small dimensionality.


class EmbeddingProvider(Protocol):
    dimension: int

    async def embed(self, texts: List[str]) -> List[List[float]]:
        ...


class FakeEmbeddingProvider:
    """Deterministic embeddings derived from SHA-256, used for tests / no-API mode."""

    dimension = EMBEDDING_DIM

    async def embed(self, texts: List[str]) -> List[List[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        floats: List[float] = []
        seed = digest
        while len(floats) < self.dimension:
            seed = hashlib.sha256(seed).digest()
            for i in range(0, len(seed), 4):
                if len(floats) >= self.dimension:
                    break
                chunk = int.from_bytes(seed[i : i + 4], "big", signed=False)
                floats.append((chunk / 0xFFFFFFFF) * 2.0 - 1.0)
        norm = math.sqrt(sum(v * v for v in floats)) or 1.0
        return [v / norm for v in floats]


class OpenAIEmbeddingProvider:
    """Wraps any OpenAI-compatible embeddings endpoint with exponential backoff.

    `base_url` lets it point at a compatible gateway (e.g. Transit, which proxies
    NVIDIA NIM embeddings and caches identical inputs). `dimension` is per-model.
    """

    dimension = EMBEDDING_DIM

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        dimension: int | None = None,
    ) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        if dimension is not None:
            self.dimension = dimension

    async def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        async def _call() -> List[List[float]]:
            response = await self._client.embeddings.create(
                model=self._model, input=texts
            )
            return [item.embedding for item in response.data]

        return await retry_async(_call, label="openai.embeddings")


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.use_transit:
        # Route embeddings through Transit (NVIDIA NIM, content-hash cached).
        return OpenAIEmbeddingProvider(
            settings.transit_api_key,
            settings.transit_embedding_model,
            base_url=settings.transit_base_url,
            dimension=settings.transit_embedding_dim,
        )
    if not settings.use_real_openai:
        return FakeEmbeddingProvider()
    return OpenAIEmbeddingProvider(settings.openai_api_key, settings.openai_embedding_model)
