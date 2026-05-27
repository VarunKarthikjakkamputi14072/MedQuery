"use client";

import { useRouter } from "next/navigation";
import { UploadZone } from "@/components/UploadZone";
import { embedDocument, uploadDocument } from "@/lib/api";

export default function UploadPage() {
  const router = useRouter();

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-clinical-accent">
          Ingest
        </p>
        <h1 className="mt-1 text-2xl font-semibold">Upload a clinical document</h1>
        <p className="mt-2 max-w-2xl text-sm text-clinical-subtle">
          We&rsquo;ll extract text with PyPDF2, chunk it into 512-token segments
          (with 50-token overlap) via LangChain, embed each chunk with OpenAI, and
          index the vectors in Pinecone — all triggered automatically after upload.
        </p>
      </div>

      <div className="rounded-xl border border-clinical-border bg-clinical-panel p-6 shadow-glow">
        <UploadZone
          onUpload={async (file, documentType, onProgress) => {
            const { document } = await uploadDocument(
              file,
              documentType,
              onProgress,
            );
            return { documentId: document.id };
          }}
          onIndex={async (documentId) => {
            await embedDocument(documentId);
          }}
        />
      </div>

      <div className="flex justify-between text-xs text-clinical-subtle">
        <span>
          Accepted formats: <span className="font-mono text-slate-200">.pdf</span>,{" "}
          <span className="font-mono text-slate-200">.txt</span>
        </span>
        <button
          type="button"
          onClick={() => router.push("/")}
          className="text-clinical-accent hover:underline"
        >
          Back to dashboard →
        </button>
      </div>
    </div>
  );
}
