"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
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

    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    use_fake_providers: bool = True

    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k: int = 5
    max_upload_mb: int = 10

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
