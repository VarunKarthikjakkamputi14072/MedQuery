"""PHI/PII redaction before text leaves the backend boundary."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import get_settings
from app.services.text_extraction import Chunk


@dataclass(frozen=True)
class RedactionResult:
    text: str
    counts: dict[str, int] = field(default_factory=dict)


class PhiRedactor(Protocol):
    def redact(self, text: str) -> RedactionResult: ...


class RegexPhiRedactor:
    """Deterministic fallback redactor used when Presidio is unavailable."""

    _patterns: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("US_SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
        ("EMAIL_ADDRESS", re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")),
        (
            "PHONE_NUMBER",
            re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        ),
        (
            "DATE_TIME",
            re.compile(
                r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|"
                r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
                r"[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b",
                re.IGNORECASE,
            ),
        ),
        (
            "MEDICAL_RECORD_NUMBER",
            re.compile(r"\b(?:MRN|medical record(?: number)?|patient id)\s*[:#-]?\s*[A-Z0-9-]{4,}\b", re.IGNORECASE),
        ),
    )
    _name_pattern = re.compile(
        r"\b(Patient|Name)\s*[:#-]?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b"
    )

    def redact(self, text: str) -> RedactionResult:
        counts: Counter[str] = Counter()
        redacted = text

        def _name_repl(match: re.Match[str]) -> str:
            counts["PERSON"] += 1
            return f"{match.group(1)} [REDACTED_PERSON]"

        redacted = self._name_pattern.sub(_name_repl, redacted)
        for entity_type, pattern in self._patterns:
            redacted, count = pattern.subn(f"[REDACTED_{entity_type}]", redacted)
            if count:
                counts[entity_type] += count

        return RedactionResult(text=redacted, counts=dict(counts))


class PresidioPhiRedactor:
    """Microsoft Presidio-backed redactor with regex cleanup for clinical IDs."""

    _entities = [
        "PERSON",
        "DATE_TIME",
        "PHONE_NUMBER",
        "EMAIL_ADDRESS",
        "US_SSN",
        "US_DRIVER_LICENSE",
        "US_PASSPORT",
        "LOCATION",
    ]

    def __init__(self) -> None:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        self._analyzer = AnalyzerEngine()
        self._anonymizer = AnonymizerEngine()
        self._fallback = RegexPhiRedactor()

    def redact(self, text: str) -> RedactionResult:
        from presidio_anonymizer.entities import OperatorConfig

        analyzer_results = self._analyzer.analyze(
            text=text,
            language="en",
            entities=self._entities,
        )
        counts: Counter[str] = Counter(result.entity_type for result in analyzer_results)
        operators = {
            entity: OperatorConfig(
                "replace",
                {"new_value": f"[REDACTED_{entity}]"},
            )
            for entity in self._entities
        }
        anonymized = self._anonymizer.anonymize(
            text=text,
            analyzer_results=analyzer_results,
            operators=operators,
        )

        # Presidio's default recognizers do not cover every hospital-specific
        # identifier format, so run the deterministic rules afterward.
        fallback = self._fallback.redact(anonymized.text)
        counts.update(fallback.counts)
        return RedactionResult(text=fallback.text, counts=dict(counts))


def get_phi_redactor() -> PhiRedactor:
    settings = get_settings()
    if settings.redaction_provider.lower() != "presidio":
        return RegexPhiRedactor()
    try:
        return PresidioPhiRedactor()
    except Exception:
        return RegexPhiRedactor()


def redact_chunks(
    chunks: list[Chunk],
    redactor: PhiRedactor | None = None,
) -> tuple[list[Chunk], dict[str, int]]:
    active_redactor = redactor or get_phi_redactor()
    totals: Counter[str] = Counter()
    redacted_chunks: list[Chunk] = []

    for chunk in chunks:
        result = active_redactor.redact(chunk.text)
        totals.update(result.counts)
        redacted_chunks.append(
            Chunk(index=chunk.index, text=result.text, page=chunk.page)
        )

    return redacted_chunks, dict(totals)
