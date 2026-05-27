"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { EntitySummaryPanel } from "@/components/EntitySummaryPanel";
import {
  deleteDocument,
  embedDocument,
  extractDocument,
  getDocument,
  listDocumentEntities,
  type DocumentRead,
  type EntityRead,
} from "@/lib/api";
import { formatBytes, formatDate } from "@/lib/format";

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [document, setDocument] = useState<DocumentRead | null>(null);
  const [entities, setEntities] = useState<EntityRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [embedding, setEmbedding] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [doc, ents] = await Promise.all([
        getDocument(id),
        listDocumentEntities(id),
      ]);
      setDocument(doc);
      setEntities(ents);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load document.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const handleEmbed = async () => {
    if (!document) return;
    setEmbedding(true);
    setWarning(null);
    try {
      const res = await embedDocument(document.id);
      if (res.warning) setWarning(res.warning);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Embedding failed.");
    } finally {
      setEmbedding(false);
    }
  };

  const handleExtract = async () => {
    if (!document) return;
    setExtracting(true);
    try {
      const res = await extractDocument(document.id);
      setEntities(res.entities);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Extraction failed.");
    } finally {
      setExtracting(false);
    }
  };

  const handleDelete = async () => {
    if (!document) return;
    if (!confirm("Delete this document and all of its data?")) return;
    await deleteDocument(document.id);
    router.push("/");
  };

  if (loading) return <p className="text-sm text-clinical-subtle">Loading…</p>;
  if (error)
    return (
      <div className="rounded-lg border border-clinical-risk/50 bg-clinical-risk/10 p-4 text-sm text-clinical-risk">
        {error}
      </div>
    );
  if (!document) return null;

  const indexed = document.pinecone_ids.length > 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link
            href="/"
            className="text-xs text-clinical-subtle hover:text-clinical-accent"
          >
            ← Back to dashboard
          </Link>
          <h1 className="mt-1 break-all font-mono text-2xl font-semibold text-slate-100">
            {document.filename}
          </h1>
          <p className="mt-1 text-sm text-clinical-subtle">
            {document.document_type} · uploaded{" "}
            {formatDate(document.upload_timestamp)} ·{" "}
            {formatBytes(document.size_bytes)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!indexed && (
            <button
              type="button"
              onClick={handleEmbed}
              disabled={embedding}
              className="rounded-md border border-clinical-accent bg-clinical-accent/10 px-3 py-1.5 text-sm text-clinical-accent hover:bg-clinical-accent/20 disabled:opacity-50"
            >
              {embedding ? "Embedding…" : "Embed"}
            </button>
          )}
          <Link
            href={`/query`}
            className="rounded-md border border-clinical-border bg-clinical-surface px-3 py-1.5 text-sm text-slate-100 hover:border-clinical-accent/50"
          >
            Ask questions
          </Link>
          <button
            type="button"
            onClick={handleDelete}
            className="rounded-md border border-clinical-border bg-clinical-surface px-3 py-1.5 text-sm text-slate-100 hover:border-clinical-risk/60 hover:text-clinical-risk"
          >
            Delete
          </button>
        </div>
      </div>

      {warning && (
        <div className="rounded-lg border border-clinical-warn/50 bg-clinical-warn/10 p-3 text-xs text-clinical-warn">
          {warning}
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Stat label="Chunks" value={document.chunk_count.toString()} />
        <Stat
          label="Vectors"
          value={document.pinecone_ids.length.toString()}
        />
        <Stat label="Status" value={document.status} />
      </div>

      <EntitySummaryPanel
        entities={entities}
        onExtract={handleExtract}
        extracting={extracting}
      />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-clinical-border bg-clinical-panel p-4">
      <p className="text-xs uppercase tracking-wider text-clinical-subtle">{label}</p>
      <p className="mt-1 font-mono text-2xl text-clinical-accent">{value}</p>
    </div>
  );
}
