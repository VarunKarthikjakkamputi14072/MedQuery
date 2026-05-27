"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AnalyticsPanel } from "@/components/AnalyticsPanel";
import { DocumentCard } from "@/components/DocumentCard";
import {
  deleteDocument,
  embedDocument,
  getAnalytics,
  listDocuments,
  listQueries,
  type AnalyticsResponse,
  type DocumentRead,
  type QueryHistoryItem,
} from "@/lib/api";
import { confidenceTone, formatDate } from "@/lib/format";

export default function DashboardPage() {
  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [queries, setQueries] = useState<QueryHistoryItem[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [embedding, setEmbedding] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setError(null);
    try {
      const [docs, qs, an] = await Promise.all([
        listDocuments(),
        listQueries(5),
        getAnalytics(),
      ]);
      setDocuments(docs);
      setQueries(qs);
      setAnalytics(an);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this document and its embeddings?")) return;
    await deleteDocument(id);
    await reload();
  };

  const handleEmbed = async (id: string) => {
    setEmbedding(id);
    setWarning(null);
    try {
      const res = await embedDocument(id);
      if (res.warning) setWarning(res.warning);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Embedding failed.");
    } finally {
      setEmbedding(null);
    }
  };

  const indexedCount = documents.filter((d) => d.pinecone_ids.length > 0).length;
  const totalChunks = documents.reduce((acc, d) => acc + d.chunk_count, 0);

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-clinical-border bg-clinical-panel p-6 shadow-glow">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-clinical-accent">
              Dashboard
            </p>
            <h1 className="mt-1 text-2xl font-semibold text-slate-100">
              Clinical document intelligence at a glance
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-clinical-subtle">
              Upload discharge summaries, lab reports, clinical notes and radiology
              reports. MedQuery extracts structured insights, indexes them for
              retrieval, and answers grounded clinical questions with citations.
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              href="/upload"
              className="rounded-md border border-clinical-accent bg-clinical-accent/10 px-4 py-2 text-sm font-medium text-clinical-accent hover:bg-clinical-accent/20"
            >
              + Upload document
            </Link>
            <Link
              href="/query"
              className="rounded-md border border-clinical-border bg-clinical-surface px-4 py-2 text-sm font-medium text-slate-100 hover:border-clinical-accent/50"
            >
              Open query interface
            </Link>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Stat label="Documents" value={documents.length.toString()} />
          <Stat label="Indexed" value={`${indexedCount}/${documents.length || 0}`} />
          <Stat label="Total chunks" value={totalChunks.toString()} />
        </div>
      </section>

      {warning && (
        <div className="rounded-lg border border-clinical-warn/50 bg-clinical-warn/10 p-3 text-xs text-clinical-warn">
          {warning}
        </div>
      )}
      {error && (
        <div className="rounded-lg border border-clinical-risk/50 bg-clinical-risk/10 p-4 text-sm text-clinical-risk">
          {error}
        </div>
      )}

      {analytics && <AnalyticsPanel data={analytics} />}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium uppercase tracking-wider text-clinical-subtle">
            Uploaded documents
          </h2>
          <button
            type="button"
            onClick={() => void reload()}
            className="text-xs text-clinical-subtle hover:text-clinical-accent"
          >
            Refresh
          </button>
        </div>

        {loading ? (
          <p className="text-sm text-clinical-subtle">Loading…</p>
        ) : documents.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {documents.map((doc) => (
              <DocumentCard
                key={doc.id}
                document={doc}
                onDelete={handleDelete}
                onEmbed={handleEmbed}
                embedding={embedding === doc.id}
              />
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-clinical-subtle">
          Recent queries
        </h2>
        {queries.length === 0 ? (
          <p className="text-sm text-clinical-subtle">
            No queries yet. Visit the{" "}
            <Link href="/query" className="text-clinical-accent hover:underline">
              query interface
            </Link>{" "}
            to ask your first clinical question.
          </p>
        ) : (
          <div className="space-y-2">
            {queries.map((q) => {
              const tone = confidenceTone(q.confidence);
              return (
                <div
                  key={q.id}
                  className="rounded-lg border border-clinical-border bg-clinical-panel p-4"
                >
                  <div className="flex items-center justify-between text-xs text-clinical-subtle">
                    <span className="font-mono">{formatDate(q.timestamp)}</span>
                    <div className="flex gap-2">
                      <span className="rounded-md border border-clinical-border bg-clinical-surface px-2 py-0.5 font-mono">
                        {q.latency_ms} ms
                      </span>
                      <span
                        className={`rounded-md border px-2 py-0.5 font-mono ${tone.className}`}
                      >
                        {tone.label}
                      </span>
                    </div>
                  </div>
                  <p className="mt-2 text-sm font-medium text-slate-100">
                    {q.question}
                  </p>
                  <p className="mt-1 line-clamp-2 text-xs text-clinical-subtle">
                    {q.answer}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-clinical-border bg-clinical-surface p-4">
      <p className="text-xs uppercase tracking-wider text-clinical-subtle">
        {label}
      </p>
      <p className="mt-1 font-mono text-2xl text-clinical-accent">{value}</p>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-xl border border-dashed border-clinical-border bg-clinical-panel p-10 text-center">
      <p className="text-sm text-slate-200">No documents indexed yet.</p>
      <p className="mt-1 text-xs text-clinical-subtle">
        Head to the upload page to ingest your first clinical document.
      </p>
      <Link
        href="/upload"
        className="mt-4 inline-flex items-center rounded-md border border-clinical-accent bg-clinical-accent/10 px-4 py-2 text-sm text-clinical-accent hover:bg-clinical-accent/20"
      >
        Upload document
      </Link>
    </div>
  );
}
