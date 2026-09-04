"""Document intelligence. Module B, second half.

Raw OCR text in, structured clinical entities out: diagnoses, medications with dosages,
investigation results with values and reference ranges, procedures — then dated and put
in order, with out-of-range values and interacting drug pairs flagged.

The brief asks for exactly this list, and the ordering matters as much as the
extraction: a physician with two minutes cannot reconstruct a timeline from a stack of
crumpled paper, which is the whole point of section 1.2.

Two rungs again, and both are used rather than one being a fallback:

  regex      dates, lab values with units, and reference ranges printed on the page.
             Deterministic, offline, and better than a model at this, because a lab
             report is a structured document pretending to be prose.
  LLM        drug names, dosages, diagnoses, free-text procedures. The messy parts.

Everything extracted here is marked `source: "document"` and never merged silently
into what the patient said. The doctor sees which is which.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from . import llm

# ---------------------------------------------------------------- reference ranges
#
# PROVENANCE: hand-entered adult ranges for analytes common on Indian OPD reports.
# Reference ranges are ASSAY- AND LABORATORY-SPECIFIC, which is why every real report
# prints its own next to the value. `extract_labs` therefore prefers the range printed
# on the document and only falls back to this table when the document omits one.
# Tracked in docs/10-unsourced.md section 6 and docs/11-deferred.md D-07.
REFERENCE_RANGES: dict[str, dict[str, Any]] = {
    "haemoglobin": {"low": 12.0, "high": 17.0, "unit": "g/dL", "aliases": ["hb", "hgb", "hemoglobin", "haemoglobin"]},
    "fasting glucose": {"low": 70.0, "high": 100.0, "unit": "mg/dL", "aliases": ["fbs", "fasting blood sugar", "fasting glucose", "glucose fasting"]},
    "post prandial glucose": {"low": 70.0, "high": 140.0, "unit": "mg/dL", "aliases": ["ppbs", "pp blood sugar", "post prandial"]},
    "hba1c": {"low": 4.0, "high": 5.7, "unit": "%", "aliases": ["hba1c", "glycated haemoglobin", "hb a1c"]},
    "total cholesterol": {"low": 0.0, "high": 200.0, "unit": "mg/dL", "aliases": ["total cholesterol", "cholesterol total"]},
    "creatinine": {"low": 0.6, "high": 1.3, "unit": "mg/dL", "aliases": ["creatinine", "s. creatinine", "serum creatinine"]},
    "urea": {"low": 15.0, "high": 40.0, "unit": "mg/dL", "aliases": ["urea", "blood urea"]},
    "tsh": {"low": 0.4, "high": 4.0, "unit": "uIU/mL", "aliases": ["tsh"]},
    "sgpt": {"low": 0.0, "high": 45.0, "unit": "U/L", "aliases": ["sgpt", "alt"]},
    "sgot": {"low": 0.0, "high": 40.0, "unit": "U/L", "aliases": ["sgot", "ast"]},
    "total bilirubin": {"low": 0.1, "high": 1.2, "unit": "mg/dL", "aliases": ["bilirubin total", "total bilirubin", "t. bilirubin"]},
    "platelet count": {"low": 150.0, "high": 450.0, "unit": "10^3/uL", "aliases": ["platelet", "platelets", "plt"]},
    "tlc": {"low": 4.0, "high": 11.0, "unit": "10^3/uL", "aliases": ["tlc", "wbc", "total leucocyte count"]},
    "uric acid": {"low": 3.5, "high": 7.2, "unit": "mg/dL", "aliases": ["uric acid"]},
}

# ---------------------------------------------------------------- interactions
#
# PROVENANCE: a small curated list of well-documented, clinically obvious pairs. This
# is NOT a pharmacological database, and the doctor screen labels it
# "screening only — not a complete interaction check". Tracked as D-08.
#
# The AYUSH pairs are included deliberately: a patient in an Ayurveda OPD is very
# often on allopathic medicine too, and that combination is exactly what no generic
# intake system looks at.
INTERACTION_PAIRS: list[dict[str, Any]] = [
    {"a": ["warfarin"], "b": ["aspirin", "clopidogrel", "ibuprofen", "diclofenac", "naproxen"],
     "note": "Increased bleeding risk.", "severity": "high"},
    {"a": ["warfarin"], "b": ["fluconazole", "metronidazole", "ciprofloxacin"],
     "note": "Anticoagulant effect may be potentiated.", "severity": "high"},
    {"a": ["metformin"], "b": ["contrast", "iodinated contrast"],
     "note": "Hold around contrast imaging.", "severity": "moderate"},
    {"a": ["ace inhibitor", "enalapril", "lisinopril", "ramipril", "telmisartan", "losartan"],
     "b": ["spironolactone", "potassium"],
     "note": "Risk of hyperkalaemia.", "severity": "moderate"},
    {"a": ["digoxin"], "b": ["furosemide", "frusemide", "amiodarone"],
     "note": "Digoxin toxicity risk.", "severity": "high"},
    {"a": ["statin", "atorvastatin", "simvastatin", "rosuvastatin"],
     "b": ["clarithromycin", "erythromycin", "gemfibrozil"],
     "note": "Increased myopathy risk.", "severity": "moderate"},
    {"a": ["nsaid", "ibuprofen", "diclofenac", "naproxen"],
     "b": ["enalapril", "lisinopril", "ramipril", "telmisartan", "losartan", "furosemide"],
     "note": "Reduced antihypertensive effect; renal risk.", "severity": "moderate"},
    # AYUSH / allopathic co-administration
    {"a": ["guduchi", "giloy", "karela", "bitter gourd", "methi", "fenugreek", "gurmar"],
     "b": ["metformin", "glimepiride", "glibenclamide", "insulin"],
     "note": "Both lower blood glucose. Additive hypoglycaemia possible.", "severity": "moderate"},
    {"a": ["ashwagandha"], "b": ["thyroxine", "levothyroxine", "eltroxin"],
     "note": "May raise thyroid hormone levels.", "severity": "moderate"},
    {"a": ["arjuna", "sarpagandha"], "b": ["amlodipine", "atenolol", "metoprolol", "telmisartan"],
     "note": "Additive blood-pressure lowering.", "severity": "moderate"},
    {"a": ["triphala", "haritaki", "isabgol"], "b": ["thyroxine", "levothyroxine", "iron", "ferrous"],
     "note": "May reduce absorption. Separate the doses.", "severity": "low"},
]


@dataclass
class LabValue:
    analyte: str
    value: float
    unit: str | None
    ref_low: float | None
    ref_high: float | None
    ref_source: str  # document | table | none
    abnormal: str | None  # high | low | None


@dataclass
class Medication:
    name: str
    dose: str | None = None
    frequency: str | None = None
    # Route was added after the first real prescription went through the pipeline: the
    # extractor put "by mouth" in `frequency`, because there was nowhere else to put it.
    # A field that does not exist is a field the model will improvise into.
    route: str | None = None
    system: str | None = None  # allopathic | ayurvedic | ...


@dataclass
class Document:
    id: str
    kind: str  # prescription | lab_report | discharge_summary | unknown
    doc_date: str | None
    raw_text: str
    diagnoses: list[str] = field(default_factory=list)
    medications: list[Medication] = field(default_factory=list)
    labs: list[LabValue] = field(default_factory=list)
    procedures: list[str] = field(default_factory=list)
    provider: str = "none"
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- dates

_DATE_PATTERNS = [
    (r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", "dmy"),
    (r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2})(?!\d)", "dmy2"),
    (r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", "ymd"),
    (r"(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{4})", "dmon"),
]
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def extract_date(text: str, today: date | None = None) -> str | None:
    """First plausible date in the text, as ISO.

    Indian documents are overwhelmingly DD/MM/YYYY, so an ambiguous pair is read that
    way. A date in the future is rejected rather than accepted, because a
    misread year that puts a prescription in 2035 would sort to the top of the
    timeline and be the first thing the doctor sees.
    """
    today = today or date.today()
    lowered = text.lower()
    for pattern, kind in _DATE_PATTERNS:
        for match in re.finditer(pattern, lowered):
            try:
                if kind == "dmy":
                    d, m, y = int(match[1]), int(match[2]), int(match[3])
                elif kind == "dmy2":
                    d, m, y = int(match[1]), int(match[2]), 2000 + int(match[3])
                elif kind == "ymd":
                    y, m, d = int(match[1]), int(match[2]), int(match[3])
                else:
                    d, m, y = int(match[1]), _MONTHS[match[2][:3]], int(match[3])
                if not (1 <= m <= 12 and 1 <= d <= 31):
                    continue
                parsed = date(y, m, d)
            except (ValueError, KeyError):
                continue
            if date(1950, 1, 1) <= parsed <= today:
                return parsed.isoformat()
    return None


# ---------------------------------------------------------------- labs

_LAB_LINE = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z0-9 .()/%-]{1,40}?)\s*[:\-]?\s+"
    r"(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>%|g/dl|mg/dl|mmol/l|u/l|iu/l|uiu/ml|miu/l|ng/ml|pg/ml|10\^3/ul|/ul|lakh|cells/cumm)?"
    r"(?:\s*(?:\(|\[)?\s*(?:ref(?:erence)?(?:\s*range)?|normal|bio\.?\s*ref\.?\s*interval)?\s*[:\-]?\s*"
    r"(?P<low>\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(?P<high>\d+(?:\.\d+)?)\s*(?:\)|\])?)?",
    re.IGNORECASE,
)


def _canonical_analyte(name: str) -> str | None:
    cleaned = re.sub(r"[^a-z0-9 ]", " ", name.lower()).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    for canonical, spec in REFERENCE_RANGES.items():
        for alias in spec["aliases"]:
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", cleaned):
                return canonical
    return None


def extract_labs(text: str) -> list[LabValue]:
    """Lab values with ranges.

    The range printed on the document always wins over the built-in table, because
    ranges are assay-specific and the document knows its own assay.
    """
    out: list[LabValue] = []
    seen: set[str] = set()
    for match in _LAB_LINE.finditer(text):
        canonical = _canonical_analyte(match.group("name"))
        if not canonical or canonical in seen:
            continue
        try:
            value = float(match.group("value"))
        except (TypeError, ValueError):
            continue

        low = high = None
        ref_source = "none"
        if match.group("low") and match.group("high"):
            low, high = float(match.group("low")), float(match.group("high"))
            ref_source = "document"
        elif canonical in REFERENCE_RANGES:
            low = REFERENCE_RANGES[canonical]["low"]
            high = REFERENCE_RANGES[canonical]["high"]
            ref_source = "table"

        abnormal = None
        if low is not None and high is not None:
            if value < low:
                abnormal = "low"
            elif value > high:
                abnormal = "high"

        unit = match.group("unit") or REFERENCE_RANGES.get(canonical, {}).get("unit")
        out.append(LabValue(canonical, value, unit, low, high, ref_source, abnormal))
        seen.add(canonical)
    return out


# ---------------------------------------------------------------- interactions


def check_interactions(medications: list[str]) -> list[dict[str, Any]]:
    """Screen a medication list against the curated pair list.

    Substring matching on purpose: OCR of a handwritten prescription yields
    "T. Metformin 500", and "metformin" has to be found inside it.
    """
    names = [m.lower() for m in medications if m]
    found = []
    for pair in INTERACTION_PAIRS:
        hit_a = next((n for n in names if any(t in n for t in pair["a"])), None)
        hit_b = next((n for n in names if any(t in n for t in pair["b"])), None)
        if hit_a and hit_b and hit_a != hit_b:
            found.append(
                {
                    "drug_a": hit_a,
                    "drug_b": hit_b,
                    "note": pair["note"],
                    "severity": pair["severity"],
                    "scope": "screening only, not a complete interaction check",
                }
            )
    return found


# ---------------------------------------------------------------- LLM extraction

_EXTRACT_PROMPT = (
    "Extract structured clinical data from this Indian medical document transcription.\n\n"
    "Reply with JSON only, in exactly this shape:\n"
    "{\n"
    '  "kind": "prescription" | "lab_report" | "discharge_summary" | "unknown",\n'
    '  "date": "YYYY-MM-DD" or null,\n'
    '  "diagnoses": ["..."],\n'
    '  "medications": [{"name": "...", "dose": "..." or null, '
    '"frequency": "..." or null, "route": "..." or null, '
    '"system": "allopathic"|"ayurvedic"|"homeopathic"|"siddha"|"unani"|null}],\n'
    '  "procedures": ["..."]\n'
    "}\n\n"
    "Rules that matter more than completeness:\n"
    "- Copy names and doses EXACTLY as written. Do not expand abbreviations, do not "
    "correct spellings, do not convert units.\n"
    "- If a dose is unreadable use null. NEVER guess a dose — a wrong dose is worse "
    "than a missing one.\n"
    "- Do not add anything that is not on the page. An empty list is a correct answer.\n"
    "- `dose` is how much (500mg, 2 tsp), `frequency` is how often (twice daily, BD, "
    "1-0-1), `route` is how it is taken (by mouth, PO, topical). Keep them apart; if "
    "only one is written, fill that one and leave the others null.\n"
    "- Ayurvedic, Siddha and Unani preparations are medications too. Record them, and "
    "set `system` accordingly.\n"
    "- `diagnoses` means conditions written on the document. Do NOT infer a diagnosis "
    "from a drug or a lab value."
)


def structure(text: str, doc_id: str) -> Document:
    """Raw OCR text to a structured document."""
    doc = Document(id=doc_id, kind="unknown", doc_date=extract_date(text), raw_text=text)
    doc.labs = extract_labs(text)

    parsed, provider = llm.chat_json(
        [
            {"role": "system", "content": _EXTRACT_PROMPT},
            {"role": "user", "content": text[:8000]},
        ]
    )
    doc.provider = provider

    if not parsed:
        # No model reachable. The regex rung already produced dates and lab values,
        # which is the part a doctor most needs at a glance. Say so rather than
        # presenting a half-read document as a fully read one.
        doc.warnings.append(
            "No model available: dates and lab values extracted, "
            "medications and diagnoses not extracted."
        )
        if doc.labs:
            doc.kind = "lab_report"
        return doc

    doc.kind = parsed.get("kind") or "unknown"
    doc.doc_date = doc.doc_date or _valid_iso(parsed.get("date"))
    doc.diagnoses = [str(d) for d in (parsed.get("diagnoses") or []) if d]
    doc.procedures = [str(p) for p in (parsed.get("procedures") or []) if p]
    for med in parsed.get("medications") or []:
        if isinstance(med, dict) and med.get("name"):
            doc.medications.append(
                Medication(
                    name=str(med["name"]),
                    dose=med.get("dose") or None,
                    frequency=med.get("frequency") or None,
                    route=med.get("route") or None,
                    system=med.get("system") or None,
                )
            )
    return doc


def _valid_iso(value: Any) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None
    return parsed.isoformat() if parsed <= date.today() else None


# ---------------------------------------------------------------- timeline


def build_timeline(documents: list[Document]) -> dict[str, Any]:
    """Order the documents and surface what a doctor needs in the first five seconds.

    Undated documents sort last rather than being dropped — a prescription with an
    unreadable date is still a prescription, and hiding it would be worse than
    showing it as undated.
    """
    ordered = sorted(
        documents,
        key=lambda d: (d.doc_date is None, d.doc_date or ""),
        reverse=False,
    )
    ordered = [d for d in ordered if d.doc_date] + [d for d in ordered if not d.doc_date]
    ordered.sort(key=lambda d: d.doc_date or "9999", reverse=True)

    all_meds = [m.name for d in ordered for m in d.medications]
    abnormal = [
        {
            "document": d.id,
            "date": d.doc_date,
            "analyte": lab.analyte,
            "value": lab.value,
            "unit": lab.unit,
            "ref_low": lab.ref_low,
            "ref_high": lab.ref_high,
            "ref_source": lab.ref_source,
            "direction": lab.abnormal,
        }
        for d in ordered
        for lab in d.labs
        if lab.abnormal
    ]

    return {
        "documents": [
            {
                "id": d.id,
                "kind": d.kind,
                "date": d.doc_date,
                "diagnoses": d.diagnoses,
                "medications": [vars(m) for m in d.medications],
                "labs": [vars(lab) for lab in d.labs],
                "procedures": d.procedures,
                "provider": d.provider,
                "warnings": d.warnings,
            }
            for d in ordered
        ],
        "abnormal_values": abnormal,
        "interactions": check_interactions(all_meds),
        "medication_count": len(all_meds),
        "date_range": {
            "earliest": min((d.doc_date for d in ordered if d.doc_date), default=None),
            "latest": max((d.doc_date for d in ordered if d.doc_date), default=None),
        },
        "undated_count": sum(1 for d in ordered if not d.doc_date),
    }
