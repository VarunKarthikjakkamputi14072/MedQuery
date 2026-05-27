export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type DocumentType =
  | "Discharge Summary"
  | "Lab Report"
  | "Clinical Note"
  | "Radiology Report";

export interface DocumentRead {
  id: string;
  filename: string;
  document_type: DocumentType;
  upload_timestamp: string;
  chunk_count: number;
  pinecone_ids: string[];
  size_bytes: number;
  status: string;
}

export interface Citation {
  chunk_id: string;
  document_id: string;
  document_name: string;
  chunk_index: number;
  text: string;
  score: number;
  page?: number | null;
}

export interface QueryResponse {
  id: string;
  session_id: string;
  question: string;
  answer: string;
  citations: Citation[];
  confidence: number;
  latency_ms: number;
  risk_flags: string[];
  timestamp: string;
}

export interface QueryHistoryItem {
  id: string;
  session_id: string;
  question: string;
  answer: string;
  latency_ms: number;
  confidence: number;
  timestamp: string;
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      // ignore
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

export async function listDocuments(): Promise<DocumentRead[]> {
  const res = await fetch(`${API_URL}/documents`, { cache: "no-store" });
  return handle<DocumentRead[]>(res);
}

export async function uploadDocument(
  file: File,
  documentType: DocumentType,
  onProgress?: (pct: number) => void,
): Promise<{ document: DocumentRead; preview: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", file);
    form.append("document_type", documentType);
    xhr.open("POST", `${API_URL}/upload`);
    xhr.upload.onprogress = (evt) => {
      if (evt.lengthComputable && onProgress) {
        onProgress(Math.round((evt.loaded / evt.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch (err) {
          reject(err);
        }
      } else {
        try {
          const body = JSON.parse(xhr.responseText);
          reject(new Error(body.detail ?? xhr.statusText));
        } catch {
          reject(new Error(`${xhr.status}: ${xhr.statusText}`));
        }
      }
    };
    xhr.onerror = () => reject(new Error("Network error"));
    xhr.send(form);
  });
}

export async function embedDocument(documentId: string): Promise<void> {
  const res = await fetch(`${API_URL}/embed`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ document_id: documentId }),
  });
  await handle(res);
}

export async function deleteDocument(documentId: string): Promise<void> {
  const res = await fetch(`${API_URL}/documents/${documentId}`, {
    method: "DELETE",
  });
  await handle(res);
}

export async function askQuestion(payload: {
  question: string;
  session_id?: string;
  document_ids?: string[];
}): Promise<QueryResponse> {
  const res = await fetch(`${API_URL}/query`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ ...payload, top_k: 5 }),
  });
  return handle<QueryResponse>(res);
}

export async function listQueries(limit = 10): Promise<QueryHistoryItem[]> {
  const res = await fetch(`${API_URL}/queries?limit=${limit}`, {
    cache: "no-store",
  });
  return handle<QueryHistoryItem[]>(res);
}
