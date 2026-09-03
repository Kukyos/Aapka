"""HTTP surface.

Thin on purpose. Every route here validates input, calls a pure module, and returns
the shape frozen in `docs/09-architecture.md`. No clinical logic lives in this file —
if a rule about the interview appears here, it is in the wrong place.

Route groups:
    /api/session/*   the kiosk
    /api/doctor/*    the consultation screen (token-gated)
    /api/triage/*    the staff alert queue
    /api/health      what is actually wired up right now
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, Header, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import abdm, asr, config, documents, fhir, llm, nlu, ocr, session as store, summary
from . import engine as eng
from .ontology import load as load_ontology

@asynccontextmanager
async def lifespan(_app: FastAPI):
    store.init_db()
    # Fail loudly at boot, never mid-interview. A malformed ontology must stop the
    # terminal from starting, not surface as a wrong question in a waiting hall.
    load_ontology()
    yield


app = FastAPI(title="Aapka intake terminal", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ont():
    return load_ontology()


def _require_session(session_id: str) -> eng.Session:
    session = store.load(session_id)
    if session is None:
        # Also the response after a wipe or a timeout, which is correct: the kiosk
        # treats it as "start again", and there is nothing left to resume.
        raise HTTPException(status_code=404, detail="session not found or already cleared")
    return session


def _require_doctor(authorization: str | None) -> None:
    token = (authorization or "").removeprefix("Bearer ").strip()
    if token != config.DOCTOR_TOKEN:
        raise HTTPException(status_code=401, detail="doctor token required")


# --------------------------------------------------------------------- models


class CreateSession(BaseModel):
    language: str | None = None
    mode: str | None = None
    returning: bool = False


class AnswerIn(BaseModel):
    node_id: str
    value: Any = None
    utterance: str | None = None
    source: str = "touch"
    elapsed_s: float | None = None


class ConsentIn(BaseModel):
    capture: bool
    share_with_hospital: bool
    link_to_abha: bool = False
    audio_played: bool = False


# --------------------------------------------------------------------- kiosk


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Deliberately verbose. Someone about to demo this needs to know in one glance
    whether the model rungs answer and whether ABDM is live or mocked."""
    ont = _ont()
    return {
        "ok": True,
        "ontology": {
            "version": ont.version,
            "nodes": len(ont.nodes),
            "slots": len(ont.slots),
            "red_flag_rules": len(ont.red_flags),
        },
        "inference": llm.available(),
        "tesseract": ocr.tesseract_available(),
        "abdm": abdm.status(),
        "config": config.status(),
        "budgets": {
            "ayush_s": eng.BUDGET_AYUSH_S,
            "core_s": eng.BUDGET_CORE_S,
            "returning_s": eng.BUDGET_RETURNING_S,
        },
    }


@app.get("/api/handoff")
def handoff() -> dict[str, Any]:
    """Where to send a patient who would rather use their own phone.

    The kiosk is not the only way in. There are more people in an OPD queue than there
    will ever be terminals, and a patient holding a phone can fill in the same intake
    from the bench instead of waiting for the machine — which is the whole throughput
    argument in `docs/12-budget-findings.md`.

    This is a *secondary* path and gate G1 is the reason it has to stay one: the brief
    rejects the smartphone as the main route in, and permits it only as a convenience
    beside a flow that assumes nothing. So the kiosk offers this and never requires it,
    and the intake on the phone is the same anonymous, temporary session that is wiped
    on submission — no account, no install, no enrolment.
    """
    url, source = config.handoff_url()
    return {
        "url": url,
        "source": source,
        # Over plain HTTP a phone gives the page no microphone and no camera. The touch
        # path is complete without either, so the handoff still works — but the kiosk
        # needs to know, so it can tell the patient to bring their papers to the desk.
        "secure": bool(url and url.startswith("https://")),
    }


