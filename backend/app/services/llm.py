"""Chat LLM provider with OpenAI implementation + deterministic fallback."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol

from app.core.config import get_settings


@dataclass
class ContextSnippet:
    label: str
    text: str


class ChatProvider(Protocol):
    async def complete(self, system_prompt: str, user_prompt: str) -> str: ...


SYSTEM_PROMPT = (
    "You are MedQuery, a careful clinical document assistant. "
    "Answer strictly using the provided document context. "
    "When you reference information, cite the chunk by its label like [Doc 1, chunk 2]. "
    "If the context does not contain the answer, say so explicitly and do not invent facts. "
    "Never provide medical advice; summarise what the documents say."
)


def build_user_prompt(question: str, snippets: List[ContextSnippet]) -> str:
    if not snippets:
        return (
            f"Question: {question}\n\n"
            "Context: (no documents matched)\n\n"
            "Reply that no relevant context was found."
        )

    context_block = "\n\n".join(f"[{s.label}]\n{s.text}" for s in snippets)
    return (
        f"Question: {question}\n\n"
        f"Context:\n{context_block}\n\n"
        "Provide a concise, evidence-grounded answer. Cite chunk labels in brackets."
    )


class FakeChatProvider:
    """Deterministic, citation-aware fake answer used when no API key is set."""

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        # Pull the question + first context snippet so the answer is grounded.
        question = ""
        first_snippet = ""
        first_label = ""
        for line in user_prompt.splitlines():
            if line.startswith("Question:"):
                question = line[len("Question:") :].strip()
            if line.startswith("[") and "]" in line and not first_label:
                first_label = line.strip("[]")
        if "Context:" in user_prompt:
            context_section = user_prompt.split("Context:", 1)[1]
            chunks = [c for c in context_section.split("\n\n") if c.strip()]
            if chunks:
                body = chunks[0]
                # Drop the [label] header line for the preview.
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


class OpenAIChatProvider:
    def __init__(self, api_key: str, model: str) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content or ""


def get_chat_provider() -> ChatProvider:
    settings = get_settings()
    if settings.use_fake_providers or not settings.openai_api_key:
        return FakeChatProvider()
    return OpenAIChatProvider(settings.openai_api_key, settings.openai_chat_model)
