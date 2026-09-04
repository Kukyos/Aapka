"""Module D, first half — FHIR R4 bundle generation.

The payload is real. ABDM's Health Information Exchange carries FHIR R4 documents, and
what this module builds is the shape it expects: a `document` Bundle whose first entry
is a Composition, followed by the Patient, Observations for each captured finding,
Conditions for reported past illness, AllergyIntolerance where relevant, and
DocumentReference entries for scanned papers.

The transport is mocked (see `abdm.py`) because we have no sandbox credentials yet.
Splitting it this way is deliberate: `03-requirements.md` lists "fake the ABDM
integration" as a lose condition, and the honest position is a real payload with a
labelled transport, not a screenshot.

Terminology: every coding carries its system. Where a NAMASTE or ICD-11 code would go,
the slot is present and the code is null, because those code lists are not publicly
available and inventing one is exactly the failure mode the ministry would catch. See
`docs/10-unsourced.md`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .engine import Session
from .ontology import Ontology

FHIR_VERSION = "4.0.1"

# ABDM's own terminology namespaces. These URLs are the identifiers ABDM uses; they
# are not code values and are safe to state.
SYS_NAMASTE = "https://namaste.ayush.gov.in/CodeSystem/namc"
SYS_ICD11_MMS = "http://id.who.int/icd/release/11/mms"
SYS_ICD11_TM2 = "http://id.who.int/icd/release/11/tm2"
SYS_ABHA = "https://healthid.ndhm.gov.in"
SYS_LOCAL = "https://github.com/Kukyos/Aapka/CodeSystem/slots"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _uid() -> str:
    return f"urn:uuid:{uuid.uuid4()}"


def _codeable(ont: Ontology, complaint: str | None) -> dict[str, Any]:
    """A CodeableConcept for the chief complaint, dual-coded where we can.

    Only codings with real values are emitted. An unsourced code is omitted entirely
    rather than sent as null or as a guess — a receiving system must never see a code
    we did not verify. What we did capture is carried in `text` and in the local
    coding, both of which are true.
    """
    entry = (ont.codes.get("complaints") or {}).get(complaint or "", {})
    codings = [
        {"system": SYS_LOCAL, "code": complaint, "display": (entry.get("label") or {}).get("en", complaint)}
    ]
    for key, system in [
        ("namaste", SYS_NAMASTE),
        ("icd11_tm2", SYS_ICD11_TM2),
        ("icd11_mms", SYS_ICD11_MMS),
    ]:
        spec = entry.get(key) or {}
        if spec.get("code") and spec.get("provenance") == "sourced":
            codings.append({"system": system, "code": spec["code"], "display": spec.get("term")})
    return {
        "coding": codings,
        "text": (entry.get("label") or {}).get("en", complaint or "Not recorded"),
    }


def _dosha_codings(ont: Ontology, slot: str, value: Any) -> list[dict[str, Any]]:
    """Standards codings for a self-reported dosha imbalance.

    Dual-coded, which is what decision D2 promised and what India's own roadmap asks
    for: the NAMASTE term the ministry publishes, and the ICD-11 TM2 pattern it maps
    to. The two come from different published sources that agree with each other — the
    NAMC export pairs `AAA-2.1` with `SR10`, and the WHO API independently titles SR10
    "Vitiation of vata pattern".

    Only `ayush.vikriti` reaches here, and only ever as a *pattern*. That is what the
    patient described about their own present state, and the Observation carrying it is
    `preliminary` with the respondent attached, so a receiving system sees a patient
    report awaiting a clinician rather than a finding.

    Prakriti gets nothing here on purpose: these systems code derangements, and a
    constitution is not a derangement. See the note in ontology/codes.yaml.
    """
    if slot != "ayush.vikriti":
        return []
    entry = (ont.codes.get("dosha_findings") or {}).get(str(value)) or {}
    out: list[dict[str, Any]] = []
    for key, system in (("namaste", SYS_NAMASTE), ("icd11_tm2", SYS_ICD11_TM2)):
        spec = entry.get(key) or {}
        if spec.get("code") and spec.get("provenance") == "sourced":
            out.append({"system": system, "code": spec["code"], "display": spec.get("term")})
    return out


def _observation(
    patient_ref: str, slot: str, value: Any, section: str, respondent: str, when: str,
    extra_value_codings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One captured finding.

    `performer` carries the respondent. Requirement R1 says a proxy-given answer is a
    different clinical fact, and FHIR has a place to say so, so it is said here rather
    than only rendered on our own screen.
    """
    obs: dict[str, Any] = {
        "resourceType": "Observation",
        "id": str(uuid.uuid4()),
        "status": "preliminary",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "survey",
                        "display": "Survey",
                    }
                ],
                "text": section,
            }
        ],
        "code": {"coding": [{"system": SYS_LOCAL, "code": slot}], "text": slot},
        "subject": {"reference": patient_ref},
        "effectiveDateTime": when,
    }
    if isinstance(value, bool):
        obs["valueBoolean"] = value
    elif isinstance(value, (int, float)):
        obs["valueInteger" if isinstance(value, int) else "valueQuantity"] = (
            value if isinstance(value, int) else {"value": value}
        )
    elif isinstance(value, dict) and "n" in value:
        obs["valueQuantity"] = {"value": value["n"], "unit": value["unit"]}
    elif isinstance(value, list):
        obs["valueCodeableConcept"] = {
            "coding": [{"system": SYS_LOCAL, "code": str(v)} for v in value],
            "text": ", ".join(str(v) for v in value),
        }
    else:
        obs["valueCodeableConcept"] = {
            "coding": [{"system": SYS_LOCAL, "code": str(value)}],
            "text": str(value),
        }

    # Standards-coded readings of the same value, where they exist and are sourced.
    # They sit beside the local code rather than replacing it, so a system that knows
    # neither NAMASTE nor TM2 still reads the answer.
    if extra_value_codings and "valueCodeableConcept" in obs:
        obs["valueCodeableConcept"]["coding"].extend(extra_value_codings)

    if respondent and respondent != "self":
        obs["performer"] = [{"display": f"Reported by {respondent} (proxy)"}]
        obs["note"] = [{"text": "Proxy-reported. Confirm with the patient."}]
    return obs


