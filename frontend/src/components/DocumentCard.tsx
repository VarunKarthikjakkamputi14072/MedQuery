"use client";

import { clsx } from "clsx";
import type { DocumentRead } from "@/lib/api";
import { formatBytes, formatDate } from "@/lib/format";

const TYPE_COLORS: Record<string, string> = {
  "Discharge Summary": "bg-sky-500/10 text-sky-300 border-sky-500/40",
  "Lab Report": "bg-emerald-500/10 text-emerald-300 border-emerald-500/40",
  "Clinical Note": "bg-violet-500/10 text-violet-300 border-violet-500/40",
  "Radiology Report": "bg-amber-500/10 text-amber-300 border-amber-500/40",
};

interface Props {
  document: DocumentRead;
  onDelete: (id: string) => void;
  onEmbed?: (id: string) => void;
  embedding?: boolean;
}

export function DocumentCard({ document, onDelete, onEmbed, embedding }: Props) {
  const indexed = document.pinecone_ids.length > 0;
  const tone =
    TYPE_COLORS[document.document_type] ??
    "bg-slate-500/10 text-slate-300 border-slate-500/40";

  return (
    <div className="group rounded-lg border border-clinical-border bg-clinical-panel p-4 transition hover:border-clinical-accent/50 hover:shadow-glow">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-mono text-sm text-slate-100" title={document.filename}>
            {document.filename}
          </p>
          <p className="mt-1 text-xs text-clinical-subtle">
            {formatDate(document.upload_timestamp)} · {formatBytes(document.size_bytes)}
          </p>
        </div>
        <span
          className={clsx(
            "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider",
            tone,
          )}
        >
          {document.document_type}
        </span>
      </div>

      <div className="mt-4 flex items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-3">
          <span className="rounded-md border border-clinical-border bg-clinical-surface px-2 py-1 font-mono text-[11px] text-slate-300">
            {document.chunk_count} chunks
          </span>
          <span
            className={clsx(
              "rounded-md border px-2 py-1 font-mono text-[11px]",
              indexed
                ? "border-clinical-ok/40 bg-clinical-ok/10 text-clinical-ok"
                : "border-clinical-warn/40 bg-clinical-warn/10 text-clinical-warn",
            )}
          >
            {indexed ? "indexed" : "not indexed"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {!indexed && onEmbed && (
            <button
              type="button"
              onClick={() => onEmbed(document.id)}
              disabled={embedding}
              className="rounded-md border border-clinical-accent/40 bg-clinical-accent/10 px-2 py-1 text-clinical-accent transition hover:bg-clinical-accent/20 disabled:opacity-50"
            >
              {embedding ? "Embedding…" : "Embed"}
            </button>
          )}
          <button
            type="button"
            onClick={() => onDelete(document.id)}
            className="rounded-md border border-clinical-border px-2 py-1 text-slate-300 transition hover:border-clinical-risk/60 hover:text-clinical-risk"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
