"""Lightweight keyword-based risk flag detection for clinical documents."""
from __future__ import annotations

import re
from typing import Iterable, List

RISK_TERMS: List[str] = [
    "sepsis",
    "hemorrhage",
    "haemorrhage",
    "stroke",
    "myocardial infarction",
    "anaphylaxis",
    "respiratory failure",
    "cardiac arrest",
    "suicidal",
    "overdose",
    "shock",
    "pulmonary embolism",
    "dka",
    "diabetic ketoacidosis",
    "code blue",
    "stat",
    "critical",
    "tachycardia",
    "hypotension",
    "hypoxia",
    "fever",
    "elevated troponin",
    "allergic reaction",
]

_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in RISK_TERMS) + r")\b",
    re.IGNORECASE,
)


def detect_risk_flags(texts: Iterable[str]) -> List[str]:
    """Return a sorted, de-duplicated list of risk terms found across the texts."""
    found: set[str] = set()
    for text in texts:
        if not text:
            continue
        for match in _PATTERN.findall(text):
            found.add(match.lower())
    return sorted(found)
