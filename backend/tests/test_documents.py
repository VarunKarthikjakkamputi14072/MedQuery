"""End-to-end coverage for upload → embed → extract → query → delete."""
from __future__ import annotations

import io

import pytest

SAMPLE_TEXT = (
    "Patient John Doe was admitted with sepsis and elevated troponin. "
    "Vital signs showed tachycardia and hypotension; on arrival the patient was "
    "deteriorating and a code blue was called STAT. "
    "Discharge plan includes broad-spectrum antibiotics and cardiology follow-up. "
    "Lab results: WBC 18.4 x10^3/uL, lactate 4.2 mmol/L, creatinine 1.6 mg/dL. "
    "Medications: vancomycin 1 g IV, piperacillin 4.5 g, metformin 500 mg PO. "
    "Procedures performed: intubation, central line placement, blood transfusion. "
) * 4


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
async def test_upload_rejects_scanned_pdf(client):
    # Minimal valid PDF with no extractable text (no /Contents stream).
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n"
        b"0000000061 00000 n \n0000000112 00000 n \n"
        b"trailer << /Size 4 /Root 1 0 R >>\nstartxref\n178\n%%EOF\n"
    )
    files = {"file": ("scan.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    response = await client.post(
        "/upload", files=files, data={"document_type": "Clinical Note"}
    )
    assert response.status_code == 422
    assert "Scanned PDF" in response.json()["detail"]


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
    assert embed_body["warning"] is None

    query = await client.post(
        "/query",
        json={"question": "Did the patient have sepsis?", "document_ids": [document_id]},
    )
    assert query.status_code == 200, query.text
    qbody = query.json()
    assert qbody["answer"]
    assert qbody["session_id"]
    assert len(qbody["citations"]) >= 1
    assert qbody["risk_flag"] is True
    assert "sepsis" in qbody["risk_flags"]
    assert qbody["latency_ms"] >= 0

    # Chunks should be unique by content after dedupe.
    chunk_ids = [c["chunk_id"] for c in qbody["citations"]]
    assert len(chunk_ids) == len(set(chunk_ids))

    history = await client.get("/queries")
    assert history.status_code == 200
    assert len(history.json()) == 1


@pytest.mark.asyncio
async def test_extract_endpoint_finds_clinical_entities(client):
    files = {"file": ("note.txt", io.BytesIO(SAMPLE_TEXT.encode("utf-8")), "text/plain")}
    upload = await client.post("/upload", files=files, data={"document_type": "Clinical Note"})
    document_id = upload.json()["document"]["id"]

    response = await client.post("/extract", json={"document_id": document_id})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document_id"] == document_id
    assert body["entities"]
    types_found = {e["entity_type"] for e in body["entities"]}
    # At minimum, the regex extractor should find diagnoses, medications, and lab values.
    assert "diagnosis" in types_found
    assert "medication" in types_found
    assert "lab_value" in types_found
    assert sum(body["summary"].values()) == len(body["entities"])

    # GET /documents/{id}/entities should return the same data.
    listing = await client.get(f"/documents/{document_id}/entities")
    assert listing.status_code == 200
    assert len(listing.json()) == len(body["entities"])


@pytest.mark.asyncio
async def test_delete_document_removes_vectors_and_entities(client):
    files = {"file": ("note.txt", io.BytesIO(SAMPLE_TEXT.encode("utf-8")), "text/plain")}
    upload = await client.post("/upload", files=files, data={"document_type": "Lab Report"})
    doc_id = upload.json()["document"]["id"]

    await client.post("/embed", json={"document_id": doc_id})
    await client.post("/extract", json={"document_id": doc_id})

    delete = await client.delete(f"/documents/{doc_id}")
    assert delete.status_code == 204

    listing = await client.get("/documents")
    assert listing.json() == []

    response = await client.post("/query", json={"question": "Any findings?"})
    assert response.status_code == 200
    assert response.json()["citations"] == []


@pytest.mark.asyncio
async def test_multi_turn_session_includes_history(client):
    files = {"file": ("note.txt", io.BytesIO(SAMPLE_TEXT.encode("utf-8")), "text/plain")}
    upload = await client.post("/upload", files=files, data={"document_type": "Clinical Note"})
    doc_id = upload.json()["document"]["id"]
    await client.post("/embed", json={"document_id": doc_id})

    create = await client.post("/sessions", json={"document_ids": [doc_id]})
    assert create.status_code == 200
    session_id = create.json()["id"]

    q1 = await client.post(
        "/query", json={"question": "What was the lactate?", "session_id": session_id}
    )
    q2 = await client.post(
        "/query", json={"question": "Was there hypotension?", "session_id": session_id}
    )
    assert q1.json()["session_id"] == session_id == q2.json()["session_id"]

    session_detail = await client.get(f"/sessions/{session_id}")
    assert session_detail.status_code == 200
    assert len(session_detail.json()["messages"]) == 2

    history = await client.get(f"/queries?session_id={session_id}")
    assert len(history.json()) == 2


@pytest.mark.asyncio
async def test_session_delete_cascades_queries(client):
    files = {"file": ("note.txt", io.BytesIO(SAMPLE_TEXT.encode("utf-8")), "text/plain")}
    upload = await client.post("/upload", files=files, data={"document_type": "Clinical Note"})
    doc_id = upload.json()["document"]["id"]
    await client.post("/embed", json={"document_id": doc_id})

    create = await client.post("/sessions", json={"document_ids": [doc_id]})
    session_id = create.json()["id"]
    await client.post(
        "/query", json={"question": "Anything notable?", "session_id": session_id}
    )

    delete = await client.delete(f"/sessions/{session_id}")
    assert delete.status_code == 204

    follow = await client.get(f"/sessions/{session_id}")
    assert follow.status_code == 404
    assert (await client.get(f"/queries?session_id={session_id}")).json() == []


@pytest.mark.asyncio
async def test_analytics_endpoint(client):
    files = {"file": ("note.txt", io.BytesIO(SAMPLE_TEXT.encode("utf-8")), "text/plain")}
    upload = await client.post("/upload", files=files, data={"document_type": "Clinical Note"})
    doc_id = upload.json()["document"]["id"]
    await client.post("/embed", json={"document_id": doc_id})

    # Two queries for the same question, one for a different question.
    await client.post("/query", json={"question": "What antibiotics were given?"})
    await client.post("/query", json={"question": "What antibiotics were given?"})
    await client.post("/query", json={"question": "Was the patient intubated?"})

    response = await client.get("/analytics")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_queries"] == 3
    assert body["avg_latency_ms"] >= 0
    assert len(body["queries_per_document"]) >= 1
    assert body["queries_per_document"][0]["document_id"] == doc_id
    # Top question should be the repeated one with count 2.
    top = body["top_questions"][0]
    assert top["question"] == "What antibiotics were given?"
    assert top["count"] == 2
