"""Medical entity extraction.

Primary backend: spaCy with the `en_core_sci_sm` scientific model from
scispaCy. When that model isn't installed (it ships as a separate wheel
and is not always available), we fall back to a deterministic regex /
keyword extractor so the `/extract` endpoint always works.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, List

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    entity_type: str
    entity_text: str
    confidence: float


# ------------------------------ heuristics ----------------------------------

MEDICATION_KEYWORDS = [
    "aspirin", "ibuprofen", "acetaminophen", "paracetamol", "tylenol",
    "amoxicillin", "azithromycin", "ciprofloxacin", "levofloxacin",
    "metformin", "insulin", "lisinopril", "atorvastatin", "simvastatin",
    "warfarin", "heparin", "clopidogrel", "metoprolol", "amlodipine",
    "furosemide", "lasix", "omeprazole", "pantoprazole", "morphine",
    "fentanyl", "oxycodone", "hydrocodone", "prednisone", "albuterol",
    "vancomycin", "piperacillin", "tazobactam", "ceftriaxone", "norepinephrine",
    "epinephrine", "dopamine", "ondansetron", "diphenhydramine",
]

# Common dosage suffixes that suggest a medication mention.
MED_DOSAGE_PATTERN = re.compile(
    r"\b([A-Z][a-zA-Z\-]{2,}(?:\s+[A-Z][a-zA-Z\-]{2,})?)\s+(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|units?|iu))\b",
    re.IGNORECASE,
)

DIAGNOSIS_KEYWORDS = [
    "sepsis", "septic shock", "pneumonia", "asthma", "copd", "diabetes",
    "hypertension", "hyperlipidemia", "hypothyroidism", "hyperthyroidism",
    "myocardial infarction", "stroke", "tia", "atrial fibrillation",
    "congestive heart failure", "heart failure", "renal failure",
    "acute kidney injury", "uti", "urinary tract infection",
    "bronchitis", "anemia", "leukocytosis", "thrombocytopenia",
    "deep vein thrombosis", "pulmonary embolism", "dka",
    "diabetic ketoacidosis", "cellulitis", "appendicitis", "gastroenteritis",
    "depression", "anxiety", "cancer", "carcinoma", "lymphoma", "fracture",
    "hyperglycemia", "hypoglycemia", "hypoxia", "tachycardia", "bradycardia",
    "hypotension", "hypertension",
]

PROCEDURE_KEYWORDS = [
    "intubation", "extubation", "cardioversion", "defibrillation",
    "catheterization", "biopsy", "endoscopy", "colonoscopy", "ct scan",
    "mri", "x-ray", "ultrasound", "ekg", "ecg", "echocardiogram",
    "angiography", "angioplasty", "stent placement", "appendectomy",
    "cholecystectomy", "hysterectomy", "thoracentesis", "paracentesis",
    "lumbar puncture", "central line", "arterial line", "dialysis",
    "blood transfusion", "transfusion", "ventilation", "surgery",
]

LAB_VALUE_PATTERN = re.compile(
    r"\b(WBC|RBC|HGB|Hgb|HCT|PLT|MCV|MCH|MCHC|RDW|"
    r"Na|K|Cl|HCO3|BUN|Cr|Glu|Glucose|Ca|Mg|Phos|Phosphorus|"
    r"AST|ALT|ALP|TBili|"
    r"Troponin|BNP|"
    r"INR|PT|PTT|"
    r"Lactate|Lac|"
    r"CRP|ESR|"
    r"pH|pCO2|pO2|"
    r"HbA1c|A1c)"
    r"\s*[:=]?\s*"
    r"(\d+(?:\.\d+)?)"
    r"\s*"
    r"(mg/dL|mmol/L|mEq/L|g/dL|mIU/L|U/L|ng/mL|pg/mL|%|x10\^3/uL|x10\^9/L|mmHg|sec|seconds)?",
    re.IGNORECASE,
)


def _keyword_matches(text: str, keywords: Iterable[str]) -> List[str]:
    found: List[str] = []
    seen: set[str] = set()
    lower = text.lower()
    for kw in keywords:
        if kw in lower:
            for m in re.finditer(r"\b" + re.escape(kw) + r"\b", lower):
                snippet = text[m.start() : m.end()]
                key = snippet.lower()
                if key not in seen:
                    seen.add(key)
                    found.append(snippet)
    return found


def _regex_extract(text: str) -> List[ExtractedEntity]:
    entities: List[ExtractedEntity] = []
    seen: set[tuple[str, str]] = set()

    def _add(entity_type: str, value: str, confidence: float) -> None:
        value = value.strip()
        if not value:
            return
        key = (entity_type, value.lower())
        if key in seen:
            return
        seen.add(key)
        entities.append(
            ExtractedEntity(entity_type=entity_type, entity_text=value, confidence=confidence)
        )

    for hit in _keyword_matches(text, MEDICATION_KEYWORDS):
        _add("medication", hit, 0.7)

    for match in MED_DOSAGE_PATTERN.finditer(text):
        name, dose = match.group(1), match.group(2)
        _add("medication", f"{name} {dose}", 0.65)

    for hit in _keyword_matches(text, DIAGNOSIS_KEYWORDS):
        _add("diagnosis", hit, 0.7)

    for hit in _keyword_matches(text, PROCEDURE_KEYWORDS):
        _add("procedure", hit, 0.7)

    for match in LAB_VALUE_PATTERN.finditer(text):
        analyte, value, unit = match.group(1), match.group(2), match.group(3) or ""
        label = f"{analyte} {value}{(' ' + unit) if unit else ''}".strip()
        _add("lab_value", label, 0.8)

    return entities


# ------------------------------ spaCy backend -------------------------------

_SPACY_NLP = None
_SPACY_TRIED = False


def _load_spacy():
    global _SPACY_NLP, _SPACY_TRIED
    if _SPACY_TRIED:
        return _SPACY_NLP
    _SPACY_TRIED = True
    try:
        import spacy  # type: ignore

        _SPACY_NLP = spacy.load("en_core_sci_sm")
        logger.info("Loaded spaCy model en_core_sci_sm for entity extraction.")
    except Exception as exc:  # pragma: no cover - depends on env
        logger.info("scispaCy not available, falling back to regex extractor: %s", exc)
        _SPACY_NLP = None
    return _SPACY_NLP


_SCISPACY_TYPE_MAP = {
    "CHEMICAL": "medication",
    "DRUG": "medication",
    "MEDICATION": "medication",
    "DISEASE": "diagnosis",
    "DISORDER": "diagnosis",
    "PROBLEM": "diagnosis",
    "TEST": "lab_value",
    "TREATMENT": "procedure",
    "PROCEDURE": "procedure",
}


def _spacy_extract(text: str) -> List[ExtractedEntity]:
    nlp = _load_spacy()
    if nlp is None:
        return []
    entities: List[ExtractedEntity] = []
    seen: set[tuple[str, str]] = set()
    doc = nlp(text)
    for ent in doc.ents:
        mapped = _SCISPACY_TYPE_MAP.get(ent.label_.upper(), "diagnosis")
        key = (mapped, ent.text.lower())
        if key in seen:
            continue
        seen.add(key)
        entities.append(
            ExtractedEntity(entity_type=mapped, entity_text=ent.text, confidence=0.85)
        )
    return entities


def extract_entities(text: str) -> List[ExtractedEntity]:
    """Extract medical entities. Uses scispaCy when available, regex otherwise."""
    if not text or not text.strip():
        return []

    spacy_entities = _spacy_extract(text)
    regex_entities = _regex_extract(text)

    if spacy_entities:
        # Merge regex hits (esp. lab values + dosed medications) the spaCy
        # model often misses, without duplicating.
        seen = {(e.entity_type, e.entity_text.lower()) for e in spacy_entities}
        merged = list(spacy_entities)
        for e in regex_entities:
            key = (e.entity_type, e.entity_text.lower())
            if key not in seen:
                seen.add(key)
                merged.append(e)
        return merged

    return regex_entities


def summarize_entities(entities: List[ExtractedEntity]) -> dict[str, int]:
    """Return {entity_type: count}."""
    summary: dict[str, int] = {}
    for e in entities:
        summary[e.entity_type] = summary.get(e.entity_type, 0) + 1
    return summary