@app.post("/api/session")
def create_session(body: CreateSession) -> dict[str, Any]:
    store.expire_stale()
    session = store.create(body.language, body.mode, body.returning)
    return {
        "session_id": session.id,
        "language": session.language,
        "mode": session.mode,
        "budget_s": session.budget_s,
    }


@app.post("/api/session/{session_id}/consent")
def consent(session_id: str, body: ConsentIn) -> dict[str, Any]:
    """Granular and revocable. `capture` false ends the session immediately and wipes
    it — a patient who declines must not leave a trace behind."""
    _require_session(session_id)
    store.record_consent(session_id, body.model_dump())
    if not body.capture:
        store.wipe(session_id)
        return {"accepted": False, "wiped": True}
    return {"accepted": True}


class PriorVisitIn(BaseModel):
    confirm: bool


class AbhaIn(BaseModel):
    abha_id: str | None = None
    declined: bool = False


ABHA_PATTERN = re.compile('(?<!\\d)(\\d{2}[-\\s]?\\d{4}[-\\s]?\\d{4}[-\\s]?\\d{4})(?!\\d)')


@app.post("/api/session/{session_id}/abha")
def set_abha(session_id: str, body: AbhaIn) -> dict[str, Any]:
    """Record the patient's health ID, or that they do not have one.

    Both outcomes are first-class. Gate G1 says the primary flow must work for a
    walk-in carrying nothing, so "no ABHA" is a recorded answer that lets the
    interview proceed, never a blocked path.
    """
    session = _require_session(session_id)
    if body.declined or not body.abha_id:
        session.slots["identity.abha_status"] = "none" if body.declined else "declined"
        store.save(session)
        return {"ok": True, "abha_status": session.slots["identity.abha_status"]}

    cleaned = re.sub(r"[^0-9]", "", body.abha_id)
    if len(cleaned) != 14:
        raise HTTPException(status_code=400, detail="an ABHA number is 14 digits")
    formatted = f"{cleaned[:2]}-{cleaned[2:6]}-{cleaned[6:10]}-{cleaned[10:]}"
    store.set_abha(session_id, formatted)
    session.slots["identity.abha_status"] = "scanned"
    store.save(session)
    return {"ok": True, "abha_status": "scanned", "abha_id": formatted,
            "prior_visit": _prior_visit_offer(formatted)}


