"use client";

import type { Citation } from "@/lib/api";

interface Props {
  citation: Citation;
  index: number;
}

export function SourceCitation({ citation, index }: Props) {
  return (
    <div className="rounded-lg border border-clinical-border bg-clinical-surface/60 p-3 text-sm">
      <div className="flex items-center justify-between gap-2 text-xs text-clinical-subtle">
        <span className="font-mono text-clinical-accent">
          [Doc {index + 1}] {citation.document_name}
          {citation.page ? ` · p.${citation.page}` : ""}
        </span>
        <span className="font-mono">
          chunk {citation.chunk_index} · score {citation.score.toFixed(3)}
        </span>
      </div>
      <p className="mt-2 whitespace-pre-wrap font-mono text-[13px] leading-relaxed text-slate-200">
        {citation.text}
      </p>
    </div>
  );
}
