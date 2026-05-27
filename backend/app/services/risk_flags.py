"""Keyword-based risk flag detection for clinical responses."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List

# Required high-risk term list. Matching is case-insensitive but order-preserving.
HIGH_RISK_TERMS: List[str] = [
    "critical",
    "STAT",
    "emergency",
    "sepsis",
    "deteriorating",
    "DNR",
    "code blue",
]

_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in HIGH_RISK_TERMS) + r")\b",
    re.IGNORECASE,
)


@dataclass
class RiskAssessment:
    risk_flag: bool
    matched_terms: List[str]


def detect_risk_flags(texts: Iterable[str]) -> RiskAssessment:
    """Scan inputs for high-risk clinical terms.

    Returns the canonical (originally-cased) matched terms in the order they
    appear in HIGH_RISK_TERMS, along with a boolean `risk_flag`.
    """
    canonical_by_lower = {term.lower(): term for term in HIGH_RISK_TERMS}
    found_lower: set[str] = set()
    for text in texts:
        if not text:
            continue
        for match in _PATTERN.findall(text):
            found_lower.add(match.lower())

    matched = [
        canonical_by_lower[term.lower()]
        for term in HIGH_RISK_TERMS
        if term.lower() in found_lower
    ]
    return RiskAssessment(risk_flag=bool(matched), matched_terms=matched)
