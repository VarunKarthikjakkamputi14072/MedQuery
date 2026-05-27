"use client";

import { useCallback, useRef, useState } from "react";
import { clsx } from "clsx";
import type { DocumentType } from "@/lib/api";

const DOCUMENT_TYPES: DocumentType[] = [
  "Discharge Summary",
  "Lab Report",
  "Clinical Note",
  "Radiology Report",
];

const MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED = [".pdf", ".txt"];

interface UploadStatus {
  state: "idle" | "uploading" | "embedding" | "done" | "error";
  progress: number;
  message?: string;
  filename?: string;
}

interface Props {
  onUpload: (
    file: File,
    documentType: DocumentType,
    onProgress: (pct: number) => void,
  ) => Promise<{ documentId: string }>;
  onIndex: (documentId: string) => Promise<void>;
}

export function UploadZone({ onUpload, onIndex }: Props) {
  const [documentType, setDocumentType] = useState<DocumentType>("Clinical Note");
  const [isDragging, setIsDragging] = useState(false);
  const [status, setStatus] = useState<UploadStatus>({
    state: "idle",
    progress: 0,
  });
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    async (fileList: FileList | null) => {
      if (!fileList || fileList.length === 0) return;
      const file = fileList[0];

      const ext = "." + (file.name.split(".").pop() || "").toLowerCase();
      if (!ALLOWED.includes(ext)) {
        setStatus({
          state: "error",
          progress: 0,
          message: "Only PDF or TXT files are accepted.",
          filename: file.name,
        });
        return;
      }
      if (file.size > MAX_BYTES) {
        setStatus({
          state: "error",
          progress: 0,
          message: "File exceeds the 10 MB limit.",
          filename: file.name,
        });
        return;
      }

      setStatus({ state: "uploading", progress: 0, filename: file.name });
      try {
        const { documentId } = await onUpload(file, documentType, (pct) => {
          setStatus((prev) => ({ ...prev, progress: pct }));
        });

        setStatus({
          state: "embedding",
          progress: 100,
          filename: file.name,
          message: "Generating embeddings…",
        });
        await onIndex(documentId);

        setStatus({
          state: "done",
          progress: 100,
          filename: file.name,
          message: "Indexed and ready to query.",
        });
      } catch (err) {
        setStatus({
          state: "error",
          progress: 0,
          filename: file.name,
          message: err instanceof Error ? err.message : "Upload failed.",
        });
      }
    },
    [documentType, onIndex, onUpload],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs uppercase tracking-wider text-clinical-subtle">
          Document Type
        </span>
        {DOCUMENT_TYPES.map((type) => (
          <button
            key={type}
            type="button"
            onClick={() => setDocumentType(type)}
            className={clsx(
              "rounded-md border px-3 py-1 text-xs transition",
              documentType === type
                ? "border-clinical-accent bg-clinical-accent/10 text-clinical-accent shadow-glow"
                : "border-clinical-border bg-clinical-panel text-slate-300 hover:border-clinical-accent/50",
            )}
          >
            {type}
          </button>
        ))}
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          void handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        className={clsx(
          "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 text-center transition",
          isDragging
            ? "border-clinical-accent bg-clinical-accent/5"
            : "border-clinical-border bg-clinical-panel hover:border-clinical-accent/60 hover:bg-clinical-surface",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt"
          className="hidden"
          onChange={(e) => void handleFiles(e.target.files)}
        />
        <svg
          className="mb-3 h-10 w-10 text-clinical-accent"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 16.5V19a2 2 0 002 2h14a2 2 0 002-2v-2.5M16 8l-4-4m0 0L8 8m4-4v12"
          />
        </svg>
        <p className="text-base font-medium text-slate-100">
          Drag and drop a clinical document
        </p>
        <p className="mt-1 text-xs text-clinical-subtle">
          PDF or TXT, up to 10 MB · or click to browse
        </p>
      </div>

      {status.state !== "idle" && (
        <div className="rounded-lg border border-clinical-border bg-clinical-panel p-4">
          <div className="flex items-center justify-between text-sm">
            <span className="font-mono text-slate-200 truncate">
              {status.filename}
            </span>
            <span
              className={clsx(
                "rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider",
                status.state === "done"
                  ? "bg-clinical-ok/10 text-clinical-ok"
                  : status.state === "error"
                    ? "bg-clinical-risk/10 text-clinical-risk"
                    : "bg-clinical-accent/10 text-clinical-accent",
              )}
            >
              {status.state}
            </span>
          </div>
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-clinical-surface">
            <div
              className={clsx(
                "h-full transition-all",
                status.state === "error"
                  ? "bg-clinical-risk"
                  : "bg-clinical-accent",
              )}
              style={{ width: `${status.progress}%` }}
            />
          </div>
          {status.message && (
            <p
              className={clsx(
                "mt-2 text-xs",
                status.state === "error"
                  ? "text-clinical-risk"
                  : "text-clinical-subtle",
              )}
            >
              {status.message}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
