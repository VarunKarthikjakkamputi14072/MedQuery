"use client";

import { useState } from "react";
import { clsx } from "clsx";
import type { Citation } from "@/lib/api";
import { confidenceTone } from "@/lib/format";
import { SourceCitation } from "./SourceCitation";

export interface ChatMessageData {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  latency_ms?: number;
  confidence?: number;
  risk_flag?: boolean;
  risk_flags?: string[];
}

interface Props {
  message: ChatMessageData;
}

export function ChatMessage({ message }: Props) {
  const [open, setOpen] = useState(false);
  const isUser = message.role === "user";
  const tone =
    message.confidence !== undefined
      ? confidenceTone(message.confidence)
      : null;

  return (
    <div className={clsx("flex w-full", isUser ? "justify-end" : "justify-start")}>
      <div
        className={clsx(
          "max-w-2xl rounded-xl border px-4 py-3 text-sm",
          isUser
            ? "border-clinical-accent/30 bg-clinical-accent/10 text-slate-100"
            : message.risk_flag
              ? "border-clinical-risk/50 bg-clinical-risk/5 text-slate-100"
              : "border-clinical-border bg-clinical-panel text-slate-100",
        )}
      >
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              "font-mono text-[10px] uppercase tracking-wider",
              isUser ? "text-clinical-accent" : "text-clinical-subtle",
            )}
          >
            {isUser ? "You" : "MedQuery"}
          </span>
          {message.latency_ms !== undefined && (
            <span className="rounded-md border border-clinical-border bg-clinical-surface px-2 py-0.5 font-mono text-[10px] text-clinical-subtle">
              {message.latency_ms} ms
            </span>
          )}
          {tone && (
            <span
              className={clsx(
                "rounded-md border px-2 py-0.5 font-mono text-[10px]",
                tone.className,
              )}
            >
              {tone.label} · {(message.confidence! * 100).toFixed(0)}%
            </span>
          )}
        </div>

        {message.risk_flag && (
          <div className="mt-3 flex flex-col gap-2 rounded-md border border-clinical-risk/60 bg-clinical-risk/15 p-3 text-clinical-risk">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider">
              <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
                <path
                  d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <span>High-risk content detected</span>
            </div>
            {message.risk_flags && message.risk_flags.length > 0 && (
              <div className="flex flex-wrap items-center gap-1">
                {message.risk_flags.map((flag) => (
                  <span
                    key={flag}
                    className="rounded-md border border-clinical-risk/60 bg-clinical-risk/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider"
                  >
                    {flag}
                  </span>
                ))}
              </div>
            )}
            <p className="text-[11px] text-clinical-risk/90">
              Review the cited evidence carefully — this response or the
              retrieved chunks mention a clinically high-risk term.
            </p>
          </div>
        )}

        <p className="mt-2 whitespace-pre-wrap leading-relaxed">{message.content}</p>

        {message.citations && message.citations.length > 0 && (
          <div className="mt-3 border-t border-clinical-border pt-3">
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className="flex w-full items-center justify-between text-xs text-clinical-subtle hover:text-clinical-accent"
            >
              <span>{message.citations.length} source citation(s)</span>
              <span>{open ? "Hide" : "Show"}</span>
            </button>
            {open && (
              <div className="mt-3 space-y-2">
                {message.citations.map((cite, idx) => (
                  <SourceCitation key={cite.chunk_id} citation={cite} index={idx} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
