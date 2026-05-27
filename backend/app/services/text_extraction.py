"""PDF/text extraction + LangChain chunking."""
from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from PyPDF2 import PdfReader

from app.core.config import get_settings

MIN_EXTRACTED_CHARS = 100


class ScannedPdfError(ValueError):
    """Raised when a PDF appears to be a scanned image with no extractable text."""


@dataclass
class Chunk:
    index: int
    text: str
    page: int | None = None


def _approx_token_to_char(tokens: int) -> int:
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
    """Return [(page_number, page_text), ...] for a PDF or plain-text upload.

    Raises ScannedPdfError if the document is a PDF and the total extracted
    text is shorter than MIN_EXTRACTED_CHARS — almost always the signature
    of an image-only scan that needs OCR.
    """
    lower = filename.lower()
    is_pdf = lower.endswith(".pdf")

    def _run() -> List[tuple[int, str]]:
        if is_pdf:
            return _extract_pdf(data)
        return _extract_text(data)

    pages = await asyncio.to_thread(_run)

    if is_pdf:
        total = sum(len(text) for _, text in pages)
        if total < MIN_EXTRACTED_CHARS:
            raise ScannedPdfError(
                "Scanned PDF detected, text extraction not supported"
            )
    return pages


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
