"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { clsx } from "clsx";
import { ChatMessage, type ChatMessageData } from "@/components/ChatMessage";
import {
  askQuestion,
  createSession,
  deleteSession,
  getSession,
  listDocuments,
  listSessions,
  type DocumentRead,
  type SessionRead,
} from "@/lib/api";
import { formatDate } from "@/lib/format";

export default function QueryPage() {
  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [sessions, setSessions] = useState<SessionRead[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [question, setQuestion] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void listDocuments().then((docs) => {
      setDocuments(docs);
      setSelected(docs.filter((d) => d.pinecone_ids.length > 0).map((d) => d.id));
    });
    void listSessions().then(setSessions);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const indexedDocs = useMemo(
    () => documents.filter((d) => d.pinecone_ids.length > 0),
    [documents],
  );

  const toggle = useCallback((id: string) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }, []);

  const refreshSessions = async () => {
    setSessions(await listSessions());
  };

  const loadSession = async (id: string) => {
    setError(null);
    try {
      const sess = await getSession(id);
      setSessionId(sess.id);
      setSelected(sess.document_ids);
      setMessages(
        sess.messages.flatMap((m) => [
          { role: "user" as const, content: m.question },
          {
            role: "assistant" as const,
            content: m.answer,
            latency_ms: m.latency_ms,
            confidence: m.confidence,
          },
        ]),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load session.");
    }
  };

  const removeSession = async (id: string) => {
    if (!confirm("Delete this session and all of its messages?")) return;
    await deleteSession(id);
    if (sessionId === id) {
      setSessionId(undefined);
      setMessages([]);
    }
    await refreshSessions();
  };

  const startSession = async () => {
    const sess = await createSession(selected);
    setSessionId(sess.id);
    setMessages([]);
    await refreshSessions();
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || pending) return;

    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setQuestion("");
    setPending(true);

    try {
      const response = await askQuestion({
        question: q,
        session_id: sessionId,
        document_ids: selected.length ? selected : undefined,
      });
      const sessionWasNew = !sessionId;
      setSessionId(response.session_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.answer,
          citations: response.citations,
          latency_ms: response.latency_ms,
          confidence: response.confidence,
          risk_flag: response.risk_flag,
          risk_flags: response.risk_flags,
        },
      ]);
      if (sessionWasNew) await refreshSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed.");
    } finally {
      setPending(false);
    }
  };

  const resetSession = () => {
    setSessionId(undefined);
    setMessages([]);
  };

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside className="space-y-4">
        <div className="rounded-xl border border-clinical-border bg-clinical-panel p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-medium uppercase tracking-wider text-clinical-subtle">
              Documents
            </h2>
            <button
              type="button"
              onClick={() =>
                setSelected(
                  selected.length === indexedDocs.length
                    ? []
                    : indexedDocs.map((d) => d.id),
                )
              }
              className="text-[11px] text-clinical-accent hover:underline"
            >
              {selected.length === indexedDocs.length ? "Clear" : "Select all"}
            </button>
          </div>
          {indexedDocs.length === 0 ? (
            <p className="mt-3 text-xs text-clinical-subtle">
              No indexed documents. Upload and embed first.
            </p>
          ) : (
            <ul className="mt-3 max-h-[360px] space-y-1 overflow-auto pr-1">
              {indexedDocs.map((doc) => {
                const checked = selected.includes(doc.id);
                return (
                  <li key={doc.id}>
                    <label
                      className={clsx(
                        "flex cursor-pointer items-start gap-2 rounded-md border p-2 text-xs transition",
                        checked
                          ? "border-clinical-accent/40 bg-clinical-accent/10"
                          : "border-clinical-border bg-clinical-surface hover:border-clinical-accent/30",
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggle(doc.id)}
                        className="mt-0.5 h-3 w-3 accent-clinical-accent"
                      />
                      <span className="min-w-0 flex-1">
                        <span
                          className="block truncate font-mono text-[12px] text-slate-100"
                          title={doc.filename}
                        >
                          {doc.filename}
                        </span>
                        <span className="block text-[10px] uppercase tracking-wider text-clinical-subtle">
                          {doc.document_type} · {doc.chunk_count} chunks
                        </span>
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="rounded-xl border border-clinical-border bg-clinical-panel p-4 text-xs text-clinical-subtle">
          <div className="flex items-center justify-between">
            <p className="font-mono uppercase tracking-wider text-clinical-accent">
              Sessions
            </p>
            <button
              type="button"
              onClick={startSession}
              className="rounded-md border border-clinical-accent/40 bg-clinical-accent/10 px-2 py-0.5 text-[11px] text-clinical-accent hover:bg-clinical-accent/20"
            >
              + New
            </button>
          </div>

          {sessionId && (
            <div className="mt-3 rounded-md border border-clinical-accent/30 bg-clinical-accent/5 p-2">
              <p className="break-all font-mono text-[10px] text-clinical-accent">
                Active: {sessionId.slice(0, 8)}…
              </p>
              <button
                type="button"
                onClick={resetSession}
                className="mt-1 text-[10px] text-slate-300 hover:text-clinical-accent"
              >
                Detach
              </button>
            </div>
          )}

          {sessions.length === 0 ? (
            <p className="mt-3">No sessions yet. They&rsquo;re created on first query.</p>
          ) : (
            <ul className="mt-3 max-h-[200px] space-y-1 overflow-auto pr-1">
              {sessions.map((s) => (
                <li
                  key={s.id}
                  className={clsx(
                    "rounded-md border p-2",
                    s.id === sessionId
                      ? "border-clinical-accent/40 bg-clinical-accent/10"
                      : "border-clinical-border bg-clinical-surface",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <button
                      type="button"
                      onClick={() => void loadSession(s.id)}
                      className="min-w-0 flex-1 text-left text-[11px] text-slate-100 hover:text-clinical-accent"
                    >
                      <span className="block truncate font-mono">
                        {s.id.slice(0, 8)}…
                      </span>
                      <span className="block text-[10px] text-clinical-subtle">
                        {formatDate(s.created_at)}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => void removeSession(s.id)}
                      className="text-[10px] text-clinical-subtle hover:text-clinical-risk"
                    >
                      Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      <section className="flex h-[calc(100vh-12rem)] flex-col rounded-xl border border-clinical-border bg-clinical-panel">
        <div className="border-b border-clinical-border px-5 py-3">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-clinical-accent">
            Conversation
          </p>
          <p className="text-sm text-clinical-subtle">
            {selected.length > 0
              ? `Querying ${selected.length} document${selected.length === 1 ? "" : "s"}`
              : "Querying all indexed documents"}
            {" · last 3 turns provided as conversation context"}
          </p>
        </div>

        <div className="flex-1 space-y-4 overflow-auto px-5 py-4">
          {messages.length === 0 && (
            <div className="rounded-lg border border-dashed border-clinical-border bg-clinical-surface p-6 text-center text-sm text-clinical-subtle">
              Ask any question about your indexed clinical documents. MedQuery
              retrieves the top-5 most relevant chunks, passes recent
              conversation history as context, and answers with grounded
              citations.
            </div>
          )}
          {messages.map((msg, idx) => (
            <ChatMessage key={idx} message={msg} />
          ))}
          {pending && (
            <div className="flex items-center gap-2 text-xs text-clinical-subtle">
              <span className="h-2 w-2 animate-pulse rounded-full bg-clinical-accent" />
              Retrieving and reasoning…
            </div>
          )}
          {error && <p className="text-xs text-clinical-risk">{error}</p>}
          <div ref={bottomRef} />
        </div>

        <form
          onSubmit={submit}
          className="flex items-end gap-3 border-t border-clinical-border px-5 py-4"
        >
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void submit(e as unknown as React.FormEvent);
              }
            }}
            rows={2}
            placeholder="e.g. What antibiotics were prescribed at discharge?"
            className="flex-1 resize-none rounded-md border border-clinical-border bg-clinical-surface px-3 py-2 font-mono text-sm text-slate-100 placeholder:text-clinical-subtle focus:border-clinical-accent focus:outline-none"
          />
          <button
            type="submit"
            disabled={pending || !question.trim()}
            className="rounded-md border border-clinical-accent bg-clinical-accent/10 px-4 py-2 text-sm font-medium text-clinical-accent transition hover:bg-clinical-accent/20 disabled:opacity-50"
          >
            {pending ? "Asking…" : "Ask"}
          </button>
        </form>
      </section>
    </div>
  );
}
