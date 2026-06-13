"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(
        default="sqlite+aiosqlite:///./medquery.db",
        description="Async SQLAlchemy database URL.",
    )

    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"

    # Route LLM + embeddings through Transit — my self-built AI gateway — instead
    # of calling OpenAI directly. When set, MedQuery uses one metered, cached af_
    # key: repeated questions and re-embeds come straight from Transit's Redis
    # cache, so I stop paying twice for the same call. Off by default (keeps the
    # direct OpenAI path). Transit is OpenAI-compatible, so this is a base_url swap.
    transit_base_url: str = ""  # e.g. https://apiforge-jnwp.onrender.com/api/v1
    transit_api_key: str = ""   # af_... key from the Transit portal
    transit_chat_model: str = "meta/llama-3.3-70b-instruct"
    transit_embedding_model: str = "nvidia/nv-embedqa-e5-v5"
    transit_embedding_dim: int = 1024

    groq_api_key: str = ""
    groq_chat_model: str = "llama-3.3-70b-versatile"

    openrouter_api_key: str = ""
    openrouter_chat_model: str = "meta-llama/llama-3.3-70b-instruct:free"

    pinecone_api_key: str = ""
    pinecone_index: str = "medquery"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    storage_dir: str = "./storage"

    # Plain string (not List) so pydantic-settings does not JSON-decode the env
    # value — a comma-separated string like
    # "http://localhost:3000,https://app.vercel.app" just works. Consumers read
    # the parsed list via the `cors_origins_list` property below.
    cors_origins: str = "http://localhost:3000"

    # Explicit override to force the deterministic fakes even when keys are set
    # (used by the test suite / for a zero-cost demo). Default off: each provider
    # auto-detects from whether its key is present (see the resolver properties
    # below). So setting OPENAI_API_KEY alone switches the real LLM + embeddings
    # on, and PINECONE_API_KEY is optional (in-memory vector store otherwise).
    use_fake_providers: bool = False

    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 5
    max_upload_mb: int = 10

    # Fuse vector search with a BM25 lexical arm (Reciprocal Rank Fusion).
    use_hybrid_retrieval: bool = True

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse the comma-separated cors_origins string into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # --- Per-provider resolution (single source of truth for the factories) ---
    @property
    def use_transit(self) -> bool:
        """Route LLM + embeddings through the Transit gateway when configured."""
        return (
            not self.use_fake_providers
            and bool(self.transit_base_url)
            and bool(self.transit_api_key)
        )

    @property
    def use_real_openai(self) -> bool:
        """Real OpenAI embeddings + chat when a key is set and fakes aren't forced."""
        return not self.use_fake_providers and bool(self.openai_api_key)

    @property
    def use_real_pinecone(self) -> bool:
        """Real Pinecone vector store when a key is set and fakes aren't forced."""
        return not self.use_fake_providers and bool(self.pinecone_api_key)

    @property
    def active_llm_provider(self) -> str:
        """Which LLM backend will be used: transit > groq > openrouter > openai > fake."""
        if self.use_fake_providers:
            return "fake"
        if self.use_transit:
            return "transit"
        if self.groq_api_key:
            return "groq"
        if self.openrouter_api_key:
            return "openrouter"
        if self.openai_api_key:
            return "openai"
        return "fake"

    def provider_status(self) -> dict:
        """Which backend each provider is currently using (for /health + debugging)."""
        if self.use_transit:
            embeddings = "transit"
        elif self.use_real_openai:
            embeddings = "openai"
        else:
            embeddings = "fake"
        return {
            "embeddings": embeddings,
            "llm": self.active_llm_provider,
            "vector_store": "pinecone" if self.use_real_pinecone else "in-memory",
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
