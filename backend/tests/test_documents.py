"""End-to-end coverage for upload → embed → query → delete."""
from __future__ import annotations

import io

import pytest

SAMPLE_TEXT = (
    "Patient John Doe was admitted with sepsis and elevated troponin. "
    "Vital signs showed tachycardia and hypotension. "
    "Discharge plan includes broad-spectrum antibiotics and cardiology follow-up. "
    "Lab results: WBC 18.4, lactate 4.2 mmol/L, creatinine 1.6 mg/dL. "
) * 6


@pytest.mark.asyncio
async def test_upload_extracts_chunks_and_lists_document(client):
    files = {"file": ("note.txt", io.BytesIO(SAMPLE_TEXT.encode("utf-8")), "text/plain")}
    data = {"document_type": "Clinical Note"}

    response = await client.post("/upload", files=files, data=data)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document"]["filename"] == "note.txt"
    assert body["document"]["chunk_count"] >= 1
    assert body["preview"]

    listing = await client.get("/documents")
    assert listing.status_code == 200
    docs = listing.json()
    assert len(docs) == 1
    assert docs[0]["document_type"] == "Clinical Note"


@pytest.mark.asyncio
async def test_upload_rejects_invalid_type(client):
    files = {"file": ("scan.exe", io.BytesIO(b"binary"), "application/octet-stream")}
    response = await client.post("/upload", files=files, data={"document_type": "Clinical Note"})
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_upload_rejects_invalid_document_type(client):
    files = {"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")}
    response = await client.post("/upload", files=files, data={"document_type": "Not Real"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_embed_and_query_round_trip(client):
    files = {"file": ("note.txt", io.BytesIO(SAMPLE_TEXT.encode("utf-8")), "text/plain")}
    upload = await client.post("/upload", files=files, data={"document_type": "Discharge Summary"})
    assert upload.status_code == 200
    document_id = upload.json()["document"]["id"]

    embed = await client.post("/embed", json={"document_id": document_id})
    assert embed.status_code == 200, embed.text
    embed_body = embed.json()
    assert embed_body["chunk_count"] > 0
    assert len(embed_body["pinecone_ids"]) == embed_body["chunk_count"]

    query = await client.post(
        "/query",
        json={"question": "Did the patient have sepsis?", "document_ids": [document_id]},
    )
    assert query.status_code == 200, query.text
    qbody = query.json()
    assert qbody["answer"]
    assert qbody["session_id"]
    assert len(qbody["citations"]) >= 1
    assert any("sepsis" in flag for flag in qbody["risk_flags"])

    history = await client.get("/queries")
    assert history.status_code == 200
    assert len(history.json()) == 1


@pytest.mark.asyncio
async def test_delete_document_removes_vectors(client):
    files = {"file": ("note.txt", io.BytesIO(SAMPLE_TEXT.encode("utf-8")), "text/plain")}
    upload = await client.post("/upload", files=files, data={"document_type": "Lab Report"})
    doc_id = upload.json()["document"]["id"]

    await client.post("/embed", json={"document_id": doc_id})

    delete = await client.delete(f"/documents/{doc_id}")
    assert delete.status_code == 204

    listing = await client.get("/documents")
    assert listing.json() == []

    # Subsequent query should return zero citations.
    response = await client.post("/query", json={"question": "Any findings?"})
    assert response.status_code == 200
    assert response.json()["citations"] == []


@pytest.mark.asyncio
async def test_sessions_create_and_reuse(client):
    files = {"file": ("note.txt", io.BytesIO(SAMPLE_TEXT.encode("utf-8")), "text/plain")}
    upload = await client.post("/upload", files=files, data={"document_type": "Clinical Note"})
    doc_id = upload.json()["document"]["id"]
    await client.post("/embed", json={"document_id": doc_id})

    create = await client.post("/sessions", json={"document_ids": [doc_id]})
    assert create.status_code == 200
    session_id = create.json()["id"]

    q1 = await client.post("/query", json={"question": "What was the lactate?", "session_id": session_id})
    q2 = await client.post("/query", json={"question": "Was there hypotension?", "session_id": session_id})
    assert q1.json()["session_id"] == session_id == q2.json()["session_id"]

    history = await client.get(f"/queries?session_id={session_id}")
    assert len(history.json()) == 2
