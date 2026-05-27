"""Document upload, embedding, listing, and deletion endpoints."""
from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    embedding_dep,
    session_dep,
    storage_dep,
    vector_dep,
)
from app.core.config import get_settings
from app.models.document import Document
from app.schemas.document import (
    DOCUMENT_TYPES,
    DocumentRead,
    EmbedRequest,
    EmbedResponse,
    UploadResponse,
)
from app.services.embeddings import EmbeddingProvider
from app.services.storage import LocalStorage
from app.services.text_extraction import extract_text, split_chunks
from app.services.vector_store import VectorRecord, VectorStore

documents_router = APIRouter(prefix="/documents", tags=["documents"])
upload_router = APIRouter(tags=["documents"])
embed_router = APIRouter(tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".txt"}


def _validate_upload(file: UploadFile, size: int) -> None:
    settings = get_settings()
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{suffix}'. Allowed: PDF, TXT.",
        )
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_upload_mb} MB limit.",
        )


def _validate_doc_type(document_type: str) -> str:
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid document_type. Allowed: {DOCUMENT_TYPES}",
        )
    return document_type


@documents_router.get("", response_model=List[DocumentRead])
async def list_documents(session: AsyncSession = Depends(session_dep)) -> List[DocumentRead]:
    result = await session.execute(select(Document).order_by(Document.upload_timestamp.desc()))
    rows = result.scalars().all()
    return [DocumentRead.model_validate(d) for d in rows]


@documents_router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: str,
    session: AsyncSession = Depends(session_dep),
) -> DocumentRead:
    document = await session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentRead.model_validate(document)


@documents_router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    session: AsyncSession = Depends(session_dep),
    storage: LocalStorage = Depends(storage_dep),
    vector_store: VectorStore = Depends(vector_dep),
) -> Response:
    document = await session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.pinecone_ids:
        await vector_store.delete(list(document.pinecone_ids))

    if document.storage_path:
        await storage.delete(document.storage_path)

    await session.delete(document)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@upload_router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form("Clinical Note"),
    session: AsyncSession = Depends(session_dep),
    storage: LocalStorage = Depends(storage_dep),
) -> UploadResponse:
    _validate_doc_type(document_type)
    data = await file.read()
    _validate_upload(file, len(data))

    storage_path, size_bytes = await storage.save(file.filename or "upload.bin", data)

    pages = await extract_text(file.filename or "upload.bin", data)
    chunks = split_chunks(pages)
    preview = "\n\n".join(c.text for c in chunks[:1])[:600]

    document = Document(
        filename=file.filename or "upload.bin",
        document_type=document_type,
        chunk_count=len(chunks),
        pinecone_ids=[],
        storage_path=storage_path,
        size_bytes=size_bytes,
        status="extracted",
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)

    return UploadResponse(document=DocumentRead.model_validate(document), preview=preview)


@embed_router.post("/embed", response_model=EmbedResponse)
async def embed_document(
    payload: EmbedRequest,
    session: AsyncSession = Depends(session_dep),
    vector_store: VectorStore = Depends(vector_dep),
    embedder: EmbeddingProvider = Depends(embedding_dep),
) -> EmbedResponse:
    document = await session.get(Document, payload.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    path = Path(document.storage_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Stored file no longer exists")

    data = path.read_bytes()
    pages = await extract_text(document.filename, data)
    chunks = split_chunks(pages)
    if not chunks:
        raise HTTPException(status_code=422, detail="No text extracted from document")

    vectors = await embedder.embed([c.text for c in chunks])
    records: list[VectorRecord] = []
    pinecone_ids: list[str] = []
    for chunk, vector in zip(chunks, vectors):
        vec_id = f"{document.id}:{chunk.index}"
        pinecone_ids.append(vec_id)
        records.append(
            VectorRecord(
                id=vec_id,
                values=vector,
                metadata={
                    "document_id": document.id,
                    "document_name": document.filename,
                    "document_type": document.document_type,
                    "chunk_index": chunk.index,
                    "page": chunk.page or 1,
                    "text": chunk.text,
                },
            )
        )

    await vector_store.upsert(records)

    document.pinecone_ids = pinecone_ids
    document.chunk_count = len(chunks)
    document.status = "indexed"
    await session.commit()
    await session.refresh(document)

    return EmbedResponse(
        document_id=document.id,
        chunk_count=document.chunk_count,
        pinecone_ids=pinecone_ids,
    )
