"use client";

import { clsx } from "clsx";
import type { EntityRead } from "@/lib/api";

const TYPE_LABELS: Record<EntityRead["entity_type"], string> = {
  medication: "Medications",
  diagnosis: "Diagnoses",
  procedure: "Procedures",
  lab_value: "Lab values",
};

const TYPE_TONES: Record<EntityRead["entity_type"], string> = {
  medication: "border-sky-500/40 bg-sky-500/10 text-sky-300",
  diagnosis: "border-rose-500/40 bg-rose-500/10 text-rose-300",
  procedure: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  lab_value: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
};

interface Props {
  entities: EntityRead[];
  onExtract?: () => void;
  extracting?: boolean;
}

export function EntitySummaryPanel({ entities, onExtract, extracting }: Props) {
  const groups: Record<EntityRead["entity_type"], EntityRead[]> = {
    medication: [],
    diagnosis: [],
    procedure: [],
    lab_value: [],
  };
  for (const e of entities) {
    if (groups[e.entity_type]) groups[e.entity_type].push(e);
  }

  return (
    <div className="rounded-xl border border-clinical-border bg-clinical-panel p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-clinical-accent">
            Medical entities
          </p>
          <p className="text-sm text-clinical-subtle">
            {entities.length === 0
              ? "No entities extracted yet."
              : `${entities.length} extracted across ${
                  Object.values(groups).filter((g) => g.length > 0).length
                } categories.`}
          </p>
        </div>
        {onExtract && (
          <button
            type="button"
            onClick={onExtract}
            disabled={extracting}
            className="rounded-md border border-clinical-accent bg-clinical-accent/10 px-3 py-1.5 text-xs font-medium text-clinical-accent transition hover:bg-clinical-accent/20 disabled:opacity-50"
          >
            {extracting ? "Extracting…" : entities.length ? "Re-extract" : "Run extraction"}
          </button>
        )}
      </div>

      {entities.length > 0 && (
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
          {(Object.keys(groups) as EntityRead["entity_type"][]).map((type) => {
            const items = groups[type];
            if (items.length === 0) return null;
            return (
              <div
                key={type}
                className="rounded-lg border border-clinical-border bg-clinical-surface p-3"
              >
                <div className="flex items-center justify-between text-xs uppercase tracking-wider text-clinical-subtle">
                  <span>{TYPE_LABELS[type]}</span>
                  <span className="font-mono text-clinical-accent">
                    {items.length}
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {items.map((e) => (
                    <span
                      key={e.id}
                      title={`confidence ${(e.confidence * 100).toFixed(0)}%`}
                      className={clsx(
                        "rounded-md border px-2 py-0.5 font-mono text-[11px]",
                        TYPE_TONES[type],
                      )}
                    >
                      {e.entity_text}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
