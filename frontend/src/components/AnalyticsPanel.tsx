"use client";

import type { AnalyticsResponse } from "@/lib/api";

interface Props {
  data: AnalyticsResponse;
}

export function AnalyticsPanel({ data }: Props) {
  return (
    <section className="rounded-xl border border-clinical-border bg-clinical-panel p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-clinical-accent">
            Analytics
          </p>
          <p className="text-sm text-clinical-subtle">
            Query volume, latency, and most-asked questions.
          </p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Stat
          label="Total queries"
          value={data.total_queries.toString()}
        />
        <Stat
          label="Avg latency"
          value={`${Math.round(data.avg_latency_ms)} ms`}
        />
        <Stat
          label="Avg confidence"
          value={`${Math.round((data.avg_confidence ?? 0) * 100)}%`}
        />
      </div>

      <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-clinical-border bg-clinical-surface p-4">
          <p className="text-xs uppercase tracking-wider text-clinical-subtle">
            Queries per document
          </p>
          {data.queries_per_document.length === 0 ? (
            <p className="mt-2 text-xs text-clinical-subtle">No queries yet.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {data.queries_per_document.slice(0, 6).map((doc) => {
                const max = Math.max(
                  ...data.queries_per_document.map((d) => d.query_count),
                );
                const pct = max === 0 ? 0 : (doc.query_count / max) * 100;
                return (
                  <li key={doc.document_id}>
                    <div className="flex items-center justify-between text-xs">
                      <span
                        className="truncate font-mono text-slate-200"
                        title={doc.document_name}
                      >
                        {doc.document_name}
                      </span>
                      <span className="font-mono text-clinical-accent">
                        {doc.query_count}
                      </span>
                    </div>
                    <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-clinical-bg">
                      <div
                        className="h-full bg-clinical-accent"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="rounded-lg border border-clinical-border bg-clinical-surface p-4">
          <p className="text-xs uppercase tracking-wider text-clinical-subtle">
            Top 5 questions
          </p>
          {data.top_questions.length === 0 ? (
            <p className="mt-2 text-xs text-clinical-subtle">No queries yet.</p>
          ) : (
            <ol className="mt-3 space-y-2 text-sm">
              {data.top_questions.map((q, idx) => (
                <li
                  key={`${q.question}-${idx}`}
                  className="flex items-start gap-2 text-slate-200"
                >
                  <span className="mt-0.5 font-mono text-xs text-clinical-accent">
                    #{idx + 1}
                  </span>
                  <span className="flex-1">{q.question}</span>
                  <span className="rounded-md border border-clinical-border bg-clinical-bg px-2 py-0.5 font-mono text-[11px] text-clinical-subtle">
                    {q.count}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-clinical-border bg-clinical-surface p-4">
      <p className="text-xs uppercase tracking-wider text-clinical-subtle">{label}</p>
      <p className="mt-1 font-mono text-2xl text-clinical-accent">{value}</p>
    </div>
  );
}