def build_bundle(
    ont: Ontology,
    session: Session,
    summary: dict[str, Any],
    timeline: dict[str, Any] | None = None,
    abha_id: str | None = None,
) -> dict[str, Any]:
    """A FHIR R4 document Bundle for one completed intake."""
    when = _now()
    patient_uid = _uid()
    composition_uid = _uid()
    respondent = session.slots.get("identity.respondent", "self")

    patient: dict[str, Any] = {
        "resourceType": "Patient",
        "id": str(uuid.uuid4()),
        # No name, no phone, no address. The kiosk never asks for them: it does not
        # need them, and DPDP 2023 makes not collecting them the cheapest compliance
        # there is. The ABHA number, when present, is the identifier.
        "identifier": (
            [{"system": SYS_ABHA, "value": abha_id}] if abha_id else []
        ),
    }
    sex = session.slots.get("identity.sex")
    if sex in {"male", "female", "other"}:
        patient["gender"] = sex
    age_band = session.slots.get("identity.age_band")
    if age_band:
        patient["extension"] = [
            {
                "url": f"{SYS_LOCAL}/age-band",
                "valueString": str(age_band),
            }
        ]

    entries: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    conditions: list[dict[str, Any]] = []
    allergies: list[dict[str, Any]] = []

    for slot, value in session.slots.items():
        if value in (None, [], ""):
            continue
        if slot.startswith("identity."):
            continue
        section = slot.split(".")[0]
        observations.append(_observation(
            patient_uid, slot, value, section, respondent, when,
            extra_value_codings=_dosha_codings(ont, slot, value),
        ))

    for condition in session.slots.get("past.conditions") or []:
        if condition in {"none", "unsure"}:
            continue
        conditions.append(
            {
                "resourceType": "Condition",
                "id": str(uuid.uuid4()),
                "clinicalStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                            "code": "active",
                        }
                    ]
                },
                "verificationStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                            # Patient-reported, never confirmed by us. This is the
                            # FHIR way of saying "the patient told a kiosk this".
                            "code": "unconfirmed",
                        }
                    ]
                },
                "code": {"coding": [{"system": SYS_LOCAL, "code": condition}], "text": condition},
                "subject": {"reference": patient_uid},
                "recordedDate": when,
            }
        )

    allergy_known = session.slots.get("drugs.allergy_known")
    if allergy_known in {"drug_allergy", "food_allergy", "both"}:
        allergies.append(
            {
                "resourceType": "AllergyIntolerance",
                "id": str(uuid.uuid4()),
                "clinicalStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                            "code": "active",
                        }
                    ]
                },
                "verificationStatus": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
                            "code": "unconfirmed",
                        }
                    ]
                },
                "category": (
                    ["medication"] if allergy_known == "drug_allergy"
                    else ["food"] if allergy_known == "food_allergy"
                    else ["medication", "food"]
                ),
                "criticality": "unable-to-assess",
                "code": {"text": session.slots.get("drugs.allergy_detail") or allergy_known},
                "patient": {"reference": patient_uid},
                "recordedDate": when,
            }
        )

    doc_refs = []
    for doc in (timeline or {}).get("documents", []):
        doc_refs.append(
            {
                "resourceType": "DocumentReference",
                "id": str(uuid.uuid4()),
                "status": "current",
                "type": {"text": doc["kind"]},
                "subject": {"reference": patient_uid},
                "date": doc.get("date") or when,
                "description": (
                    f"Patient-supplied {doc['kind'].replace('_', ' ')} digitised at the intake terminal"
                ),
                "content": [
                    {
                        "attachment": {
                            "contentType": "text/plain",
                            "title": f"OCR transcription ({doc.get('provider', 'unknown')})",
                            # The image itself is NOT carried. It is wiped with the
                            # session on submit; only the extracted text survives, and
                            # only because the doctor needs it in the room.
                            "data": None,
                        }
                    }
                ],
            }
        )

    composition = {
        "resourceType": "Composition",
        "id": str(uuid.uuid4()),
        "status": "preliminary",
        "type": {
            "coding": [
                {"system": "http://loinc.org", "code": "34117-2", "display": "History and physical note"}
            ],
            "text": "Pre-consultation intake history",
        },
        "subject": {"reference": patient_uid},
        "date": when,
        "author": [{"display": "Aapka pre-consultation intake terminal"}],
        "title": "Pre-consultation clinical history",
        "confidentiality": "R",
        "section": [
            {
                "title": section["title"],
                "text": {
                    "status": "generated",
                    "div": (
                        '<div xmlns="http://www.w3.org/1999/xhtml">'
                        + "".join(f"<p>{_escape(line)}</p>" for line in section["lines"])
                        + "</div>"
                    ),
                },
            }
            for section in summary["sections"]
            if section["lines"]
        ],
    }
    if session.slots.get("cc.primary"):
        composition["section"].insert(
            0,
            {
                "title": "Chief complaint (coded)",
                "code": _codeable(ont, session.slots.get("cc.primary")),
                "text": {
                    "status": "generated",
                    "div": '<div xmlns="http://www.w3.org/1999/xhtml"><p>'
                    + _escape(_codeable(ont, session.slots["cc.primary"])["text"])
                    + "</p></div>",
                },
            },
        )

    entries.append({"fullUrl": composition_uid, "resource": composition})
    entries.append({"fullUrl": patient_uid, "resource": patient})
    for resource in observations + conditions + allergies + doc_refs:
        entries.append({"fullUrl": _uid(), "resource": resource})

    return {
        "resourceType": "Bundle",
        "id": str(uuid.uuid4()),
        "meta": {
            "versionId": "1",
            "lastUpdated": when,
            "profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/DocumentBundle"],
        },
        "identifier": {"system": SYS_LOCAL, "value": session.id},
        "type": "document",
        "timestamp": when,
        "entry": entries,
    }


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def validate(bundle: dict[str, Any]) -> list[str]:
    """Structural checks only.

    This is not a FHIR validator — a real one needs the profile packages and is a
    different project. It catches the mistakes that would make ABDM reject the bundle
    outright, so that when credentials do arrive the first attempt is not wasted.
    """
    problems: list[str] = []
    if bundle.get("resourceType") != "Bundle":
        problems.append("root resourceType must be Bundle")
    if bundle.get("type") != "document":
        problems.append("a clinical document Bundle must have type 'document'")
    entries = bundle.get("entry") or []
    if not entries:
        problems.append("bundle has no entries")
        return problems
    first = entries[0].get("resource", {})
    if first.get("resourceType") != "Composition":
        problems.append("the first entry of a document Bundle must be a Composition")
    if not bundle.get("timestamp"):
        problems.append("bundle is missing a timestamp")

    full_urls = {e.get("fullUrl") for e in entries}
    for entry in entries:
        resource = entry.get("resource", {})
        if not entry.get("fullUrl"):
            problems.append(f"{resource.get('resourceType')} entry has no fullUrl")
        if not resource.get("resourceType"):
            problems.append("entry has a resource with no resourceType")
        subject = (resource.get("subject") or resource.get("patient") or {}).get("reference")
        if subject and subject not in full_urls:
            problems.append(f"dangling reference {subject}")

    # The rule from docs/10-unsourced.md, enforced rather than documented: an
    # unverified code must never leave this system.
    for entry in entries:
        for coding in _all_codings(entry.get("resource", {})):
            if coding.get("system") in {SYS_NAMASTE, SYS_ICD11_MMS, SYS_ICD11_TM2}:
                if not coding.get("code"):
                    problems.append(f"empty code emitted for {coding.get('system')}")
    return problems


def _all_codings(node: Any) -> list[dict]:
    out = []
    if isinstance(node, dict):
        if "coding" in node and isinstance(node["coding"], list):
            out.extend(c for c in node["coding"] if isinstance(c, dict))
        for value in node.values():
            out.extend(_all_codings(value))
    elif isinstance(node, list):
        for item in node:
            out.extend(_all_codings(item))
    return out
