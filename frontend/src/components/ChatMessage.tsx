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
    <div
      className={clsx(
        "flex w-full",
        isUser ? "justify-end" : "justify-start",
      )}
    >
      <div
        className={clsx(
          "max-w-2xl rounded-xl border px-4 py-3 text-sm",
          isUser
            ? "border-clinical-accent/30 bg-clinical-accent/10 text-slate-100"
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

        <p className="mt-2 whitespace-pre-wrap leading-relaxed">
          {message.content}
        </p>

        {message.risk_flags && message.risk_flags.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-1">
            <span className="text-[10px] uppercase tracking-wider text-clinical-risk">
              Risk flags
            </span>
            {message.risk_flags.map((flag) => (
              <span
                key={flag}
                className="rounded-md border border-clinical-risk/40 bg-clinical-risk/10 px-2 py-0.5 font-mono text-[10px] text-clinical-risk"
              >
                {flag}
              </span>
            ))}
          </div>
        )}

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
