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

    use_fake_providers: bool = True

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
