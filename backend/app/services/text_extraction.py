"""PDF/text extraction + LangChain chunking."""
from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from PyPDF2 import PdfReader

from app.core.config import get_settings


@dataclass
class Chunk:
    index: int
    text: str
    page: int | None = None


def _approx_token_to_char(tokens: int) -> int:
    # OpenAI tokens roughly correspond to ~4 chars on average for English text.
    return tokens * 4


def _extract_pdf(data: bytes) -> List[tuple[int, str]]:
    reader = PdfReader(io.BytesIO(data))
    pages: List[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((i, text))
    return pages


def _extract_text(data: bytes) -> List[tuple[int, str]]:
    text = data.decode("utf-8", errors="replace")
    return [(1, text)] if text.strip() else []


async def extract_text(filename: str, data: bytes) -> List[tuple[int, str]]:
    """Return [(page_number, page_text), ...] for a PDF or plain-text upload."""
    lower = filename.lower()

    def _run() -> List[tuple[int, str]]:
        if lower.endswith(".pdf"):
            return _extract_pdf(data)
        return _extract_text(data)

    return await asyncio.to_thread(_run)


def split_chunks(pages: List[tuple[int, str]]) -> List[Chunk]:
    """Split pages into ~512-token chunks with 50-token overlap."""
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=_approx_token_to_char(settings.chunk_size),
        chunk_overlap=_approx_token_to_char(settings.chunk_overlap),
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks: List[Chunk] = []
    counter = 0
    for page_number, page_text in pages:
        for piece in splitter.split_text(page_text):
            piece = piece.strip()
            if not piece:
                continue
            chunks.append(Chunk(index=counter, text=piece, page=page_number))
            counter += 1
    return chunks