@app.post("/api/session/{session_id}/abha/scan")
async def scan_abha(session_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    """Read an ABHA number off a photographed card.

    Uses the same OCR ladder as the document pipeline, then looks for the 14-digit
    pattern. A miss is not an error: the kiosk offers the card again or the
    no-ABHA path, and the interview is identical either way.
    """
    _require_session(session_id)
    image = await file.read()
    read = ocr.read(image, file.content_type or "image/jpeg")
    if not read.ok:
        return {"ok": False, "found": False, "error": read.error}
    match = ABHA_PATTERN.search(read.text)
    if not match:
        return {"ok": True, "found": False, "provider": read.provider}
    cleaned = re.sub(r"[^0-9]", "", match.group(1))
    formatted = f"{cleaned[:2]}-{cleaned[2:6]}-{cleaned[6:10]}-{cleaned[10:]}"
    store.set_abha(session_id, formatted)
    session = _require_session(session_id)
    session.slots["identity.abha_status"] = "scanned"
    store.save(session)
    return {"ok": True, "found": True, "abha_id": formatted, "provider": read.provider,
            "prior_visit": _prior_visit_offer(formatted)}


def _prior_visit_offer(abha_id: str) -> dict[str, Any] | None:
    """What we remember about this patient, phrased for the screen that asks them.

    Returns None for a first visit, which is the common case and not an error. The
    caller shows this to the patient and prefills nothing until they say it is right —
    a remembered fact is an offer, never an assumption.
    """
    if config.PRIOR_VISIT_SOURCE == "off":
        return None
    if config.PRIOR_VISIT_SOURCE == "abdm":
        # D-03. The ABHA fetch lands here and the shape below does not change.
        return None
    remembered = store.recall_visit(abha_id)
    if not remembered:
        return None
    ont = _ont()
    return {
        "source": "local",
        "visited_at": remembered["visited_at"],
        "slots": remembered["slots"],
        # Rendered on the kiosk, so it has to be language-bearing text and not slot ids.
        "lines": summary.describe_slots(ont, remembered["slots"],
                                        remembered.get("language") or "en"),
    }


@app.post("/api/session/{session_id}/prior-visit")
def confirm_prior_visit(session_id: str, body: PriorVisitIn) -> dict[str, Any]:
    """The returning-patient fast path, and the only way into it.

    Nothing is carried until the patient has been shown it and said it is still true.
    Declining is not a failure: the interview simply runs as a new one, which is the
    correct behaviour for a patient whose circumstances changed and the reason the
    engine has no separate returning-patient graph to fall out of.
    """
    session = _require_session(session_id)
    abha_id = store.get_abha(session_id)
    if not abha_id:
        raise HTTPException(status_code=400, detail="no ABHA on this session")

    if not body.confirm:
        session.audit.append({
            "node": None,
            "why": "patient declined the carried-over history; interviewed as new",
            "answered": None,
        })
        store.save(session)
        return {"ok": True, "prefilled": [], "returning": False}

    offer = _prior_visit_offer(abha_id)
    if not offer:
        return {"ok": True, "prefilled": [], "returning": False}

    filled = eng.prefill(_ont(), session, offer["slots"])
    # The budget moves to 90 s only once something was actually carried. A "returning"
    # patient we remember nothing about is a new patient with a card.
    session.returning = bool(filled)
    store.save(session)
    return {"ok": True, "prefilled": filled, "returning": session.returning,
            "budget_s": session.budget_s, "source": offer["source"]}


@app.delete("/api/session/{session_id}/prior-visit")
def forget_prior_visit(session_id: str) -> dict[str, Any]:
    """Erasure. The DPDP Act gives the patient this right, so it needs a door."""
    _require_session(session_id)
    abha_id = store.get_abha(session_id)
    if abha_id:
        store.forget_visit(abha_id)
    return {"ok": True, "forgotten": bool(abha_id)}


@app.get("/api/session/{session_id}/next")
def next_question(session_id: str) -> dict[str, Any]:
    session = _require_session(session_id)
    action = eng.next_action(_ont(), session)
    store.save(session)
    _maybe_alert(session)
    return action


@app.post("/api/session/{session_id}/answer")
def answer(session_id: str, body: AnswerIn) -> dict[str, Any]:
    session = _require_session(session_id)
    ont = _ont()
    try:
        node = ont.node(body.node_id)
    except KeyError:
        raise HTTPException(status_code=400, detail=f"unknown node {body.node_id}")

    value = body.value
    nlu_meta = None

    # Voice path. The utterance is mapped onto THIS node's declared options and
    # nothing else — see nlu.py for why that constraint is the whole design.
    if value is None and body.utterance:
        result = nlu.extract(node, body.utterance)
        nlu_meta = {
            "method": result.method,
            "confidence": result.confidence,
            "matched": result.matched_text,
        }
        if not result.ok:
            # Not an error. The kiosk re-asks or waits for a tap, which is a worse
            # interview and never a wrong one.
            return {
                "accepted": False,
                "reason": "unclear",
                "nlu": nlu_meta,
                "question": eng.render(node, session),
            }
        value = result.value

    if value is None:
        raise HTTPException(status_code=400, detail="need a value or an utterance")

    problem = _validate_value(node, value)
    if problem:
        raise HTTPException(status_code=400, detail=problem)

    eng.apply_answer(
        ont,
        session,
        eng.Answer(
            node_id=node.id,
            slot=node.slot,
            value=value,
            respondent=session.slots.get("identity.respondent", "self"),
            source=body.source,
            elapsed_s=body.elapsed_s or node.cost_s,
            raw_utterance=body.utterance,
        ),
    )
    action = eng.next_action(ont, session)
    store.save(session)
    _maybe_alert(session)
    action["accepted"] = True
    action["nlu"] = nlu_meta
    return action


def _validate_value(node, value: Any) -> str | None:
    """A trust boundary. The kiosk is not the only thing that can POST here."""
    legal = {str(o.value) for o in node.options}
    if node.answer_type in {"single_choice"} and legal and str(value) not in legal:
        return f"{value!r} is not a valid option for {node.id}"
    if node.answer_type == "multi_choice":
        if not isinstance(value, list):
            return f"{node.id} expects a list"
        bad = [v for v in value if legal and str(v) not in legal]
        if bad:
            return f"{bad!r} are not valid options for {node.id}"
    if node.answer_type == "boolean" and not isinstance(value, bool):
        return f"{node.id} expects true or false"
    if node.answer_type == "scale":
        if not isinstance(value, int) or not (node.min or 0) <= value <= (node.max or 10):
            return f"{node.id} expects an integer between {node.min} and {node.max}"
    if node.answer_type == "duration":
        if not isinstance(value, dict) or "n" in value and not isinstance(value.get("n"), int):
            return f"{node.id} expects {{n, unit}}"
    return None


@app.post("/api/session/{session_id}/skip")
def skip(session_id: str, node_id: str = Body(..., embed=True)) -> dict[str, Any]:
    session = _require_session(session_id)
    ont = _ont()
    try:
        eng.skip(ont, session, node_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    action = eng.next_action(ont, session)
    store.save(session)
    return action


@app.post("/api/session/{session_id}/transcribe")
async def transcribe(session_id: str, file: UploadFile = File(...),
                     language: str = Form("hi")) -> dict[str, Any]:
    """Server-side ASR. The kiosk prefers the browser recogniser; this is the path for
    captured audio and the one the eval harness measures against."""
    _require_session(session_id)
    audio = await file.read()
    result = asr.transcribe(audio, file.filename or "clip.webm", language)
    return {
        "text": result.text,
        "provider": result.provider,
        "ok": result.ok,
        "error": result.error,
    }


@app.post("/api/session/{session_id}/document")
async def add_document(session_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    """Scan one document. OCR, then structure, then fold into the timeline."""
    _require_session(session_id)
    image = await file.read()
    if len(image) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="image too large")

    read = ocr.read(image, file.content_type or "image/jpeg")
    if not read.ok:
        return {"ok": False, "error": read.error or "could not read the document"}

    doc_id = uuid.uuid4().hex
    doc = documents.structure(read.text, doc_id)
    store.add_document(session_id, doc_id, image, read.text, _doc_dict(doc))
    return {
        "ok": True,
        "document_id": doc_id,
        "kind": doc.kind,
        "date": doc.doc_date,
        "ocr_provider": read.provider,
        "extraction_provider": doc.provider,
        "medications": [vars(m) for m in doc.medications],
        "diagnoses": doc.diagnoses,
        "labs": [vars(l) for l in doc.labs],
        "warnings": doc.warnings,
    }


def _doc_dict(doc: documents.Document) -> dict[str, Any]:
    return {
        "id": doc.id,
        "kind": doc.kind,
        "doc_date": doc.doc_date,
        "diagnoses": doc.diagnoses,
        "medications": [vars(m) for m in doc.medications],
        "labs": [vars(l) for l in doc.labs],
        "procedures": doc.procedures,
        "provider": doc.provider,
        "warnings": doc.warnings,
    }


def _timeline_for(session_id: str) -> dict[str, Any] | None:
    rows = store.documents_for(session_id)
    if not rows:
        return None
    import json as _json

    docs = []
    for row in rows:
        data = _json.loads(row["structured"])
        doc = documents.Document(
            id=data["id"], kind=data["kind"], doc_date=data["doc_date"],
            raw_text=row["raw_text"] or "",
            diagnoses=data.get("diagnoses", []),
            medications=[documents.Medication(**m) for m in data.get("medications", [])],
            labs=[documents.LabValue(**l) for l in data.get("labs", [])],
            procedures=data.get("procedures", []),
            provider=data.get("provider", "none"),
            warnings=data.get("warnings", []),
        )
        docs.append(doc)
    return documents.build_timeline(docs)


@app.get("/api/session/{session_id}/summary")
def session_summary(session_id: str) -> dict[str, Any]:
    """Preview for the patient's own review step, before they submit."""
    session = _require_session(session_id)
    return summary.build(_ont(), session, _timeline_for(session_id))


@app.post("/api/session/{session_id}/submit")
def submit(session_id: str, abha_id: str | None = Body(None, embed=True)) -> dict[str, Any]:
    """Finish: build the summary and the bundle, push it, then WIPE.

    Everything the doctor will read is inside the returned payload and inside the
    bundle on disk. After this call the session no longer exists.
    """
    session = _require_session(session_id)
    ont = _ont()
    timeline = _timeline_for(session_id)
    built = summary.build(ont, session, timeline)

    if session.status == "active":
        session.status = "complete"

    resolved_abha = abha_id or store.get_abha(session_id)
    bundle = fhir.build_bundle(ont, session, built, timeline, resolved_abha)
    problems = fhir.validate(bundle)
    receipt = abdm.push(bundle, session.id, resolved_abha)

    # The doctor screen reads from the bundle directory, not from the session, which
    # is what lets the session be destroyed a line later.
    _publish_for_doctor(session.id, built, receipt)

    # Keep the handful of facts that will still be true next time — but only for a
    # patient who has an ABHA and consented to it being linked. No consent, no row.
    # The session itself is destroyed on the next line regardless; this is a separate,
    # consented record and not a surviving fragment of the interview.
    consent = store.get_consent(session_id) or {}
    if (config.PRIOR_VISIT_SOURCE == "local" and resolved_abha
            and consent.get("link_to_abha")):
        store.remember_visit(resolved_abha, session, eng.carry_over_slots(ont))

    wipe_result = store.submit(session, receipt.get("bundle_path", ""), built["coverage"])

    return {
        "ok": True,
        "session_id": session.id,
        "summary": built,
        "fhir": {
            "bundle_id": bundle["id"],
            "entries": len(bundle["entry"]),
            "validation_problems": problems,
            "valid": not problems,
        },
        "abdm": receipt,
        "privacy": wipe_result,
    }


@app.post("/api/session/{session_id}/abandon")
def abandon(session_id: str) -> dict[str, Any]:
    """Requirement R2. A half-finished history never reaches a doctor."""
    store.wipe(session_id)
    return {"wiped": True, "forwarded": False}


# --------------------------------------------------------------------- doctor

# Submitted summaries live here, keyed by session id, until the doctor accepts or
# rejects them. In-process on purpose: they are transient by design, and a restart
# losing an unreviewed summary is the correct failure mode for a device that is
# supposed to forget people.
_PENDING: dict[str, dict[str, Any]] = {}


def _publish_for_doctor(session_id: str, built: dict[str, Any], receipt: dict[str, Any]) -> None:
    _PENDING[session_id] = {
        "summary": built,
        "abdm": receipt,
        "reviewed": False,
        "decision": None,
    }


@app.get("/api/doctor/queue")
def doctor_queue(authorization: str | None = Header(None)) -> dict[str, Any]:
    _require_doctor(authorization)
    return {
        "waiting": [
            {
                "session_id": sid,
                "complaint": next(
                    (s["lines"][0] for s in item["summary"]["sections"]
                     if s["key"] == "cc" and s["lines"]), "Not recorded"
                ),
                "age_band": item["summary"]["patient"]["age_band"],
                "sex": item["summary"]["patient"]["sex"],
                "red_flag": bool(item["summary"]["red_flag"]),
                "proxy": item["summary"]["proxy_note"] is not None,
                "reviewed": item["reviewed"],
            }
            for sid, item in _PENDING.items()
        ],
        "stats": store.stats(),
        "abdm": abdm.status(),
    }


@app.get("/api/doctor/summary/{session_id}")
def doctor_summary(session_id: str, authorization: str | None = Header(None)) -> dict[str, Any]:
    _require_doctor(authorization)
    item = _PENDING.get(session_id)
    if not item:
        raise HTTPException(status_code=404, detail="no summary waiting for that session")
    return item


@app.post("/api/doctor/summary/{session_id}/decision")
def doctor_decision(
    session_id: str,
    decision: str = Body(..., embed=True),
    amendments: dict[str, Any] | None = Body(None, embed=True),
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """Accept, amend or reject. Gate G3 — nothing is permanent until this call."""
    _require_doctor(authorization)
    item = _PENDING.get(session_id)
    if not item:
        raise HTTPException(status_code=404, detail="no summary waiting for that session")
    if decision not in {"accept", "amend", "reject"}:
        raise HTTPException(status_code=400, detail="decision must be accept, amend or reject")
    item["reviewed"] = True
    item["decision"] = decision
    if decision == "amend" and amendments:
        item["amendments"] = amendments

    # Accept and reject both end the summary's life here. The bundle is already on
    # disk and the session row is already gone; holding the rendered summary — which
    # carries the patient's verbatim narration — any longer would quietly undo the
    # wipe-on-submission guarantee. Amend keeps it so the doctor can keep editing.
    if decision in {"accept", "reject"}:
        _PENDING.pop(session_id, None)
    return {"ok": True, "decision": decision}


# --------------------------------------------------------------------- triage


def _maybe_alert(session: eng.Session) -> None:
    if session.status == "escalated" and session.red_flag:
        existing = [a for a in store.open_alerts() if a["session_id"] == session.id]
        if not existing:
            store.raise_alert(
                session.id,
                session.red_flag["severity"],
                session.red_flag["id"],
                session.red_flag["staff_alert"],
            )


@app.get("/api/triage/alerts")
def triage_alerts() -> dict[str, Any]:
    """Unauthenticated on purpose: this runs on a screen at the triage desk inside the
    hospital, and it carries no patient identity — a severity, a rule, and a sentence
    telling a nurse to go and find someone."""
    return {"alerts": store.open_alerts()}


@app.post("/api/triage/alerts/{alert_id}/ack")
def acknowledge(alert_id: str) -> dict[str, Any]:
    store.acknowledge_alert(alert_id)
    return {"ok": True}


# --------------------------------------------------------------------- ontology


@app.get("/api/ontology")
def ontology_summary() -> dict[str, Any]:
    """Served so the kiosk can preload icons and so the graph is inspectable without
    reading YAML. Read-only."""
    ont = _ont()
    return {
        "version": ont.version,
        "sections": ont.sections,
        "nodes": [
            {
                "id": n.id, "slot": n.slot, "section": n.section, "mode": n.mode,
                "priority": n.priority, "required": n.required, "cost_s": n.cost_s,
                "type": n.answer_type,
                "icons": [o.icon for o in n.options if o.icon],
            }
            for n in ont.nodes
        ],
        "red_flags": [
            {"id": r.id, "severity": r.severity, "label": r.label, "source": r.source}
            for r in ont.red_flags
        ],
    }


@app.exception_handler(Exception)
async def unhandled(request, exc):  # noqa: ANN001
    """A crash must not leave a patient staring at a stack trace. The kiosk shows a
    'please see the staff desk' screen on a 500."""
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": "internal error", "detail": str(exc)[:200]},
    )
