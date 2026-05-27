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
  redaction_counts: Record<string, number>;
  size_bytes: number;
  status: string;
  processing_error?: string | null;
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
  risk_flag: boolean;
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

export interface EntityRead {
  id: string;
  document_id: string;
  entity_type: "medication" | "diagnosis" | "procedure" | "lab_value";
  entity_text: string;
  confidence: number;
  created_at: string;
}

export interface ExtractResponse {
  document_id: string;
  entities: EntityRead[];
  summary: Record<string, number>;
}

export interface EmbedResponse {
  document_id: string;
  chunk_count: number;
  pinecone_ids: string[];
  warning?: string | null;
  status: string;
  error?: string | null;
}

export interface SessionRead {
  id: string;
  created_at: string;
  document_ids: string[];
}

export interface SessionWithMessages extends SessionRead {
  messages: QueryHistoryItem[];
}

export interface DocumentUsage {
  document_id: string;
  document_name: string;
  query_count: number;
}

export interface TopQuestion {
  question: string;
  count: number;
}

export interface AnalyticsResponse {
  total_queries: number;
  avg_latency_ms: number;
  avg_confidence: number;
  queries_per_document: DocumentUsage[];
  top_questions: TopQuestion[];
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

export async function getDocument(id: string): Promise<DocumentRead> {
  const res = await fetch(`${API_URL}/documents/${id}`, { cache: "no-store" });
  return handle<DocumentRead>(res);
}

export async function uploadDocument(
  file: File,
  documentType: DocumentType,
  onProgress?: (pct: number) => void,
): Promise<{ document: DocumentRead; preview: string; task_id?: string | null }> {
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

export async function embedDocument(documentId: string): Promise<EmbedResponse> {
  const res = await fetch(`${API_URL}/embed`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ document_id: documentId }),
  });
  return handle<EmbedResponse>(res);
}

export async function extractDocument(
  documentId: string,
): Promise<ExtractResponse> {
  const res = await fetch(`${API_URL}/extract`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ document_id: documentId }),
  });
  return handle<ExtractResponse>(res);
}

export async function listDocumentEntities(
  documentId: string,
): Promise<EntityRead[]> {
  const res = await fetch(`${API_URL}/documents/${documentId}/entities`, {
    cache: "no-store",
  });
  return handle<EntityRead[]>(res);
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

export async function listSessions(): Promise<SessionRead[]> {
  const res = await fetch(`${API_URL}/sessions`, { cache: "no-store" });
  return handle<SessionRead[]>(res);
}

export async function createSession(documentIds: string[]): Promise<SessionRead> {
  const res = await fetch(`${API_URL}/sessions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ document_ids: documentIds }),
  });
  return handle<SessionRead>(res);
}

export async function getSession(id: string): Promise<SessionWithMessages> {
  const res = await fetch(`${API_URL}/sessions/${id}`, { cache: "no-store" });
  return handle<SessionWithMessages>(res);
}

export async function deleteSession(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/sessions/${id}`, { method: "DELETE" });
  await handle(res);
}

export async function getAnalytics(): Promise<AnalyticsResponse> {
  const res = await fetch(`${API_URL}/analytics`, { cache: "no-store" });
  return handle<AnalyticsResponse>(res);
}
