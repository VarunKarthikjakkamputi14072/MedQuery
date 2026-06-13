"""Chat LLM provider with OpenAI implementation + deterministic fallback."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol

from app.core.config import get_settings
from app.services.retry import retry_async


@dataclass
class ContextSnippet:
    label: str
    text: str


@dataclass
class TurnHistory:
    """A previous question/answer pair surfaced as conversation context."""

    question: str
    answer: str


class ChatProvider(Protocol):
    async def complete(self, system_prompt: str, user_prompt: str) -> str: ...


SYSTEM_PROMPT = (
    "You are MedQuery, a careful clinical document assistant. "
    "Answer strictly using the provided document context. "
    "When you reference information, cite the chunk by its label like [Doc 1, chunk 2]. "
    "If the context does not contain the answer, say so explicitly and do not invent facts. "
    "Treat the conversation history as background only — every new answer must still "
    "be grounded in the provided context. "
    "Never provide medical advice; summarise what the documents say."
)


def build_user_prompt(
    question: str,
    snippets: List[ContextSnippet],
    history: List[TurnHistory] | None = None,
) -> str:
    sections: List[str] = []

    if history:
        history_block = "\n\n".join(
            f"Q{i + 1}: {h.question}\nA{i + 1}: {h.answer}"
            for i, h in enumerate(history)
        )
        sections.append(f"Conversation so far:\n{history_block}")

    sections.append(f"Question: {question}")

    if snippets:
        context_block = "\n\n".join(f"[{s.label}]\n{s.text}" for s in snippets)
        sections.append(f"Context:\n{context_block}")
        sections.append(
            "Provide a concise, evidence-grounded answer. Cite chunk labels in brackets."
        )
    else:
        sections.append("Context: (no documents matched)")
        sections.append("Reply that no relevant context was found.")

    return "\n\n".join(sections)


class FakeChatProvider:
    """Deterministic, citation-aware fake answer used when no API key is set."""

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        question = ""
        first_snippet = ""
        first_label = ""
        for line in user_prompt.splitlines():
            if line.startswith("Question:") and not question:
                question = line[len("Question:") :].strip()
            if line.startswith("[") and "]" in line and not first_label:
                first_label = line.strip("[]")
        if "Context:" in user_prompt:
            context_section = user_prompt.split("Context:", 1)[1]
            chunks = [c for c in context_section.split("\n\n") if c.strip()]
            if chunks:
                body = chunks[0]
                first_snippet = body.split("\n", 1)[1] if "\n" in body else body
                first_snippet = first_snippet.strip()[:400]

        if not first_snippet:
            return (
                "I couldn't find any relevant content in the indexed documents for "
                f"\"{question}\". Try uploading more material or refining the question."
            )

        label_part = f"[{first_label}]" if first_label else ""
        return (
            f"Based on the retrieved clinical context {label_part}, here is what the "
            f"documents say about \"{question}\":\n\n{first_snippet}\n\n"
            "This summary is grounded in the cited chunk and is not medical advice."
        )


class OpenAICompatibleChatProvider:
    """Works with any OpenAI-compatible endpoint (OpenAI, Groq, OpenRouter, etc.)."""

    def __init__(self, api_key: str, model: str, base_url: str | None = None, label: str = "llm") -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._label = label

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        async def _call() -> str:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
            )
            return response.choices[0].message.content or ""

        return await retry_async(_call, label=self._label)


def get_chat_provider() -> ChatProvider:
    settings = get_settings()
    provider = settings.active_llm_provider

    if provider == "transit":
        # Route chat through Transit (NVIDIA NIM, metered + cached). One af_ key
        # fronts both chat and embeddings; repeated questions hit Transit's cache.
        return OpenAICompatibleChatProvider(
            api_key=settings.transit_api_key,
            model=settings.transit_chat_model,
            base_url=settings.transit_base_url,
            label="transit.chat",
        )
    if provider == "groq":
        return OpenAICompatibleChatProvider(
            api_key=settings.groq_api_key,
            model=settings.groq_chat_model,
            base_url="https://api.groq.com/openai/v1",
            label="groq.chat",
        )
    if provider == "openrouter":
        return OpenAICompatibleChatProvider(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_chat_model,
            base_url="https://openrouter.ai/api/v1",
            label="openrouter.chat",
        )
    if provider == "openai":
        return OpenAICompatibleChatProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_chat_model,
            label="openai.chat",
        )
    return FakeChatProvider()
