"""File storage abstraction. Currently uses the local filesystem to mock S3."""
from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Tuple

from app.core.config import get_settings


class LocalStorage:
    """Lightweight async wrapper around local filesystem writes."""

    def __init__(self, base_dir: str | None = None) -> None:
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.storage_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, filename: str, data: bytes) -> Tuple[str, int]:
        """Persist bytes to disk and return (absolute_path, size)."""
        safe_name = f"{uuid.uuid4().hex}_{Path(filename).name}"
        path = self.base_dir / safe_name

        def _write() -> int:
            with open(path, "wb") as fh:
                fh.write(data)
            return os.path.getsize(path)

        size = await asyncio.to_thread(_write)
        return str(path), size

    async def delete(self, path: str) -> None:
        def _unlink() -> None:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

        await asyncio.to_thread(_unlink)


def get_storage() -> LocalStorage:
    return LocalStorage()
